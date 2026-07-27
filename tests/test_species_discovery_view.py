from streamlit.testing.v1 import AppTest

from hike_journal.ui.views import species_log


def test_collected_discovery_row_renders_as_one_html_fragment(monkeypatch) -> None:
    rendered: list[str] = []
    monkeypatch.setattr(species_log.st, "html", rendered.append)

    species_log._render_discovery_species_rows(
        [
            {
                "taxon_id": 1,
                "common_name": "American Alligator",
                "scientific_name": "Alligator mississippiensis",
                "observation_count": 244,
                "nearby_rank": 1,
                "collected": True,
                "collection_photo_url": "https://photos.example/alligator.jpg",
                "reference_photo": {
                    "url": "https://inat.example/alligator.jpg",
                    "attribution": "(c) Example Naturalist",
                },
            }
        ],
        show_focus=False,
    )

    assert len(rendered) == 1
    assert "\n" not in rendered[0]
    assert "is-collected" in rendered[0]
    assert "244 research-grade reports nearby</div>" in rendered[0]
    assert '<div class="field-quest-species-rank">01</div>' in rendered[0]
    assert rendered[0].endswith("</div>")


def test_focus_selection_includes_collected_taxa_and_preserves_order() -> None:
    taxa = [
        {"taxon_id": 1, "collected": True},
        {"taxon_id": 2, "collected": False},
        {"taxon_id": 3, "collected": False},
    ]

    assert species_log._normalize_focus_taxon_ids([1, 3, 999, 1], taxa) == [1, 3]
    assert species_log._toggle_focus_taxon_id([1], 2) == [1, 2]
    assert species_log._toggle_focus_taxon_id([1, 2], 1) == [2]
    assert species_log._toggle_focus_taxon_id([1, 2, 3, 4, 5], 6) == [1, 2, 3, 4, 5]


def test_selected_focus_row_has_direct_selection_state() -> None:
    html = species_log._build_discovery_species_row_html(
        {
            "taxon_id": 1,
            "common_name": "American Alligator",
            "scientific_name": "Alligator mississippiensis",
            "observation_count": 244,
            "nearby_rank": 1,
            "collected": True,
            "focus_order": 1,
        },
        show_focus=True,
        focus_selected=True,
    )

    assert "is-collected is-focus-selected" in html
    assert "Quest pick 1 of 5" in html


def test_unseen_reference_photo_opens_a_color_view() -> None:
    html = species_log._build_discovery_species_row_html(
        {
            "taxon_id": 2,
            "common_name": "White Ibis",
            "scientific_name": "Eudocimus albus",
            "observation_count": 88,
            "nearby_rank": 2,
            "collected": False,
            "reference_photo": {
                "url": "https://inat.example/ibis.jpg",
                "attribution": "(c) Example Naturalist",
            },
        },
        show_focus=False,
    )

    assert "field-quest-species-image-link" in html
    assert "View White Ibis in color" in html
    assert "target='_blank'" in html
    assert "<span>View in color</span>" in html


def test_focus_picker_shows_five_numbered_slots_and_selection_count() -> None:
    html = species_log._build_focus_picker_html(
        [
            {"taxon_id": 1, "common_name": "White Ibis"},
            {"taxon_id": 2, "common_name": "Roseate Spoonbill"},
        ],
        [1, 2],
    )

    assert "2 of 5 selected" in html
    assert html.count("field-quest-focus-slot") == 5
    assert "White Ibis" in html
    assert "Choose a species" in html


def test_collected_species_can_be_selected_from_its_displayed_row() -> None:
    app = AppTest.from_string(
        """
from hike_journal.ui.views.species_log import _render_discovery_species_rows

_render_discovery_species_rows(
    [{
        "taxon_id": 1,
        "common_name": "American Alligator",
        "scientific_name": "Alligator mississippiensis",
        "observation_count": 244,
        "nearby_rank": 1,
        "collected": True,
    }],
    show_focus=True,
    focus_state_key="test_focus_ids",
    key_prefix="test",
)
        """
    ).run()

    assert not app.exception
    assert app.button[0].label == "Select"

    app.button[0].click().run()

    assert not app.exception
    assert app.button[0].label == "Selected 1/5"
