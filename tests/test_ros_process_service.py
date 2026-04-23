"""Unit tests for RosProcessService state transitions.

No real ros2 binary is needed — subprocess calls are mocked.
STATUS: wired and tested in mock mode (subprocess mocked)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.operator_services import RosProcessService
from tests import make_test_dir


def _make_service(project_root: Path, robot_mode: str = "mock") -> RosProcessService:
    return RosProcessService(
        project_root=project_root,
        robot_mode=robot_mode,
        interface_name="eth0",
    )


def _running_popen():
    """Mock Popen for a live process."""
    mock = MagicMock()
    mock.poll.return_value = None
    mock.pid = 12345
    return mock


def _finished_popen(returncode: int = 0):
    """Mock Popen for an already-exited process."""
    mock = MagicMock()
    mock.poll.return_value = returncode
    mock.pid = 12346
    return mock


# ─── Status ──────────────────────────────────────────────

def test_initial_status_shows_nothing_running() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    status = svc.status()
    assert status["mapping"]["running"] is False
    assert status["navigation"]["running"] is False


def test_ros2_available_when_on_path() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    with patch("shutil.which", return_value="/usr/bin/ros2"):
        status = svc.status()
    assert status["ros2_available"] is True


def test_ros2_not_available_when_off_path() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    with patch("shutil.which", return_value=None):
        status = svc.status()
    assert status["ros2_available"] is False


# ─── Mapping start / stop ────────────────────────────────

def test_start_mapping_returns_ok_with_mocked_process() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    mock_proc = _running_popen()
    mock_file = MagicMock()

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("builtins.open", return_value=mock_file):
        result = svc.start_mapping()

    assert result["ok"] is True
    assert "mapping" in result["message"].lower()


def test_start_mapping_already_running_returns_ok_without_new_process() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    mock_proc = _running_popen()
    mock_file = MagicMock()

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("builtins.open", return_value=mock_file):
        svc.start_mapping()
        result = svc.start_mapping()

    assert result["ok"] is True
    assert "running" in result["message"].lower()


def test_stop_mapping_when_not_running_returns_ok() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    result = svc.stop_mapping()
    assert result["ok"] is True
    assert "not running" in result["message"].lower()


def test_stop_mapping_terminates_running_process() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    # Process is running until terminate() is called, then exits.
    poll_values = [None]  # mutable so the side_effect closure can update it

    def poll_side_effect():
        return poll_values[0]

    mock_proc = MagicMock()
    mock_proc.poll.side_effect = poll_side_effect
    mock_proc.pid = 99

    def _terminate():
        poll_values[0] = -15  # process exits after terminate

    mock_proc.terminate.side_effect = _terminate
    mock_proc.wait.return_value = None
    mock_file = MagicMock()

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("builtins.open", return_value=mock_file):
        svc.start_mapping()

    result = svc.stop_mapping()
    assert result["ok"] is True
    mock_proc.terminate.assert_called_once()


# ─── Navigation start / stop ─────────────────────────────

def test_start_navigation_fails_without_map() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    result = svc.start_navigation({"map_id": "nonexistent_map"})
    assert result["ok"] is False


def test_start_navigation_fails_with_empty_map_id() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    result = svc.start_navigation({})
    assert result["ok"] is False
    assert "map" in result["message"].lower()


def test_start_navigation_with_existing_map_file() -> None:
    root = make_test_dir("ros_svc")
    maps_dir = root / "shared_missions" / "maps"
    maps_dir.mkdir(parents=True)
    (maps_dir / "test_map.yaml").write_text("image: test_map.pgm\nresolution: 0.05\n")

    svc = _make_service(root)
    mock_proc = _running_popen()
    mock_file = MagicMock()

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("builtins.open", return_value=mock_file):
        result = svc.start_navigation({"map_id": "test_map"})

    assert result["ok"] is True


def test_stop_navigation_when_not_running_returns_ok() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    result = svc.stop_navigation()
    assert result["ok"] is True


# ─── SDK ownership guard ─────────────────────────────────

def test_go2_app_blocks_go2_ros_mapping() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root, robot_mode="go2")
    result = svc.start_mapping({"robot_mode": "go2"})
    assert result["ok"] is False
    msg = result["message"].lower()
    assert "blocked" in msg or "mock" in msg


def test_mock_app_allows_go2_ros_mapping() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root, robot_mode="mock")
    mock_proc = _running_popen()
    mock_file = MagicMock()
    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("builtins.open", return_value=mock_file):
        result = svc.start_mapping({"robot_mode": "go2"})
    assert result["ok"] is True


# ─── Mission control ─────────────────────────────────────

def test_start_mission_fails_when_navigation_not_running() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    result = svc.start_mission(root / "shared_missions" / "missions" / "test.json")
    assert result["ok"] is False
    assert "navigation" in result["message"].lower()


def test_ros2_not_found_returns_friendly_message() -> None:
    root = make_test_dir("ros_svc")
    svc = _make_service(root)
    with patch("subprocess.Popen", side_effect=FileNotFoundError("ros2")), \
         patch("builtins.open", return_value=MagicMock()):
        result = svc.start_mapping()
    assert result["ok"] is False
    assert "ros2" in result["message"].lower()
