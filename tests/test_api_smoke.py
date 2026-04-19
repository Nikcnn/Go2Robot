from __future__ import annotations

import time

import yaml
from fastapi.testclient import TestClient

from tests import make_test_dir
from src.api import _dispatch_action, _manual_mode_block_reason, _start_runtime, create_app
from src.config import AppConfig, RobotConfig
from src.state_machine import EffectiveState


class _StartupControl:
    def __init__(self) -> None:
        self.started = False
        self.estop = False

    def start(self) -> None:
        self.started = True

    def latch_estop(self) -> None:
        self.estop = True


class _StartupAdapter:
    def __init__(self) -> None:
        self.connected = False

    def connect(self) -> None:
        raise RuntimeError("boom")


class _StartupService:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True


class _StartupRuntime:
    def __init__(self) -> None:
        self.config = AppConfig(robot=RobotConfig(mode="go2"))
        self.control = _StartupControl()
        self.adapter = _StartupAdapter()
        self.telemetry = _StartupService()
        self.camera = _StartupService()


def write_test_config():
    tmp_path = make_test_dir("api_smoke")
    config_dir = tmp_path / "config"
    routes_dir = config_dir / "routes"
    routes_dir.mkdir(parents=True)

    (routes_dir / "demo_route.json").write_text(
        """
{
  "route_id": "demo_route_v1",
  "steps": [
    {"id": "move_1", "type": "move", "vx": 0.15, "vy": 0.0, "vyaw": 0.0, "duration_sec": 0.2},
    {"id": "checkpoint_1", "type": "checkpoint", "waypoint_id": "panel_A", "settle_time_sec": 0.05, "analyzer": "simple_presence"},
    {"id": "stop_1", "type": "stop"}
  ]
}
""".strip(),
        encoding="utf-8",
    )

    config_path = config_dir / "app_config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "robot": {"mode": "mock", "max_vx": 0.5, "max_vyaw": 1.0},
                "telemetry": {"hz": 5},
                "camera": {"fps": 5, "width": 320, "height": 240, "jpeg_quality": 70},
                "control": {"watchdog_timeout_ms": 200},
                "analysis": {"frame_diff_threshold": 0.25},
                "server": {"host": "127.0.0.1", "port": 8000},
                "storage": {"runs_dir": "runs"},
                "logging": {"level": "INFO"},
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_mock_api_smoke() -> None:
    config_path = write_test_config()
    app = create_app(config_path=config_path)

    with TestClient(app) as client:
        status = client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["adapter_mode"] == "mock"

        with client.websocket_connect("/ws/telemetry") as websocket:
            telemetry = websocket.receive_json()
            assert telemetry["mode"] in {"AUTO", "MANUAL", "ESTOP"}
            assert telemetry["robot_state"]["battery_percent"] is not None
            assert telemetry["robot_state"]["camera_status"] == "Live via mock camera"

        with client.websocket_connect("/ws/events") as websocket:
            event = websocket.receive_json()
            assert "event" in event

        camera_bytes = app.state.runtime.camera.get_latest_jpeg()
        assert camera_bytes is not None
        assert camera_bytes[:2] == b"\xff\xd8"

        start = client.post("/api/mission/start", json={"route_id": "demo_route"})
        assert start.status_code == 200

        deadline = time.time() + 3.0
        completed = False
        while time.time() < deadline:
            current = client.get("/api/mission/current")
            assert current.status_code == 200
            mission_status = current.json()["mission_status"]
            if mission_status == "COMPLETED":
                completed = True
                break
            time.sleep(0.05)

        assert completed


def test_start_runtime_falls_back_to_estop_on_connect_error() -> None:
    runtime = _StartupRuntime()
    events: list[tuple[str, dict]] = []

    adapter_ready = _start_runtime(runtime, lambda event, details: events.append((event, details)))

    assert adapter_ready is False
    assert runtime.control.started is True
    assert runtime.control.estop is True
    assert runtime.telemetry.started is True
    assert runtime.camera.started is True
    assert [event for event, _details in events] == [
        "adapter_startup_failed",
        "server_started",
    ]


def test_api_exposes_sit_endpoint() -> None:
    config_path = write_test_config()
    app = create_app(config_path=config_path)
    assert any(getattr(route, "path", None) == "/api/mode/sit" for route in app.routes)


def test_api_activate_robot_endpoint_succeeds_in_mock_mode() -> None:
    config_path = write_test_config()
    app = create_app(config_path=config_path)

    with TestClient(app) as client:
        response = client.post("/api/robot/activate")

    assert response.status_code == 200
    assert response.json()["ok"] is True


class _DispatchControl:
    def __init__(self) -> None:
        self.estop_latched = False
        self.activate_calls = 0
        self.reset_estop_calls = 0
        self.take_manual_calls = 0

    def activate_robot(self) -> bool:
        self.activate_calls += 1
        return True

    def reset_estop(self) -> bool:
        self.reset_estop_calls += 1
        return True

    def take_manual(self) -> bool:
        self.take_manual_calls += 1
        return True


class _DispatchStateMachine:
    def __init__(self, effective: EffectiveState) -> None:
        self._effective = effective

    def get_effective(self) -> EffectiveState:
        return self._effective


class _DispatchRuntime:
    def __init__(self, effective: EffectiveState) -> None:
        self.control = _DispatchControl()
        self.state_machine = _DispatchStateMachine(effective)


def test_manual_mode_block_reason_rejects_faulted_state() -> None:
    reason = _manual_mode_block_reason(EffectiveState.ERROR)
    assert reason == "manual mode is blocked while effective state is 'error'"


def test_manual_mode_block_reason_allows_ready_state() -> None:
    assert _manual_mode_block_reason(EffectiveState.READY) is None


def test_reset_fault_action_attempts_recovery_via_activate() -> None:
    runtime = _DispatchRuntime(EffectiveState.ERROR)

    success, reason = _dispatch_action("reset_fault", runtime, lambda *_args, **_kwargs: None)

    assert success is True
    assert reason == "recovery attempted via activate()"
    assert runtime.control.activate_calls == 1
    assert runtime.control.reset_estop_calls == 0


def test_manual_mode_action_rejects_faulted_effective_state() -> None:
    runtime = _DispatchRuntime(EffectiveState.ERROR)

    success, reason = _dispatch_action("manual_mode", runtime, lambda *_args, **_kwargs: None)

    assert success is False
    assert reason == "manual mode is blocked while effective state is 'error'"
    assert runtime.control.take_manual_calls == 0
