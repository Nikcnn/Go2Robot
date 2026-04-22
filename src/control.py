from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from .models import (
    CommandSource,
    MissionCurrentResponse,
    MissionStatus,
    MotionCommand,
    MotionDiagnosticsResponse,
    MotionMode,
    RobotMode,
    VelocityTriplet,
)


TERMINAL_STATUSES = {
    MissionStatus.COMPLETED,
    MissionStatus.ABORTED,
    MissionStatus.FAILED,
    MissionStatus.ESTOPPED,
}

_log = logging.getLogger(__name__)

_CONTROL_LOOP_PERIOD_S = 1.0 / 50.0
_STAND_UP_SETTLE_S = 1.75
_MIN_VX = 0.22
_MIN_VY = 0.22
_MIN_VYAW = 0.45
_ACCEL_VX = 0.9
_DECEL_VX = 1.2
_ACCEL_VY = 0.9
_DECEL_VY = 1.2
_ACCEL_VYAW = 2.4
_DECEL_VYAW = 3.2
_AXIS_EPS = 1e-3


@dataclass(frozen=True)
class _Velocity:
    vx: float = 0.0
    vy: float = 0.0
    vyaw: float = 0.0


class ControlCore:
    def __init__(
        self,
        adapter,
        max_vx: float,
        max_vy: float,
        max_vyaw: float,
        watchdog_timeout_ms: int,
        event_callback: Optional[Callable[[str, Dict], None]] = None,
    ) -> None:
        self.adapter = adapter
        self.max_vx = max_vx
        self.max_vy = max_vy
        self.max_vyaw = max_vyaw
        self.watchdog_timeout_s = watchdog_timeout_ms / 1000.0
        self.event_callback = event_callback

        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._stop_event = threading.Event()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._control_thread: Optional[threading.Thread] = None

        self.mode = RobotMode.AUTO
        self.mission_status = MissionStatus.IDLE
        self.estop_latched = False
        self.mission_id: Optional[str] = None
        self.route_id: Optional[str] = None
        self.active_step_id: Optional[str] = None
        self.steps_executed = 0
        self.last_teleop_ts = 0.0
        self._abort_requested = False
        self._watchdog_fired = False

        self._manual_target = _Velocity()
        self._auto_target = _Velocity()
        self._current_velocity = _Velocity()
        self._last_sent_command = _Velocity()
        self._last_nonzero_command: Optional[_Velocity] = None
        self._last_move_return_code: Optional[int] = None
        self._last_stop_return_code: Optional[int] = None
        self._last_stand_up_return_code: Optional[int] = None
        self._last_action_message = "idle"
        self._settle_until = 0.0
        self._explicit_stop_requested = False
        self._stop_sent = True

    def start(self) -> None:
        if not self._control_thread or not self._control_thread.is_alive():
            self._control_thread = threading.Thread(target=self._control_loop, name="control-motion", daemon=True)
            self._control_thread.start()
        if not self._watchdog_thread or not self._watchdog_thread.is_alive():
            self._watchdog_thread = threading.Thread(target=self._watchdog_loop, name="control-watchdog", daemon=True)
            self._watchdog_thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        if self._control_thread:
            self._control_thread.join(timeout=1.0)
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
            self._auto_target = _Velocity()
            self._explicit_stop_requested = False
            self._condition.notify_all()
        self._emit("mission_started", {"mission_id": mission_id, "route_id": route_id})

    def mark_running(self) -> None:
        with self._condition:
            if self.mission_status == MissionStatus.STARTING:
                self.mission_status = MissionStatus.RUNNING
                self._condition.notify_all()
        self._emit("mission_running", {"mission_id": self.mission_id, "route_id": self.route_id})

    def set_active_step(self, step_id: Optional[str]) -> None:
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
            self._reset_motion_locked(
                clear_manual_target=False,
                clear_auto_target=True,
                explicit_stop=True,
                message=f"mission paused: {reason}",
            )
            self._condition.notify_all()
        _log.info("mission paused", extra={"reason": reason, "mission_id": self.mission_id})
        self._emit("mission_paused", {"reason": reason, "mission_id": self.mission_id})
        return True

    def take_manual(self) -> bool:
        with self._condition:
            if self.estop_latched or self.mode == RobotMode.MANUAL:
                return False
            previous_mode = self.mode
            previous_status = self.mission_status
            pause_needed = self.mission_status in {MissionStatus.STARTING, MissionStatus.RUNNING}
            self.mode = RobotMode.MANUAL
            self.last_teleop_ts = time.monotonic()
            self._watchdog_fired = False
            if pause_needed:
                self.mission_status = MissionStatus.PAUSED_MANUAL
            self._condition.notify_all()
        try:
            self.adapter.enter_manual_mode()
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

        self.stop_motion("manual_takeover")
        _log.info("manual control engaged", extra={"mission_id": self.mission_id, "route_id": self.route_id})
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
            self.adapter.exit_manual_mode()
        except Exception:
            with self._condition:
                self.mode = previous_mode
                self._condition.notify_all()
            raise

        self.stop_motion("manual_release")
        _log.info("manual control released", extra={"mission_id": self.mission_id, "route_id": self.route_id})
        self._emit("mode_changed", {"from": previous_mode.value, "to": self.mode.value, "reason": "manual_release"})
        return True

    def clear_manual_target(self) -> bool:
        with self._condition:
            if self.mode != RobotMode.MANUAL:
                return False
            self._manual_target = _Velocity()
            self.last_teleop_ts = time.monotonic()
            self._watchdog_fired = False
            self._last_action_message = "manual target cleared"
            self._condition.notify_all()
        return True

    def stand_up(self) -> Optional[int]:
        with self._lock:
            if self.estop_latched:
                raise RuntimeError("Robot cannot stand up while ESTOP is latched.")

        stand_up = getattr(self.adapter, "stand_up", None)
        if callable(stand_up):
            rc = stand_up()
        else:
            rc = self.adapter.activate()

        with self._condition:
            self._settle_until = time.monotonic() + _STAND_UP_SETTLE_S
            self._current_velocity = _Velocity()
            self._last_sent_command = _Velocity()
            self._stop_sent = False
            self._explicit_stop_requested = False
            self._last_stand_up_return_code = self._normalize_return_code(rc)
            self._last_action_message = "stand_up requested"
            if self.mode == RobotMode.MANUAL:
                self.last_teleop_ts = time.monotonic()
                self._watchdog_fired = False
            self._condition.notify_all()
        _log.info("stand_up requested", extra={"mode": self.mode.value})
        return self._last_stand_up_return_code

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
            self.active_step_id = None
            self._reset_motion_locked(
                clear_manual_target=False,
                clear_auto_target=True,
                explicit_stop=True,
                message="mission aborted",
            )
            self._condition.notify_all()
        _log.info("mission aborted", extra={"mission_id": self.mission_id})
        self._emit("mission_aborted", {"mission_id": self.mission_id})
        return True

    def sit_down(self) -> bool:
        with self._condition:
            active_mission = self.mission_status in {MissionStatus.STARTING, MissionStatus.RUNNING, MissionStatus.PAUSED_MANUAL}
            if active_mission:
                self._abort_requested = True
                self.mission_status = MissionStatus.ABORTED
            self._reset_motion_locked(
                clear_manual_target=True,
                clear_auto_target=True,
                explicit_stop=True,
                message="sit_down requested",
            )
            self._condition.notify_all()

        self.adapter.sit_down()
        self._emit("robot_seated", {"mission_id": self.mission_id, "active_mission": active_mission})
        return True

    def activate_robot(self) -> bool:
        with self._lock:
            if self.estop_latched:
                return False

        self.stand_up()
        self._emit("robot_activated", {"mission_id": self.mission_id, "robot_mode": self.mode.value})
        return True

    def complete_mission(self) -> None:
        with self._condition:
            if self.mission_status not in TERMINAL_STATUSES:
                self.mission_status = MissionStatus.COMPLETED
                self.active_step_id = None
                self._reset_motion_locked(
                    clear_manual_target=False,
                    clear_auto_target=True,
                    explicit_stop=True,
                    message="mission completed",
                )
                self._condition.notify_all()
        self._emit("mission_completed", {"mission_id": self.mission_id, "steps_executed": self.steps_executed})

    def fail_mission(self, error: str) -> None:
        with self._condition:
            self.mission_status = MissionStatus.FAILED
            self.active_step_id = None
            self._reset_motion_locked(
                clear_manual_target=False,
                clear_auto_target=True,
                explicit_stop=True,
                message=f"mission failed: {error}",
            )
            self._condition.notify_all()
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
            self.active_step_id = None
            self._reset_motion_locked(
                clear_manual_target=True,
                clear_auto_target=True,
                explicit_stop=True,
                message="estop latched",
            )
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
            self._reset_motion_locked(
                clear_manual_target=True,
                clear_auto_target=True,
                explicit_stop=True,
                message="estop reset",
            )
            self._condition.notify_all()
        self._emit("mode_changed", {"from": previous_mode.value, "to": self.mode.value, "reason": "reset_estop"})
        self._emit("estop_reset", {"mission_id": self.mission_id})
        return True

    def submit(self, command: MotionCommand, source: CommandSource) -> bool:
        with self._condition:
            if self.estop_latched:
                self._explicit_stop_requested = True
                self._last_action_message = "command rejected: ESTOP latched"
                self._condition.notify_all()
                return False

            accepted = self._can_accept_locked(source)
            if not accepted:
                self._last_action_message = f"{source.value.lower()} command rejected by control priority"
                return False

            if not getattr(self.adapter, "can_move", True):
                self._last_action_message = f"command rejected: adapter cannot move ({getattr(self.adapter, 'block_reason', 'unknown')})"
                return False

            target = _Velocity(
                vx=self._clamp(command.vx, self.max_vx),
                vy=self._clamp(command.vy, self.max_vy),
                vyaw=self._clamp(command.vyaw, self.max_vyaw),
            )

            if source == CommandSource.MANUAL:
                self._manual_target = target
                self.last_teleop_ts = time.monotonic()
                self._watchdog_fired = False
                self._last_action_message = (
                    f"manual target set vx={target.vx:.2f} vy={target.vy:.2f} vyaw={target.vyaw:.2f}"
                )
            elif source == CommandSource.AUTO:
                self._auto_target = target
                self._last_action_message = (
                    f"mission target set vx={target.vx:.2f} vy={target.vy:.2f} vyaw={target.vyaw:.2f}"
                )
            else:
                self._manual_target = target
                self._auto_target = target
                self._last_action_message = (
                    f"system target set vx={target.vx:.2f} vy={target.vy:.2f} vyaw={target.vyaw:.2f}"
                )

            if self._has_motion(target):
                self._explicit_stop_requested = False
                self._stop_sent = False

            self._condition.notify_all()
            return True

    def stop_motion(self, reason: str = "operator_stop") -> None:
        with self._condition:
            self._reset_motion_locked(
                clear_manual_target=True,
                clear_auto_target=True,
                explicit_stop=True,
                message=reason,
            )
            self._condition.notify_all()
        _log.info("motion stop requested", extra={"reason": reason, "mode": self.mode.value})

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

    def wait_for_settle(self) -> bool:
        while not self._stop_event.is_set():
            if not self.wait_until_runnable():
                return False
            with self._lock:
                remaining = max(0.0, self._settle_until - time.monotonic())
            if remaining <= 0.0:
                return True
            time.sleep(min(0.05, remaining))
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

    def motion_state(self) -> MotionDiagnosticsResponse:
        with self._lock:
            target = self._active_target_locked()
            now = time.monotonic()
            return MotionDiagnosticsResponse(
                current_mode=self._derive_motion_mode_locked(now),
                target=self._triplet(target),
                current=self._triplet(self._current_velocity),
                last_nonzero_command=self._triplet(self._last_nonzero_command) if self._last_nonzero_command else None,
                last_move_return_code=self._last_move_return_code,
                last_stop_return_code=self._last_stop_return_code,
                last_stand_up_return_code=self._last_stand_up_return_code,
                last_action_message=self._last_action_message,
                standup_settle_remaining_sec=round(max(0.0, self._settle_until - now), 3),
                manual_control_active=self.mode == RobotMode.MANUAL,
                mission_control_active=self.mission_status in {MissionStatus.STARTING, MissionStatus.RUNNING},
            )

    def _can_accept_locked(self, source: CommandSource) -> bool:
        if source == CommandSource.SYSTEM:
            return True
        if source == CommandSource.AUTO:
            return self.mode != RobotMode.MANUAL
        if source == CommandSource.MANUAL:
            return self.mode == RobotMode.MANUAL
        return False

    def _control_loop(self) -> None:
        last_tick = time.monotonic()
        while not self._stop_event.wait(_CONTROL_LOOP_PERIOD_S):
            now = time.monotonic()
            dt = max(0.0, min(0.25, now - last_tick))
            last_tick = now

            action: Optional[str] = None
            command = _Velocity()

            with self._condition:
                settling = now < self._settle_until
                desired = self._active_target_locked()

                if self.estop_latched or self._explicit_stop_requested or settling:
                    self._current_velocity = _Velocity()
                    effective = _Velocity()
                else:
                    self._current_velocity = _Velocity(
                        vx=self._step_towards(self._current_velocity.vx, desired.vx, dt, _ACCEL_VX, _DECEL_VX),
                        vy=self._step_towards(self._current_velocity.vy, desired.vy, dt, _ACCEL_VY, _DECEL_VY),
                        vyaw=self._step_towards(self._current_velocity.vyaw, desired.vyaw, dt, _ACCEL_VYAW, _DECEL_VYAW),
                    )
                    effective = _Velocity(
                        vx=self._effective_axis(self._current_velocity.vx, desired.vx, _MIN_VX, self.max_vx),
                        vy=self._effective_axis(self._current_velocity.vy, desired.vy, _MIN_VY, self.max_vy),
                        vyaw=self._effective_axis(self._current_velocity.vyaw, desired.vyaw, _MIN_VYAW, self.max_vyaw),
                    )

                if self._has_motion(effective):
                    command = effective
                    self._last_sent_command = effective
                    self._last_nonzero_command = effective
                    self._stop_sent = False
                    action = "move"
                else:
                    should_stop = (not self._stop_sent) and (
                        self._explicit_stop_requested
                        or self._has_motion(self._last_sent_command)
                        or settling
                    )
                    if should_stop:
                        self._last_sent_command = _Velocity()
                        self._stop_sent = True
                        action = "stop"

            if action == "move":
                try:
                    rc = self.adapter.send_velocity(command.vx, command.vy, command.vyaw)
                except Exception as exc:
                    with self._condition:
                        self._last_action_message = f"Move failed: {exc}"
                    self._emit("warning", {"message": str(exc), "kind": "move_failed"})
                    continue
                with self._condition:
                    self._last_move_return_code = self._normalize_return_code(rc)
            elif action == "stop":
                try:
                    rc = self.adapter.stop()
                except Exception as exc:
                    with self._condition:
                        self._last_action_message = f"StopMove failed: {exc}"
                    self._emit("warning", {"message": str(exc), "kind": "stop_failed"})
                    continue
                with self._condition:
                    self._last_stop_return_code = self._normalize_return_code(rc)

    def _watchdog_loop(self) -> None:
        while not self._stop_event.wait(0.05):
            should_stop = False
            captured_ts = 0.0
            with self._lock:
                settling = time.monotonic() < self._settle_until
                if (
                    self.mode == RobotMode.MANUAL
                    and not settling
                    and not self._watchdog_fired
                    and self.last_teleop_ts
                    and time.monotonic() - self.last_teleop_ts > self.watchdog_timeout_s
                ):
                    self._watchdog_fired = True
                    should_stop = True
                    captured_ts = self.last_teleop_ts
            if should_stop:
                with self._lock:
                    if self.last_teleop_ts != captured_ts:
                        self._watchdog_fired = False
                        should_stop = False
            if should_stop:
                self.stop_motion("manual teleop watchdog timeout")
                self._emit("warning", {"message": "manual teleop watchdog timeout", "kind": "watchdog_timeout"})

    def _active_target_locked(self) -> _Velocity:
        if self.mode == RobotMode.MANUAL:
            return self._manual_target
        if self.mission_status not in TERMINAL_STATUSES | {MissionStatus.PAUSED_MANUAL}:
            return self._auto_target
        return _Velocity()

    def _derive_motion_mode_locked(self, now: float) -> MotionMode:
        if now < self._settle_until:
            return MotionMode.SETTLING
        if self.estop_latched or self._explicit_stop_requested:
            return MotionMode.STOPPED
        if self.mode == RobotMode.MANUAL:
            return MotionMode.MANUAL
        if self.mission_status in {MissionStatus.STARTING, MissionStatus.RUNNING}:
            return MotionMode.MISSION
        return MotionMode.IDLE

    def _reset_motion_locked(
        self,
        *,
        clear_manual_target: bool,
        clear_auto_target: bool,
        explicit_stop: bool,
        message: str,
    ) -> None:
        if clear_manual_target:
            self._manual_target = _Velocity()
        if clear_auto_target:
            self._auto_target = _Velocity()
        if explicit_stop:
            self._current_velocity = _Velocity()
            self._last_sent_command = _Velocity()
            self._stop_sent = False
        self._explicit_stop_requested = explicit_stop
        self._last_action_message = message

    def _step_towards(self, current: float, target: float, dt: float, accel: float, decel: float) -> float:
        delta = target - current
        if abs(delta) <= _AXIS_EPS:
            return target
        limit = accel * dt if abs(target) > abs(current) else decel * dt
        if delta > 0:
            return min(target, current + limit)
        return max(target, current - limit)

    def _effective_axis(self, current: float, target: float, minimum: float, maximum: float) -> float:
        if abs(current) <= _AXIS_EPS:
            return 0.0
        if abs(target) <= _AXIS_EPS:
            return self._clamp(current, maximum)
        sign = 1.0 if target >= 0.0 else -1.0
        magnitude = max(abs(current), minimum)
        return self._clamp(sign * magnitude, maximum)

    def _triplet(self, velocity: _Velocity) -> VelocityTriplet:
        return VelocityTriplet(vx=round(velocity.vx, 4), vy=round(velocity.vy, 4), vyaw=round(velocity.vyaw, 4))

    def _has_motion(self, velocity: _Velocity) -> bool:
        return any(abs(value) > _AXIS_EPS for value in (velocity.vx, velocity.vy, velocity.vyaw))

    def _clamp(self, value: float, maximum: float) -> float:
        return max(-maximum, min(maximum, float(value)))

    def _normalize_return_code(self, result: object) -> Optional[int]:
        if result is None:
            return None
        try:
            return int(result)
        except (TypeError, ValueError):
            return None

    def _emit(self, event: str, details: dict) -> None:
        if self.event_callback:
            self.event_callback(event, details)
