from hike_journal.services.wikipedia import (
    enrich_missing_wikipedia_summaries,
    fetch_wikipedia_summary,
    fill_missing_wikipedia_summary,
)


def test_fallback_adds_a_concise_wikipedia_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        "hike_journal.services.wikipedia.fetch_wikipedia_summary",
        lambda **_kwargs: {
            "wikipedia_summary": "The wild turkey is a large North American bird.",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Wild_turkey",
        },
    )

    updated, changed = fill_missing_wikipedia_summary(
        {"scientific_name": "Meleagris gallopavo", "preferred_common_name": "Wild turkey"}
    )

    assert changed
    assert updated["wikipedia_summary"] == "The wild turkey is a large North American bird."
    assert updated["wikipedia_summary_source"] == "wikipedia"
    assert updated["wikipedia_lookup_attempted"] is True


def test_fallback_preserves_iNaturalist_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        "hike_journal.services.wikipedia.fetch_wikipedia_summary",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not fetch")),
    )

    updated, changed = fill_missing_wikipedia_summary(
        {"wikipedia_summary": "Already provided by iNaturalist."}
    )

    assert not changed
    assert updated["wikipedia_summary"] == "Already provided by iNaturalist."


def test_scientific_name_lookup_never_falls_back_to_an_ambiguous_common_name(monkeypatch) -> None:
    requested_urls: list[str] = []

    class MissingResponse:
        status_code = 404

    def fake_get(url, **_kwargs):
        requested_urls.append(url)
        return MissingResponse()

    monkeypatch.setattr("hike_journal.services.wikipedia.requests.get", fake_get)

    result = fetch_wikipedia_summary(scientific_name="Rhexia nashii", common_name="Maid Marian")

    assert result is None
    assert len(requested_urls) == 1
    assert requested_urls[0].endswith("Rhexia%20nashii")


def test_briefing_enrichment_fills_only_missing_wikipedia_copy(monkeypatch) -> None:
    calls = []

    def fake_fetch(**kwargs):
        calls.append(kwargs["scientific_name"])
        return {
            "wikipedia_summary": f"A field-guide entry for {kwargs['scientific_name']}.",
            "wikipedia_url": "https://example.test/wiki",
        }

    monkeypatch.setattr("hike_journal.services.wikipedia.fetch_wikipedia_summary", fake_fetch)

    enriched = enrich_missing_wikipedia_summaries(
        [
            {"scientific_name": "Taxon one", "common_name": "One", "wikipedia_summary": ""},
            {"scientific_name": "Taxon two", "common_name": "Two", "wikipedia_summary": "Existing."},
        ]
    )

    assert enriched[0]["wikipedia_summary"] == "A field-guide entry for Taxon one."
    assert enriched[1]["wikipedia_summary"] == "Existing."
    assert calls == ["Taxon one"]
