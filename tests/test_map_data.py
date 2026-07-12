from hike_journal.domain.map_data import (
    MapViewport,
    bounds_from_point_features,
    fallback_route_features,
    normalize_bounds,
    normalize_rpc_payload,
    viewport_from_value,
)


def test_viewport_rejects_untrusted_component_values() -> None:
    viewport = viewport_from_value({"west": "bad"}, fallback_bounds=[-82, 27, -80, 30])

    assert viewport == MapViewport(west=-82.0, south=27.0, east=-80.0, north=30.0, zoom=8.0)


def test_viewport_clamps_browser_coordinates_and_zoom() -> None:
    viewport = viewport_from_value({"west": -999, "south": -90, "east": 999, "north": 90, "zoom": 99})

    assert viewport.west == -180
    assert viewport.east == 180
    assert viewport.south == -85.051129
    assert viewport.north == 85.051129
    assert viewport.zoom == 22


def test_normalize_bounds_orders_extent() -> None:
    assert normalize_bounds([-80, 30, -82, 27]) == (-82.0, 27.0, -80.0, 30.0)


def test_rpc_payload_accepts_postgrest_singleton_shape() -> None:
    payload = normalize_rpc_payload([{"type": "FeatureCollection", "features": [{"id": 1}], "meta": {"clustered": True}}], include_meta=True)

    assert payload["features"] == [{"id": 1}]
    assert payload["meta"]["clustered"] is True


def test_bounds_from_point_features_cover_every_cluster() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"geometry": {"type": "Point", "coordinates": [-81.3, 28.8]}},
            {"geometry": {"type": "Point", "coordinates": [-80.9, 28.4]}},
        ],
    }

    assert bounds_from_point_features(payload) == (-81.3, 28.4, -80.9, 28.8)


def test_bounds_from_single_cluster_have_nonzero_area() -> None:
    payload = {"features": [{"geometry": {"type": "Point", "coordinates": [-81, 28]}}]}

    assert bounds_from_point_features(payload) == (-81.01, 27.99, -80.99, 28.01)


def test_fallback_routes_respect_ownership_scope_and_point_budget() -> None:
    route = {
        "hike_id": "visible",
        "track_geojson": {"type": "LineString", "coordinates": [[-81 + i / 10000, 28] for i in range(1000)]},
    }
    hidden = {"hike_id": "hidden", "track_geojson": route["track_geojson"]}
    payload = fallback_route_features(
        [route, hidden],
        visible_hike_ids={"visible"},
        selected_hike_id=None,
        viewport=MapViewport(-82, 27, -79, 30, 8),
    )

    assert len(payload["features"]) == 1
    assert len(payload["features"][0]["geometry"]["coordinates"]) == 250
