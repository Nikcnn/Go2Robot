from __future__ import annotations

import threading
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import RobotState


class EffectiveState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    MOVING = "moving"
    PAUSED = "paused"
    ESTOP = "estop"


def derive_state(
    connected: bool,
    robot_state: Optional["RobotState"],
    estop_latched: bool,
    is_moving: bool = False,
    is_paused: bool = False,
) -> EffectiveState:
    """Pure function: derive effective state from connection and control flags."""
    if estop_latched:
        return EffectiveState.ESTOP
    if not connected:
        return EffectiveState.DISCONNECTED
    if robot_state is None:
        return EffectiveState.CONNECTING
    if is_paused:
        return EffectiveState.PAUSED
    if is_moving:
        return EffectiveState.MOVING
    return EffectiveState.READY


class RobotStateMachine:
    """Thread-safe tracker for effective robot state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._effective: EffectiveState = EffectiveState.DISCONNECTED
        self._last_transition: Optional[datetime] = None
        self._last_command_ok: Optional[str] = None
        self._last_command_rejected: Optional[str] = None
        self._is_moving: bool = False

    def update(
        self,
        connected: bool,
        robot_state: Optional["RobotState"],
        estop_latched: bool,
        is_paused: bool = False,
    ) -> tuple[EffectiveState, bool]:
        """Recompute effective state. Returns (new_state, did_transition)."""
        with self._lock:
            is_moving = self._is_moving

        new_state = derive_state(connected, robot_state, estop_latched, is_moving, is_paused)

        with self._lock:
            changed = new_state != self._effective
            if changed:
                self._effective = new_state
                self._last_transition = datetime.now(timezone.utc)
        return new_state, changed

    def notify_motion(self, is_moving: bool) -> None:
        """Called by ControlCore when a motion command is submitted or stopped."""
        with self._lock:
            self._is_moving = is_moving

    def get_effective(self) -> EffectiveState:
        with self._lock:
            return self._effective

    def record_command_ok(self, action: str) -> None:
        with self._lock:
            self._last_command_ok = action

    def record_command_rejected(self, action: str) -> None:
        with self._lock:
            self._last_command_rejected = action

    def can_move(self) -> tuple[bool, str]:
        """Check if movement commands are currently allowed. Returns (ok, reason)."""
        state = self.get_effective()
        if state in (EffectiveState.READY, EffectiveState.MOVING):
            return True, ""
        reasons: dict[EffectiveState, str] = {
            EffectiveState.ESTOP: "e-stop latched",
            EffectiveState.DISCONNECTED: "robot not connected",
            EffectiveState.CONNECTING: "robot connecting, no telemetry yet",
            EffectiveState.PAUSED: "mission is paused",
        }
        return False, reasons.get(state, f"movement not allowed in state {state.value}")

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "last_transition": self._last_transition.isoformat() if self._last_transition else None,
                "last_command_ok": self._last_command_ok,
                "last_command_rejected": self._last_command_rejected,
            }
