from __future__ import annotations

from typing import Any

import hike_journal.ui.views.map as map_view


class SessionState(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class Control:
    def __init__(self) -> None:
        self.slider_calls = 0
        self.captions: list[str] = []

    def radio(self, _label, options, **_kwargs):
        return options[0]

    def selectbox(self, _label, options, **_kwargs):
        return options[0]

    def slider(self, *_args, **_kwargs):
        self.slider_calls += 1
        raise AssertionError("A zero- or one-photo map must not create a degenerate slider.")

    def caption(self, value, **_kwargs):
        self.captions.append(str(value))


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = SessionState()
        self.query_params: dict[str, str] = {}
        self.controls = [Control() for _ in range(4)]
        self.warnings: list[str] = []

    def columns(self, *_args, **_kwargs):
        return self.controls

    def write(self, *_args, **_kwargs):
        return None

    def info(self, *_args, **_kwargs):
        return None

    def warning(self, value, **_kwargs):
        self.warnings.append(str(value))

    def caption(self, *_args, **_kwargs):
        return None


class MapRepository:
    def __init__(
        self,
        *,
        photo_count: int,
        route_count: int,
        markers: dict[str, Any] | None = None,
        routes: dict[str, Any] | None = None,
        summary_bounds: list[float] | None = None,
        spatial_rpc_ready: bool = True,
        route_imports: list[dict[str, Any]] | None = None,
    ) -> None:
        self.photo_count = photo_count
        self.route_count = route_count
        self.markers = markers or {"type": "FeatureCollection", "features": [], "meta": {}}
        self.routes = routes or {"type": "FeatureCollection", "features": []}
        self.summary_bounds = summary_bounds
        self.spatial_rpc_ready = spatial_rpc_ready
        self.route_imports = route_imports or []

    def get_map_summary(self, **_kwargs):
        return {
            "photo_count": self.photo_count,
            "species_count": 0,
            "species": [],
            "bounds": self.summary_bounds,
            "spatial_rpc_ready": self.spatial_rpc_ready,
        }

    def get_map_viewport(self, **_kwargs):
        return self.markers

    def get_map_routes_viewport(self, **_kwargs):
        return self.routes

    def get_map_route_index_status(self, **_kwargs):
        return self.route_count, self.route_count

    def list_hike_route_imports(self):
        return self.route_imports

    def get_map_photo_detail(self, **_kwargs):
        raise AssertionError("No photo was selected in this test.")


def install_map_fakes(monkeypatch):
    fake_st = FakeStreamlit()
    rendered: list[dict[str, Any]] = []
    monkeypatch.setattr(map_view, "st", fake_st)
    monkeypatch.setattr(map_view, "section_heading", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(map_view, "fetch_unindexed_map_routes", lambda *_args: [])
    monkeypatch.setattr(map_view, "render_maplibre", lambda **kwargs: rendered.append(kwargs))
    return fake_st, rendered


def render_outing(repository) -> None:
    map_view.render_map_view(
        repository,
        [{"id": "hike-1"}],
        {},
        selected_hike={"id": "hike-1"},
        format_confidence_label=lambda _observation: "",
    )


def test_empty_outing_map_skips_degenerate_slider_and_shows_empty_state(monkeypatch) -> None:
    fake_st, rendered = install_map_fakes(monkeypatch)

    render_outing(MapRepository(photo_count=0, route_count=0))

    assert fake_st.controls[2].slider_calls == 0
    assert fake_st.controls[2].captions == ["No mapped photos"]
    assert fake_st.warnings == ["This outing does not have a recorded route or geotagged photos yet."]
    assert rendered == []


def test_one_photo_outing_map_keeps_route_extent_and_clickable_photo_point(monkeypatch) -> None:
    photo_feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-81.1, 28.1]},
        "properties": {
            "kind": "point",
            "layer": "photo",
            "photo_id": "photo-1",
            "hike_id": "hike-1",
            "photo_number": 1,
            "title": "Trail photo",
        },
    }
    route_feature = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[-82.0, 27.0], [-80.0, 30.0]]},
        "properties": {"hike_id": "hike-1"},
    }
    fake_st, rendered = install_map_fakes(monkeypatch)

    render_outing(
        MapRepository(
            photo_count=1,
            route_count=1,
            markers={"type": "FeatureCollection", "features": [photo_feature], "meta": {}},
            routes={"type": "FeatureCollection", "features": [route_feature]},
            summary_bounds=[-82.0, 27.0, -80.0, 30.0],
        )
    )

    assert fake_st.controls[2].slider_calls == 0
    assert fake_st.controls[2].captions == ["1 mapped photo"]
    assert len(rendered) == 1
    assert rendered[0]["fit_bounds"] == (-82.0, 27.0, -80.0, 30.0)
    assert rendered[0]["routes"]["features"] == [route_feature]
    assert rendered[0]["markers"]["features"] == [photo_feature]


def test_outing_map_stays_mounted_when_current_viewport_has_no_features(monkeypatch) -> None:
    fake_st, rendered = install_map_fakes(monkeypatch)

    render_outing(MapRepository(photo_count=0, route_count=1))

    assert fake_st.controls[2].slider_calls == 0
    assert fake_st.warnings == []
    assert len(rendered) == 1
    assert rendered[0]["markers"]["features"] == []
    assert rendered[0]["routes"]["features"] == []


def test_unindexed_route_outside_default_region_supplies_initial_bounds(monkeypatch) -> None:
    route_import = {
        "hike_id": "hike-1",
        "track_geojson": {
            "type": "LineString",
            "coordinates": [[-123.0, 47.0], [-121.0, 48.0]],
        },
    }
    _fake_st, rendered = install_map_fakes(monkeypatch)

    render_outing(
        MapRepository(
            photo_count=0,
            route_count=1,
            spatial_rpc_ready=False,
            route_imports=[route_import],
        )
    )

    assert len(rendered) == 1
    assert rendered[0]["fit_bounds"] == (-123.0, 47.0, -121.0, 48.0)
    assert rendered[0]["routes"]["features"][0]["geometry"] == route_import["track_geojson"]


def test_changed_summary_bounds_refit_once_after_route_sync(monkeypatch) -> None:
    fake_st, rendered = install_map_fakes(monkeypatch)

    render_outing(
        MapRepository(
            photo_count=0,
            route_count=1,
            summary_bounds=[-82.0, 27.0, -80.0, 30.0],
        )
    )
    first_fit_request = rendered[-1]["fit_request"]
    fake_st.session_state["maplibre_hike-1"] = {
        "viewport": {"west": -82.0, "south": 27.0, "east": -80.0, "north": 30.0, "zoom": 10.0}
    }

    render_outing(
        MapRepository(
            photo_count=0,
            route_count=1,
            summary_bounds=[-123.0, 47.0, -121.0, 48.0],
        )
    )

    assert rendered[-1]["fit_bounds"] == (-123.0, 47.0, -121.0, 48.0)
    assert rendered[-1]["fit_request"] != first_fit_request

    render_outing(
        MapRepository(
            photo_count=0,
            route_count=1,
            summary_bounds=[-123.0, 47.0, -121.0, 48.0],
        )
    )

    assert rendered[-1]["fit_bounds"] is None
    assert rendered[-1]["fit_request"] is None
