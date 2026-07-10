from __future__ import annotations

from typing import Any


def select_shared_candidate(
    aggregate_candidates: list[dict[str, Any]],
    *,
    photo_count: int,
) -> dict[str, Any] | None:
    if photo_count < 2:
        return None
    for candidate in aggregate_candidates:
        support_count = int(candidate.get("support_count") or 0)
        top1_count = int(candidate.get("top1_count") or 0)
        if support_count == photo_count and top1_count > photo_count / 2:
            return candidate
    return None
