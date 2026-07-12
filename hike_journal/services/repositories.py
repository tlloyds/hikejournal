from __future__ import annotations

from datetime import UTC, date, datetime
import re
from typing import Any

from supabase import Client

from hike_journal.models import HikeDraft, SpeciesCandidate


LIGHTWEIGHT_OBSERVATION_COLUMNS = (
    "id,photo_id,hike_id,owner_subject,owner_email,taxon_id,common_name,scientific_name,"
    "confidence,status,is_primary,identified_at,source,inat_observation_id,inat_observation_url,"
    "inat_posted_at,inat_photo_attached,"
    "species_log_main_photo:raw_response_json->species_log_main_photo"
)


def _slugify_location_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower().strip())
    return re.sub(r"-+", "-", slug).strip("-") or "location"


class HikeJournalRepository:
    def __init__(self, client: Client):
        self.client = client

    def _select_all_rows(self, query_factory, *, page_size: int = 1000) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = query_factory().range(offset, offset + page_size - 1).execute()
            batch = response.data or []
            rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return rows

    def _chunks(self, values: list[str], size: int = 25):
        for start in range(0, len(values), size):
            yield values[start : start + size]

    def list_hikes(self) -> list[dict[str, Any]]:
        try:
            response = (
                self.client.table("hikes")
                .select("*")
                .order("is_archived")
                .order("hike_date", desc=True)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception:
            response = (
                self.client.table("hikes")
                .select("*")
                .order("hike_date", desc=True)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []

    def list_hike_route_imports(self) -> list[dict[str, Any]]:
        try:
            response = (
                self.client.table("hike_route_imports")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception:
            return []

    def get_hike_route_import(self, hike_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("hike_route_imports")
                .select("*")
                .eq("hike_id", hike_id)
                .limit(1)
                .execute()
            )
        except Exception:
            return None
        records = response.data or []
        return records[0] if records else None

    def create_hike(self, draft: HikeDraft) -> dict[str, Any]:
        payload = {
            "title": draft.title.strip(),
            "hike_date": draft.hike_date.isoformat(),
            "distance_miles": draft.distance_miles,
            "location_name": draft.location_name.strip() or None,
            "notes": draft.notes.strip() or None,
            "owner_subject": draft.owner_subject,
            "owner_email": draft.owner_email,
        }
        try:
            response = self.client.table("hikes").insert(payload).execute()
        except Exception:
            legacy_payload = {key: value for key, value in payload.items() if key not in {"owner_subject", "owner_email"}}
            response = self.client.table("hikes").insert(legacy_payload).execute()
        return response.data[0]

    def update_hike(self, hike_id: str, *, title: str, hike_date: date, distance_miles: float | None, location_name: str, notes: str) -> dict[str, Any]:
        payload = {
            "title": title.strip(),
            "hike_date": hike_date.isoformat(),
            "distance_miles": distance_miles,
            "location_name": location_name.strip() or None,
            "notes": notes.strip() or None,
        }
        response = self.client.table("hikes").update(payload).eq("id", hike_id).execute()
        return response.data[0]

    def list_hike_locations(self) -> list[dict[str, Any]]:
        try:
            return self._select_all_rows(
                lambda: self.client.table("hike_locations").select("*").order("name")
            )
        except Exception:
            return []

    def list_hike_location_tags(self) -> list[dict[str, Any]]:
        try:
            return self._select_all_rows(
                lambda: self.client.table("hike_location_tags").select("*").order("created_at")
            )
        except Exception:
            return []

    def upsert_hike_location(self, name: str, **values: Any) -> dict[str, Any] | None:
        clean_name = name.strip()
        if not clean_name:
            return None
        payload = {
            "name": clean_name,
            "slug": values.get("slug") or _slugify_location_name(clean_name),
            "location_type": values.get("location_type") or "manual",
            "source": values.get("source") or "manual",
            "source_url": values.get("source_url"),
            "lat": values.get("lat"),
            "lng": values.get("lng"),
            "aliases": values.get("aliases") or [],
        }
        try:
            response = self.client.table("hike_locations").upsert(payload, on_conflict="slug").execute()
            rows = response.data or []
            return rows[0] if rows else payload
        except Exception:
            return None

    def upsert_hike_locations(self, locations: list[dict[str, Any]]) -> int:
        payloads: list[dict[str, Any]] = []
        for location in locations:
            name = str(location.get("name") or "").strip()
            if not name:
                continue
            payloads.append(
                {
                    "name": name,
                    "slug": str(location.get("slug") or _slugify_location_name(name)),
                    "location_type": location.get("location_type"),
                    "source": location.get("source") or "seed",
                    "source_url": location.get("source_url"),
                    "lat": location.get("lat"),
                    "lng": location.get("lng"),
                    "aliases": location.get("aliases") or [],
                }
            )
        if not payloads:
            return 0
        try:
            for start in range(0, len(payloads), 200):
                self.client.table("hike_locations").upsert(
                    payloads[start : start + 200],
                    on_conflict="slug",
                ).execute()
            return len(payloads)
        except Exception:
            return 0

    def set_hike_location_tags(self, hike_id: str, location_ids: list[str]) -> None:
        normalized_ids: list[str] = []
        seen = set()
        for location_id in location_ids:
            clean_id = str(location_id).strip()
            if clean_id and clean_id not in seen:
                normalized_ids.append(clean_id)
                seen.add(clean_id)
        try:
            self.client.table("hike_location_tags").delete().eq("hike_id", hike_id).execute()
            if normalized_ids:
                payloads = [
                    {
                        "hike_id": hike_id,
                        "location_id": location_id,
                        "is_primary": index == 0,
                    }
                    for index, location_id in enumerate(normalized_ids)
                ]
                self.client.table("hike_location_tags").insert(payloads).execute()
        except Exception:
            return

    def upsert_hike_route_import(self, hike_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_payload = dict(payload)
        normalized_payload["hike_id"] = hike_id
        response = (
            self.client.table("hike_route_imports")
            .upsert(normalized_payload, on_conflict="hike_id")
            .execute()
        )
        return response.data[0]

    def delete_hike_route_import(self, hike_id: str) -> dict[str, Any] | None:
        existing = self.get_hike_route_import(hike_id)
        if not existing:
            return None
        self.client.table("hike_route_imports").delete().eq("hike_id", hike_id).execute()
        return existing

    def update_hike_archive(self, hike_id: str, is_archived: bool) -> dict[str, Any]:
        response = self.client.table("hikes").update({"is_archived": is_archived}).eq("id", hike_id).execute()
        return response.data[0]

    def update_hike_cover_photo(self, hike_id: str, photo_id: str | None) -> dict[str, Any]:
        response = (
            self.client.table("hikes")
            .update({"cover_photo_id": photo_id})
            .eq("id", hike_id)
            .execute()
        )
        return response.data[0]

    def claim_unowned_hikes(self, *, owner_subject: str | None, owner_email: str | None) -> None:
        if not owner_email and not owner_subject:
            return
        payload = {
            "owner_subject": owner_subject,
            "owner_email": owner_email,
        }
        query = (
            self.client.table("hikes")
            .update(payload)
            .is_("owner_subject", "null")
            .is_("owner_email", "null")
        )
        query.execute()

    def list_photos(self, hike_id: str) -> list[dict[str, Any]]:
        return self._select_all_rows(
            lambda: (
                self.client.table("photos")
                .select("*")
                .eq("hike_id", hike_id)
                .order("taken_at")
                .order("created_at")
            )
        )

    def list_standalone_photos(self) -> list[dict[str, Any]]:
        return self._select_all_rows(
            lambda: (
                self.client.table("photos")
                .select("*")
                .is_("hike_id", "null")
                .order("taken_at", desc=True)
                .order("created_at", desc=True)
            )
        )

    def list_map_photos(self, hike_id: str | None = None) -> list[dict[str, Any]]:
        def query_factory():
            query = (
                self.client.table("photos")
                .select("id,hike_id,owner_subject,owner_email,caption,public_url,lat,lng,taken_at,created_at,width,height,exif_json")
                .not_.is_("lat", "null")
                .not_.is_("lng", "null")
            )
            if hike_id:
                query = query.eq("hike_id", hike_id)
            return query

        return self._select_all_rows(query_factory)

    def list_review_queue_photos(self) -> list[dict[str, Any]]:
        return self._select_all_rows(
            lambda: (
                self.client.table("photos")
                .select("*")
                .eq("processing_status", "in_review")
                .order("taken_at")
                .order("created_at")
            )
        )

    def list_photo_hike_refs(self) -> list[dict[str, Any]]:
        return self._select_all_rows(
            lambda: self.client.table("photos").select("hike_id,owner_subject,owner_email")
        )

    def list_photo_storage_records(self) -> list[dict[str, Any]]:
        return self._select_all_rows(
            lambda: self.client.table("photos").select("id,hike_id,owner_subject,owner_email,file_size,exif_json")
        )

    def list_photo_records_for_ids(self, photo_ids: list[str]) -> list[dict[str, Any]]:
        normalized_ids = [str(photo_id) for photo_id in photo_ids if str(photo_id).strip()]
        if not normalized_ids:
            return []
        rows_by_id: dict[str, dict[str, Any]] = {}
        chunk_size = 200
        for start in range(0, len(normalized_ids), chunk_size):
            chunk_ids = normalized_ids[start : start + chunk_size]
            response = (
                self.client.table("photos")
                .select("id,hike_id,owner_subject,owner_email,caption,public_url,lat,lng,taken_at,created_at,width,height,exif_json")
                .in_("id", chunk_ids)
                .execute()
            )
            for row in response.data or []:
                row_id = str(row.get("id") or "")
                if row_id:
                    rows_by_id[row_id] = row
        return [rows_by_id[photo_id] for photo_id in normalized_ids if photo_id in rows_by_id]

    def create_photo(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.table("photos").insert(payload).execute()
        return response.data[0]

    def update_photo_caption(self, photo_id: str, caption: str) -> dict[str, Any]:
        response = self.client.table("photos").update({"caption": caption.strip() or None}).eq("id", photo_id).execute()
        return response.data[0]

    def update_photo_exif_json(self, photo_id: str, exif_json: dict[str, Any]) -> dict[str, Any]:
        response = self.client.table("photos").update({"exif_json": exif_json}).eq("id", photo_id).execute()
        return response.data[0]

    def update_photo_media_metadata(
        self,
        photo_id: str,
        *,
        width: int,
        height: int,
        file_size: int,
        content_type: str,
        exif_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "width": width,
            "height": height,
            "file_size": file_size,
            "content_type": content_type,
        }
        if exif_json is not None:
            payload["exif_json"] = exif_json
        response = self.client.table("photos").update(payload).eq("id", photo_id).execute()
        return response.data[0]

    def update_photo_public_url(self, photo_id: str, public_url: str) -> dict[str, Any]:
        response = self.client.table("photos").update({"public_url": public_url}).eq("id", photo_id).execute()
        return response.data[0]

    def update_photo_processing_status(self, photo_id: str, status: str) -> dict[str, Any]:
        response = self.client.table("photos").update({"processing_status": status}).eq("id", photo_id).execute()
        return response.data[0]

    def update_photo_processing_statuses(self, photo_ids: list[str], status: str) -> list[dict[str, Any]]:
        normalized_ids = [str(photo_id) for photo_id in photo_ids if str(photo_id).strip()]
        if not normalized_ids:
            return []
        response = (
            self.client.table("photos")
            .update({"processing_status": status})
            .in_("id", normalized_ids)
            .execute()
        )
        return response.data or []

    def delete_photo(self, photo_id: str) -> None:
        try:
            self.client.table("hikes").update({"cover_photo_id": None}).eq("cover_photo_id", photo_id).execute()
        except Exception:
            pass
        self.client.table("species_observations").delete().eq("photo_id", photo_id).execute()
        self.client.table("photos").delete().eq("id", photo_id).execute()

    def delete_observations(self, observation_ids: list[str]) -> None:
        normalized_ids = [str(observation_id) for observation_id in observation_ids if str(observation_id).strip()]
        if not normalized_ids:
            return
        for chunk_ids in self._chunks(normalized_ids, size=200):
            self.client.table("species_observations").delete().in_("id", chunk_ids).execute()

    def delete_observations_for_photo_ids(self, photo_ids: list[str]) -> None:
        normalized_ids = [str(photo_id) for photo_id in photo_ids if str(photo_id).strip()]
        if not normalized_ids:
            return
        for chunk_ids in self._chunks(normalized_ids, size=200):
            self.client.table("species_observations").delete().in_("photo_id", chunk_ids).execute()

    def delete_hike(self, hike_id: str) -> None:
        self.client.table("hike_collaborators").delete().eq("hike_id", hike_id).execute()
        try:
            self.client.table("hike_location_tags").delete().eq("hike_id", hike_id).execute()
        except Exception:
            pass
        self.client.table("hike_route_imports").delete().eq("hike_id", hike_id).execute()
        self.client.table("species_observations").delete().eq("hike_id", hike_id).execute()
        self.client.table("photos").delete().eq("hike_id", hike_id).execute()
        self.client.table("hikes").delete().eq("id", hike_id).execute()

    def list_observations(self, hike_id: str) -> list[dict[str, Any]]:
        try:
            return self._select_all_rows(
                lambda: (
                    self.client.table("species_observations")
                    .select("*")
                    .eq("hike_id", hike_id)
                    .order("is_primary", desc=True)
                    .order("identified_at", desc=True)
                )
            )
        except Exception:
            return self._select_all_rows(
                lambda: (
                    self.client.table("species_observations")
                    .select("*")
                    .eq("hike_id", hike_id)
                    .order("identified_at", desc=True)
                )
            )

    def list_lightweight_observations(
        self,
        *,
        hike_id: str | None = None,
        photo_ids: list[str] | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_ids = None
        if photo_ids is not None:
            normalized_ids = [str(photo_id) for photo_id in photo_ids if str(photo_id).strip()]
            if not normalized_ids:
                return []

        def query_factory(chunk_ids: list[str] | None = None):
            query = self.client.table("species_observations").select(
                LIGHTWEIGHT_OBSERVATION_COLUMNS
            )
            if hike_id:
                query = query.eq("hike_id", hike_id)
            if status:
                query = query.eq("status", status)
            if chunk_ids is not None:
                query = query.in_("photo_id", chunk_ids)
            return query

        if normalized_ids is not None:
            rows: list[dict[str, Any]] = []
            for chunk_ids in self._chunks(normalized_ids):
                rows.extend(self._select_all_rows(lambda chunk_ids=chunk_ids: query_factory(chunk_ids)))
            return rows

        return self._select_all_rows(lambda: query_factory())

    def list_observations_for_photo_ids(self, photo_ids: list[str]) -> list[dict[str, Any]]:
        normalized_ids = [str(photo_id) for photo_id in photo_ids if str(photo_id).strip()]
        if not normalized_ids:
            return []
        rows: list[dict[str, Any]] = []
        for chunk_ids in self._chunks(normalized_ids):
            try:
                response = (
                    self.client.table("species_observations")
                    .select("*")
                    .in_("photo_id", chunk_ids)
                    .order("is_primary", desc=True)
                    .order("identified_at", desc=True)
                    .execute()
                )
            except Exception:
                response = (
                    self.client.table("species_observations")
                    .select("*")
                    .in_("photo_id", chunk_ids)
                    .order("identified_at", desc=True)
                    .execute()
                )
            rows.extend(response.data or [])
        return rows

    def list_observations_by_ids(self, observation_ids: list[str]) -> list[dict[str, Any]]:
        normalized_ids = [str(observation_id) for observation_id in observation_ids if str(observation_id).strip()]
        if not normalized_ids:
            return []
        rows: list[dict[str, Any]] = []
        for chunk_ids in self._chunks(normalized_ids):
            response = (
                self.client.table("species_observations")
                .select("*")
                .in_("id", chunk_ids)
                .execute()
            )
            rows.extend(response.data or [])
        return rows

    def list_species_log_photo_preferences(self, observation_ids: list[str]) -> list[dict[str, Any]]:
        normalized_ids = [str(observation_id) for observation_id in observation_ids if str(observation_id).strip()]
        if not normalized_ids:
            return []
        rows: list[dict[str, Any]] = []
        for chunk_ids in self._chunks(normalized_ids, size=200):
            response = (
                self.client.table("species_observations")
                .select("id,species_log_main_photo:raw_response_json->species_log_main_photo")
                .in_("id", chunk_ids)
                .execute()
            )
            rows.extend(response.data or [])
        return rows

    def list_confirmed_observation_hike_refs(self) -> list[dict[str, Any]]:
        return self._select_all_rows(
            lambda: (
                self.client.table("species_observations")
                .select("hike_id,owner_subject,owner_email")
                .eq("status", "confirmed")
            )
        )

    def _clear_primary_for_photo(self, photo_id: str, *, except_observation_id: str | None = None) -> None:
        query = self.client.table("species_observations").update({"is_primary": False}).eq("photo_id", photo_id).eq("is_primary", True)
        if except_observation_id:
            query = query.neq("id", except_observation_id)
        query.execute()

    def upsert_observation(
        self,
        hike_id: str | None,
        photo_id: str,
        candidate: SpeciesCandidate,
        *,
        owner_subject: str | None = None,
        owner_email: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "hike_id": hike_id,
            "owner_subject": owner_subject,
            "owner_email": owner_email,
            "photo_id": photo_id,
            "taxon_id": candidate.taxon_id,
            "common_name": candidate.common_name,
            "scientific_name": candidate.scientific_name,
            "confidence": round(candidate.confidence, 4),
            "status": "pending",
            "is_primary": True,
            "source": "inaturalist_cv",
            "raw_response_json": candidate.raw_payload,
        }
        try:
            existing = (
                self.client.table("species_observations")
                .select("id")
                .eq("photo_id", photo_id)
                .eq("is_primary", True)
                .limit(1)
                .execute()
            ).data or []
            if existing:
                response = self.client.table("species_observations").update(payload).eq("id", existing[0]["id"]).execute()
                return response.data[0]
            self._clear_primary_for_photo(photo_id)
            response = self.client.table("species_observations").insert(payload).execute()
            return response.data[0]
        except Exception:
            legacy_payload = {key: value for key, value in payload.items() if key != "is_primary"}
            response = self.client.table("species_observations").upsert(legacy_payload, on_conflict="photo_id").execute()
            return response.data[0]

    def create_manual_observation(
        self,
        *,
        hike_id: str | None,
        photo_id: str,
        taxon_id: int | None,
        common_name: str | None,
        scientific_name: str | None,
        source: str,
        raw_payload: dict[str, Any],
        is_primary: bool,
        status: str,
        owner_subject: str | None = None,
        owner_email: str | None = None,
    ) -> dict[str, Any]:
        if is_primary:
            self._clear_primary_for_photo(photo_id)
        payload = {
            "hike_id": hike_id,
            "owner_subject": owner_subject,
            "owner_email": owner_email,
            "photo_id": photo_id,
            "taxon_id": taxon_id,
            "common_name": common_name,
            "scientific_name": scientific_name,
            "confidence": None,
            "status": status,
            "is_primary": is_primary,
            "source": source,
            "raw_response_json": raw_payload,
        }
        try:
            response = self.client.table("species_observations").insert(payload).execute()
            return response.data[0]
        except Exception as exc:
            raise RuntimeError("The database needs the multi-observation migration before manual secondary species can be added.") from exc

    def apply_candidate_to_observation(
        self,
        observation_id: str,
        *,
        photo_id: str,
        candidate: SpeciesCandidate,
        status: str | None,
        is_primary: bool,
    ) -> dict[str, Any]:
        if is_primary:
            self._clear_primary_for_photo(photo_id, except_observation_id=observation_id)
        payload = {
            "taxon_id": candidate.taxon_id,
            "common_name": candidate.common_name,
            "scientific_name": candidate.scientific_name,
            "confidence": round(candidate.confidence, 4),
            "source": "inaturalist_cv",
            "raw_response_json": candidate.raw_payload,
            "is_primary": is_primary,
        }
        if status is not None:
            payload["status"] = status
        response = self.client.table("species_observations").update(payload).eq("id", observation_id).execute()
        return response.data[0]

    def update_observation_status(self, observation_id: str, status: str) -> dict[str, Any]:
        response = self.client.table("species_observations").update({"status": status}).eq("id", observation_id).execute()
        return response.data[0]

    def update_observation_details(
        self,
        observation_id: str,
        *,
        common_name: str,
        scientific_name: str,
        photo_id: str | None = None,
        is_primary: bool | None = None,
        status: str | None = None,
        source: str | None = None,
        taxon_id: int | None = None,
        clear_confidence: bool = False,
    ) -> dict[str, Any]:
        if is_primary and photo_id:
            try:
                self._clear_primary_for_photo(photo_id, except_observation_id=observation_id)
            except Exception:
                pass
        payload = {
            "common_name": common_name.strip() or None,
            "scientific_name": scientific_name.strip() or None,
        }
        if is_primary is not None:
            payload["is_primary"] = is_primary
        if status is not None:
            payload["status"] = status
        if source is not None:
            payload["source"] = source
        if clear_confidence:
            payload["confidence"] = None
        if taxon_id is not None or (taxon_id is None and source in {"manual_override", "community_id_request"}):
            payload["taxon_id"] = taxon_id
        try:
            response = self.client.table("species_observations").update(payload).eq("id", observation_id).execute()
        except Exception:
            legacy_payload = {key: value for key, value in payload.items() if key != "is_primary"}
            response = self.client.table("species_observations").update(legacy_payload).eq("id", observation_id).execute()
        return response.data[0]

    def update_observation_raw_payload(self, observation_id: str, raw_payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.table("species_observations").update({"raw_response_json": raw_payload}).eq("id", observation_id).execute()
        return response.data[0]

    def update_observation_inat_posting(
        self,
        observation_id: str,
        *,
        inat_observation_id: int,
        inat_observation_url: str,
        inat_posted_at: str,
        inat_photo_attached: bool,
    ) -> dict[str, Any]:
        payload = {
            "inat_observation_id": int(inat_observation_id),
            "inat_observation_url": inat_observation_url,
            "inat_posted_at": inat_posted_at,
            "inat_photo_attached": bool(inat_photo_attached),
        }
        response = self.client.table("species_observations").update(payload).eq("id", observation_id).execute()
        return response.data[0]

    def apply_observation_inat_sync(
        self,
        observation_id: str,
        *,
        inat_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        existing_response = (
            self.client.table("species_observations")
            .select("*")
            .eq("id", observation_id)
            .limit(1)
            .execute()
        )
        existing_records = existing_response.data or []
        if not existing_records:
            raise RuntimeError("HikeJournal could not find the observation to sync.")
        existing = existing_records[0]
        raw_payload = existing.get("raw_response_json") if isinstance(existing.get("raw_response_json"), dict) else {}
        raw_payload = dict(raw_payload or {})
        history = raw_payload.get("inat_sync_history")
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "synced_at": datetime.now(UTC).isoformat(),
                "inat_observation_id": inat_snapshot.get("observation_id") or existing.get("inat_observation_id"),
                "previous": {
                    "taxon_id": existing.get("taxon_id"),
                    "common_name": existing.get("common_name"),
                    "scientific_name": existing.get("scientific_name"),
                    "source": existing.get("source"),
                },
                "accepted": {
                    "taxon_id": inat_snapshot.get("taxon_id"),
                    "common_name": inat_snapshot.get("common_name"),
                    "scientific_name": inat_snapshot.get("scientific_name"),
                    "quality_grade": inat_snapshot.get("quality_grade"),
                    "community_taxon_id": inat_snapshot.get("community_taxon_id"),
                    "observation_updated_at": inat_snapshot.get("observation_updated_at"),
                },
            }
        )
        raw_payload["inat_sync_history"] = history[-25:]
        raw_payload["inat_last_sync"] = {
            "synced_at": datetime.now(UTC).isoformat(),
            "snapshot": {
                "taxon_id": inat_snapshot.get("taxon_id"),
                "common_name": inat_snapshot.get("common_name"),
                "scientific_name": inat_snapshot.get("scientific_name"),
                "quality_grade": inat_snapshot.get("quality_grade"),
                "community_taxon_id": inat_snapshot.get("community_taxon_id"),
                "observation_updated_at": inat_snapshot.get("observation_updated_at"),
            },
        }
        payload = {
            "taxon_id": inat_snapshot.get("taxon_id"),
            "common_name": str(inat_snapshot.get("common_name") or "").strip() or None,
            "scientific_name": str(inat_snapshot.get("scientific_name") or "").strip() or None,
            "confidence": None,
            "source": "inaturalist_sync",
            "raw_response_json": raw_payload,
        }
        response = self.client.table("species_observations").update(payload).eq("id", observation_id).execute()
        return response.data[0]
