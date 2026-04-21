from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

from ..models import Pose, RobotState
from .robot_adapter import AdapterCapabilities

try:
    from unitree_sdk2py.core.channel import (
        ChannelFactory,
        ChannelSubscriber,
    )
    from unitree_sdk2py.go2.robot_state.robot_state_client import RobotStateClient
    from unitree_sdk2py.go2.sport.sport_client import SportClient
    from unitree_sdk2py.go2.video.video_client import VideoClient
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, SportModeState_

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

_log = logging.getLogger(__name__)

_SPORT_STATE_TOPIC = "rt/sportmodestate"
_LOW_STATE_TOPIC = "rt/lowstate"
_CAMERA_URI = "udp://230.1.1.1:1720"
_SERVICE_REFRESH_INTERVAL_SEC = 5.0
_SPORT_MODE_LABELS = {
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


class Go2RobotAdapter:
    """Real Go2 adapter using unitree_sdk2py (DDS/CycloneDDS transport).

    Movement uses SportClient.Move(vx, vy, vyaw) directly, as shown in the
    official SDK examples. Emergency stop escalates to Damp(), which is a
    passive state and requires activate() before scripted motion resumes.
    """

    capabilities: AdapterCapabilities

    def __init__(
        self,
        interface_name: Optional[str] = None,
        camera_enabled: bool = False,
    ) -> None:
        if not SDK_AVAILABLE:
            raise RuntimeError(
                "unitree_sdk2py is not installed. "
                "Install with:\n"
                "  git clone https://github.com/unitreerobotics/unitree_sdk2_python\n"
                "  pip install -e unitree_sdk2_python"
            )
        self._interface_name = interface_name
        self._camera_enabled = camera_enabled
        self.capabilities = AdapterCapabilities(has_camera=camera_enabled, has_pose=True)

        self._sport: Optional[SportClient] = None
        self._motion_ready = False
        self._motion_lock = threading.RLock()
        self._manual_mode_active = False
        self._state_lock = threading.Lock()
        self._latest_state: Optional[SportModeState_] = None
        self._latest_low_state: Optional[LowState_] = None
        self._state_sub: Optional[ChannelSubscriber] = None
        self._low_state_sub: Optional[ChannelSubscriber] = None
        self._robot_state_client: Optional[RobotStateClient] = None
        self._service_state_lock = threading.Lock()
        self._service_states: dict[str, int] = {}
        self._next_service_refresh_at = 0.0

        self._video_client: Optional[VideoClient] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._camera_status_lock = threading.Lock()
        self._camera_status = "Camera disabled in config." if not camera_enabled else "Waiting for camera frames."
        self._camera_warned: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Initialise DDS transport, subscribers, and sport client."""
        ChannelFactory().Init(0, self._interface_name)

        self._state_sub = ChannelSubscriber(_SPORT_STATE_TOPIC, SportModeState_)
        self._state_sub.Init(self._on_state_update, queueLen=10)
        self._low_state_sub = ChannelSubscriber(_LOW_STATE_TOPIC, LowState_)
        self._low_state_sub.Init(self._on_low_state_update, queueLen=10)

        self._sport = SportClient()
        self._sport.SetTimeout(10.0)
        self._sport.Init()
        self._init_robot_state_client()
        self._init_camera_clients()
        self._motion_ready = False
        self._manual_mode_active = False
        self._next_service_refresh_at = 0.0
        self._maybe_refresh_service_states(force=True)

    def disconnect(self) -> None:
        """Close subscribers and release camera."""
        self._best_effort_sit_down()
        if self._low_state_sub is not None:
            try:
                self._low_state_sub.Close()
            except Exception as exc:
                _log.warning(
                    "go2 low-state subscriber close error",
                    extra={"adapter": "go2", "op": "disconnect.lowstate", "err": str(exc)},
                )
            self._low_state_sub = None
        if self._state_sub is not None:
            try:
                self._state_sub.Close()
            except Exception as exc:
                _log.warning(
                    "go2 state subscriber close error",
                    extra={"adapter": "go2", "op": "disconnect", "err": str(exc)},
                )
            self._state_sub = None
        with self._state_lock:
            self._latest_state = None
            self._latest_low_state = None
        self._sport = None
        self._robot_state_client = None
        self._motion_ready = False
        self._manual_mode_active = False
        with self._service_state_lock:
            self._service_states = {}

        self._video_client = None

        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self._set_camera_status("Camera disabled in config." if not self._camera_enabled else "Camera disconnected.")

    def activate(self) -> int:
        """Stand the robot up and prepare for motion.

        StandUp alone leaves the robot in a rigid posture where Move() causes
        stretching instead of a walking gait. BalanceStand transitions it into
        the dynamic balance mode (mode=1) from which Move() produces correct
        locomotion (mode=3).
        """
        with self._motion_lock:
            if self._sport is None:
                raise RuntimeError("Go2 sport client is not connected.")
            if self._motion_ready:
                return 0

            _log.info("go2 activate: StandUp → BalanceStand", extra={"adapter": "go2", "op": "activate"})
            stand_up_rc = self._call_sport_method("StandUp", settle_seconds=1.5)
            self._call_sport_method("BalanceStand", settle_seconds=0.5)
            self._motion_ready = True
            return stand_up_rc

    # ------------------------------------------------------------------
    # Motion
    # ------------------------------------------------------------------

    def enter_manual_mode(self) -> None:
        with self._motion_lock:
            self._manual_mode_active = True

    def stand_up(self) -> int:
        with self._motion_lock:
            if self._sport is None:
                raise RuntimeError("Go2 sport client is not connected.")
            _log.info("go2 stand_up: StandUp", extra={"adapter": "go2", "op": "stand_up"})
            result = self._call_sport_method("StandUp", settle_seconds=0.0)
            self._motion_ready = True
            return result

    def exit_manual_mode(self) -> None:
        with self._motion_lock:
            if self._manual_mode_active:
                self._send_move(0.0, 0.0, 0.0)
            self._manual_mode_active = False

    def send_velocity(self, vx: float, vy: float, vyaw: float) -> Optional[int]:
        """Send velocity via SportClient.Move (official SDK method)."""
        return self._send_move(vx, vy, vyaw)

    def stop(self) -> Optional[int]:
        """Zero velocity while preserving the current standing posture."""
        if self._sport is None:
            return None
        try:
            result = self._sport.StopMove()
            code = 0 if result is None else int(result)
            if code != 0:
                _log.warning(
                    "go2 StopMove returned non-zero",
                    extra={"adapter": "go2", "op": "stop.StopMove", "code": code},
                )
            return code
        except Exception as exc:
            _log.warning(
                "go2 StopMove failed",
                extra={"adapter": "go2", "op": "stop.StopMove", "err": str(exc)},
            )
            return None

    def sit_down(self) -> Optional[int]:
        """Best-effort transition to a seated posture before shutdown."""
        result = self._best_effort_sit_down()
        self._motion_ready = False
        self._manual_mode_active = False
        return result

    def emergency_stop(self) -> None:
        """Software e-stop: zero velocity + passive damp."""
        self.stop()
        if self._sport is None:
            return
        try:
            self._sport.Damp()
            self._motion_ready = False
            self._manual_mode_active = False
        except Exception as exc:
            _log.warning(
                "go2 Damp failed",
                extra={"adapter": "go2", "op": "emergency_stop.Damp", "err": str(exc)},
            )

    # ------------------------------------------------------------------
    # State & telemetry
    # ------------------------------------------------------------------

    def get_state(self) -> RobotState:
        """Return the latest battery data and human-readable faults."""
        with self._state_lock:
            state = self._latest_state
            low_state = self._latest_low_state

        self._maybe_refresh_service_states()

        battery_percent: Optional[float] = None
        battery_voltage_v: Optional[float] = None
        battery_current_a: Optional[float] = None
        battery_cycles: Optional[int] = None
        imu_yaw: Optional[float] = None
        faults: list[str] = []

        if state is None:
            faults.append("No rt/sportmodestate sample received from the robot yet.")
        else:
            imu_yaw = float(state.imu_state.rpy[2])
            if state.error_code != 0:
                faults.append(self._format_sport_error(int(state.error_code), int(state.mode)))

        if low_state is None:
            faults.append("No rt/lowstate sample received yet, so battery details are unavailable.")
        else:
            battery_percent = float(low_state.bms_state.soc)
            battery_voltage_v = round(float(low_state.power_v), 2)
            battery_current_a = round(float(low_state.power_a), 2)
            battery_cycles = int(low_state.bms_state.cycle)
            bms_status_raw = int(low_state.bms_state.status)
            if bms_status_raw != 0:
                faults.append(f"BMS status flag is 0x{bms_status_raw:02X}.")
            if battery_percent <= 20:
                faults.append(f"Battery low: {battery_percent:.0f}% remaining.")

        faults.extend(self._build_service_faults())

        return RobotState(
            battery_percent=battery_percent,
            battery_voltage_v=battery_voltage_v,
            battery_current_a=battery_current_a,
            battery_cycles=battery_cycles,
            imu_yaw=imu_yaw,
            camera_status=self._get_camera_status(),
            faults=faults,
        )

    def get_pose(self) -> Optional[Pose]:
        """Return (x, y, yaw) from the latest SportModeState, or None."""
        with self._state_lock:
            state = self._latest_state
        if state is None:
            return None
        return Pose(
            x=float(state.position[0]),
            y=float(state.position[1]),
            yaw=float(state.imu_state.rpy[2]),
        )

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------

    def capture_frame(self) -> Optional[np.ndarray]:
        """Return latest camera frame as ndarray, or None."""
        data = self.get_camera_frame()
        if data is None:
            return None
        buf = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def get_camera_frame(self) -> Optional[bytes]:
        """Return latest camera frame as JPEG bytes, or None."""
        if not self._camera_enabled:
            self._set_camera_status("Camera disabled in config.")
            return None

        if self._video_client is not None:
            try:
                code, data = self._video_client.GetImageSample()
                if code == 0 and data:
                    self._set_camera_status("Live via Unitree VideoClient.")
                    return bytes(data)
                if code != 0:
                    self._set_camera_status(
                        f"Unitree VideoClient returned code={code}; trying UDP/GStreamer fallback."
                    )
                    if not self._camera_warned:
                        _log.warning(
                            "go2 VideoClient frame read failed",
                            extra={"adapter": "go2", "op": "get_camera_frame.video_client", "code": code},
                        )
                        self._camera_warned = True
                else:
                    self._set_camera_status("VideoClient returned no data; trying UDP/GStreamer fallback.")
            except Exception as exc:
                self._set_camera_status(f"VideoClient error: {exc}. Trying UDP/GStreamer fallback.")
                if not self._camera_warned:
                    _log.warning(
                        "go2 VideoClient error",
                        extra={"adapter": "go2", "op": "get_camera_frame.video_client", "err": str(exc)},
                    )
                    self._camera_warned = True

        try:
            if self._cap is None or not self._cap.isOpened():
                self._cap = cv2.VideoCapture(_CAMERA_URI, cv2.CAP_GSTREAMER)
                if not self._cap.isOpened():
                    self._set_camera_status(
                        "Camera stream unavailable. SDK video failed and UDP/GStreamer could not open."
                    )
                    if not self._camera_warned:
                        _log.warning(
                            "go2 camera pipeline failed to open — "
                            "requires GStreamer with H264 support",
                            extra={
                                "adapter": "go2",
                                "op": "get_camera_frame",
                                "err": "cap.isOpened() == False",
                                "uri": _CAMERA_URI,
                            },
                        )
                        self._camera_warned = True
                    self._cap = None
                    return None

            ok, frame = self._cap.read()
            if not ok or frame is None:
                self._set_camera_status("UDP/GStreamer camera opened but no frame has arrived yet.")
                return None

            enc_ok, encoded = cv2.imencode(".jpg", frame)
            if not enc_ok:
                self._set_camera_status("UDP/GStreamer camera produced a frame but JPEG encoding failed.")
                return None
            self._set_camera_status("Live via UDP/GStreamer fallback.")
            return encoded.tobytes()

        except Exception as exc:
            self._set_camera_status(f"Camera stream error: {exc}.")
            if not self._camera_warned:
                _log.warning(
                    "go2 camera error",
                    extra={"adapter": "go2", "op": "get_camera_frame", "err": str(exc)},
                )
                self._camera_warned = True
            return None

    # ------------------------------------------------------------------
    # SDK callbacks
    # ------------------------------------------------------------------

    def _on_state_update(self, msg: SportModeState_) -> None:
        with self._state_lock:
            self._latest_state = msg

    def _on_low_state_update(self, msg: LowState_) -> None:
        with self._state_lock:
            self._latest_low_state = msg

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_move(self, vx: float, vy: float, vyaw: float) -> Optional[int]:
        if self._sport is None:
            return None
        try:
            result = self._sport.Move(vx, vy, vyaw)
            code = 0 if result is None else int(result)
            if code != 0:
                _log.warning(
                    "go2 Move returned non-zero",
                    extra={"adapter": "go2", "op": "send_move", "code": code},
                )
            return code
        except Exception as exc:
            _log.warning(
                "go2 Move failed",
                extra={"adapter": "go2", "op": "send_move", "err": str(exc)},
            )
            return None

    def _best_effort_sit_down(self) -> Optional[int]:
        if self._sport is None:
            return None
        try:
            result = self._sport.StandDown()
            self._motion_ready = False
            code = 0 if result is None else int(result)
            if code != 0:
                _log.warning(
                    "go2 StandDown returned non-zero",
                    extra={"adapter": "go2", "op": "shutdown.StandDown", "code": code},
                )
            return code
        except Exception as exc:
            _log.warning(
                "go2 StandDown failed",
                extra={"adapter": "go2", "op": "shutdown.StandDown", "err": str(exc)},
            )
        self._motion_ready = False
        return None

    def _call_sport_method(self, method_name: str, settle_seconds: float) -> int:
        if self._sport is None:
            raise RuntimeError("Go2 sport client is not connected.")

        method = getattr(self._sport, method_name, None)
        if method is None:
            raise RuntimeError(f"SportClient.{method_name} is not available in this SDK build.")

        result = method()
        code = 0 if result is None else int(result)
        if code != 0:
            raise RuntimeError(f"SportClient.{method_name} failed with code={code}.")
        if settle_seconds > 0:
            time.sleep(settle_seconds)
        return code

    def _init_robot_state_client(self) -> None:
        try:
            client = RobotStateClient()
            client.SetTimeout(3.0)
            client.Init()
        except Exception as exc:
            _log.warning(
                "go2 RobotStateClient init failed",
                extra={"adapter": "go2", "op": "connect.robot_state_client", "err": str(exc)},
            )
            self._robot_state_client = None
            return
        self._robot_state_client = client

    def _init_camera_clients(self) -> None:
        self._camera_warned = False
        if not self._camera_enabled:
            self._video_client = None
            self._set_camera_status("Camera disabled in config.")
            return
        try:
            client = VideoClient()
            client.SetTimeout(3.0)
            client.Init()
        except Exception as exc:
            _log.warning(
                "go2 VideoClient init failed",
                extra={"adapter": "go2", "op": "connect.video_client", "err": str(exc)},
            )
            self._video_client = None
            self._set_camera_status("Waiting for UDP/GStreamer camera fallback.")
            return
        self._video_client = client
        self._set_camera_status("Waiting for frames from Unitree VideoClient.")

    def _maybe_refresh_service_states(self, force: bool = False) -> None:
        if self._robot_state_client is None:
            return
        now = time.monotonic()
        if not force and now < self._next_service_refresh_at:
            return
        self._next_service_refresh_at = now + _SERVICE_REFRESH_INTERVAL_SEC
        try:
            code, services = self._robot_state_client.ServiceList()
        except Exception as exc:
            _log.warning(
                "go2 service list refresh failed",
                extra={"adapter": "go2", "op": "service_list", "err": str(exc)},
            )
            return
        if code != 0 or services is None:
            _log.warning(
                "go2 service list returned non-zero code",
                extra={"adapter": "go2", "op": "service_list", "code": code},
            )
            return
        with self._service_state_lock:
            self._service_states = {service.name: int(service.status) for service in services}

    def _build_service_faults(self) -> list[str]:
        with self._service_state_lock:
            service_states = dict(self._service_states)
        faults: list[str] = []
        sport_mode_status = service_states.get("sport_mode")
        if sport_mode_status not in (None, 1):
            faults.append(f"Robot service 'sport_mode' status={sport_mode_status}.")
        return faults

    def _format_sport_error(self, error_code: int, mode: int) -> str:
        active_bits = [str(bit) for bit in range(32) if error_code & (1 << bit)]
        bit_text = ", ".join(active_bits) if active_bits else "none"
        mode_label = _SPORT_MODE_LABELS.get(mode, f"unknown_{mode}")
        return (
            f"Sport mode error code {error_code} (0x{error_code:08X}; "
            f"active bits: {bit_text}; current mode: {mode_label})."
        )

    def _set_camera_status(self, status: str) -> None:
        with self._camera_status_lock:
            self._camera_status = status

    def _get_camera_status(self) -> str:
        with self._camera_status_lock:
            return self._camera_status
