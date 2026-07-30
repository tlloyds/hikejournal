from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Iterable
from zipfile import BadZipFile, LargeZipFile, ZipFile, ZipInfo

from hike_journal.media import is_supported_video_upload, video_content_type


PHOTO_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "heic": "image/heic",
    "heif": "image/heif",
}
MAX_MEDIA_FILES = 500
MAX_ARCHIVE_ENTRIES = 5_000
MAX_ARCHIVE_ENTRY_BYTES = 30 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


class MediaUploadError(ValueError):
    """Raised when selected upload media cannot be prepared safely."""


@dataclass
class PreparedMediaUpload:
    name: str
    type: str
    _source: Any = field(repr=False)
    _archive_info: ZipInfo | None = field(default=None, repr=False)

    @property
    def from_archive(self) -> bool:
        return self._archive_info is not None

    def getvalue(self) -> bytes:
        if self._archive_info is None:
            return bytes(self._source.getvalue())

        try:
            with _open_zip(self._source) as archive:
                with archive.open(self._archive_info, "r") as entry:
                    payload = entry.read(MAX_ARCHIVE_ENTRY_BYTES + 1)
        except (BadZipFile, LargeZipFile, RuntimeError, OSError) as exc:
            raise MediaUploadError(
                f"Could not read {self.name} from the ZIP. Download the album again and retry."
            ) from exc

        if len(payload) > MAX_ARCHIVE_ENTRY_BYTES:
            raise MediaUploadError(
                f"{self.name} is larger than the 30 MB per-photo ZIP limit."
            )
        return payload


@dataclass(frozen=True)
class PreparedMediaBatch:
    uploads: tuple[PreparedMediaUpload, ...]
    archive_count: int
    archived_photo_count: int
    ignored_archive_entry_count: int


def _source_name(uploaded_file: Any) -> str:
    return str(getattr(uploaded_file, "name", "") or "").strip()


def _extension(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    return PurePosixPath(normalized).suffix.lower().lstrip(".")


def _safe_basename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    return PurePosixPath(normalized).name


def _is_metadata_artifact(filename: str) -> bool:
    normalized = filename.replace("\\", "/")
    path = PurePosixPath(normalized)
    return "__MACOSX" in path.parts or path.name.startswith("._") or path.name == ".DS_Store"


def _open_zip(source: Any) -> ZipFile:
    seek = getattr(source, "seek", None)
    if callable(seek):
        seek(0)
        return ZipFile(source, "r", allowZip64=True)
    return ZipFile(BytesIO(bytes(source.getvalue())), "r", allowZip64=True)


def _photo_content_type(filename: str) -> str | None:
    return PHOTO_CONTENT_TYPES.get(_extension(filename))


def _compression_ratio_too_high(info: ZipInfo) -> bool:
    if info.file_size <= 1024 * 1024:
        return False
    return info.compress_size == 0 or info.file_size / info.compress_size > MAX_COMPRESSION_RATIO


def _prepare_archive(
    uploaded_file: Any,
) -> tuple[list[PreparedMediaUpload], int]:
    archive_name = _source_name(uploaded_file) or "selected ZIP"
    prepared: list[PreparedMediaUpload] = []
    ignored_count = 0
    expanded_bytes = 0

    try:
        with _open_zip(uploaded_file) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise MediaUploadError(
                    f"{archive_name} contains too many entries. ZIP albums may contain up to "
                    f"{MAX_ARCHIVE_ENTRIES:,} files and folders."
                )

            for info in entries:
                if info.is_dir():
                    continue

                filename = _safe_basename(info.filename)
                content_type = _photo_content_type(filename)
                if not filename or _is_metadata_artifact(info.filename) or content_type is None:
                    ignored_count += 1
                    continue
                if info.flag_bits & 0x1:
                    raise MediaUploadError(
                        f"{archive_name} is password-protected. Upload an unencrypted Google Photos ZIP."
                    )
                if info.file_size > MAX_ARCHIVE_ENTRY_BYTES:
                    raise MediaUploadError(
                        f"{filename} is larger than the 30 MB per-photo ZIP limit."
                    )
                if _compression_ratio_too_high(info):
                    raise MediaUploadError(
                        f"{archive_name} has an unsafe compression ratio and was not opened."
                    )

                expanded_bytes += info.file_size
                if expanded_bytes > MAX_ARCHIVE_TOTAL_BYTES:
                    raise MediaUploadError(
                        f"{archive_name} expands beyond the 2 GB album limit."
                    )
                prepared.append(
                    PreparedMediaUpload(
                        name=filename,
                        type=content_type,
                        _source=uploaded_file,
                        _archive_info=info,
                    )
                )
    except MediaUploadError:
        raise
    except (BadZipFile, LargeZipFile, RuntimeError, OSError) as exc:
        raise MediaUploadError(
            f"{archive_name} is not a readable ZIP file. Download the album again and retry."
        ) from exc

    return prepared, ignored_count


def prepare_media_uploads(
    uploaded_files: Iterable[Any],
    *,
    allow_direct_videos: bool,
    max_media_files: int = MAX_MEDIA_FILES,
) -> PreparedMediaBatch:
    prepared: list[PreparedMediaUpload] = []
    archive_count = 0
    archived_photo_count = 0
    ignored_archive_entry_count = 0

    for uploaded_file in uploaded_files:
        name = _source_name(uploaded_file)
        extension = _extension(name)
        reported_type = str(getattr(uploaded_file, "type", "") or "").strip()

        if extension == "zip" or reported_type.lower() in {
            "application/zip",
            "application/x-zip-compressed",
        }:
            archive_uploads, ignored_count = _prepare_archive(uploaded_file)
            archive_count += 1
            archived_photo_count += len(archive_uploads)
            ignored_archive_entry_count += ignored_count
            prepared.extend(archive_uploads)
        elif (content_type := _photo_content_type(name)) is not None:
            prepared.append(
                PreparedMediaUpload(
                    name=name,
                    type=reported_type or content_type,
                    _source=uploaded_file,
                )
            )
        elif allow_direct_videos and is_supported_video_upload(name, reported_type):
            prepared.append(
                PreparedMediaUpload(
                    name=name,
                    type=video_content_type(name, reported_type),
                    _source=uploaded_file,
                )
            )
        else:
            raise MediaUploadError(f"{name or 'The selected file'} is not a supported photo or video.")

        if len(prepared) > max_media_files:
            raise MediaUploadError(
                f"Choose no more than {max_media_files} photos and videos at a time."
            )

    if not prepared:
        if archive_count:
            raise MediaUploadError(
                "The selected ZIP did not contain supported photos. Use JPG, JPEG, PNG, WebP, HEIC, or HEIF originals."
            )
        raise MediaUploadError("Choose at least one photo to upload.")

    return PreparedMediaBatch(
        uploads=tuple(prepared),
        archive_count=archive_count,
        archived_photo_count=archived_photo_count,
        ignored_archive_entry_count=ignored_archive_entry_count,
    )
