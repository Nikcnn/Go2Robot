from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from tests import make_test_dir
from src.config import AppConfig, RealsenseConfig
from src.sensors.realsense_camera import RealsenseCameraService, _FrameBundle


def test_realsense_config_defaults_to_optional() -> None:
    config = AppConfig()
    assert config.realsense.enabled is False
    assert config.realsense.startup_required is False
    assert config.realsense.enable_color is True
    assert config.realsense.enable_depth is True


def test_realsense_service_disabled_mode_is_noop() -> None:
    tmp_path = make_test_dir("realsense_disabled")
    service = RealsenseCameraService(RealsenseConfig(enabled=False))

    service.start()

    status = service.get_status()
    snapshot = service.capture_snapshot(tmp_path, "panel_A")
    assert status["status"] == "disabled"
    assert status["available"] is False
    assert snapshot["status"] == "disabled"
    assert service.get_latest_color_frame() is None
    assert service.get_latest_depth_frame() is None


def test_realsense_service_handles_missing_backend_when_optional() -> None:
    service = RealsenseCameraService(RealsenseConfig(enabled=True, startup_required=False), rs_module=None)

    service.start()

    status = service.get_status()
    assert status["enabled"] is True
    assert status["available"] is False
    assert "pyrealsense2" in str(status["status"])


def test_realsense_service_raises_when_backend_missing_and_required() -> None:
    service = RealsenseCameraService(RealsenseConfig(enabled=True, startup_required=True), rs_module=None)

    with pytest.raises(RuntimeError, match="pyrealsense2"):
        service.start()


def test_realsense_snapshot_writes_artifacts_from_cached_frames() -> None:
    tmp_path = make_test_dir("realsense_snapshot")
    service = RealsenseCameraService(RealsenseConfig(enabled=True), rs_module=None)
    timestamp = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    color = np.full((4, 5, 3), 127, dtype=np.uint8)
    depth = np.arange(20, dtype=np.uint16).reshape(4, 5)

    with service._lock:
        service._available = True
        service._status = "streaming"
        service._last_frame_at = timestamp
        service._color_intrinsics = {"width": 5, "height": 4, "fx": 1.0, "fy": 1.0, "ppx": 0.5, "ppy": 0.5, "coeffs": [0.0] * 5}
        service._depth_intrinsics = {"width": 5, "height": 4, "fx": 1.0, "fy": 1.0, "ppx": 0.5, "ppy": 0.5, "coeffs": [0.0] * 5}
        service._latest = _FrameBundle(
            timestamp=timestamp,
            sequence_id=7,
            color_frame_id=101,
            depth_frame_id=202,
            color_frame=color,
            depth_frame=depth,
        )

    snapshot = service.capture_snapshot(tmp_path, "panel_A")

    assert snapshot["status"] == "ok"
    assert snapshot["sequence_id"] == 7
    assert snapshot["color_frame_id"] == 101
    assert snapshot["depth_frame_id"] == 202
    assert snapshot["resolution"] == {"width": 5, "height": 4}
    assert snapshot["color_image_path"] is not None
    assert snapshot["depth_npy_path"] is not None
    assert snapshot["depth_preview_path"] is not None
    assert (tmp_path / snapshot["color_image_path"]).exists()
    assert (tmp_path / snapshot["depth_npy_path"]).exists()
    assert (tmp_path / snapshot["depth_preview_path"]).exists()
    restored = np.load(tmp_path / snapshot["depth_npy_path"])
    assert restored.shape == (4, 5)
