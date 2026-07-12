import app

from hike_journal.models import SpeciesCandidate


def species_candidate(taxon_id: int, confidence: float) -> SpeciesCandidate:
    return SpeciesCandidate(
        common_name=f"Species {taxon_id}",
        scientific_name=f"Species testus {taxon_id}",
        confidence=confidence,
        taxon_id=taxon_id,
        raw_payload={},
    )


class PairScoringClient:
    def score_species_candidates(self, *, filename: str, **_kwargs):
        if filename == "photo-a.jpg":
            return [species_candidate(10, 0.76), species_candidate(20, 0.40)], {}
        return [species_candidate(20, 0.91), species_candidate(10, 0.30)], {}


def test_two_photo_smart_id_applies_the_stronger_top_choice_to_the_group(monkeypatch) -> None:
    monkeypatch.setattr(app, "_download_public_image", lambda _url: b"image")
    photos = [
        {"id": "photo-a", "public_url": "https://example.test/a.jpg"},
        {"id": "photo-b", "public_url": "https://example.test/b.jpg"},
    ]

    grouped_candidate, processed_photos, individual_candidates, warnings = app._build_grouped_species_candidate(
        PairScoringClient(),
        photos,
        require_consensus=True,
    )

    assert grouped_candidate is not None
    assert grouped_candidate.taxon_id == 20
    assert grouped_candidate.confidence == 0.91
    assert [photo["id"] for photo in processed_photos] == ["photo-a", "photo-b"]
    assert individual_candidates["photo-a"].taxon_id == 10
    assert individual_candidates["photo-b"].taxon_id == 20
    assert warnings == []
