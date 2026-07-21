from __future__ import annotations

from uuid import uuid4

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
            return f"{settings.r2_public_base_url}/{path}"
        if not self.client:
            raise RuntimeError("Supabase client is required for Supabase storage.")
        return self.client.storage.from_(self.supabase_bucket).get_public_url(path)

    def _upload_bytes(self, path: str, file_bytes: bytes, content_type: str) -> tuple[str, str]:
        if self.backend == "r2":
            self._r2_client.put_object(
                Bucket=self.r2_bucket,
                Key=path,
                Body=file_bytes,
                ContentType=content_type,
                CacheControl="public, max-age=3600",
            )
            return path, self._build_public_url(path)

        if not self.client:
            raise RuntimeError("Supabase client is required for Supabase storage.")
        self.client.storage.from_(self.supabase_bucket).upload(
            path=path,
            file=file_bytes,
            file_options={"content-type": content_type, "cache-control": "3600", "upsert": "false"},
        )
        return path, self._build_public_url(path)

    def replace_file(self, path: str, file_bytes: bytes, content_type: str) -> tuple[str, str]:
        if self.backend == "r2":
            self._r2_client.put_object(
                Bucket=self.r2_bucket,
                Key=path,
                Body=file_bytes,
                ContentType=content_type,
                CacheControl="public, max-age=3600",
            )
            return path, self._build_public_url(path)

        if not self.client:
            raise RuntimeError("Supabase client is required for Supabase storage.")
        self.client.storage.from_(self.supabase_bucket).upload(
            path=path,
            file=file_bytes,
            file_options={"content-type": content_type, "cache-control": "3600", "upsert": "true"},
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

    def upload_hike_route_import(self, hike_id: str, file_bytes: bytes, content_type: str = "application/vnd.garmin.tcx+xml") -> tuple[str, str]:
        path = f"hikes/{hike_id}/imports/{uuid4().hex}.tcx"
        return self._upload_bytes(path, file_bytes, content_type)

    def upload_standalone_photo(self, image_bytes: bytes, content_type: str) -> tuple[str, str]:
        path = f"standalone/{uuid4().hex}.jpg"
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
