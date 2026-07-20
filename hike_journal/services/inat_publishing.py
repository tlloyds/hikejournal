from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import requests

from hike_journal.services.inat import InatClient, InatRequestError
from hike_journal.services.repositories import HikeJournalRepository


MAX_PUBLISH_IMAGE_BYTES = 30 * 1024 * 1024


def get_inat_posting(observation: dict[str, Any]) -> dict[str, Any]:
    raw_payload = observation.get("raw_response_json")
    raw_payload = raw_payload if isinstance(raw_payload, dict) else {}
    raw_posting = raw_payload.get("inat_posting")
    raw_posting = raw_posting if isinstance(raw_posting, dict) else {}
    if observation.get("inat_observation_id"):
        return {
            **raw_posting,
            "observation_id": observation.get("inat_observation_id"),
            "observation_url": observation.get("inat_observation_url")
            or build_inat_observation_url(observation.get("inat_observation_id")),
            "posted_at": observation.get("inat_posted_at"),
            "photo_attached": observation.get("inat_photo_attached"),
        }
    return raw_posting


def get_publish_state(observation: dict[str, Any]) -> str:
    posting = get_inat_posting(observation)
    if posting.get("observation_id"):
        return "needs_attention" if posting.get("photo_attached") is False else "posted"
    return "ready"


def build_inat_observation_url(observation_id: int | str) -> str:
    return f"https://www.inaturalist.org/observations/{observation_id}"


def download_public_image(public_url: str) -> bytes:
    if not public_url.strip():
        raise RuntimeError("This record is missing its public photo URL.")
    response = requests.get(public_url, timeout=30)
    response.raise_for_status()
    image_bytes = response.content
    if not image_bytes:
        raise RuntimeError("The field photo was empty.")
    if len(image_bytes) > MAX_PUBLISH_IMAGE_BYTES:
        raise RuntimeError("The field photo is too large to publish from HikeJournal.")
    return image_bytes


def publish_single_observation(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    observation: dict[str, Any],
    photo: dict[str, Any],
    *,
    place_guess: str | None,
    owner_subject: str | None,
    owner_email: str | None,
    image_loader: Callable[[str], bytes] = download_public_image,
    description: str | None = None,
    tags: list[str] | None = None,
    geoprivacy: str = "open",
    captive: bool = False,
) -> dict[str, Any]:
    return publish_observation_group(
        repository,
        inat_client,
        [(observation, photo)],
        place_guess=place_guess,
        owner_subject=owner_subject,
        owner_email=owner_email,
        image_loader=image_loader,
        description=description,
        tags=tags,
        geoprivacy=geoprivacy,
        captive=captive,
    )


def publish_observation_group(
    repository: HikeJournalRepository,
    inat_client: InatClient,
    records: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    place_guess: str | None,
    owner_subject: str | None,
    owner_email: str | None,
    image_loader: Callable[[str], bytes] = download_public_image,
    description: str | None = None,
    tags: list[str] | None = None,
    geoprivacy: str = "open",
    captive: bool = False,
) -> dict[str, Any]:
    if not records:
        raise RuntimeError("Choose at least one confirmed sighting before publishing.")
    if len(records) > 10:
        raise RuntimeError("An iNaturalist observation can include at most 10 HikeJournal photos at once.")
    if geoprivacy not in {"open", "obscured", "private"}:
        raise RuntimeError("Choose open, obscured, or private location sharing.")

    observations = [record[0] for record in records]
    photos = [record[1] for record in records]
    for observation in observations:
        if get_inat_posting(observation).get("observation_id"):
            raise RuntimeError("One of these sightings has already been published to iNaturalist.")
        if observation.get("status") != "confirmed":
            raise RuntimeError("Confirm every species identification before publishing.")

    identities = {
        str(observation.get("taxon_id") or observation.get("scientific_name") or "").strip().casefold()
        for observation in observations
    }
    if "" in identities or len(identities) != 1:
        raise RuntimeError("Grouped photos must show the same confirmed species.")

    inat_client.validate_credentials()
    images = [image_loader(str(photo.get("public_url") or "").strip()) for photo in photos]
    lead_observation = observations[0]
    lead_photo = photos[0]
    observed_on = _parse_datetime(lead_photo.get("taken_at") or lead_photo.get("created_at"))
    species_guess = str(
        lead_observation.get("common_name") or lead_observation.get("scientific_name") or ""
    ).strip()
    photo_captions = [str(photo.get("caption") or "").strip() for photo in photos]
    default_description = next((caption for caption in photo_captions if caption), "")
    final_description = (description or default_description).strip()
    final_description = (
        f"{final_description}\n\nPosted from HikeJournal."
        if final_description
        else "Posted from HikeJournal."
    )
    final_tags = list(dict.fromkeys(["HikeJournal", *(tags or [])]))
    created = inat_client.create_observation(
        taxon_id=lead_observation.get("taxon_id"),
        species_guess=species_guess,
        observed_on=observed_on,
        lat=lead_photo.get("lat"),
        lng=lead_photo.get("lng"),
        place_guess=place_guess,
        description=final_description,
        tags=final_tags,
        geoprivacy=geoprivacy,
        captive=captive,
    )
    created_id = created.get("id")
    if created_id in (None, ""):
        raise InatRequestError("iNaturalist created a response without an observation ID.")

    observation_url = str(
        created.get("uri")
        or created.get("html_url")
        or build_inat_observation_url(created_id)
    )
    posting: dict[str, Any] = {
        "observation_id": int(created_id),
        "observation_url": observation_url,
        "posted_at": datetime.now().astimezone().isoformat(),
        "posted_by_subject": owner_subject,
        "posted_by_email": owner_email,
        "photo_attached": True,
        "photo_count": len(photos),
        "attached_photo_count": 0,
        "local_photo_ids": [str(photo.get("id") or "") for photo in photos],
        "local_observation_ids": [str(observation.get("id") or "") for observation in observations],
        "group_lead_observation_id": str(lead_observation.get("id") or ""),
        "grouped": len(records) > 1,
        "geoprivacy": geoprivacy,
        "captive": captive,
        "tags": final_tags,
        "attached_local_photo_ids": [],
        "failed_local_photo_ids": [],
    }
    upload_errors: list[str] = []
    for photo, image_bytes in zip(photos, images, strict=True):
        photo_id = str(photo.get("id") or "")
        try:
            inat_client.attach_photo_to_observation(
                observation_id=int(created_id),
                image_bytes=image_bytes,
                filename=f"{photo_id or 'hikejournal'}.jpg",
                content_type=str(photo.get("content_type") or "image/jpeg"),
            )
        except InatRequestError as exc:
            posting["failed_local_photo_ids"].append(photo_id)
            upload_errors.append(str(exc))
        else:
            posting["attached_local_photo_ids"].append(photo_id)
    posting["attached_photo_count"] = len(posting["attached_local_photo_ids"])
    posting["photo_attached"] = not posting["failed_local_photo_ids"]
    if upload_errors:
        posting["upload_errors"] = upload_errors

    for observation in observations:
        raw_payload = observation.get("raw_response_json")
        raw_payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
        raw_payload["inat_posting"] = posting
        repository.update_observation_raw_payload(str(observation["id"]), raw_payload)
        repository.update_observation_inat_posting(
            str(observation["id"]),
            inat_observation_id=int(created_id),
            inat_observation_url=observation_url,
            inat_posted_at=str(posting["posted_at"]),
            inat_photo_attached=bool(posting["photo_attached"]),
        )
    return posting


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
