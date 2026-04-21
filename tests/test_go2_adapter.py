"""Tests for adapter selection, Go2RobotAdapter safety behaviour, and control priority.

All tests are hardware-free. SDK-dependent paths are exercised by patching
``src.robot.go2_adapter.SDK_AVAILABLE`` so the real DDS stack is never touched.
"""

from __future__ import annotations

import time
import unittest.mock as mock
from types import SimpleNamespace

import pytest

from src.control import ControlCore
from src.models import CommandSource, MissionStatus, MotionCommand
from src.robot.robot_adapter import AdapterCapabilities, MockRobotAdapter, build_robot_adapter


# ---------------------------------------------------------------------------
# 1. Adapter selection — mock mode
# ---------------------------------------------------------------------------

def test_adapter_selection_mock():
    adapter = build_robot_adapter("mock", width=320, height=240)
    assert isinstance(adapter, MockRobotAdapter)
    assert adapter.capabilities.has_camera is True
    assert adapter.capabilities.has_pose is True


# ---------------------------------------------------------------------------
# 2. Adapter selection — go2 mode reports missing SDK on connect
# ---------------------------------------------------------------------------

def test_adapter_selection_go2_sdk_missing():
    """build_robot_adapter('go2') can construct, but connect() must fail clearly without the SDK."""
    import src.robot.go2_adapter as _mod  # ensure module is loaded first

    with mock.patch.object(_mod, "SDK_AVAILABLE", False):
        adapter = build_robot_adapter("go2")
        with pytest.raises(RuntimeError, match="unitree_sdk2py"):
            adapter.connect()


# ---------------------------------------------------------------------------
# 3. MockRobotAdapter.stop() is idempotent
# ---------------------------------------------------------------------------

def test_mock_stop_is_idempotent():
    adapter = MockRobotAdapter(width=320, height=240)
    adapter.connect()
    adapter.send_velocity(0.3, 0.0, 0.5)
    adapter.stop()
    adapter.stop()
    adapter.stop()  # third call must not raise
    state = adapter.get_state()
    assert state.faults == []  # still connected, no fault


# ---------------------------------------------------------------------------
# 4. go2 adapter returns None from get_camera_frame when camera_enabled=False
# ---------------------------------------------------------------------------

def test_mock_camera_returns_none_when_disabled():
    """Go2RobotAdapter with camera_enabled=False always returns None for camera frames.

    Uses the real Go2RobotAdapter (SDK is present in this environment) but
    never calls connect(), so no network activity occurs.
    """
    from src.robot.go2_adapter import Go2RobotAdapter

    adapter = Go2RobotAdapter(interface_name=None, camera_enabled=False)
    assert adapter.capabilities.has_camera is False
    assert adapter.get_camera_frame() is None


def test_go2_adapter_sit_down_uses_stand_down_sdk_command():
    from src.robot.go2_adapter import Go2RobotAdapter

    calls: list[str] = []

    class DummySport:
        def Sit(self) -> None:
            calls.append("Sit")

        def StandDown(self) -> None:
            calls.append("StandDown")

    adapter = Go2RobotAdapter(interface_name=None, camera_enabled=False)
    adapter._sport = DummySport()  # type: ignore[attr-defined]

    adapter.sit_down()

    assert calls == ["StandDown"]


def test_go2_adapter_activate_uses_stand_sequence_once():
    from src.robot.go2_adapter import Go2RobotAdapter
    import src.robot.go2_adapter as _mod

    calls: list[str] = []

    class DummySport:
        def StandUp(self) -> int:
            calls.append("StandUp")
            return 0

        def BalanceStand(self) -> int:
            calls.append("BalanceStand")
            return 0

    adapter = Go2RobotAdapter(interface_name=None, camera_enabled=False)
    adapter._sport = DummySport()  # type: ignore[attr-defined]

    with mock.patch.object(_mod.time, "sleep") as sleep:
        adapter.activate()
        adapter.activate()  # second call is no-op

    # StandUp then BalanceStand, exactly once (second activate() is skipped)
    assert calls == ["StandUp", "BalanceStand"]
    assert sleep.call_count == 2


def test_go2_adapter_stop_preserves_posture_but_estop_damps():
    from src.robot.go2_adapter import Go2RobotAdapter

    calls: list[str] = []

    class DummySport:
        def StopMove(self) -> None:
            calls.append("StopMove")

        def Damp(self) -> None:
            calls.append("Damp")

    adapter = Go2RobotAdapter(interface_name=None, camera_enabled=False)
    adapter._sport = DummySport()  # type: ignore[attr-defined]

    adapter.stop()
    adapter.emergency_stop()

    assert calls == ["StopMove", "StopMove", "Damp"]


def test_go2_adapter_manual_mode_uses_sport_client_move():
    """Manual mode send_velocity routes through SportClient.Move directly."""
    from src.robot.go2_adapter import Go2RobotAdapter

    calls: list[object] = []

    class DummySport:
        def Move(self, vx: float, vy: float, vyaw: float) -> int:
            calls.append(("sport.Move", vx, vy, vyaw))
            return 0

        def StopMove(self) -> int:
            calls.append("sport.StopMove")
            return 0

    adapter = Go2RobotAdapter(interface_name=None, camera_enabled=False)
    adapter._sport = DummySport()  # type: ignore[attr-defined]

    adapter.enter_manual_mode()
    adapter.send_velocity(0.25, 0.15, -0.4)
    adapter.exit_manual_mode()

    assert ("sport.Move", 0.25, 0.15, -0.4) in calls


def test_go2_adapter_get_state_includes_battery_and_detailed_fault_text():
    from src.robot.go2_adapter import Go2RobotAdapter

    adapter = Go2RobotAdapter(interface_name=None, camera_enabled=True)
    adapter._latest_state = SimpleNamespace(  # type: ignore[attr-defined]
        error_code=100,
        mode=7,
        imu_state=SimpleNamespace(rpy=[0.0, 0.0, 1.25]),
        position=[0.0, 0.0, 0.0],
    )
    adapter._latest_low_state = SimpleNamespace(  # type: ignore[attr-defined]
        bms_state=SimpleNamespace(soc=87, status=3, cycle=21),
        power_v=28.74,
        power_a=4.21,
    )
    adapter._service_states = {"sport_mode": 0}  # type: ignore[attr-defined]
    adapter._camera_status = "Live via Unitree VideoClient."  # type: ignore[attr-defined]

    state = adapter.get_state()

    assert state.battery_percent == 87.0
    assert state.battery_voltage_v == 28.74
    assert state.battery_current_a == 4.21
    assert state.battery_cycles == 21
    assert state.imu_yaw == 1.25
    assert state.camera_status == "Live via Unitree VideoClient."
    assert any("0x00000064" in fault for fault in state.faults)
    assert any("active bits: 2, 5, 6" in fault for fault in state.faults)
    assert any("BMS status flag is 0x03" in fault for fault in state.faults)
    assert any("sport_mode" in fault for fault in state.faults)


def test_go2_adapter_prefers_video_client_for_camera_frames():
    from src.robot.go2_adapter import Go2RobotAdapter

    jpeg_bytes = b"\xff\xd8unitree\xff\xd9"

    class DummyVideoClient:
        def GetImageSample(self) -> tuple[int, bytes]:
            return 0, jpeg_bytes

    adapter = Go2RobotAdapter(interface_name=None, camera_enabled=True)
    adapter._video_client = DummyVideoClient()  # type: ignore[attr-defined]

    frame = adapter.get_camera_frame()

    assert frame == jpeg_bytes
    assert adapter._cap is None  # type: ignore[attr-defined]
    assert adapter.get_state().camera_status == "Live via Unitree VideoClient."


# ---------------------------------------------------------------------------
# 5. Go2RobotAdapter connect raises clearly when SDK is absent
# ---------------------------------------------------------------------------

def test_go2_adapter_graceful_no_sdk():
    """connect() must raise RuntimeError with 'unitree_sdk2py' in message."""
    import src.robot.go2_adapter as _mod

    with mock.patch.object(_mod, "SDK_AVAILABLE", False):
        from src.robot.go2_adapter import Go2RobotAdapter

        adapter = Go2RobotAdapter(interface_name="eth0", camera_enabled=False)
        with pytest.raises(RuntimeError) as exc_info:
            adapter.connect()

    assert "unitree_sdk2py" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Shared helper adapter for control-priority tests
# ---------------------------------------------------------------------------

class _RecordingAdapter:
    """Minimal adapter stub that records calls; satisfies ControlCore duck-typing."""

    def __init__(self) -> None:
        self.velocity_commands: list[tuple[float, float, float]] = []
        self.stop_count: int = 0
        self.estop_count: int = 0
        self.manual_enter_count: int = 0
        self.manual_exit_count: int = 0

    def stop(self) -> int:
        self.stop_count += 1
        return 0

    def emergency_stop(self) -> None:
        self.estop_count += 1

    def enter_manual_mode(self) -> None:
        self.manual_enter_count += 1

    def exit_manual_mode(self) -> None:
        self.manual_exit_count += 1

    def sit_down(self) -> None:
        self.stop_count += 1

    def stand_up(self) -> int:
        return 0

    def activate(self) -> int:
        return self.stand_up()

    def send_velocity(self, vx: float, vy: float, vyaw: float) -> int:
        self.velocity_commands.append((vx, vy, vyaw))
        return 0


# ---------------------------------------------------------------------------
# 6. ESTOP blocks send_velocity — MockRobotAdapter
# ---------------------------------------------------------------------------

def test_control_priority_mock():
    """ESTOP must block all motion commands regardless of adapter type (mock)."""
    adapter = MockRobotAdapter(width=320, height=240)
    adapter.connect()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vy=0.5, max_vyaw=1.0, watchdog_timeout_ms=500)
    control.start()
    try:
        assert control.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
        assert control.latch_estop()
        assert not control.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
        assert control.current().mission_status == MissionStatus.ESTOPPED
    finally:
        control.shutdown()
        adapter.disconnect()


# ---------------------------------------------------------------------------
# 7. ESTOP blocks send_velocity — stub that mimics Go2RobotAdapter surface
# ---------------------------------------------------------------------------

def test_control_priority_go2_mock():
    """ESTOP must block all motion commands regardless of adapter type (go2 stub).

    The stub has the same stop()/send_velocity() surface as Go2RobotAdapter
    without requiring a real SDK connection.
    """
    adapter = _RecordingAdapter()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vy=0.5, max_vyaw=1.0, watchdog_timeout_ms=500)
    control.start()
    try:
        control.begin_mission("mission-1", "route-1")
        control.mark_running()
        # One accepted command before ESTOP
        assert control.submit(MotionCommand(vx=0.3), CommandSource.AUTO)
        deadline = time.time() + 1.0
        while time.time() < deadline and len(adapter.velocity_commands) == 0:
            time.sleep(0.02)
        assert len(adapter.velocity_commands) >= 1

        assert control.latch_estop()

        # All subsequent commands rejected; stop() called at least once
        assert not control.submit(MotionCommand(vx=0.3), CommandSource.AUTO)
        assert len(adapter.velocity_commands) >= 1
        assert adapter.estop_count >= 1
        assert control.current().mission_status == MissionStatus.ESTOPPED
    finally:
        control.shutdown()
