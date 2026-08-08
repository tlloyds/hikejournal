from __future__ import annotations

import os
from typing import Any, Iterable


MOBILE_CONTRACT_VERSION = "1"

BASE_MOBILE_CAPABILITIES = (
    "offline_sync",
    "grouped_inat_publish",
    "map_packs",
    "live_inat_cv",
    "grouped_species_review",
    "mobile_inat_oauth",
    "species_discovery",
    "everyday_sightings",
    "hike_covers",
    "hike_deletion",
    "reversible_species_review",
)


def build_mobile_config(
    *,
    web_url: str,
    api_version: str,
    additional_capabilities: Iterable[str] = (),
) -> dict[str, Any]:
    """Build the additive v1 handshake shared by old and new Android clients."""

    capabilities = list(
        dict.fromkeys((*BASE_MOBILE_CAPABILITIES, *additional_capabilities))
    )
    minimum_android_version = os.getenv("MOBILE_MIN_ANDROID_VERSION", "").strip() or None
    recommended_android_version = (
        os.getenv("MOBILE_RECOMMENDED_ANDROID_VERSION", "").strip() or api_version
    )
    return {
        # Keep the original keys and shapes stable for already installed APKs.
        "web_url": web_url.rstrip("/"),
        "api_version": api_version,
        "capabilities": capabilities,
        # New clients can use these fields without guessing from release names.
        "contract_version": MOBILE_CONTRACT_VERSION,
        "compatibility": {
            "minimum_android_version": minimum_android_version,
            "recommended_android_version": recommended_android_version,
        },
    }
