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
