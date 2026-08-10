from __future__ import annotations

from datetime import UTC, date, datetime
import re
from typing import Any

from supabase import Client

from hike_journal.domain.discovery import candidate_taxon_snapshot
from hike_journal.models import HikeDraft, SpeciesCandidate
from hike_journal.domain.map_data import (
    MAX_VIEWPORT_FEATURES,
    MIN_UNCLUSTERED_MAP_ZOOM,
    MapViewport,
    empty_feature_collection,
    normalize_rpc_payload,
    route_geojson_to_2d_multiline,
)


LIGHTWEIGHT_OBSERVATION_COLUMNS = (
    "id,photo_id,hike_id,owner_subject,owner_email,taxon_id,species_taxon_id,rank,iconic_taxon_name,"
    "common_name,scientific_name,"
    "confidence,status,is_primary,identified_at,source,observed_on,occurrence_precision,"
    "identification_confidence,identification_provenance,inat_observation_id,inat_observation_url,"
    "inat_posted_at,inat_photo_attached,"
    "species_log_main_photo:raw_response_json->species_log_main_photo,"
    "wikipedia_url:raw_response_json->taxon_enrichment->>wikipedia_url,"
    "wikipedia_summary:raw_response_json->taxon_enrichment->>wikipedia_summary"
)
LEGACY_LIGHTWEIGHT_OBSERVATION_COLUMNS = LIGHTWEIGHT_OBSERVATION_COLUMNS.replace(
    "species_taxon_id,rank,iconic_taxon_name,",
    "",
).replace(
    "observed_on,occurrence_precision,identification_confidence,identification_provenance,",
    "",
)


def _slugify_location_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower().strip())
    return re.sub(r"-+", "-", slug).strip("-") or "location"


def _identification_confidence(value: float | None, *, confirmed: bool = False) -> str:
    if confirmed and value is not None and value >= 0.9:
        return "confident"
    if value is not None and value >= 0.65:
        return "likely"
    return "tentative"


def _identification_provenance(source: str | None) -> str:
    normalized = str(source or "").strip().lower()
    if normalized in {"inaturalist_cv", "inat_cv", "inaturalist_computer_vision"}:
        return "inat_computer_vision"
    if normalized in {"manual", "manual_override", "known_species", "user"}:
        return "user"
    if normalized in {"community_id_request", "inat_community"}:
        return "inat_community"
    return "imported_record"


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

    def get_hike_route_import(
        self,
        hike_id: str,
        *,
        raise_errors: bool = False,
    ) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("hike_route_imports")
                .select("*")
                .eq("hike_id", hike_id)
                .limit(1)
                .execute()
            )
        except Exception:
            if raise_errors:
                raise
            return None
        records = response.data or []
        return records[0] if records else None

    def create_hike(self, draft: HikeDraft, *, hike_id: str | None = None) -> dict[str, Any]:
        payload = {
            "title": draft.title.strip(),
            "hike_date": draft.hike_date.isoformat(),
            "distance_miles": draft.distance_miles,
            "location_name": draft.location_name.strip() or None,
            "notes": draft.notes.strip() or None,
            "owner_subject": draft.owner_subject,
            "owner_email": draft.owner_email,
        }
        if hike_id:
            payload["id"] = hike_id
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

    def get_hike_location(self, location_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("hike_locations")
                .select("*")
                .eq("id", location_id)
                .limit(1)
                .execute()
            )
        except Exception:
            return None
        rows = response.data or []
        return rows[0] if rows else None

    def get_species_discovery_snapshot(self, cache_key: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("species_discovery_snapshots")
                .select("*")
                .eq("cache_key", cache_key)
                .limit(1)
                .execute()
            )
        except Exception:
            return None
        rows = response.data or []
        return rows[0] if rows else None

    def upsert_species_discovery_snapshot(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("species_discovery_snapshots")
                .upsert(payload, on_conflict="cache_key")
                .execute()
            )
        except Exception:
            return None
        rows = response.data or []
        return rows[0] if rows else None

    def create_species_quest(
        self,
        payload: dict[str, Any],
        taxa: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            response = self.client.table("species_quests").insert(payload).execute()
        except Exception as exc:
            raise RuntimeError(
                "Field Quests need sql/species_discovery_migration.sql before they can be saved."
            ) from exc
        quest = response.data[0]
        quest_id = str(quest["id"])
        target_rows = []
        for item in taxa[:100]:
            photo = item.get("reference_photo") if isinstance(item.get("reference_photo"), dict) else {}
            target_rows.append(
                {
                    "quest_id": quest_id,
                    "taxon_id": int(item["taxon_id"]),
                    "common_name": str(item.get("common_name") or "Unknown species"),
                    "scientific_name": str(item.get("scientific_name") or ""),
                    "rank": str(item.get("rank") or "species"),
                    "iconic_taxon_name": str(item.get("iconic_taxon_name") or "Other"),
                    "observation_count": int(item.get("observation_count") or 0),
                    "nearby_rank": int(item.get("nearby_rank") or len(target_rows) + 1),
                    "frequency_band": str(item.get("frequency_band") or "Less often reported"),
                    "reference_photo_url": str((photo or {}).get("url") or "") or None,
                    "reference_photo_attribution": str((photo or {}).get("attribution") or "") or None,
                    "reference_photo_license": str((photo or {}).get("license_code") or "") or None,
                    "wikipedia_url": str(item.get("wikipedia_url") or "") or None,
                    "wikipedia_summary": str(item.get("wikipedia_summary") or "") or None,
                    "focus_order": item.get("focus_order"),
                }
            )
        try:
            if target_rows:
                self.client.table("species_quest_taxa").insert(target_rows).execute()
        except Exception as exc:
            # Earlier production installs predate the optional Wikipedia
            # columns.  Keep quests usable until that migration is applied.
            if "wikipedia_" in str(exc).lower():
                legacy_target_rows = [
                    {
                        key: value
                        for key, value in target_row.items()
                        if key not in {"wikipedia_url", "wikipedia_summary"}
                    }
                    for target_row in target_rows
                ]
                try:
                    self.client.table("species_quest_taxa").insert(legacy_target_rows).execute()
                    return self.get_species_quest(quest_id) or {**quest, "taxa": []}
                except Exception as legacy_exc:
                    exc = legacy_exc
            # A partially saved quest is not useful, but cleanup must not hide
            # the actionable migration error from the mobile API.
            try:
                self.client.table("species_quests").delete().eq("id", quest_id).execute()
            except Exception:
                pass
            raise RuntimeError(
                "Field Quest targets could not be saved. Apply sql/species_discovery_migration.sql and try again."
            ) from exc
        return self.get_species_quest(quest_id) or {**quest, "taxa": []}

    def list_species_quests(
        self,
        *,
        owner_subject: str | None,
        owner_email: str | None,
    ) -> list[dict[str, Any]]:
        try:
            query = self.client.table("species_quests").select("*").order("created_at", desc=True)
            if owner_subject:
                query = query.eq("owner_subject", owner_subject)
            elif owner_email:
                query = query.eq("owner_email", owner_email.strip().lower())
            rows = query.execute().data or []
        except Exception:
            return []
        return [self._attach_species_quest_taxa(row) for row in rows]

    def get_species_quest(self, quest_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("species_quests")
                .select("*")
                .eq("id", quest_id)
                .limit(1)
                .execute()
            )
        except Exception:
            return None
        rows = response.data or []
        return self._attach_species_quest_taxa(rows[0]) if rows else None

    def _attach_species_quest_taxa(self, quest: dict[str, Any]) -> dict[str, Any]:
        try:
            response = (
                self.client.table("species_quest_taxa")
                .select("*")
                .eq("quest_id", str(quest["id"]))
                .order("nearby_rank")
                .execute()
            )
            target_rows = response.data or []
        except Exception:
            target_rows = []
        taxa = []
        for item in target_rows:
            taxa.append(
                {
                    "taxon_id": item.get("taxon_id"),
                    "common_name": item.get("common_name"),
                    "scientific_name": item.get("scientific_name"),
                    "rank": item.get("rank"),
                    "iconic_taxon_name": item.get("iconic_taxon_name"),
                    "observation_count": item.get("observation_count"),
                    "nearby_rank": item.get("nearby_rank"),
                    "frequency_band": item.get("frequency_band"),
                    "focus_order": item.get("focus_order"),
                    "reference_photo": (
                        {
                            "url": item.get("reference_photo_url"),
                            "attribution": item.get("reference_photo_attribution") or "",
                            "license_code": item.get("reference_photo_license") or "",
                        }
                        if item.get("reference_photo_url")
                        else None
                    ),
                    "wikipedia_url": item.get("wikipedia_url") or "",
                    "wikipedia_summary": item.get("wikipedia_summary") or "",
                }
            )
        return {**quest, "taxa": taxa}

    def update_species_quest(
        self,
        quest_id: str,
        *,
        title: str | None = None,
        status: str | None = None,
        linked_hike_id: str | None = None,
        set_linked_hike: bool = False,
        focus_taxon_ids: list[int] | None = None,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title.strip()
        if status is not None:
            payload["status"] = status
        if set_linked_hike:
            payload["linked_hike_id"] = linked_hike_id
        if payload:
            payload["updated_at"] = datetime.now(UTC).isoformat()
            self.client.table("species_quests").update(payload).eq("id", quest_id).execute()
        if focus_taxon_ids is not None:
            self.client.table("species_quest_taxa").update({"focus_order": None}).eq(
                "quest_id",
                quest_id,
            ).execute()
            for index, taxon_id in enumerate(focus_taxon_ids[:10]):
                (
                    self.client.table("species_quest_taxa")
                    .update({"focus_order": index + 1})
                    .eq("quest_id", quest_id)
                    .eq("taxon_id", int(taxon_id))
                    .execute()
                )
        return self.get_species_quest(quest_id)

    def delete_species_quest(self, quest_id: str) -> None:
        self.client.table("species_quests").delete().eq("id", quest_id).execute()

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
        spatial_geometry = route_geojson_to_2d_multiline(normalized_payload.get("track_geojson"))
        response = (
            self.client.table("hike_route_imports")
            .upsert(normalized_payload, on_conflict="hike_id")
            .execute()
        )
        saved = response.data[0]
        if spatial_geometry:
            try:
                # Keep this separate from the GeoJSON upsert. Older trigger
                # versions can reject 3D TCX coordinates and overwrite
                # track_geom; a geometry-only update is not handled by that
                # trigger and makes route imports self-healing.
                spatial_response = (
                    self.client.table("hike_route_imports")
                    .update({"track_geom": spatial_geometry})
                    .eq("hike_id", hike_id)
                    .execute()
                )
                if spatial_response.data:
                    saved = spatial_response.data[0]
            except Exception:
                # Projects that have not run the scalable map migration still
                # retain the route import and can be migrated later.
                pass
        return saved

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

    def list_photos_page(self, hike_id: str, *, offset: int, limit: int) -> list[dict[str, Any]]:
        """Fetch only one ordered page for the native hike detail API."""
        response = (
            self.client.table("photos")
            .select("*")
            .eq("hike_id", hike_id)
            .order("taken_at")
            .order("created_at")
            .range(offset, offset + limit - 1)
            .execute()
        )
        return response.data or []

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

    def get_map_summary(self, *, visible_hike_ids: list[str], hike_id: str | None = None) -> dict[str, Any]:
        params = {"p_hike_ids": visible_hike_ids, "p_hike_id": hike_id}
        try:
            response = self.client.rpc("map_summary", params).execute()
            payload = response.data
            if isinstance(payload, list) and len(payload) == 1:
                payload = payload[0]
            if isinstance(payload, dict):
                payload["spatial_rpc_ready"] = True
                return payload
        except Exception:
            pass

        # Compatibility path while the spatial migration is being applied.
        photos = [
            photo for photo in self.list_map_photos(hike_id)
            if str(photo.get("hike_id") or "") in set(visible_hike_ids)
        ]
        observations = self.list_lightweight_observations(status="confirmed", hike_id=hike_id)
        photo_ids = {str(photo.get("id")) for photo in photos}
        species = sorted({
            str(observation.get("common_name") or observation.get("scientific_name") or "Confirmed species")
            for observation in observations
            if str(observation.get("photo_id") or "") in photo_ids
        })
        bounds = None
        if photos:
            lngs = [float(photo["lng"]) for photo in photos]
            lats = [float(photo["lat"]) for photo in photos]
            bounds = [min(lngs), min(lats), max(lngs), max(lats)]
        return {
            "photo_count": len(photos),
            "species_count": len(species),
            "species": species,
            "bounds": bounds,
            "spatial_rpc_ready": False,
        }

    def get_map_viewport(
        self,
        *,
        visible_hike_ids: list[str],
        hike_id: str | None,
        viewport: MapViewport,
        layer_mode: str,
        species_filter: str,
        range_start: int,
        range_end: int,
    ) -> dict[str, Any]:
        params = {
            "p_hike_ids": visible_hike_ids,
            "p_hike_id": hike_id,
            "p_west": viewport.west,
            "p_south": viewport.south,
            "p_east": viewport.east,
            "p_north": viewport.north,
            # Outing maps favor individually clickable photographs. The master
            # map keeps the real zoom so its larger collection can cluster.
            "p_zoom": max(viewport.zoom, MIN_UNCLUSTERED_MAP_ZOOM) if hike_id else viewport.zoom,
            "p_layer_mode": layer_mode,
            "p_species_filter": species_filter,
            "p_range_start": range_start,
            "p_range_end": range_end,
            "p_max_features": MAX_VIEWPORT_FEATURES,
        }
        try:
            response = self.client.rpc("map_viewport", params).execute()
            return normalize_rpc_payload(response.data, include_meta=True)
        except Exception:
            return self._fallback_map_viewport(
                visible_hike_ids=visible_hike_ids,
                hike_id=hike_id,
                viewport=viewport,
                layer_mode=layer_mode,
                species_filter=species_filter,
            )

    def _fallback_map_viewport(
        self,
        *,
        visible_hike_ids: list[str],
        hike_id: str | None,
        viewport: MapViewport,
        layer_mode: str,
        species_filter: str,
    ) -> dict[str, Any]:
        query = (
            self.client.table("photos")
            .select("id,hike_id,lat,lng,taken_at,created_at")
            .in_("hike_id", [hike_id] if hike_id else visible_hike_ids)
            .gte("lat", viewport.south)
            .lte("lat", viewport.north)
            .gte("lng", viewport.west)
            .lte("lng", viewport.east)
            .order("taken_at")
            .limit(min(MAX_VIEWPORT_FEATURES, 500))
        )
        photos = query.execute().data or []
        photo_ids = [str(photo["id"]) for photo in photos]
        observations: list[dict[str, Any]] = []
        for chunk_ids in self._chunks(photo_ids, 200):
            try:
                response = (
                    self.client.table("species_observations")
                    .select(LIGHTWEIGHT_OBSERVATION_COLUMNS)
                    .in_("photo_id", chunk_ids)
                    .eq("status", "confirmed")
                    .execute()
                )
                observations.extend(response.data or [])
            except Exception:
                # Photo markers remain useful while the migration is pending.
                break
        observations_by_photo: dict[str, list[dict[str, Any]]] = {}
        for observation in observations:
            observations_by_photo.setdefault(str(observation.get("photo_id")), []).append(observation)
        features: list[dict[str, Any]] = []
        for photo in photos:
            photo_observations = observations_by_photo.get(str(photo["id"]), [])
            primary = next((item for item in photo_observations if item.get("is_primary")), None)
            if layer_mode in {"Both", "Photos"}:
                features.append(self._map_point_feature(photo, layer="photo", title=(primary or {}).get("common_name") or "Trail photo"))
            if layer_mode in {"Both", "Species"}:
                for observation in photo_observations:
                    name = observation.get("common_name") or observation.get("scientific_name") or "Confirmed species"
                    if species_filter not in {"", "All confirmed species", name}:
                        continue
                    features.append(self._map_point_feature(photo, layer="species", title=name))
        return {
            "type": "FeatureCollection",
            "features": features[:MAX_VIEWPORT_FEATURES],
            "meta": {"matched": len(features), "clustered": False, "fallback": True},
        }

    @staticmethod
    def _map_point_feature(photo: dict[str, Any], *, layer: str, title: str) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [photo["lng"], photo["lat"]]},
            "properties": {
                "kind": "point",
                "layer": layer,
                "photo_id": photo["id"],
                "hike_id": photo.get("hike_id"),
                "title": title,
            },
        }

    def get_map_routes_viewport(
        self,
        *,
        visible_hike_ids: list[str],
        hike_id: str | None,
        viewport: MapViewport,
    ) -> dict[str, Any]:
        params = {
            "p_hike_ids": visible_hike_ids,
            "p_hike_id": hike_id,
            "p_west": viewport.west,
            "p_south": viewport.south,
            "p_east": viewport.east,
            "p_north": viewport.north,
            "p_zoom": viewport.zoom,
        }
        try:
            response = self.client.rpc("map_routes_viewport", params).execute()
            return normalize_rpc_payload(response.data)
        except Exception:
            return empty_feature_collection(fallback=True)

    def get_map_route_index_status(self, *, visible_hike_ids: list[str], hike_id: str | None) -> tuple[int, int]:
        scoped_ids = [hike_id] if hike_id else visible_hike_ids
        if not scoped_ids:
            return 0, 0
        try:
            total_response = (
                self.client.table("hike_route_imports")
                .select("id", count="exact")
                .in_("hike_id", scoped_ids)
                .limit(0)
                .execute()
            )
            indexed_response = (
                self.client.table("hike_route_imports")
                .select("id", count="exact")
                .in_("hike_id", scoped_ids)
                .not_.is_("track_geom", "null")
                .limit(0)
                .execute()
            )
            return int(total_response.count or 0), int(indexed_response.count or 0)
        except Exception:
            return 0, 0

    def list_unindexed_map_routes(self, *, visible_hike_ids: list[str], hike_id: str | None) -> list[dict[str, Any]]:
        scoped_ids = [hike_id] if hike_id else visible_hike_ids
        if not scoped_ids:
            return []
        try:
            response = (
                self.client.table("hike_route_imports")
                .select("hike_id,track_point_count,track_geojson")
                .in_("hike_id", scoped_ids)
                .is_("track_geom", "null")
                .execute()
            )
            return response.data or []
        except Exception:
            return []

    def get_map_photo_detail(self, *, photo_id: str, visible_hike_ids: list[str]) -> dict[str, Any] | None:
        try:
            response = self.client.rpc(
                "map_photo_detail",
                {"p_photo_id": photo_id, "p_hike_ids": visible_hike_ids},
            ).execute()
            payload = response.data
            if isinstance(payload, list) and len(payload) == 1:
                payload = payload[0]
            if isinstance(payload, dict) and payload.get("photo_id"):
                return payload
        except Exception:
            pass
        records = self.list_photo_records_for_ids([photo_id])
        if not records or str(records[0].get("hike_id") or "") not in set(visible_hike_ids):
            return None
        photo = dict(records[0])
        photo["photo_id"] = photo["id"]
        photo["image_url"] = photo.get("public_url")
        photo["observations"] = self.list_lightweight_observations(photo_ids=[photo_id], status="confirmed")
        return photo

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
                .select("id,hike_id,owner_subject,owner_email,caption,public_url,storage_path,lat,lng,taken_at,created_at,width,height,exif_json")
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

        try:
            if normalized_ids is not None:
                rows: list[dict[str, Any]] = []
                for chunk_ids in self._chunks(normalized_ids):
                    rows.extend(self._select_all_rows(lambda chunk_ids=chunk_ids: query_factory(chunk_ids)))
                return rows
            return self._select_all_rows(lambda: query_factory())
        except Exception:
            def legacy_query_factory(chunk_ids: list[str] | None = None):
                query = self.client.table("species_observations").select(
                    LEGACY_LIGHTWEIGHT_OBSERVATION_COLUMNS
                )
                if hike_id:
                    query = query.eq("hike_id", hike_id)
                if status:
                    query = query.eq("status", status)
                if chunk_ids is not None:
                    query = query.in_("photo_id", chunk_ids)
                return query

            if normalized_ids is not None:
                legacy_rows: list[dict[str, Any]] = []
                for chunk_ids in self._chunks(normalized_ids):
                    legacy_rows.extend(
                        self._select_all_rows(
                            lambda chunk_ids=chunk_ids: legacy_query_factory(chunk_ids)
                        )
                    )
                return legacy_rows
            return self._select_all_rows(lambda: legacy_query_factory())

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

    def list_identification_events(self, observation_ids: list[str]) -> list[dict[str, Any]]:
        normalized_ids = [str(value) for value in observation_ids if str(value).strip()]
        if not normalized_ids:
            return []
        rows: list[dict[str, Any]] = []
        for chunk_ids in self._chunks(normalized_ids, size=200):
            response = (
                self.client.table("identification_events")
                .select("*")
                .in_("observation_id", chunk_ids)
                .order("created_at", desc=True)
                .execute()
            )
            rows.extend(response.data or [])
        return rows

    def list_observation_annotations(self, observation_ids: list[str]) -> list[dict[str, Any]]:
        normalized_ids = [str(value) for value in observation_ids if str(value).strip()]
        if not normalized_ids:
            return []
        rows: list[dict[str, Any]] = []
        for chunk_ids in self._chunks(normalized_ids, size=200):
            response = (
                self.client.table("observation_annotations")
                .select("*")
                .in_("observation_id", chunk_ids)
                .order("created_at")
                .execute()
            )
            rows.extend(response.data or [])
        return rows

    def set_observation_natural_history(
        self,
        observation_id: str,
        *,
        confidence: str,
        provenance: str,
        phenophases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            response = self.client.rpc(
                "set_observation_natural_history",
                {
                    "p_observation_id": observation_id,
                    "p_confidence": confidence,
                    "p_provenance": provenance,
                    "p_phenophases": phenophases,
                },
            ).execute()
        except Exception as exc:
            raise RuntimeError(
                "Observation history needs sql/longitudinal_intelligence_migration.sql before it can be edited."
            ) from exc
        rows = response.data or []
        if isinstance(rows, dict):
            return rows
        if not rows:
            raise RuntimeError("The observation could not be updated.")
        return rows[0]

    def list_field_marks(self, hike_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                self.client.table("field_marks")
                .select("*")
                .eq("hike_id", hike_id)
                .order("marked_at")
                .execute()
            )
        except Exception as exc:
            raise RuntimeError(
                "Field Marks need sql/longitudinal_intelligence_migration.sql before they can sync."
            ) from exc
        return response.data or []

    def get_field_mark(self, mark_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("field_marks")
                .select("*")
                .eq("id", mark_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RuntimeError(
                "Field Marks need sql/longitudinal_intelligence_migration.sql before they can sync."
            ) from exc
        rows = response.data or []
        return rows[0] if rows else None

    def upsert_field_mark(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.table("field_marks").upsert(payload, on_conflict="id").execute()
        except Exception as exc:
            raise RuntimeError(
                "Field Marks need sql/longitudinal_intelligence_migration.sql before they can sync."
            ) from exc
        rows = response.data or []
        if not rows:
            raise RuntimeError("The field mark could not be saved.")
        return rows[0]

    def get_hike_weather_snapshot(self, hike_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("hike_weather_snapshots")
                .select("*")
                .eq("hike_id", hike_id)
                .order("enriched_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception:
            return None
        rows = response.data or []
        return rows[0] if rows else None

    def upsert_hike_weather_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.table("hike_weather_snapshots").upsert(
                payload,
                on_conflict="hike_id,provider,algorithm_version",
            ).execute()
        except Exception as exc:
            raise RuntimeError(
                "Weather history needs sql/longitudinal_intelligence_migration.sql before it can be saved."
            ) from exc
        rows = response.data or []
        if not rows:
            raise RuntimeError("The weather summary could not be saved.")
        return rows[0]

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
        taxon_snapshot = candidate_taxon_snapshot(
            taxon_id=candidate.taxon_id,
            scientific_name=candidate.scientific_name,
            raw_payload=candidate.raw_payload,
        )
        payload = {
            "hike_id": hike_id,
            "owner_subject": owner_subject,
            "owner_email": owner_email,
            "photo_id": photo_id,
            "taxon_id": candidate.taxon_id,
            "species_taxon_id": taxon_snapshot["species_taxon_id"],
            "rank": taxon_snapshot["rank"],
            "iconic_taxon_name": taxon_snapshot["iconic_taxon_name"],
            "common_name": candidate.common_name,
            "scientific_name": candidate.scientific_name,
            "confidence": round(candidate.confidence, 4),
            "status": "pending",
            "is_primary": True,
            "source": "inaturalist_cv",
            "identification_confidence": _identification_confidence(candidate.confidence),
            "identification_provenance": "inat_computer_vision",
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
            legacy_payload = {
                key: value
                for key, value in payload.items()
                if key not in {
                    "is_primary", "species_taxon_id", "identification_confidence",
                    "identification_provenance",
                }
            }
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
        taxon_snapshot = candidate_taxon_snapshot(
            taxon_id=taxon_id,
            scientific_name=str(scientific_name or ""),
            raw_payload=raw_payload,
        )
        payload = {
            "hike_id": hike_id,
            "owner_subject": owner_subject,
            "owner_email": owner_email,
            "photo_id": photo_id,
            "taxon_id": taxon_id,
            "species_taxon_id": taxon_snapshot["species_taxon_id"],
            "rank": taxon_snapshot["rank"],
            "iconic_taxon_name": taxon_snapshot["iconic_taxon_name"],
            "common_name": common_name,
            "scientific_name": scientific_name,
            "confidence": None,
            "status": status,
            "is_primary": is_primary,
            "source": source,
            "identification_confidence": "confident" if status == "confirmed" else "tentative",
            "identification_provenance": _identification_provenance(source),
            "raw_response_json": raw_payload,
        }
        try:
            response = self.client.table("species_observations").insert(payload).execute()
            return response.data[0]
        except Exception:
            payload.pop("species_taxon_id", None)
            payload.pop("identification_confidence", None)
            payload.pop("identification_provenance", None)
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
        taxon_snapshot = candidate_taxon_snapshot(
            taxon_id=candidate.taxon_id,
            scientific_name=candidate.scientific_name,
            raw_payload=candidate.raw_payload,
        )
        payload = {
            "taxon_id": candidate.taxon_id,
            "species_taxon_id": taxon_snapshot["species_taxon_id"],
            "rank": taxon_snapshot["rank"],
            "iconic_taxon_name": taxon_snapshot["iconic_taxon_name"],
            "common_name": candidate.common_name,
            "scientific_name": candidate.scientific_name,
            "confidence": round(candidate.confidence, 4),
            "source": "inaturalist_cv",
            "identification_confidence": _identification_confidence(
                candidate.confidence,
                confirmed=status == "confirmed",
            ),
            "identification_provenance": "inat_computer_vision",
            "raw_response_json": candidate.raw_payload,
            "is_primary": is_primary,
        }
        if status is not None:
            payload["status"] = status
        try:
            response = self.client.table("species_observations").update(payload).eq("id", observation_id).execute()
        except Exception:
            payload.pop("species_taxon_id", None)
            payload.pop("identification_confidence", None)
            payload.pop("identification_provenance", None)
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
            payload["identification_provenance"] = _identification_provenance(source)
        if clear_confidence:
            payload["confidence"] = None
        if taxon_id is not None or (taxon_id is None and source in {"manual_override", "community_id_request"}):
            payload["taxon_id"] = taxon_id
        if source in {"manual_override", "community_id_request"}:
            payload["species_taxon_id"] = None
            payload["rank"] = None
            payload["iconic_taxon_name"] = None
        try:
            response = self.client.table("species_observations").update(payload).eq("id", observation_id).execute()
        except Exception:
            legacy_payload = {
                key: value
                for key, value in payload.items()
                if key not in {"is_primary", "identification_provenance"}
            }
            response = self.client.table("species_observations").update(legacy_payload).eq("id", observation_id).execute()
        return response.data[0]

    def update_observation_raw_payload(self, observation_id: str, raw_payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.table("species_observations").update({"raw_response_json": raw_payload}).eq("id", observation_id).execute()
        return response.data[0]

    def update_observation_taxon_resolution(
        self,
        observation_id: str,
        *,
        taxon_id: int | None = None,
        rank: str | None,
        iconic_taxon_name: str | None,
        species_taxon_id: int | None,
    ) -> dict[str, Any] | None:
        payload = {
            "rank": rank,
            "iconic_taxon_name": iconic_taxon_name,
            "species_taxon_id": species_taxon_id,
        }
        if taxon_id is not None:
            payload["taxon_id"] = taxon_id
        try:
            response = (
                self.client.table("species_observations")
                .update(payload)
                .eq("id", observation_id)
                .execute()
            )
        except Exception:
            return None
        rows = response.data or []
        return rows[0] if rows else None

    def update_observation_taxon_resolutions(
        self,
        observation_ids: list[str],
        *,
        taxon_id: int,
        rank: str | None,
        iconic_taxon_name: str | None,
        species_taxon_id: int | None,
    ) -> int:
        normalized_ids = list(dict.fromkeys(str(value) for value in observation_ids if str(value).strip()))
        updated_count = 0
        payload = {
            "taxon_id": int(taxon_id),
            "rank": rank,
            "iconic_taxon_name": iconic_taxon_name,
            "species_taxon_id": species_taxon_id,
        }
        for chunk_ids in self._chunks(normalized_ids, size=200):
            response = (
                self.client.table("species_observations")
                .update(payload)
                .in_("id", chunk_ids)
                .execute()
            )
            updated_count += len(response.data or [])
        return updated_count

    def list_observations_for_taxonomy_reconciliation(
        self,
        *,
        status: str = "confirmed",
    ) -> list[dict[str, Any]]:
        return self._select_all_rows(
            lambda: (
                self.client.table("species_observations")
                .select(
                    "id,taxon_id,species_taxon_id,rank,iconic_taxon_name,"
                    "common_name,scientific_name,status,raw_response_json"
                )
                .eq("status", status)
                .not_.is_("taxon_id", "null")
            ),
            page_size=200,
        )

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
            "species_taxon_id": None,
            "rank": None,
            "iconic_taxon_name": None,
            "common_name": str(inat_snapshot.get("common_name") or "").strip() or None,
            "scientific_name": str(inat_snapshot.get("scientific_name") or "").strip() or None,
            "confidence": None,
            "source": "inaturalist_sync",
            "raw_response_json": raw_payload,
        }
        response = self.client.table("species_observations").update(payload).eq("id", observation_id).execute()
        return response.data[0]
