"""Smoke tests for GET /api/operator/overview in mock mode.

STATUS: wired and tested in mock mode
"""
from __future__ import annotations

from tests.test_api_smoke import _route_endpoint, started_app, write_test_config


def test_overview_returns_expected_shape_in_mock_mode() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        overview_ep = _route_endpoint(app, "/api/operator/overview")
        overview = overview_ep()

    assert isinstance(overview, dict)
    assert "connection" in overview
    assert "mode" in overview
    assert "sensors" in overview
    assert "ros" in overview
    assert "maps" in overview
    assert "missions" in overview
    assert "status_sentence" in overview
    assert "mission_progress" in overview


def test_overview_connection_is_online_in_mock_mode() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        overview_ep = _route_endpoint(app, "/api/operator/overview")
        overview = overview_ep()

    conn = overview["connection"]
    assert conn["online"] is True
    assert conn["adapter_mode"] == "mock"
    assert isinstance(conn["label"], str)


def test_overview_status_sentence_is_human_readable() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        overview_ep = _route_endpoint(app, "/api/operator/overview")
        overview = overview_ep()

    sentence = overview["status_sentence"]
    assert isinstance(sentence, str)
    assert len(sentence) > 3
    # Must not expose raw ROS or SDK internals
    assert "/scan" not in sentence
    assert "ChannelFactory" not in sentence


def test_overview_sensor_keys_present() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        sensors_ep = _route_endpoint(app, "/api/operator/sensors")
        sensors = sensors_ep()["sensors"]

    assert "built_in_camera" in sensors
    assert "realsense_d435i" in sensors
    assert "built_in_lidar" in sensors

    assert sensors["built_in_camera"]["online"] is True
    assert sensors["realsense_d435i"]["enabled"] is False
    assert sensors["built_in_lidar"]["preview_available"] is True


def test_operator_check_system_returns_ok_field() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        check_ep = _route_endpoint(app, "/api/operator/check-system", "POST")
        result = check_ep()

    assert "ok" in result
    assert "checked_at" in result
    assert isinstance(result["ok"], bool)
