from hike_journal.services.wikipedia import fill_missing_wikipedia_summary


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
