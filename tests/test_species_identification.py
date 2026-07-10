from hike_journal.services.species_identification import select_shared_candidate


def candidate(taxon_id: int, *, support: int, top1: int) -> dict:
    return {
        "taxon_id": taxon_id,
        "support_count": support,
        "top1_count": top1,
    }


def test_selects_candidate_supported_by_every_photo_and_top_choice_majority() -> None:
    selected = select_shared_candidate(
        [candidate(10, support=3, top1=2), candidate(20, support=3, top1=1)],
        photo_count=3,
    )

    assert selected is not None
    assert selected["taxon_id"] == 10


def test_rejects_candidate_missing_from_one_photos_results() -> None:
    selected = select_shared_candidate(
        [candidate(10, support=2, top1=2)],
        photo_count=3,
    )

    assert selected is None


def test_two_photo_group_requires_both_top_choices_to_agree() -> None:
    selected = select_shared_candidate(
        [candidate(10, support=2, top1=1), candidate(20, support=2, top1=1)],
        photo_count=2,
    )

    assert selected is None
