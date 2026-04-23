"""CRUD tests for coordinate waypoint missions via API.

STATUS: wired and tested in mock mode
"""
from __future__ import annotations

from pathlib import Path

from src.api import create_app
from tests.test_api_smoke import _route_endpoint, write_test_config

_SAMPLE_MISSION = {
    "mission_id": "missions_test_route",
    "map_id": "site_test",
    "waypoints": [
        {"id": "alpha", "x": 1.0, "y": 2.0, "yaw": 0.0, "task": "inspect"},
        {"id": "beta",  "x": 3.5, "y": 1.2, "yaw": 1.57, "task": "photo"},
    ],
}


def _make_endpoints(config_path):
    app = create_app(config_path=config_path)
    return {
        "create":  _route_endpoint(app, "/api/missions", "POST"),
        "list":    _route_endpoint(app, "/api/missions"),
        "get":     _route_endpoint(app, "/api/missions/{mission_id}"),
        "update":  _route_endpoint(app, "/api/missions/{mission_id}", "PUT"),
        "delete":  _route_endpoint(app, "/api/missions/{mission_id}", "DELETE"),
    }


def test_create_mission_returns_mission_id() -> None:
    ep = _make_endpoints(write_test_config())
    result = ep["create"](_SAMPLE_MISSION)
    assert result["mission_id"] == "missions_test_route"
    assert result["map_id"] == "site_test"
    assert len(result["waypoints"]) == 2
    ep["delete"]("missions_test_route")


def test_created_mission_persists_to_shared_missions_dir() -> None:
    ep = _make_endpoints(write_test_config())
    result = ep["create"](_SAMPLE_MISSION)
    path = Path(result["path"])
    assert path.exists()
    assert path.name == "missions_test_route.json"
    assert path.parent.name == "missions"
    assert path.parent.parent.name == "shared_missions"
    ep["delete"]("missions_test_route")


def test_list_missions_includes_created_mission() -> None:
    ep = _make_endpoints(write_test_config())
    ep["create"](_SAMPLE_MISSION)
    missions = ep["list"]()["missions"]
    assert any(m["mission_id"] == "missions_test_route" for m in missions)
    ep["delete"]("missions_test_route")


def test_get_mission_returns_full_waypoints() -> None:
    ep = _make_endpoints(write_test_config())
    ep["create"](_SAMPLE_MISSION)
    loaded = ep["get"]("missions_test_route")
    assert loaded["mission_id"] == "missions_test_route"
    wp_ids = [w["id"] for w in loaded["waypoints"]]
    assert wp_ids == ["alpha", "beta"]
    ep["delete"]("missions_test_route")


def test_update_mission_appends_waypoint() -> None:
    ep = _make_endpoints(write_test_config())
    ep["create"](_SAMPLE_MISSION)
    loaded = ep["get"]("missions_test_route")
    loaded["waypoints"].append({"id": "gamma", "x": 5.0, "y": 0.0, "yaw": 0.0, "task": "log"})
    updated = ep["update"]("missions_test_route", loaded)
    assert len(updated["waypoints"]) == 3
    assert updated["waypoints"][2]["id"] == "gamma"
    ep["delete"]("missions_test_route")


def test_delete_mission_removes_file() -> None:
    ep = _make_endpoints(write_test_config())
    created = ep["create"](_SAMPLE_MISSION)
    path = Path(created["path"])
    assert path.exists()
    result = ep["delete"]("missions_test_route")
    assert result["ok"] is True
    assert not path.exists()


def test_get_missing_mission_raises_404() -> None:
    import pytest
    from fastapi import HTTPException

    ep = _make_endpoints(write_test_config())
    with pytest.raises(HTTPException) as exc_info:
        ep["get"]("does_not_exist_xyz")
    assert exc_info.value.status_code == 404


def test_delete_missing_mission_raises_404() -> None:
    import pytest
    from fastapi import HTTPException

    ep = _make_endpoints(write_test_config())
    with pytest.raises(HTTPException) as exc_info:
        ep["delete"]("does_not_exist_xyz")
    assert exc_info.value.status_code == 404


def test_mission_id_validation_rejects_path_traversal() -> None:
    import pytest
    from fastapi import HTTPException

    ep = _make_endpoints(write_test_config())
    with pytest.raises((HTTPException, ValueError)):
        ep["create"]({"mission_id": "../evil", "map_id": "x", "waypoints": []})
