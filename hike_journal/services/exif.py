from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import exifread
from PIL import ExifTags, Image
from pillow_heif import register_heif_opener

from hike_journal.models import PhotoMetadata


register_heif_opener()
GPS_TAG = next(key for key, value in ExifTags.TAGS.items() if value == "GPSInfo")
DATETIME_TAGS = (
    "DateTimeOriginal",
    "DateTimeDigitized",
    "DateTime",
)
EXIFREAD_DATETIME_TAGS = (
    "EXIF DateTimeOriginal",
    "EXIF DateTimeDigitized",
    "Image DateTime",
)


def _rational_to_float(value: Any) -> float:
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        return float(value.numerator) / float(value.denominator)
    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        return float(numerator) / float(denominator)
    return float(value)


def _dms_to_decimal(values: list[Any] | tuple[Any, ...], ref: str) -> float | None:
    if len(values) != 3:
        return None
    degrees = _rational_to_float(values[0])
    minutes = _rational_to_float(values[1])
    seconds = _rational_to_float(values[2])
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in {"S", "W"}:
        decimal *= -1
    return round(decimal, 6)


def _parse_taken_at(exif_map: dict[str, Any]) -> datetime | None:
    for key in DATETIME_TAGS:
        value = exif_map.get(key)
        if not value:
            continue
        try:
            return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _extract_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "values"):
        return list(value.values)
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _parse_exifread_metadata(image_bytes: bytes) -> dict[str, Any]:
    try:
        tags = exifread.process_file(BytesIO(image_bytes), details=False)
    except Exception:
        return {}

    gps_latitude = tags.get("GPS GPSLatitude")
    gps_longitude = tags.get("GPS GPSLongitude")
    gps_latitude_ref = tags.get("GPS GPSLatitudeRef")
    gps_longitude_ref = tags.get("GPS GPSLongitudeRef")

    lat = None
    lng = None
    if gps_latitude and gps_latitude_ref:
        lat = _dms_to_decimal(_extract_sequence(gps_latitude), str(gps_latitude_ref))
    if gps_longitude and gps_longitude_ref:
        lng = _dms_to_decimal(_extract_sequence(gps_longitude), str(gps_longitude_ref))

    exif_map: dict[str, Any] = {}
    for datetime_key, mapped_key in zip(EXIFREAD_DATETIME_TAGS, DATETIME_TAGS):
        value = tags.get(datetime_key)
        if value:
            exif_map[mapped_key] = str(value)

    make = tags.get("Image Make")
    model = tags.get("Image Model")
    if make:
        exif_map["Make"] = str(make)
    if model:
        exif_map["Model"] = str(model)

    return {
        "lat": lat,
        "lng": lng,
        "exif_map": exif_map,
    }


def extract_metadata(image_bytes: bytes) -> PhotoMetadata:
    with Image.open(BytesIO(image_bytes)) as image:
        raw_exif = image.getexif() or {}
        gps_ifd = {}
        if hasattr(raw_exif, "get_ifd"):
            try:
                gps_ifd = raw_exif.get_ifd(ExifTags.IFD.GPSInfo) or {}
            except Exception:
                gps_ifd = {}

    exif_map: dict[str, Any] = {}
    gps_map: dict[str, Any] = {ExifTags.GPSTAGS.get(k, str(k)): v for k, v in gps_ifd.items()} if gps_ifd else {}

    for tag_id, value in raw_exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        if tag_id == GPS_TAG and isinstance(value, dict):
            gps_map = {ExifTags.GPSTAGS.get(k, str(k)): v for k, v in value.items()}
        else:
            exif_map[tag_name] = value

    exifread_metadata = _parse_exifread_metadata(image_bytes)
    fallback_exif_map = exifread_metadata.get("exif_map") or {}
    for key, value in fallback_exif_map.items():
        exif_map.setdefault(key, value)

    lat = None
    lng = None
    if gps_map:
        lat_values = gps_map.get("GPSLatitude")
        lat_ref = gps_map.get("GPSLatitudeRef")
        lng_values = gps_map.get("GPSLongitude")
        lng_ref = gps_map.get("GPSLongitudeRef")
        if lat_values and lat_ref:
            lat = _dms_to_decimal(lat_values, str(lat_ref))
        if lng_values and lng_ref:
            lng = _dms_to_decimal(lng_values, str(lng_ref))
    if lat is None:
        lat = exifread_metadata.get("lat")
    if lng is None:
        lng = exifread_metadata.get("lng")

    taken_at = _parse_taken_at(exif_map)
    safe_exif_json = {
        "datetime_original": exif_map.get("DateTimeOriginal"),
        "datetime_digitized": exif_map.get("DateTimeDigitized"),
        "datetime": exif_map.get("DateTime"),
        "gps_latitude": lat,
        "gps_longitude": lng,
        "make": exif_map.get("Make"),
        "model": exif_map.get("Model"),
    }

    return PhotoMetadata(lat=lat, lng=lng, taken_at=taken_at, exif_json=safe_exif_json)
