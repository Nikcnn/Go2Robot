from __future__ import annotations

from pathlib import Path

from src.api import create_app
from tests.test_api_smoke import _route_endpoint, started_app, write_test_config


def test_operator_overview_and_sensor_summary_in_mock_mode() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        overview_endpoint = _route_endpoint(app, "/api/operator/overview")
        sensors_endpoint = _route_endpoint(app, "/api/operator/sensors")

        overview = overview_endpoint()
        sensors = sensors_endpoint()["sensors"]

    assert overview["connection"]["online"] is True
    assert overview["connection"]["adapter_mode"] == "mock"
    assert overview["status_sentence"] in {"Ready for mapping", "Ready to navigate", "Building map"}
    assert sensors["built_in_camera"]["online"] is True
    assert sensors["built_in_camera"]["stream_url"] == "/stream/camera"
    assert sensors["realsense_d435i"]["enabled"] is False
    assert sensors["built_in_lidar"]["preview_available"] is True


def test_waypoint_mission_crud_uses_shared_missions_directory() -> None:
    config_path = write_test_config()
    app = create_app(config_path=config_path)

    create_mission = _route_endpoint(app, "/api/missions", "POST")
    list_missions = _route_endpoint(app, "/api/missions")
    get_mission = _route_endpoint(app, "/api/missions/{mission_id}")
    update_mission = _route_endpoint(app, "/api/missions/{mission_id}", "PUT")
    delete_mission = _route_endpoint(app, "/api/missions/{mission_id}", "DELETE")

    created = create_mission(
        {
            "mission_id": "operator_test_route",
            "map_id": "test_map",
            "waypoints": [{"id": "start", "x": 1.0, "y": 2.0, "yaw": 0.25, "task": "inspect"}],
        }
    )

    mission_path = Path(created["path"])
    assert mission_path.name == "operator_test_route.json"
    assert mission_path.parent.name == "missions"
    assert mission_path.parent.parent.name == "shared_missions"
    assert created["waypoints"][0]["id"] == "start"

    listed = list_missions()["missions"]
    assert any(item["mission_id"] == "operator_test_route" for item in listed)

    loaded = get_mission("operator_test_route")
    loaded["waypoints"].append({"id": "finish", "x": 3.0, "y": 4.0, "yaw": 1.0, "task": "photo"})
    updated = update_mission("operator_test_route", loaded)
    assert [item["id"] for item in updated["waypoints"]] == ["start", "finish"]

    deleted = delete_mission("operator_test_route")
    assert deleted["ok"] is True
    assert not mission_path.exists()


def test_waypoint_from_current_pose_appends_to_mission_file() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        from_pose = _route_endpoint(app, "/api/waypoints/from-current-pose", "POST")
        get_mission = _route_endpoint(app, "/api/missions/{mission_id}")

        response = from_pose(
            {
                "mission_id": "pose_capture_route",
                "map_id": "test_map",
                "waypoint_id": "robot_here",
                "task": "inspect",
            }
        )
        mission = get_mission("pose_capture_route")

    assert response["ok"] is True
    assert mission["mission_id"] == "pose_capture_route"
    assert mission["map_id"] == "test_map"
    assert mission["waypoints"][0]["id"] == "robot_here"
    assert mission["waypoints"][0]["task"] == "inspect"
    assert isinstance(mission["waypoints"][0]["x"], float)
