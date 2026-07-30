from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from hike_journal.services import media_uploads
from hike_journal.services.media_uploads import MediaUploadError, prepare_media_uploads


class FakeUpload(BytesIO):
    def __init__(self, payload: bytes, *, name: str, content_type: str) -> None:
        super().__init__(payload)
        self.name = name
        self.type = content_type


def build_zip(entries: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return output.getvalue()


def zip_upload(entries: dict[str, bytes], *, name: str = "album.zip") -> FakeUpload:
    return FakeUpload(build_zip(entries), name=name, content_type="application/zip")


def test_prepares_nested_google_photos_zip_without_reencoding_originals() -> None:
    first_photo = b"original-jpeg-with-exif"
    second_photo = b"original-heic-with-exif"
    uploaded = zip_upload(
        {
            "Google Photos/Hike/IMG_0001.JPG": first_photo,
            "Google Photos/Hike/nested/IMG_0002.HEIC": second_photo,
            "Google Photos/Hike/IMG_0001.JPG.json": b'{"geoData": {}}',
            "__MACOSX/._IMG_0001.JPG": b"finder metadata",
        }
    )

    batch = prepare_media_uploads([uploaded], allow_direct_videos=False)

    assert batch.archive_count == 1
    assert batch.archived_photo_count == 2
    assert batch.ignored_archive_entry_count == 2
    assert [item.name for item in batch.uploads] == ["IMG_0001.JPG", "IMG_0002.HEIC"]
    assert [item.type for item in batch.uploads] == ["image/jpeg", "image/heic"]
    assert [item.getvalue() for item in batch.uploads] == [first_photo, second_photo]
    assert all(item.from_archive for item in batch.uploads)


def test_flattens_archive_paths_and_keeps_direct_video_support() -> None:
    uploaded = zip_upload(
        {
            "../../outside.jpg": b"safe-in-memory-photo",
            r"windows\folder\trail.png": b"another-photo",
        }
    )
    video = FakeUpload(b"video", name="trail.MOV", content_type="video/quicktime")

    batch = prepare_media_uploads([uploaded, video], allow_direct_videos=True)

    assert [item.name for item in batch.uploads] == ["outside.jpg", "trail.png", "trail.MOV"]
    assert batch.uploads[-1].type == "video/quicktime"
    assert not batch.uploads[-1].from_archive


def test_rejects_invalid_zip() -> None:
    uploaded = FakeUpload(b"not a zip", name="album.zip", content_type="application/zip")

    with pytest.raises(MediaUploadError, match="not a readable ZIP"):
        prepare_media_uploads([uploaded], allow_direct_videos=False)


def test_rejects_zip_without_supported_photos() -> None:
    uploaded = zip_upload({"album/metadata.json": b"{}", "album/clip.mp4": b"video"})

    with pytest.raises(MediaUploadError, match="did not contain supported photos"):
        prepare_media_uploads([uploaded], allow_direct_videos=False)


def test_enforces_combined_media_count_for_archive_and_direct_files() -> None:
    uploaded = zip_upload(
        {
            "one.jpg": b"one",
            "two.jpg": b"two",
        }
    )
    direct = FakeUpload(b"three", name="three.jpg", content_type="image/jpeg")

    with pytest.raises(MediaUploadError, match="no more than 2"):
        prepare_media_uploads(
            [uploaded, direct],
            allow_direct_videos=False,
            max_media_files=2,
        )


def test_rejects_oversized_archive_photo_before_reading_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(media_uploads, "MAX_ARCHIVE_ENTRY_BYTES", 8)
    uploaded = zip_upload({"large.jpg": b"123456789"})

    with pytest.raises(MediaUploadError, match="30 MB per-photo ZIP limit"):
        prepare_media_uploads([uploaded], allow_direct_videos=False)


def test_rejects_suspicious_compression_ratio() -> None:
    uploaded = zip_upload({"suspicious.jpg": b"\x00" * (2 * 1024 * 1024)})

    with pytest.raises(MediaUploadError, match="unsafe compression ratio"):
        prepare_media_uploads([uploaded], allow_direct_videos=False)


def test_rejects_unsupported_direct_file() -> None:
    uploaded = FakeUpload(b"{}", name="metadata.json", content_type="application/json")

    with pytest.raises(MediaUploadError, match="not a supported photo or video"):
        prepare_media_uploads([uploaded], allow_direct_videos=True)
