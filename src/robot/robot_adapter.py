from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import cv2
import numpy as np

from ..models import Pose, RobotState


@dataclass(frozen=True)
class AdapterCapabilities:
    has_camera: bool
    has_pose: bool


@runtime_checkable
class RobotAdapterProtocol(Protocol):
    """Structural protocol that all robot adapters must satisfy."""

    capabilities: AdapterCapabilities

    def activate(self) -> int | None: ...
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def enter_manual_mode(self) -> None: ...
    def emergency_stop(self) -> None: ...
    def exit_manual_mode(self) -> None: ...
    def send_velocity(self, vx: float, vy: float, vyaw: float) -> int | None: ...
    def stand_up(self) -> int | None: ...
    def stop(self) -> int | None: ...
    def sit_down(self) -> int | None: ...
    def get_state(self) -> RobotState: ...
    def get_camera_frame(self) -> bytes | None: ...


# Backward-compat alias — existing code that references RobotAdapter keeps working.
RobotAdapter = RobotAdapterProtocol


class MockRobotAdapter:
    """Fully-featured in-process mock; satisfies RobotAdapterProtocol structurally."""

    capabilities = AdapterCapabilities(has_camera=True, has_pose=True)

    def __init__(self, width: int = 640, height: int = 480) -> None:
        self.width = width
        self.height = height
        self._lock = threading.Lock()
        self._connected = False
        self._vx = 0.0
        self._vy = 0.0
        self._vyaw = 0.0
        self._pose = Pose(x=0.0, y=0.0, yaw=0.0)
        self._last_update = time.monotonic()
        self._battery_base = 92.0

    def connect(self) -> None:
        with self._lock:
            self._connected = True
            self._last_update = time.monotonic()

    def activate(self) -> int:
        return self.stand_up()

    def stand_up(self) -> int:
        return 0

    def disconnect(self) -> None:
        with self._lock:
            self._integrate_locked()
            self._connected = False
            self._vx = 0.0
            self._vy = 0.0
            self._vyaw = 0.0

    def emergency_stop(self) -> None:
        self.stop()

    def enter_manual_mode(self) -> None:
        return

    def exit_manual_mode(self) -> None:
        return

    def send_velocity(self, vx: float, vy: float, vyaw: float) -> int:
        with self._lock:
            self._integrate_locked()
            self._vx = float(vx)
            self._vy = float(vy)
            self._vyaw = float(vyaw)
        return 0

    def stop(self) -> int:
        with self._lock:
            self._integrate_locked()
            self._vx = 0.0
            self._vy = 0.0
            self._vyaw = 0.0
        return 0

    def sit_down(self) -> int:
        return self.stop()

    def get_state(self) -> RobotState:
        with self._lock:
            self._integrate_locked()
            battery_drop = (time.monotonic() % 900.0) / 900.0 * 6.0
            battery = max(10.0, self._battery_base - battery_drop)
            current_draw = 1.1 + abs(self._vx) * 4.0 + abs(self._vy) * 4.0 + abs(self._vyaw) * 1.5
            voltage = 27.6 + (battery / 100.0) * 2.0
            return RobotState(
                battery_percent=round(battery, 1),
                battery_voltage_v=round(voltage, 2),
                battery_current_a=round(current_draw, 2),
                battery_cycles=48,
                imu_yaw=round(self._pose.yaw, 3),
                camera_status="Live via mock camera",
                faults=[] if self._connected else ["mock_disconnected"],
            )

    def get_pose(self) -> Pose | None:
        with self._lock:
            self._integrate_locked()
            return Pose(x=self._pose.x, y=self._pose.y, yaw=self._pose.yaw)

    def capture_frame(self) -> np.ndarray | None:
        """Return synthesised frame as ndarray. Used by streaming/mission code."""
        with self._lock:
            self._integrate_locked()
            pose = Pose(x=self._pose.x, y=self._pose.y, yaw=self._pose.yaw)
            battery_drop = (time.monotonic() % 900.0) / 900.0 * 6.0
            battery = max(10.0, self._battery_base - battery_drop)

        t = time.monotonic()
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        gradient = np.linspace(30, 120, self.width, dtype=np.uint8)
        frame[:, :, 0] = gradient
        frame[:, :, 1] = gradient[::-1]
        frame[:, :, 2] = 40

        horizon = int(self.height * 0.65)
        frame[horizon:, :, :] = np.array([40, 90, 40], dtype=np.uint8)
        frame[:horizon, :, :] = np.maximum(frame[:horizon, :, :], np.array([70, 70, 30], dtype=np.uint8))

        marker_x = int(self.width * 0.5 + math.sin(t * 1.4) * self.width * 0.2)
        marker_y = int(self.height * 0.35 + math.cos(t * 1.1) * self.height * 0.08)
        cv2.circle(frame, (marker_x, marker_y), 28, (0, 220, 255), -1)

        stripe_x = int((t * 90.0) % max(1, self.width - 120))
        cv2.rectangle(frame, (stripe_x, horizon - 30), (stripe_x + 120, horizon + 20), (255, 180, 40), -1)

        cv2.putText(frame, "GO2 MOCK CAMERA", (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240, 240, 240), 2)
        cv2.putText(
            frame,
            f"x={pose.x:.2f} y={pose.y:.2f} yaw={pose.yaw:.2f}",
            (18, self.height - 42),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            frame,
            f"battery={battery:.1f}%",
            (18, self.height - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )
        return frame

    def get_camera_frame(self) -> bytes | None:
        """Return latest frame encoded as JPEG bytes."""
        frame = self.capture_frame()
        if frame is None:
            return None
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        return encoded.tobytes() if ok else None

    def _integrate_locked(self) -> None:
        now = time.monotonic()
        dt = max(0.0, now - self._last_update)
        self._last_update = now

        yaw = self._pose.yaw
        world_vx = self._vx * math.cos(yaw) - self._vy * math.sin(yaw)
        world_vy = self._vx * math.sin(yaw) + self._vy * math.cos(yaw)

        self._pose = Pose(
            x=self._pose.x + world_vx * dt,
            y=self._pose.y + world_vy * dt,
            yaw=self._pose.yaw + self._vyaw * dt,
        )


def build_robot_adapter(
    mode: str,
    width: int = 640,
    height: int = 480,
    interface_name: str | None = None,
    camera_enabled: bool = False,
) -> RobotAdapterProtocol:
    if mode == "mock":
        return MockRobotAdapter(width=width, height=height)
    if mode == "go2":
        from .go2_adapter import Go2RobotAdapter  # deferred; raises if SDK absent
        return Go2RobotAdapter(interface_name=interface_name, camera_enabled=camera_enabled)
    raise ValueError(f"Unsupported robot.mode: {mode!r}. Choose 'mock' or 'go2'.")
