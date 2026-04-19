from __future__ import annotations

import threading
import time
from collections.abc import Callable

from .models import CommandSource, MissionCurrentResponse, MissionStatus, MotionCommand, RobotMode


TERMINAL_STATUSES = {
    MissionStatus.COMPLETED,
    MissionStatus.ABORTED,
    MissionStatus.FAILED,
    MissionStatus.ESTOPPED,
}


class ControlCore:
    def __init__(
        self,
        adapter,
        max_vx: float,
        max_vyaw: float,
        watchdog_timeout_ms: int,
        event_callback: Callable[[str, dict], None] | None = None,
    ) -> None:
        self.adapter = adapter
        self.max_vx = max_vx
        self.max_vyaw = max_vyaw
        self.watchdog_timeout_s = watchdog_timeout_ms / 1000.0
        self.event_callback = event_callback

        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._stop_event = threading.Event()
        self._watchdog_thread: threading.Thread | None = None

        self.mode = RobotMode.AUTO
        self.mission_status = MissionStatus.IDLE
        self.estop_latched = False
        self.mission_id: str | None = None
        self.route_id: str | None = None
        self.active_step_id: str | None = None
        self.steps_executed = 0
        self.last_teleop_ts = 0.0
        self._abort_requested = False
        self._watchdog_fired = False

    def start(self) -> None:
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, name="control-watchdog", daemon=True)
        self._watchdog_thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=1.0)
        self.sit_down()

    def can_start_mission(self) -> bool:
        with self._lock:
            return (
                not self.estop_latched
                and self.mode == RobotMode.AUTO
                and self.mission_status not in {MissionStatus.STARTING, MissionStatus.RUNNING, MissionStatus.PAUSED_MANUAL}
            )

    def begin_mission(self, mission_id: str, route_id: str) -> None:
        with self._condition:
            if not self.can_start_mission():
                raise RuntimeError("Mission cannot start in the current control state.")
            self.mission_id = mission_id
            self.route_id = route_id
            self.active_step_id = None
            self.steps_executed = 0
            self._abort_requested = False
            self.mission_status = MissionStatus.STARTING
            self._condition.notify_all()
        self._emit("mission_started", {"mission_id": mission_id, "route_id": route_id})

    def mark_running(self) -> None:
        with self._condition:
            if self.mission_status == MissionStatus.STARTING:
                self.mission_status = MissionStatus.RUNNING
                self._condition.notify_all()
        self._emit("mission_running", {"mission_id": self.mission_id, "route_id": self.route_id})

    def set_active_step(self, step_id: str | None) -> None:
        with self._lock:
            self.active_step_id = step_id

    def mark_step_completed(self) -> None:
        with self._lock:
            self.steps_executed += 1

    def pause_mission(self, reason: str = "operator_pause") -> bool:
        with self._condition:
            if self.mission_status not in {MissionStatus.STARTING, MissionStatus.RUNNING}:
                return False
            self.mission_status = MissionStatus.PAUSED_MANUAL
            self._condition.notify_all()
        self.adapter.stop()
        self._emit("mission_paused", {"reason": reason, "mission_id": self.mission_id})
        return True

    def take_manual(self) -> bool:
        with self._condition:
            if self.estop_latched or self.mode == RobotMode.MANUAL:
                return False
            previous_mode = self.mode
            previous_status = self.mission_status
            self.mode = RobotMode.MANUAL
            self.last_teleop_ts = time.monotonic()
            self._watchdog_fired = False
            pause_needed = self.mission_status in {MissionStatus.STARTING, MissionStatus.RUNNING}
            if pause_needed:
                self.mission_status = MissionStatus.PAUSED_MANUAL
            self._condition.notify_all()
        try:
            self.adapter.enter_manual_mode()
            self.adapter.stop()
        except Exception:
            try:
                self.adapter.exit_manual_mode()
            except Exception:
                pass
            with self._condition:
                self.mode = previous_mode
                self.mission_status = previous_status
                self.last_teleop_ts = 0.0
                self._watchdog_fired = False
                self._condition.notify_all()
            raise
        self._emit("mode_changed", {"from": previous_mode.value, "to": self.mode.value, "reason": "manual_take"})
        if pause_needed:
            self._emit("mission_paused", {"reason": "manual_takeover", "mission_id": self.mission_id})
        return True

    def release_manual(self) -> bool:
        with self._condition:
            if self.mode != RobotMode.MANUAL:
                return False
            previous_mode = self.mode
            self.mode = RobotMode.AUTO
            self._condition.notify_all()
        try:
            self.adapter.stop()
            self.adapter.exit_manual_mode()
        except Exception:
            with self._condition:
                self.mode = previous_mode
                self._condition.notify_all()
            raise
        self._emit("mode_changed", {"from": previous_mode.value, "to": self.mode.value, "reason": "manual_release"})
        return True

    def resume_mission(self) -> bool:
        with self._condition:
            if self.estop_latched or self.mode != RobotMode.AUTO or self.mission_status != MissionStatus.PAUSED_MANUAL:
                return False
            self.mission_status = MissionStatus.RUNNING
            self._condition.notify_all()
        self._emit("mission_resumed", {"mission_id": self.mission_id})
        return True

    def abort_mission(self) -> bool:
        with self._condition:
            if self.mission_status in TERMINAL_STATUSES | {MissionStatus.IDLE}:
                return False
            self._abort_requested = True
            self.mission_status = MissionStatus.ABORTED
            self._condition.notify_all()
        self.adapter.stop()
        self._emit("mission_aborted", {"mission_id": self.mission_id})
        return True

    def sit_down(self) -> bool:
        with self._condition:
            active_mission = self.mission_status in {MissionStatus.STARTING, MissionStatus.RUNNING, MissionStatus.PAUSED_MANUAL}
            if active_mission:
                self._abort_requested = True
                self.mission_status = MissionStatus.ABORTED
                self._condition.notify_all()

        self.adapter.sit_down()
        self._emit("robot_seated", {"mission_id": self.mission_id, "active_mission": active_mission})
        return True

    def activate_robot(self) -> bool:
        with self._lock:
            if self.estop_latched:
                return False

        self.adapter.activate()
        self._emit("robot_activated", {"mission_id": self.mission_id, "robot_mode": self.mode.value})
        return True

    def complete_mission(self) -> None:
        with self._condition:
            if self.mission_status not in TERMINAL_STATUSES:
                self.mission_status = MissionStatus.COMPLETED
                self.active_step_id = None
                self._condition.notify_all()
        self._emit("mission_completed", {"mission_id": self.mission_id, "steps_executed": self.steps_executed})

    def fail_mission(self, error: str) -> None:
        with self._condition:
            self.mission_status = MissionStatus.FAILED
            self.active_step_id = None
            self._condition.notify_all()
        self.adapter.stop()
        self._emit("error", {"message": error, "mission_id": self.mission_id})

    def latch_estop(self) -> bool:
        with self._condition:
            if self.estop_latched:
                return False
            previous_mode = self.mode
            self.estop_latched = True
            self.mode = RobotMode.ESTOP
            self._abort_requested = True
            self.mission_status = MissionStatus.ESTOPPED
            self._condition.notify_all()
        self.adapter.emergency_stop()
        self._emit("mode_changed", {"from": previous_mode.value, "to": self.mode.value, "reason": "estop"})
        self._emit("estop_latched", {"mission_id": self.mission_id})
        return True

    def reset_estop(self) -> bool:
        with self._condition:
            if not self.estop_latched:
                return False
            previous_mode = self.mode
            self.estop_latched = False
            self.mode = RobotMode.AUTO
            self._condition.notify_all()
        self._emit("mode_changed", {"from": previous_mode.value, "to": self.mode.value, "reason": "reset_estop"})
        self._emit("estop_reset", {"mission_id": self.mission_id})
        return True

    def submit(self, command: MotionCommand, source: CommandSource) -> bool:
        with self._lock:
            if self.estop_latched:
                should_stop = True
                accepted = False
                vx = vy = vyaw = 0.0
            else:
                should_stop = False
                accepted = self._can_accept_locked(source)
                vx = max(-self.max_vx, min(self.max_vx, command.vx))
                vy = max(-self.max_vx, min(self.max_vx, command.vy))
                vyaw = max(-self.max_vyaw, min(self.max_vyaw, command.vyaw))
                if accepted and source == CommandSource.MANUAL:
                    self.last_teleop_ts = time.monotonic()
                    self._watchdog_fired = False

        if should_stop:
            self.adapter.stop()
            return False

        if not accepted:
            return False

        if abs(vx) < 1e-6 and abs(vy) < 1e-6 and abs(vyaw) < 1e-6:
            self.adapter.stop()
        else:
            self.adapter.send_velocity(vx, vy, vyaw)
        return True

    def stop_motion(self) -> None:
        self.submit(MotionCommand(), CommandSource.SYSTEM)

    def wait_until_runnable(self) -> bool:
        with self._condition:
            while not self._stop_event.is_set():
                if self.estop_latched:
                    return False
                if self._abort_requested or self.mission_status in TERMINAL_STATUSES:
                    return False
                if self.mission_status == MissionStatus.PAUSED_MANUAL:
                    self._condition.wait(timeout=0.1)
                    continue
                return True
            return False

    def current(self) -> MissionCurrentResponse:
        with self._lock:
            return MissionCurrentResponse(
                mission_id=self.mission_id,
                route_id=self.route_id,
                mission_status=self.mission_status,
                robot_mode=self.mode,
                active_step_id=self.active_step_id,
                steps_executed=self.steps_executed,
                paused=self.mission_status == MissionStatus.PAUSED_MANUAL,
                estop_latched=self.estop_latched,
            )

    def _can_accept_locked(self, source: CommandSource) -> bool:
        if source == CommandSource.SYSTEM:
            return True
        if source == CommandSource.AUTO:
            return self.mode != RobotMode.MANUAL
        if source == CommandSource.MANUAL:
            return self.mode == RobotMode.MANUAL
        return False

    def _watchdog_loop(self) -> None:
        while not self._stop_event.wait(0.05):
            should_stop = False
            captured_ts: float = 0.0
            with self._lock:
                if (
                    self.mode == RobotMode.MANUAL
                    and not self._watchdog_fired
                    and self.last_teleop_ts
                    and time.monotonic() - self.last_teleop_ts > self.watchdog_timeout_s
                ):
                    self._watchdog_fired = True
                    should_stop = True
                    captured_ts = self.last_teleop_ts
            if should_stop:
                # Re-check: a concurrent submit() may have arrived between lock release and here.
                # If last_teleop_ts changed, that submit() already called send_velocity(); don't stop.
                with self._lock:
                    if self.last_teleop_ts != captured_ts:
                        self._watchdog_fired = False
                        should_stop = False
            if should_stop:
                self.adapter.stop()
                self._emit("warning", {"message": "manual teleop watchdog timeout", "kind": "watchdog_timeout"})

    def _emit(self, event: str, details: dict) -> None:
        if self.event_callback:
            self.event_callback(event, details)
