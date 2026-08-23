from __future__ import annotations

import time
from threading import Lock
from uuid import uuid4
from pathlib import Path

import boto3
from botocore.config import Config
from supabase import Client

from hike_journal.config import settings


class StorageService:
    def __init__(self, client: Client | None):
        self.client = client
        self.backend = settings.storage_backend
        self.supabase_bucket = settings.supabase_bucket
        self.r2_bucket = settings.r2_bucket
        self._r2_client = None
        self._download_url_cache: dict[tuple[str, int], tuple[float, str]] = {}
        self._download_url_cache_lock = Lock()

        if self.backend == "r2":
            if not settings.r2_configured:
                raise RuntimeError("R2 storage backend is enabled but not fully configured.")
            self._r2_client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name=settings.r2_region,
                config=Config(signature_version="s3v4"),
            )

    def _build_public_url(self, path: str) -> str:
        if self.backend == "r2":
            if settings.r2_public_base_url:
                return f"{settings.r2_public_base_url}/{path}"
            # `photos.public_url` remains non-null for compatibility with older
            # schemas, but private R2 installations do not need a public HTTP
            # origin. Reads are resolved through `create_download_url` instead.
            return f"r2://{self.r2_bucket}/{path}"
        if not self.client:
            raise RuntimeError("Supabase client is required for Supabase storage.")
        return self.client.storage.from_(self.supabase_bucket).get_public_url(path)

    def create_download_url(self, storage_path: str, *, expires_in: int = 86_400) -> str:
        """Return a time-limited URL without making the object store public."""
        clean_path = storage_path.strip().lstrip("/")
        if not clean_path:
            raise ValueError("The stored media path is missing.")
        bounded_expiry = max(300, min(int(expires_in), 604_800))
        # Signing a URL is cheap in isolation but expensive at journal scale:
        # every list/map request used to mint a new bearer URL for the same
        # object. Reuse it for most of its lifetime. Authorization is still
        # checked by the repository before this method is called, and the URL
        # remains time-limited.
        cache = getattr(self, "_download_url_cache", None)
        lock = getattr(self, "_download_url_cache_lock", None)
        if cache is None:
            cache = self._download_url_cache = {}
        if lock is None:
            lock = self._download_url_cache_lock = Lock()
        cache_key = (clean_path, bounded_expiry)
        now = time.monotonic()
        with lock:
            cached = cache.get(cache_key)
            if cached and cached[0] > now:
                return cached[1]
        if self.backend == "r2":
            if self._r2_client is None:
                raise RuntimeError("R2 storage client is not configured.")
            signed_url = str(
                self._r2_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.r2_bucket, "Key": clean_path},
                    ExpiresIn=bounded_expiry,
                )
            )
        else:
            if not self.client:
                raise RuntimeError("Supabase client is required for Supabase storage.")
            response = self.client.storage.from_(self.supabase_bucket).create_signed_url(
                clean_path,
                bounded_expiry,
            )
            signed_url = response.get("signedURL") or response.get("signedUrl")
            if not signed_url:
                raise RuntimeError("The object store did not return a signed media URL.")
            signed_url = str(signed_url)
        cache_ttl = max(60, bounded_expiry - 300)
        with lock:
            cache[cache_key] = (time.monotonic() + cache_ttl, signed_url)
            if len(cache) > 4096:
                expired = [key for key, (expires_at, _) in cache.items() if expires_at <= time.monotonic()]
                for key in expired[:2048]:
                    cache.pop(key, None)
        return signed_url

    @staticmethod
    def thumbnail_path(storage_path: str) -> str:
        """Return the deterministic derivative path for an uploaded image."""
        clean_path = storage_path.strip().lstrip("/")
        if not clean_path:
            raise ValueError("The stored media path is missing.")
        source = Path(clean_path)
        return str(source.parent / "thumbs" / f"{source.stem}.jpg")

    def upload_thumbnail(
        self,
        storage_path: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> tuple[str, str]:
        """Store a cacheable list-view derivative without changing the original."""
        path = self.thumbnail_path(storage_path)
        return self.replace_file(
            path,
            image_bytes,
            content_type,
            cache_control="public, max-age=604800, immutable",
        )

    def resolve_download_url(self, storage_path: str) -> str:
        return self.create_download_url(
            storage_path,
            expires_in=settings.media_signed_url_ttl_seconds,
        )

    def check_health(self) -> None:
        """Verify that the configured object store is reachable.

        This intentionally performs no writes and returns no bucket contents, so
        it is safe for readiness checks and operational diagnostics.
        """

        if self.backend == "r2":
            if self._r2_client is None:
                raise RuntimeError("R2 storage client is not configured.")
            self._r2_client.head_bucket(Bucket=self.r2_bucket)
            return
        if not self.client:
            raise RuntimeError("Supabase client is required for Supabase storage.")
        self.client.storage.get_bucket(self.supabase_bucket)

    def _upload_bytes(
        self,
        path: str,
        file_bytes: bytes,
        content_type: str,
        *,
        cache_control: str = "private, max-age=3600",
    ) -> tuple[str, str]:
        if self.backend == "r2":
            self._r2_client.put_object(
                Bucket=self.r2_bucket,
                Key=path,
                Body=file_bytes,
                ContentType=content_type,
                CacheControl=cache_control,
            )
            return path, self._build_public_url(path)

        if not self.client:
            raise RuntimeError("Supabase client is required for Supabase storage.")
        self.client.storage.from_(self.supabase_bucket).upload(
            path=path,
            file=file_bytes,
            file_options={"content-type": content_type, "cache-control": cache_control, "upsert": "false"},
        )
        return path, self._build_public_url(path)

    def replace_file(
        self,
        path: str,
        file_bytes: bytes,
        content_type: str,
        *,
        cache_control: str = "private, max-age=3600",
    ) -> tuple[str, str]:
        if self.backend == "r2":
            self._r2_client.put_object(
                Bucket=self.r2_bucket,
                Key=path,
                Body=file_bytes,
                ContentType=content_type,
                CacheControl=cache_control,
            )
            return path, self._build_public_url(path)

        if not self.client:
            raise RuntimeError("Supabase client is required for Supabase storage.")
        self.client.storage.from_(self.supabase_bucket).upload(
            path=path,
            file=file_bytes,
            file_options={"content-type": content_type, "cache-control": cache_control, "upsert": "true"},
        )
        return path, self._build_public_url(path)

    def upload_hike_photo(
        self,
        hike_id: str,
        image_bytes: bytes,
        content_type: str,
        *,
        object_id: str | None = None,
    ) -> tuple[str, str]:
        path = f"hikes/{hike_id}/{object_id or uuid4().hex}.jpg"
        if object_id:
            return self.replace_file(path, image_bytes, content_type)
        return self._upload_bytes(path, image_bytes, content_type)

    def upload_hike_video(
        self,
        hike_id: str,
        video_bytes: bytes,
        content_type: str,
        *,
        filename: str,
        object_id: str | None = None,
    ) -> tuple[str, str]:
        extension = Path(filename or "").suffix.lower().lstrip(".") or "mp4"
        path = f"hikes/{hike_id}/{object_id or uuid4().hex}.{extension}"
        if object_id:
            return self.replace_file(path, video_bytes, content_type)
        return self._upload_bytes(path, video_bytes, content_type)

    def upload_hike_route_import(self, hike_id: str, file_bytes: bytes, content_type: str = "application/vnd.garmin.tcx+xml") -> tuple[str, str]:
        path = f"hikes/{hike_id}/imports/{uuid4().hex}.tcx"
        return self._upload_bytes(path, file_bytes, content_type)

    def upload_standalone_photo(
        self,
        image_bytes: bytes,
        content_type: str,
        *,
        object_id: str | None = None,
    ) -> tuple[str, str]:
        path = f"standalone/{object_id or uuid4().hex}.jpg"
        if object_id:
            return self.replace_file(path, image_bytes, content_type)
        return self._upload_bytes(path, image_bytes, content_type)

    def delete_file(self, storage_path: str) -> None:
        if not storage_path:
            return
        if self.backend == "r2":
            self._r2_client.delete_object(Bucket=self.r2_bucket, Key=storage_path)
            return
        if not self.client:
            raise RuntimeError("Supabase client is required for Supabase storage.")
        self.client.storage.from_(self.supabase_bucket).remove([storage_path])

    def download_file(self, storage_path: str) -> bytes:
        """Read a stored photo without routing the CV request through a public URL."""
        if not storage_path:
            raise ValueError("The photo does not have a storage path.")
        if self.backend == "r2":
            response = self._r2_client.get_object(Bucket=self.r2_bucket, Key=storage_path)
            return response["Body"].read()
        if not self.client:
            raise RuntimeError("Supabase client is required for Supabase storage.")
        return self.client.storage.from_(self.supabase_bucket).download(storage_path)
