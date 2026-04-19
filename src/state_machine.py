from __future__ import annotations

import threading
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RobotState

# Sport mode error codes — confirmed from go2_adapter.py and spec.
# Any code not listed here is explicitly marked UNKNOWN.
_SPORT_ERROR_DAMPING = 1001
_SPORT_ERROR_STANDING_LOCK = 1002

_SPORT_ERROR_LABELS: dict[int, str] = {
    0: "none",
    _SPORT_ERROR_DAMPING: "damping",
    _SPORT_ERROR_STANDING_LOCK: "standing_lock",
}

# Motion mode values from _SPORT_MODE_LABELS in go2_adapter.py
_MOTION_MODE_IDLE = 0
_MOTION_MODE_BALANCE_STAND = 1
_MOTION_MODE_POSE = 2
_MOTION_MODE_LOCOMOTION = 3

_MOTION_MODE_LABELS: dict[int, str] = {
    0: "idle",
    1: "balanceStand",
    2: "pose",
    3: "locomotion",
    4: "reserved_4",
    5: "lieDown",
    6: "jointLock",
    7: "damping",
    8: "recoveryStand",
    9: "reserved_9",
    10: "sit",
    11: "frontFlip",
    12: "frontJump",
    13: "frontPounce",
}

# BMS status flags — only 0x08 is confirmed from SDK observation.
_BMS_FLAG_ABNORMAL = 0x08


class EffectiveState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    STANDING = "standing"
    READY = "ready"
    MOVING = "moving"
    PAUSED = "paused"
    DAMPING = "damping"
    STANDING_LOCK = "standing_lock"
    ERROR = "error"
    ESTOP = "estop"


def derive_state(
    connected: bool,
    robot_state: "RobotState | None",
    estop_latched: bool,
    is_moving: bool = False,
    is_paused: bool = False,
) -> EffectiveState:
    """Pure function: derive effective state from observable telemetry.

    Priority: estop > disconnected > connecting (no data) > sport_error > motion_mode > operational.
    Effective state is derived from hardware telemetry, NOT operator intent.
    """
    if estop_latched:
        return EffectiveState.ESTOP
    if not connected:
        return EffectiveState.DISCONNECTED
    if robot_state is None:
        return EffectiveState.CONNECTING

    sport_error = robot_state.sport_mode_error
    if sport_error is not None and sport_error != 0:
        if sport_error == _SPORT_ERROR_DAMPING:
            return EffectiveState.DAMPING
        if sport_error == _SPORT_ERROR_STANDING_LOCK:
            return EffectiveState.STANDING_LOCK
        return EffectiveState.ERROR

    motion_mode = robot_state.motion_mode
    if motion_mode is None:
        # No DDS sample yet — adapter connected but robot not responding
        return EffectiveState.CONNECTING
    if motion_mode == _MOTION_MODE_IDLE:
        return EffectiveState.IDLE

    # Robot is in an active motion mode
    if is_paused:
        return EffectiveState.PAUSED
    if is_moving:
        return EffectiveState.MOVING
    if motion_mode in (_MOTION_MODE_BALANCE_STAND, _MOTION_MODE_POSE):
        return EffectiveState.STANDING
    # locomotion (3) or any unlisted active mode → ready for commands
    return EffectiveState.READY


def decode_sport_error(code: int | None) -> dict:
    """Decode a sport mode error code. Unknown codes are marked UNKNOWN."""
    if code is None:
        return {"code": None, "decoded": "UNKNOWN"}
    if code == 0:
        return {"code": 0, "decoded": "none"}
    decoded = _SPORT_ERROR_LABELS.get(code, "UNKNOWN")
    return {"code": code, "decoded": decoded}


def decode_motion_mode(mode: int | None) -> str:
    """Decode a raw motion mode integer. Unknown modes are marked UNKNOWN_N."""
    if mode is None:
        return "UNKNOWN"
    return _MOTION_MODE_LABELS.get(mode, f"UNKNOWN_{mode}")


def decode_bms_flags(bms_status: int | None) -> dict:
    """Decode BMS status flags. Only 0x08 (abnormal) is confirmed; others are UNKNOWN."""
    if bms_status is None:
        return {"raw": None, "decoded": "UNKNOWN"}
    flags: list[str] = []
    if bms_status & _BMS_FLAG_ABNORMAL:
        flags.append("abnormal")
    unknown_bits = bms_status & ~_BMS_FLAG_ABNORMAL
    if unknown_bits:
        flags.append(f"UNKNOWN_bits=0x{unknown_bits:02X}")
    return {
        "raw": f"0x{bms_status:02X}",
        "decoded": ", ".join(flags) if flags else "ok",
    }


class RobotStateMachine:
    """Thread-safe tracker for effective and requested robot state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._effective: EffectiveState = EffectiveState.DISCONNECTED
        self._requested: EffectiveState | None = None
        self._last_transition: datetime | None = None
        self._last_command_ok: str | None = None
        self._last_command_rejected: str | None = None
        self._is_moving: bool = False

    def update(
        self,
        connected: bool,
        robot_state: "RobotState | None",
        estop_latched: bool,
        is_paused: bool = False,
    ) -> tuple[EffectiveState, bool]:
        """Recompute effective state from telemetry. Returns (new_state, did_transition)."""
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

    def set_requested(self, state: EffectiveState) -> None:
        with self._lock:
            self._requested = state

    def record_command_ok(self, action: str) -> None:
        with self._lock:
            self._last_command_ok = action

    def record_command_rejected(self, action: str) -> None:
        with self._lock:
            self._last_command_rejected = action

    def can_move(self) -> tuple[bool, str]:
        """Check if movement commands are currently allowed. Returns (ok, reason)."""
        state = self.get_effective()
        if state in (EffectiveState.READY, EffectiveState.MOVING, EffectiveState.STANDING):
            return True, ""
        reasons: dict[EffectiveState, str] = {
            EffectiveState.IDLE: "motion_mode=idle: robot not in locomotion mode; call stand_up/activate first",
            EffectiveState.DAMPING: "sport_mode_error=1001: robot is damping; activate() required after reset",
            EffectiveState.STANDING_LOCK: "sport_mode_error=1002: robot is standing-locked",
            EffectiveState.ERROR: "sport mode error active",
            EffectiveState.ESTOP: "e-stop latched",
            EffectiveState.DISCONNECTED: "robot not connected",
            EffectiveState.CONNECTING: "robot connecting, no telemetry yet",
            EffectiveState.PAUSED: "mission is paused",
        }
        return False, reasons.get(state, f"movement not allowed in state {state.value}")

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "effective": self._effective.value,
                "requested": self._requested.value if self._requested else None,
                "last_transition": self._last_transition.isoformat() if self._last_transition else None,
                "last_command_ok": self._last_command_ok,
                "last_command_rejected": self._last_command_rejected,
            }
