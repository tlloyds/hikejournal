from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from hike_journal.config import settings
from hike_journal.models import ProcessedImage


register_heif_opener()
RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS


def _process_image(image_bytes: bytes, *, max_dimension: int, quality: int) -> ProcessedImage:
    with Image.open(BytesIO(image_bytes)) as image:
        normalized = ImageOps.exif_transpose(image)
        if normalized.mode not in {"RGB", "L"}:
            normalized = normalized.convert("RGB")
        elif normalized.mode == "L":
            normalized = normalized.convert("RGB")

        width, height = normalized.size
        max_source_dimension = max(width, height)
        if max_source_dimension > max_dimension:
            scale = max_dimension / max_source_dimension
            normalized = normalized.resize((int(width * scale), int(height * scale)), RESAMPLE)

        output = BytesIO()
        normalized.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
        payload = output.getvalue()
        final_width, final_height = normalized.size

    return ProcessedImage(
        bytes_data=payload,
        width=final_width,
        height=final_height,
        format="JPEG",
        content_type="image/jpeg",
    )


def optimize_image(image_bytes: bytes) -> ProcessedImage:
    return _process_image(
        image_bytes,
        max_dimension=settings.image_max_dimension,
        quality=settings.image_quality,
    )


def build_thumbnail(image_bytes: bytes) -> ProcessedImage:
    return _process_image(
        image_bytes,
        max_dimension=settings.thumbnail_max_dimension,
        quality=settings.thumbnail_quality,
    )


def recompress_image(image_bytes: bytes, *, max_dimension: int, quality: int) -> ProcessedImage:
    return _process_image(
        image_bytes,
        max_dimension=max_dimension,
        quality=quality,
    )
