"""Hardware-free lifecycle tests for locomotion state machine, ESTOP, and analysis.

Covers all 7 cases from Part F of the spec.
"""
from __future__ import annotations

import threading
import time
from typing import List
import unittest.mock as mock

import cv2
import pytest

from src.analysis import FrameDiffAnalyzer, NarrowClassifierHook, analyze
from src.control import ControlCore
from src.models import AnalysisResult, CommandSource, MissionStatus, MotionCommand
from src.robot.robot_adapter import MockRobotAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_control(adapter=None, watchdog_ms=500):
    if adapter is None:
        adapter = MockRobotAdapter(width=160, height=120)
        adapter.connect()
    ctrl = ControlCore(adapter=adapter, max_vx=0.5, max_vy=0.5, max_vyaw=1.0, watchdog_timeout_ms=watchdog_ms)
    ctrl.start()
    return ctrl, adapter


# ---------------------------------------------------------------------------
# 1. Move blocked when ESTOP latched
# ---------------------------------------------------------------------------

def test_move_blocked_when_estop_latched():
    ctrl, adapter = _make_control()
    try:
        assert ctrl.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
        assert ctrl.latch_estop()
        # ESTOP: control layer blocks
        assert not ctrl.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
        # adapter is in damped state after emergency_stop
        assert adapter._locomotion_state == "damped"
        assert not adapter.can_move
        assert adapter.block_reason == "robot_damped"
    finally:
        ctrl.shutdown()


# ---------------------------------------------------------------------------
# 2. Move blocked until robot is motion-ready
# ---------------------------------------------------------------------------

def test_move_blocked_until_motion_ready():
    adapter = MockRobotAdapter(width=160, height=120)
    # deliberately NOT calling connect() → locomotion_state = "disconnected"
    ctrl = ControlCore(adapter=adapter, max_vx=0.5, max_vy=0.5, max_vyaw=1.0, watchdog_timeout_ms=500)
    ctrl.start()
    try:
        assert not adapter.can_move
        assert not ctrl.submit(MotionCommand(vx=0.2), CommandSource.AUTO)

        adapter.connect()  # locomotion_state → "ready"
        assert adapter.can_move
        assert ctrl.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
    finally:
        ctrl.shutdown()


# ---------------------------------------------------------------------------
# 3. ensure_motion_ready() called before mission movement
# ---------------------------------------------------------------------------

def test_ensure_motion_ready_called_before_mission():
    from src.mission import MissionManager
    from src.models import RouteModel
    from src.storage import StorageManager
    from tests import make_test_dir

    adapter = MockRobotAdapter(width=160, height=120)
    adapter.connect()

    calls: List[str] = []
    original_ensure = adapter.ensure_motion_ready

    def tracking_ensure(timeout=5.0):
        calls.append("ensure_motion_ready")
        return original_ensure(timeout)

    adapter.ensure_motion_ready = tracking_ensure  # type: ignore[method-assign]

    ctrl = ControlCore(adapter=adapter, max_vx=0.5, max_vy=0.5, max_vyaw=1.0, watchdog_timeout_ms=500)
    ctrl.start()

    runs_dir = make_test_dir("lifecycle_ensure")
    storage = StorageManager(runs_dir)

    # Minimal telemetry stub
    class _FakeTelemetry:
        def get_latest(self):
            from src.models import TelemetrySnapshot, RobotMode, MissionStatus
            from datetime import datetime, timezone
            return TelemetrySnapshot(
                timestamp=datetime.now(timezone.utc),
                mode=RobotMode.AUTO,
                mission_status=MissionStatus.IDLE,
            )

    mission = MissionManager(
        routes_dir=runs_dir,  # won't be used — route injected directly
        project_root=runs_dir,
        control=ctrl,
        adapter=adapter,
        telemetry=_FakeTelemetry(),
        storage=storage,
        analysis_threshold=0.25,
        event_callback=lambda event, details: None,
    )

    route = RouteModel.model_validate({
        "route_id": "test_lifecycle",
        "steps": [
            {"id": "m1", "type": "move", "vx": 0.1, "vy": 0.0, "vyaw": 0.0, "duration_sec": 0.1},
        ],
    })
    run = storage.start_run(route.route_id)
    ctrl.begin_mission(run.mission_id, route.route_id)
    t = threading.Thread(target=mission._run_mission, args=(route,), daemon=True)
    t.start()
    t.join(timeout=3.0)

    assert "ensure_motion_ready" in calls, "ensure_motion_ready() was not called before mission movement"
    ctrl.shutdown()


# ---------------------------------------------------------------------------
# 4. Manual takeover pauses mission; release does NOT auto-resume
# ---------------------------------------------------------------------------

def test_manual_takeover_pauses_and_release_does_not_auto_resume():
    ctrl, adapter = _make_control()
    try:
        ctrl.begin_mission("m1", "r1")
        ctrl.mark_running()

        assert ctrl.take_manual()
        assert ctrl.current().mission_status == MissionStatus.PAUSED_MANUAL

        assert ctrl.release_manual()
        # After releasing manual, mission is still PAUSED_MANUAL (no auto-resume)
        assert ctrl.current().mission_status == MissionStatus.PAUSED_MANUAL

        # Must explicitly resume
        assert ctrl.resume_mission()
        assert ctrl.current().mission_status == MissionStatus.RUNNING
    finally:
        ctrl.shutdown()


# ---------------------------------------------------------------------------
# 5. ESTOP requires explicit reset + activate before new Move()
# ---------------------------------------------------------------------------

def test_estop_requires_reset_and_activate_before_move():
    ctrl, adapter = _make_control()
    try:
        assert ctrl.submit(MotionCommand(vx=0.2), CommandSource.AUTO)

        assert ctrl.latch_estop()
        assert not ctrl.submit(MotionCommand(vx=0.2), CommandSource.AUTO)

        # Reset ESTOP — adapter still damped
        assert ctrl.reset_estop()
        assert not ctrl.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
        assert not adapter.can_move
        assert adapter.block_reason == "robot_damped"

        # Activate — adapter becomes ready
        assert ctrl.activate_robot()
        assert adapter.can_move
        assert ctrl.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
    finally:
        ctrl.shutdown()


# ---------------------------------------------------------------------------
# 6. Checkpoint analysis returns valid AnalysisResult
# ---------------------------------------------------------------------------

def test_checkpoint_analysis_returns_valid_analysis_result():
    import numpy as np

    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    # FrameDiffAnalyzer — no reference → not_configured, still AnalysisResult
    result = FrameDiffAnalyzer().analyze(frame, {"threshold": 0.25})
    assert isinstance(result, AnalysisResult)
    assert result.analyzer_name == "frame_diff"
    assert result.score == 0.0
    assert result.passed is False

    # NarrowClassifierHook — blank frame should be classified as absent
    result2 = NarrowClassifierHook().analyze(frame, {"threshold": 0.5})
    assert isinstance(result2, AnalysisResult)
    assert result2.analyzer_name == "narrow_classifier"
    assert result2.label == "absent"
    assert result2.passed is False

    textured = frame.copy()
    cv2.rectangle(textured, (30, 20), (130, 100), (255, 255, 255), -1)
    result_present = analyze(textured, "simple_presence", {"threshold": 0.25})
    assert isinstance(result_present, AnalysisResult)
    assert result_present.label == "present"
    assert result_present.passed is True

    # analyze() top-level function with unknown analyzer
    result3 = analyze(frame, "unknown_xyz", {})
    assert isinstance(result3, AnalysisResult)
    assert result3.label == "not_configured"
    assert result3.timestamp != ""

    # analyze() with None frame
    result4 = analyze(None, "frame_diff", {})
    assert isinstance(result4, AnalysisResult)
    assert result4.label == "capture_failed"


def test_narrow_classifier_reference_similarity():
    import numpy as np
    from tests import make_test_dir

    reference = np.zeros((96, 96, 3), dtype=np.uint8)
    cv2.rectangle(reference, (20, 18), (76, 78), (255, 255, 255), -1)
    reference_path = make_test_dir("narrow_classifier_ref") / "panel_ref.jpg"
    assert cv2.imwrite(str(reference_path), reference)

    match = NarrowClassifierHook().analyze(
        reference.copy(),
        {"threshold": 0.6, "reference_image": str(reference_path)},
    )
    mismatch = NarrowClassifierHook().analyze(
        np.zeros_like(reference),
        {"threshold": 0.6, "reference_image": str(reference_path)},
    )

    assert match.label == "present"
    assert match.passed is True
    assert mismatch.label == "absent"
    assert mismatch.passed is False


# ---------------------------------------------------------------------------
# 7. Mock mode passes all above (smoke test with MockRobotAdapter)
# ---------------------------------------------------------------------------

def test_mock_mode_estop_blocks_and_recovers():
    adapter = MockRobotAdapter(width=160, height=120)
    adapter.connect()
    assert adapter._locomotion_state == "ready"

    ctrl = ControlCore(adapter=adapter, max_vx=0.5, max_vy=0.5, max_vyaw=1.0, watchdog_timeout_ms=500)
    ctrl.start()
    try:
        assert ctrl.submit(MotionCommand(vx=0.3), CommandSource.AUTO)
        time.sleep(0.1)
        assert adapter._locomotion_state == "moving"

        ctrl.latch_estop()
        assert adapter._locomotion_state == "damped"
        assert not ctrl.submit(MotionCommand(vx=0.3), CommandSource.AUTO)

        ctrl.reset_estop()
        assert not ctrl.submit(MotionCommand(vx=0.3), CommandSource.AUTO)  # still damped

        ctrl.activate_robot()
        assert adapter._locomotion_state == "ready"
        assert ctrl.submit(MotionCommand(vx=0.3), CommandSource.AUTO)
    finally:
        ctrl.shutdown()


def test_mock_mode_ensure_motion_ready_raises_when_damped():
    adapter = MockRobotAdapter(width=160, height=120)
    adapter.connect()
    adapter.emergency_stop()
    assert adapter._locomotion_state == "damped"

    with pytest.raises(RuntimeError, match="damped"):
        adapter.ensure_motion_ready(timeout=0.1)


def test_mock_mode_ensure_motion_ready_passes_when_ready():
    adapter = MockRobotAdapter(width=160, height=120)
    adapter.connect()
    # should not raise
    adapter.ensure_motion_ready(timeout=1.0)
