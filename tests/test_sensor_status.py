"""Tests for sensor status aggregation with mock adapter.

STATUS: wired and tested in mock mode
All sensor paths tested here use only mock adapter and mock realsense.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.operator_services import build_sensor_summary
from tests.test_api_smoke import started_app, write_test_config


def _make_minimal_runtime(app):
    """Return the app runtime object (started state)."""
    return app.state.runtime


class TestSensorSummaryShape:
    def test_sensor_summary_has_required_keys(self) -> None:
        config_path = write_test_config()
        with started_app(config_path) as app:
            rt = _make_minimal_runtime(app)
            sensors = build_sensor_summary(rt)

        assert "built_in_camera" in sensors
        assert "realsense_d435i" in sensors
        assert "built_in_lidar" in sensors

    def test_each_sensor_has_name_online_status_fields(self) -> None:
        config_path = write_test_config()
        with started_app(config_path) as app:
            rt = _make_minimal_runtime(app)
            sensors = build_sensor_summary(rt)

        for key in ("built_in_camera", "realsense_d435i", "built_in_lidar"):
            sensor = sensors[key]
            assert "name" in sensor, f"{key} missing 'name'"
            assert "online" in sensor, f"{key} missing 'online'"
            assert "status" in sensor, f"{key} missing 'status'"


class TestBuiltInCameraStatus:
    def test_built_in_camera_online_in_mock_mode(self) -> None:
        config_path = write_test_config()
        with started_app(config_path) as app:
            rt = _make_minimal_runtime(app)
            sensors = build_sensor_summary(rt)

        camera = sensors["built_in_camera"]
        assert camera["online"] is True
        assert camera["stream_url"] == "/stream/camera"

    def test_built_in_camera_runtime_note_present(self) -> None:
        config_path = write_test_config()
        with started_app(config_path) as app:
            rt = _make_minimal_runtime(app)
            sensors = build_sensor_summary(rt)

        # Runtime note must exist and explain the validation state
        assert "runtime_note" in sensors["built_in_camera"]
        assert len(sensors["built_in_camera"]["runtime_note"]) > 5


class TestRealsenseStatus:
    def test_realsense_disabled_in_mock_mode(self) -> None:
        config_path = write_test_config()
        with started_app(config_path) as app:
            rt = _make_minimal_runtime(app)
            sensors = build_sensor_summary(rt)

        rs = sensors["realsense_d435i"]
        assert rs["enabled"] is False
        assert rs["online"] is False

    def test_realsense_stream_url_present(self) -> None:
        config_path = write_test_config()
        with started_app(config_path) as app:
            rt = _make_minimal_runtime(app)
            sensors = build_sensor_summary(rt)

        assert sensors["realsense_d435i"]["stream_url"] == "/stream/realsense/color"


class TestLidarStatus:
    def test_lidar_online_in_mock_mode(self) -> None:
        config_path = write_test_config()
        with started_app(config_path) as app:
            rt = _make_minimal_runtime(app)
            sensors = build_sensor_summary(rt)

        lidar = sensors["built_in_lidar"]
        # Mock adapter has get_lidar_scan so preview is available
        assert lidar["online"] is True

    def test_lidar_preview_available_in_mock(self) -> None:
        config_path = write_test_config()
        with started_app(config_path) as app:
            rt = _make_minimal_runtime(app)
            sensors = build_sensor_summary(rt)

        assert sensors["built_in_lidar"]["preview_available"] is True

    def test_lidar_status_is_informative(self) -> None:
        config_path = write_test_config()
        with started_app(config_path) as app:
            rt = _make_minimal_runtime(app)
            sensors = build_sensor_summary(rt)

        status = sensors["built_in_lidar"].get("status", "")
        assert len(status) > 5
