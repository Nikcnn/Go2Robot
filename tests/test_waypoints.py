"""Tests for POST /api/waypoints/from-current-pose in mock mode.

STATUS: wired and tested in mock mode
The mock adapter provides a synthetic pose so no hardware is required.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from tests.test_api_smoke import _route_endpoint, started_app, write_test_config


def test_from_current_pose_without_mission_id_returns_waypoint_only() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        from_pose = _route_endpoint(app, "/api/waypoints/from-current-pose", "POST")
        response = from_pose({"waypoint_id": "standalone_point", "task": "inspect"})

    assert response["ok"] is True
    result = response["result"]
    assert result["id"] == "standalone_point"
    assert result["task"] == "inspect"
    assert isinstance(result["x"], float)
    assert isinstance(result["y"], float)
    assert isinstance(result["yaw"], float)


def test_from_current_pose_with_mission_id_creates_mission_file() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        from_pose = _route_endpoint(app, "/api/waypoints/from-current-pose", "POST")
        get_mission = _route_endpoint(app, "/api/missions/{mission_id}")

        response = from_pose({
            "mission_id": "waypoint_test_route",
            "map_id": "test_map_a",
            "waypoint_id": "first_stop",
            "task": "inspect",
        })
        mission = get_mission("waypoint_test_route")

    assert response["ok"] is True
    assert mission["mission_id"] == "waypoint_test_route"
    assert mission["map_id"] == "test_map_a"
    assert len(mission["waypoints"]) == 1
    assert mission["waypoints"][0]["id"] == "first_stop"
    assert mission["waypoints"][0]["task"] == "inspect"


def test_from_current_pose_appends_to_existing_mission() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        from_pose = _route_endpoint(app, "/api/waypoints/from-current-pose", "POST")
        get_mission = _route_endpoint(app, "/api/missions/{mission_id}")

        from_pose({
            "mission_id": "append_test_route",
            "map_id": "map_x",
            "waypoint_id": "point_a",
            "task": "inspect",
        })
        from_pose({
            "mission_id": "append_test_route",
            "map_id": "map_x",
            "waypoint_id": "point_b",
            "task": "photo",
        })
        mission = get_mission("append_test_route")

    assert len(mission["waypoints"]) == 2
    ids = [w["id"] for w in mission["waypoints"]]
    assert ids == ["point_a", "point_b"]


def test_duplicate_waypoint_id_in_same_mission_raises_400() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        from_pose = _route_endpoint(app, "/api/waypoints/from-current-pose", "POST")

        from_pose({
            "mission_id": "dup_test_route",
            "map_id": "map_y",
            "waypoint_id": "dup_point",
            "task": "inspect",
        })
        with pytest.raises(HTTPException) as exc_info:
            from_pose({
                "mission_id": "dup_test_route",
                "map_id": "map_y",
                "waypoint_id": "dup_point",
                "task": "inspect",
            })
        assert exc_info.value.status_code == 400


def test_from_current_pose_returns_float_coordinates() -> None:
    """Mock pose provides synthetic x/y/yaw — all must be float, not None."""
    config_path = write_test_config()

    with started_app(config_path) as app:
        from_pose = _route_endpoint(app, "/api/waypoints/from-current-pose", "POST")
        response = from_pose({"waypoint_id": "coord_check", "task": "log"})

    assert response["ok"] is True
    result = response["result"]
    for field in ("x", "y", "yaw"):
        assert isinstance(result[field], float), f"Expected float for {field}"
