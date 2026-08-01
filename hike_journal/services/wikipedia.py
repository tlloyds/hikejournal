from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import requests


WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKIPEDIA_USER_AGENT = "HikeJournal/1.0 (personal field journal; contact: addlloyd@gmail.com)"
MAX_SUMMARY_CHARACTERS = 480


class WikipediaRequestError(RuntimeError):
    """Raised when Wikipedia cannot provide a usable article summary."""


def _plain_text(value: Any) -> str:
    without_tags = re.sub(r"<[^>]+>", "", str(value or ""))
    return re.sub(r"\s+", " ", without_tags).strip()


def _concise_summary(value: Any) -> str:
    """Keep the field-guide blurb readable while retaining complete sentences."""
    text = _plain_text(value)
    if len(text) <= MAX_SUMMARY_CHARACTERS:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected: list[str] = []
    length = 0
    for sentence in sentences:
        if not sentence:
            continue
        proposed = length + len(sentence) + (1 if selected else 0)
        if selected and proposed > MAX_SUMMARY_CHARACTERS:
            break
        selected.append(sentence)
        length = proposed
    if selected:
        return " ".join(selected)
    return text[:MAX_SUMMARY_CHARACTERS].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def fetch_wikipedia_summary(*, scientific_name: str | None, common_name: str | None) -> dict[str, str] | None:
    """Find a concise Wikipedia summary, preferring the scientific-name article.

    A redirect from a scientific name to its common-name article is intentional and
    keeps the result tied to the taxon iNaturalist already resolved for us.
    """
    names = [str(scientific_name or "").strip(), str(common_name or "").strip()]
    tried: set[str] = set()
    for name in names:
        key = name.casefold()
        if not name or key in tried:
            continue
        tried.add(key)
        try:
            response = requests.get(
                f"{WIKIPEDIA_SUMMARY_URL}/{quote(name, safe='')}",
                headers={"User-Agent": WIKIPEDIA_USER_AGENT},
                timeout=6,
            )
        except requests.RequestException as exc:
            raise WikipediaRequestError("Wikipedia lookup failed.") from exc
        if response.status_code == 404:
            continue
        if response.status_code >= 400:
            raise WikipediaRequestError(f"Wikipedia lookup returned {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise WikipediaRequestError("Wikipedia returned an invalid response.") from exc
        if payload.get("type") == "disambiguation":
            continue
        summary = _concise_summary(payload.get("extract"))
        page_url = str(((payload.get("content_urls") or {}).get("desktop") or {}).get("page") or "").strip()
        if summary and page_url:
            return {"wikipedia_summary": summary, "wikipedia_url": page_url}
    return None


def fill_missing_wikipedia_summary(enrichment: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Add a Wikipedia fallback once, without replacing iNaturalist-provided copy."""
    updated = dict(enrichment)
    if _plain_text(updated.get("wikipedia_summary")):
        return updated, False
    if updated.get("wikipedia_lookup_attempted"):
        return updated, False
    try:
        wikipedia = fetch_wikipedia_summary(
            scientific_name=updated.get("scientific_name"),
            common_name=(updated.get("preferred_common_name") or updated.get("english_common_name")),
        )
    except WikipediaRequestError:
        return updated, False
    updated["wikipedia_lookup_attempted"] = True
    if not wikipedia:
        return updated, True
    updated.update(wikipedia)
    updated["wikipedia_summary_source"] = "wikipedia"
    return updated, True
