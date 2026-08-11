from hike_journal.ui.map_component import MAP_COMPONENT_HTML, MAP_COMPONENT_JS


def test_streamlit_map_overlays_official_florida_trail_with_distinct_routes() -> None:
    assert "FNST%20Master/FeatureServer/0/query" in MAP_COMPONENT_JS
    assert "'line-color':'#f47a32'" in MAP_COMPONENT_JS
    assert "'line-color':'#22d3ee'" in MAP_COMPONENT_JS
    assert "'line-color':'#ff4d8d'" in MAP_COMPONENT_JS
    assert "'circle-color':'#8bd3ff'" in MAP_COMPONENT_JS
    assert "overlappingRouteFeatures" in MAP_COMPONENT_JS
    assert "Florida Trail · USFS / FTA" in MAP_COMPONENT_HTML
    assert "Shared route" in MAP_COMPONENT_HTML
