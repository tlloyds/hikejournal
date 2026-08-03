from hike_journal.services.wikipedia import fetch_wikipedia_summary, fill_missing_wikipedia_summary


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
