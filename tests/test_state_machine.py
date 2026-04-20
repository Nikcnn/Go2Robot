from __future__ import annotations

from src.models import RobotState
from src.state_machine import (
    EffectiveState,
    RobotStateMachine,
    derive_state,
)
from src.event_log import PersistentEventLog
from tests import make_test_dir


def _rs(**kw) -> RobotState:
    return RobotState(**kw)


# --------------------------------------------------------------------------- #
# derive_state — pure function                                                 #
# --------------------------------------------------------------------------- #

def test_disconnected_when_not_connected():
    assert derive_state(False, None, False) == EffectiveState.DISCONNECTED


def test_estop_overrides_everything():
    assert derive_state(True, _rs(), True) == EffectiveState.ESTOP
    assert derive_state(False, None, True) == EffectiveState.ESTOP


def test_connecting_when_no_telemetry_yet():
    assert derive_state(True, None, False) == EffectiveState.CONNECTING


def test_ready_when_connected():
    assert derive_state(True, _rs(), False) == EffectiveState.READY


def test_moving():
    assert derive_state(True, _rs(), False, is_moving=True) == EffectiveState.MOVING


def test_paused():
    assert derive_state(True, _rs(), False, is_moving=False, is_paused=True) == EffectiveState.PAUSED


def test_paused_takes_priority_over_moving():
    assert derive_state(True, _rs(), False, is_moving=True, is_paused=True) == EffectiveState.PAUSED


# --------------------------------------------------------------------------- #
# movement blocking                                                            #
# --------------------------------------------------------------------------- #

def test_movement_blocked_disconnected():
    sm = RobotStateMachine()
    ok, reason = sm.can_move()
    assert not ok
    assert reason


def test_movement_blocked_estop():
    sm = RobotStateMachine()
    sm.update(True, _rs(), True)
    ok, reason = sm.can_move()
    assert not ok
    assert "estop" in reason.lower() or "e-stop" in reason.lower()


def test_movement_blocked_paused():
    sm = RobotStateMachine()
    sm.update(True, _rs(), False, is_paused=True)
    ok, reason = sm.can_move()
    assert not ok
    assert "paused" in reason.lower()


def test_movement_allowed_in_ready():
    sm = RobotStateMachine()
    sm.update(True, _rs(), False)
    ok, reason = sm.can_move()
    assert ok
    assert reason == ""


def test_movement_allowed_while_moving():
    sm = RobotStateMachine()
    sm.update(True, _rs(), False)
    sm.notify_motion(True)
    sm.update(True, _rs(), False)
    ok, _ = sm.can_move()
    assert ok


# --------------------------------------------------------------------------- #
# State machine transitions and snapshot                                       #
# --------------------------------------------------------------------------- #

def test_state_machine_transition_logged():
    sm = RobotStateMachine()
    _, changed = sm.update(True, _rs(), False)
    assert changed
    snap = sm.snapshot()
    assert snap["last_transition"] is not None


def test_state_machine_no_spurious_transition():
    sm = RobotStateMachine()
    sm.update(True, _rs(), False)
    _, changed = sm.update(True, _rs(), False)
    assert not changed


def test_state_machine_records_ok_command():
    sm = RobotStateMachine()
    sm.record_command_ok("stand_up")
    assert sm.snapshot()["last_command_ok"] == "stand_up"


def test_state_machine_records_rejected_command():
    sm = RobotStateMachine()
    sm.record_command_rejected("stand_up: ESTOP latched")
    assert "stand_up" in sm.snapshot()["last_command_rejected"]


# --------------------------------------------------------------------------- #
# Event log                                                                    #
# --------------------------------------------------------------------------- #

def test_log_entry_accepted_action():
    d = make_test_dir("log_accepted")
    log = PersistentEventLog(d / "events.jsonl")
    record = log.append("info", "action_accepted", "action:stand_up", "ok")
    assert record["category"] == "action_accepted"
    assert record["level"] == "info"
    assert record["event"] == "action:stand_up"


def test_log_entry_rejected_action():
    d = make_test_dir("log_rejected")
    log = PersistentEventLog(d / "events.jsonl")
    record = log.append("warn", "action_rejected", "action:stand_up", "ESTOP latched")
    assert record["category"] == "action_rejected"
    assert record["level"] == "warn"
    assert "ESTOP" in record["message"]


def test_log_persists_to_disk():
    d = make_test_dir("log_persist")
    path = d / "events.jsonl"
    log = PersistentEventLog(path)
    log.append("info", "mission", "mission_started", "started")
    assert path.exists()
    text = path.read_text()
    assert "mission_started" in text


def test_log_query_filters_by_level():
    d = make_test_dir("log_filter_level")
    log = PersistentEventLog(d / "events.jsonl")
    log.append("info", "mission", "ev1", "ok")
    log.append("warn", "fault", "ev2", "bad")
    results = log.query(level="warn")
    assert len(results) == 1
    assert results[0]["level"] == "warn"


def test_log_query_filters_by_category():
    d = make_test_dir("log_filter_cat")
    log = PersistentEventLog(d / "events.jsonl")
    log.append("info", "mission", "m1", "m1")
    log.append("info", "fault", "f1", "f1")
    results = log.query(category="fault")
    assert len(results) == 1
    assert results[0]["category"] == "fault"


def test_log_query_reverse_chronological():
    d = make_test_dir("log_chrono")
    log = PersistentEventLog(d / "events.jsonl")
    for i in range(5):
        log.append("info", "mission", f"ev{i}", f"msg{i}")
    results = log.query(limit=5)
    assert results[0]["event"] == "ev4"


# --------------------------------------------------------------------------- #
# /api/robot/status response shape (smoke test)                               #
# --------------------------------------------------------------------------- #

def _make_mock_app():
    from fastapi.testclient import TestClient
    from src.api import create_app
    from src.config import (
        AppConfig, RobotConfig, TelemetryConfig, CameraConfig,
        ControlConfig, AnalysisConfig, ServerConfig, StorageConfig, LoggingConfig,
    )
    d = make_test_dir("api_status")
    config_file = d / "config" / "app_config.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("robot:\n  mode: mock\n")
    config = AppConfig(
        robot=RobotConfig(mode="mock"),
        telemetry=TelemetryConfig(),
        camera=CameraConfig(),
        control=ControlConfig(),
        analysis=AnalysisConfig(),
        server=ServerConfig(),
        storage=StorageConfig(runs_dir=str(d / "runs")),
        logging=LoggingConfig(),
    )
    return TestClient(create_app(config=config, config_path=config_file))


def test_robot_status_endpoint_shape():
    """Smoke test: /api/robot/status must return the required keys."""
    with _make_mock_app() as client:
        resp = client.get("/api/robot/status")
        assert resp.status_code == 200
        data = resp.json()
        for key in [
            "connection", "battery", "faults", "pose",
            "last_command_ok", "last_command_rejected", "last_transition_ts",
        ]:
            assert key in data, f"missing key: {key}"


def test_robot_history_endpoint():
    """Smoke test: /api/robot/history returns a records list."""
    with _make_mock_app() as client:
        resp = client.get("/api/robot/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data
        assert "count" in data
