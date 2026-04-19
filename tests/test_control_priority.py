from __future__ import annotations

import time

import pytest

from src.control import ControlCore
from src.models import CommandSource, MissionStatus, MotionCommand


class DummyAdapter:
    can_move = True
    block_reason = None

    def __init__(self) -> None:
        self.commands: list[tuple[float, float, float]] = []
        self.stop_count = 0
        self.estop_count = 0
        self.sit_count = 0
        self.activate_count = 0
        self.manual_enter_count = 0
        self.manual_exit_count = 0

    def stop(self) -> None:
        self.stop_count += 1

    def emergency_stop(self) -> None:
        self.estop_count += 1

    def sit_down(self) -> None:
        self.sit_count += 1

    def activate(self) -> None:
        self.activate_count += 1

    def enter_manual_mode(self) -> None:
        self.manual_enter_count += 1

    def exit_manual_mode(self) -> None:
        self.manual_exit_count += 1

    def send_velocity(self, vx: float, vy: float, vyaw: float) -> None:
        self.commands.append((vx, vy, vyaw))


def test_estop_blocks_all_motion() -> None:
    adapter = DummyAdapter()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vyaw=1.0, watchdog_timeout_ms=200)
    control.start()
    try:
        assert control.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
        assert control.latch_estop()
        assert not control.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
        assert adapter.estop_count >= 1
        assert control.current().mission_status == MissionStatus.ESTOPPED
    finally:
        control.shutdown()


def test_manual_blocks_auto_and_requires_explicit_resume() -> None:
    adapter = DummyAdapter()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vyaw=1.0, watchdog_timeout_ms=200)
    control.start()
    try:
        control.begin_mission("mission-1", "route-1")
        control.mark_running()
        assert control.take_manual()
        assert adapter.manual_enter_count == 1
        assert control.current().mission_status == MissionStatus.PAUSED_MANUAL
        assert not control.submit(MotionCommand(vx=0.2), CommandSource.AUTO)
        assert control.release_manual()
        assert adapter.manual_exit_count == 1
        assert control.current().mission_status == MissionStatus.PAUSED_MANUAL
        assert control.resume_mission()
        assert control.current().mission_status == MissionStatus.RUNNING
    finally:
        control.shutdown()


def test_take_manual_reverts_state_when_adapter_manual_entry_fails() -> None:
    class FailingAdapter(DummyAdapter):
        def enter_manual_mode(self) -> None:
            super().enter_manual_mode()
            raise RuntimeError("manual mode unavailable")

    adapter = FailingAdapter()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vyaw=1.0, watchdog_timeout_ms=200)
    control.start()
    try:
        with pytest.raises(RuntimeError, match="manual mode unavailable"):
            control.take_manual()
        assert control.current().robot_mode.value == "AUTO"
        assert adapter.manual_enter_count == 1
        assert adapter.manual_exit_count == 1
    finally:
        control.shutdown()


def test_watchdog_stops_stale_manual_teleop() -> None:
    adapter = DummyAdapter()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vyaw=1.0, watchdog_timeout_ms=120)
    control.start()
    try:
        assert control.take_manual()
        assert control.submit(MotionCommand(vx=0.2), CommandSource.MANUAL)
        deadline = time.time() + 1.0
        while time.time() < deadline and adapter.stop_count == 0:
            time.sleep(0.02)
        assert adapter.stop_count >= 1
    finally:
        control.shutdown()


def test_watchdog_does_not_fire_before_first_manual_teleop_command() -> None:
    adapter = DummyAdapter()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vyaw=1.0, watchdog_timeout_ms=120)
    control.start()
    try:
        assert control.take_manual()
        stop_count_after_take_manual = adapter.stop_count
        time.sleep(0.2)
        assert adapter.stop_count == stop_count_after_take_manual
    finally:
        control.shutdown()


def test_activate_robot_calls_adapter_when_estop_is_clear() -> None:
    adapter = DummyAdapter()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vyaw=1.0, watchdog_timeout_ms=200)
    control.start()
    try:
        assert control.activate_robot()
        assert adapter.activate_count == 1
        assert control.latch_estop()
        assert not control.activate_robot()
        assert adapter.activate_count == 1
    finally:
        control.shutdown()


def test_shutdown_requests_sit_down() -> None:
    adapter = DummyAdapter()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vyaw=1.0, watchdog_timeout_ms=200)
    control.start()
    try:
        control.shutdown()
        assert adapter.sit_count >= 1
    finally:
        pass


def test_sit_down_aborts_active_mission_and_seats_robot() -> None:
    adapter = DummyAdapter()
    control = ControlCore(adapter=adapter, max_vx=0.5, max_vyaw=1.0, watchdog_timeout_ms=200)
    control.start()
    try:
        control.begin_mission("mission-1", "route-1")
        control.mark_running()
        assert control.sit_down()
        assert control.current().mission_status == MissionStatus.ABORTED
        assert adapter.sit_count >= 1
    finally:
        control.shutdown()
