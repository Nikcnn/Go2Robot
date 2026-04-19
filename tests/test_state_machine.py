from __future__ import annotations

from src.models import RobotState
from src.state_machine import (
    EffectiveState,
    RobotStateMachine,
    decode_bms_flags,
    decode_sport_error,
    derive_state,
)
from src.event_log import PersistentEventLog
from tests import make_test_dir


# --------------------------------------------------------------------------- #
# derive_state — pure function                                                 #
# --------------------------------------------------------------------------- #

def _rs(**kw) -> RobotState:
    """Convenience factory for minimal RobotState objects."""
    return RobotState(**kw)


def test_disconnected_when_not_connected():
    assert derive_state(False, None, False) == EffectiveState.DISCONNECTED


def test_estop_overrides_everything():
    # Estop must win even over disconnected or active states
    assert derive_state(True, _rs(sport_mode_error=0, motion_mode=3), True) == EffectiveState.ESTOP
    assert derive_state(False, None, True) == EffectiveState.ESTOP


def test_connecting_when_no_telemetry_yet():
    assert derive_state(True, None, False) == EffectiveState.CONNECTING


def test_connecting_when_motion_mode_none():
    # motion_mode=None means DDS message not yet received
    assert derive_state(True, _rs(sport_mode_error=0, motion_mode=None), False) == EffectiveState.CONNECTING


def test_idle_motion_mode():
    state = _rs(sport_mode_error=0, motion_mode=0)
    assert derive_state(True, state, False) == EffectiveState.IDLE


def test_standing_balancestand():
    state = _rs(sport_mode_error=0, motion_mode=1)
    assert derive_state(True, state, False) == EffectiveState.STANDING


def test_standing_pose():
    state = _rs(sport_mode_error=0, motion_mode=2)
    assert derive_state(True, state, False) == EffectiveState.STANDING


def test_ready_locomotion():
    state = _rs(sport_mode_error=0, motion_mode=3)
    assert derive_state(True, state, False) == EffectiveState.READY


def test_moving():
    state = _rs(sport_mode_error=0, motion_mode=3)
    assert derive_state(True, state, False, is_moving=True) == EffectiveState.MOVING


def test_paused():
    state = _rs(sport_mode_error=0, motion_mode=3)
    assert derive_state(True, state, False, is_moving=False, is_paused=True) == EffectiveState.PAUSED


def test_paused_takes_priority_over_moving():
    state = _rs(sport_mode_error=0, motion_mode=3)
    assert derive_state(True, state, False, is_moving=True, is_paused=True) == EffectiveState.PAUSED


# --------------------------------------------------------------------------- #
# Sport mode error codes                                                       #
# --------------------------------------------------------------------------- #

def test_damping_error_1001():
    state = _rs(sport_mode_error=1001, motion_mode=7)
    assert derive_state(True, state, False) == EffectiveState.DAMPING


def test_standing_lock_error_1002():
    state = _rs(sport_mode_error=1002, motion_mode=6)
    assert derive_state(True, state, False) == EffectiveState.STANDING_LOCK


def test_unknown_sport_error_code_maps_to_error():
    state = _rs(sport_mode_error=9999, motion_mode=0)
    assert derive_state(True, state, False) == EffectiveState.ERROR


def test_zero_sport_error_is_no_error():
    # error_code=0 means "no error" and should not override motion_mode derivation
    state = _rs(sport_mode_error=0, motion_mode=3)
    assert derive_state(True, state, False) == EffectiveState.READY


# --------------------------------------------------------------------------- #
# movement blocking                                                            #
# --------------------------------------------------------------------------- #

def test_movement_blocked_in_idle():
    sm = RobotStateMachine()
    sm.update(True, _rs(sport_mode_error=0, motion_mode=0), False)
    ok, reason = sm.can_move()
    assert not ok
    assert "idle" in reason.lower()


def test_movement_blocked_in_damping():
    sm = RobotStateMachine()
    sm.update(True, _rs(sport_mode_error=1001, motion_mode=7), False)
    ok, reason = sm.can_move()
    assert not ok
    assert "1001" in reason


def test_movement_blocked_in_standing_lock():
    sm = RobotStateMachine()
    sm.update(True, _rs(sport_mode_error=1002, motion_mode=6), False)
    ok, reason = sm.can_move()
    assert not ok
    assert "1002" in reason


def test_movement_blocked_in_error():
    sm = RobotStateMachine()
    sm.update(True, _rs(sport_mode_error=5000, motion_mode=0), False)
    ok, reason = sm.can_move()
    assert not ok
    assert reason  # must surface a reason


def test_movement_allowed_in_ready():
    sm = RobotStateMachine()
    sm.update(True, _rs(sport_mode_error=0, motion_mode=3), False)
    ok, reason = sm.can_move()
    assert ok
    assert reason == ""


def test_movement_allowed_in_standing():
    sm = RobotStateMachine()
    sm.update(True, _rs(sport_mode_error=0, motion_mode=1), False)
    ok, _ = sm.can_move()
    assert ok


# --------------------------------------------------------------------------- #
# BMS flags                                                                    #
# --------------------------------------------------------------------------- #

def test_bms_0x08_decoded_as_abnormal():
    result = decode_bms_flags(0x08)
    assert result["decoded"] == "abnormal"
    assert result["raw"] == "0x08"


def test_bms_0x00_decoded_as_ok():
    result = decode_bms_flags(0x00)
    assert result["decoded"] == "ok"


def test_bms_none_decoded_as_unknown():
    result = decode_bms_flags(None)
    assert result["decoded"] == "UNKNOWN"
    assert result["raw"] is None


def test_bms_0x08_does_not_block_movement():
    # BMS flag degrades readiness (surface warning) but does NOT change effective state
    state = _rs(sport_mode_error=0, motion_mode=3, bms_status=0x08)
    eff = derive_state(True, state, False)
    assert eff == EffectiveState.READY


# --------------------------------------------------------------------------- #
# Fault decoder                                                                #
# --------------------------------------------------------------------------- #

def test_decode_sport_error_1001():
    result = decode_sport_error(1001)
    assert result["code"] == 1001
    assert result["decoded"] == "damping"


def test_decode_sport_error_1002():
    result = decode_sport_error(1002)
    assert result["code"] == 1002
    assert result["decoded"] == "standing_lock"


def test_decode_sport_error_0():
    result = decode_sport_error(0)
    assert result["code"] == 0
    assert result["decoded"] == "none"


def test_decode_sport_error_unknown():
    result = decode_sport_error(9999)
    assert result["code"] == 9999
    assert result["decoded"] == "UNKNOWN"


def test_decode_sport_error_none():
    result = decode_sport_error(None)
    assert result["code"] is None
    assert result["decoded"] == "UNKNOWN"


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
    # First entry should be the most recent (ev4)
    assert results[0]["event"] == "ev4"


# --------------------------------------------------------------------------- #
# State machine transitions and snapshot                                       #
# --------------------------------------------------------------------------- #

def test_state_machine_transition_logged():
    sm = RobotStateMachine()
    _, changed = sm.update(True, _rs(sport_mode_error=0, motion_mode=3), False)
    assert changed
    snap = sm.snapshot()
    assert snap["effective"] == "ready"
    assert snap["last_transition"] is not None


def test_state_machine_no_spurious_transition():
    sm = RobotStateMachine()
    sm.update(True, _rs(sport_mode_error=0, motion_mode=3), False)
    _, changed = sm.update(True, _rs(sport_mode_error=0, motion_mode=3), False)
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
# Manual override priority                                                     #
# --------------------------------------------------------------------------- #

def test_manual_override_yields_paused_state():
    # When manual mode is taken and mission is paused, is_paused=True
    # effective state should reflect paused, not moving/ready
    state = _rs(sport_mode_error=0, motion_mode=3)
    eff = derive_state(True, state, False, is_moving=True, is_paused=True)
    assert eff == EffectiveState.PAUSED


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
            "connection", "effective_state", "requested_state", "motion_mode",
            "sport_mode_error", "bms_flags", "battery", "pose",
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
