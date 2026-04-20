from __future__ import annotations

from contextlib import contextmanager
import time

import yaml
from fastapi.routing import APIRoute

from tests import make_test_dir
from src.api import _STRUCTURED_LOG_MAP, _start_runtime, create_app
from src.config import AppConfig, RobotConfig
from src.models import MissionRunRequest, MissionStartRequest, TeleopCommandRequest


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
                "robot": {"mode": "mock", "max_vx": 0.5, "max_vy": 0.5, "max_vyaw": 1.0},
                "telemetry": {"hz": 5},
                "camera": {"fps": 5, "width": 320, "height": 240, "jpeg_quality": 70},
                "control": {"watchdog_timeout_ms": 600},
                "analysis": {"frame_diff_threshold": 0.25},
                "server": {"host": "127.0.0.1", "port": 8000},
                "storage": {"runs_dir": "runs"},
                "logging": {"level": "INFO"},
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _route_endpoint(app, path: str, method: str = "GET"):
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method.upper() in route.methods:
            return route.endpoint
    raise AssertionError(f"Route {method} {path} not found")


@contextmanager
def started_app(config_path):
    app = create_app(config_path=config_path)
    runtime = app.state.runtime

    def emit_event(event: str, details: dict) -> None:
        runtime.storage.record_event(event, details)
        runtime.events.publish(event, details)
        mapping = _STRUCTURED_LOG_MAP.get(event)
        if mapping:
            level, category = mapping
            runtime.event_log.append(
                level=level,  # type: ignore[arg-type]
                category=category,  # type: ignore[arg-type]
                event=event,
                message=details.get("reason") or details.get("message") or event,
                details=details,
            )

    _start_runtime(runtime, emit_event)
    try:
        yield app
    finally:
        runtime.mission.shutdown()
        runtime.realsense.stop()
        runtime.camera.stop()
        runtime.telemetry.stop()
        runtime.control.shutdown()
        runtime.adapter.disconnect()


def test_mock_api_smoke() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        get_status = _route_endpoint(app, "/api/status")
        get_current = _route_endpoint(app, "/api/mission/current")
        start_mission = _route_endpoint(app, "/api/mission/start", "POST")

        status = get_status()
        assert status.adapter_mode == "mock"
        assert status.sensor_statuses["realsense"]["enabled"] is False

        telemetry = app.state.runtime.telemetry.get_latest()
        assert telemetry.mode.value in {"AUTO", "MANUAL", "ESTOP"}
        assert telemetry.robot_state.battery_percent is not None
        assert telemetry.robot_state.camera_status == "Live via mock camera"

        recent_events = app.state.runtime.events.recent()
        assert any(event["event"] == "server_started" for event in recent_events)

        camera_bytes = app.state.runtime.camera.get_latest_jpeg()
        assert camera_bytes is not None
        assert camera_bytes[:2] == b"\xff\xd8"

        response = start_mission(MissionStartRequest(route_id="demo_route"))
        assert response.ok is True

        deadline = time.time() + 3.0
        completed = False
        while time.time() < deadline:
            current = get_current()
            if current.mission_status.value == "COMPLETED":
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

    with started_app(config_path) as app:
        activate_robot = _route_endpoint(app, "/api/robot/activate", "POST")
        response = activate_robot()

    assert response.ok is True


def test_manual_state_endpoint_reports_motion_diagnostics() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        manual_stand_up = _route_endpoint(app, "/api/robot/manual/stand-up", "POST")
        manual_state = _route_endpoint(app, "/api/robot/manual/state")
        manual_cmd = _route_endpoint(app, "/api/robot/manual/cmd", "POST")

        stand = manual_stand_up()
        assert stand.ok is True

        state = manual_state()
        assert state.robot_mode.value == "MANUAL"
        assert state.motion.current_mode.value in {"manual", "settling"}
        assert state.motion.last_stand_up_return_code == 0

        cmd = manual_cmd(TeleopCommandRequest(vx=0.0, vy=0.25, vyaw=0.0))
        assert cmd.ok is True

        deadline = time.time() + 1.0
        latest_state = state
        while time.time() < deadline:
            latest_state = manual_state()
            if latest_state.motion.target.vy == 0.25:
                break
            time.sleep(0.05)

        assert latest_state.motion.target.vy == 0.25
        assert latest_state.motion.manual_control_active is True


def test_inline_mission_supports_initial_strafe_step() -> None:
    config_path = write_test_config()

    with started_app(config_path) as app:
        run_mission = _route_endpoint(app, "/api/missions/run", "POST")
        mission_state = _route_endpoint(app, "/api/missions/state")

        response = run_mission(
            MissionRunRequest(
                route_id="inline_strafe_demo",
                steps=[
                    {"id": "stand_1", "type": "stand_up"},
                    {"id": "strafe_1", "type": "move_velocity", "vx": 0.0, "vy": 0.25, "vyaw": 0.0, "duration_sec": 0.3},
                    {"id": "stop_1", "type": "stop"},
                ],
            )
        )
        assert response.ok is True

        deadline = time.time() + 5.0
        latest = mission_state()
        while time.time() < deadline:
            latest = mission_state()
            if latest.mission_status.value == "COMPLETED":
                break
            time.sleep(0.05)

        assert latest.mission_status.value == "COMPLETED"

        pose = app.state.runtime.adapter.get_pose()
        assert pose is not None
        assert abs(pose.y) > 0.03
