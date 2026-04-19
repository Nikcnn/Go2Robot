from __future__ import annotations

# All annotations are evaluated lazily (PEP 563), so SDK types in signatures are
# safe even when SDK_AVAILABLE = False.

import logging
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from ..models import Pose, RobotState
from .robot_adapter import AdapterCapabilities

try:
    from unitree_sdk2py.core.channel import (
        ChannelFactory,
        ChannelSubscriber,
    )
    from unitree_sdk2py.go2.obstacles_avoid.obstacles_avoid_client import ObstaclesAvoidClient
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
_SPORT_ERROR_DAMPING = 1001
_SPORT_ERROR_STANDING_LOCK = 1002
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
_DDS_READY_MOTION_MODES = frozenset({1, 2, 3})
_DDS_DAMPING_MOTION_MODES = frozenset({7})
_DDS_STANDING_LOCK_MOTION_MODES = frozenset({6})
_DDS_IDLE_MOTION_MODES = frozenset({0, 5, 6, 10})
_UNSET = object()


@dataclass(frozen=True)
class _LocomotionSnapshot:
    locomotion_state: str
    can_move: bool
    block_reason: str | None
    motion_mode: int | None
    sport_mode_error: int | None


class Go2RobotAdapter:
    """Real Go2 adapter using unitree_sdk2py (DDS/CycloneDDS transport).

    Manual motion note: manual driving uses ObstaclesAvoidClient.Move(x, y,
    yaw) instead of direct joint-style body commands. The adapter explicitly
    claims and releases the SDK remote-command source on manual mode entry and
    exit so translation commands remain reliable.

    Emergency stop note: Go2 has no dedicated hardware e-stop API through
    SportClient. Normal stop() preserves posture. emergency_stop() escalates to
    Damp(), which is a passive state and requires a later activate() before
    scripted motion resumes.
    """

    capabilities: AdapterCapabilities  # set in __init__; Protocol requires the attribute

    def __init__(
        self,
        interface_name: str | None = None,
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

        self._sport: SportClient | None = None
        self._obstacle_avoid: ObstaclesAvoidClient | None = None
        self._motion_ready = False
        self._motion_lock = threading.RLock()
        self._manual_mode_active = False
        self._remote_commands_from_api = False
        self._manual_mode_switch_original: bool | None = None
        self._obstacle_avoid_usable = True
        self._state_lock = threading.Lock()
        self._latest_state: SportModeState_ | None = None
        self._latest_low_state: LowState_ | None = None
        self._state_sub: ChannelSubscriber | None = None
        self._low_state_sub: ChannelSubscriber | None = None
        self._robot_state_client: RobotStateClient | None = None
        self._service_state_lock = threading.Lock()
        self._service_states: dict[str, int] = {}
        self._next_service_refresh_at = 0.0

        # Camera state — VideoClient is preferred, OpenCV/GStreamer stays as fallback.
        self._video_client: VideoClient | None = None
        self._cap: cv2.VideoCapture | None = None
        self._camera_status_lock = threading.Lock()
        self._camera_status = "Camera disabled in config." if not camera_enabled else "Waiting for camera frames."
        self._camera_warned: bool = False

        # Locomotion state machine: disconnected → idle → activating → ready ↔ moving
        #                                                                 ↓
        #                                                               damped / fault
        self._locomotion_state: str = "disconnected"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Initialise DDS transport, subscribers, and high-level motion clients."""
        # ChannelFactory is a Singleton; Init() is idempotent after first call.
        ChannelFactory().Init(0, self._interface_name)

        self._state_sub = ChannelSubscriber(_SPORT_STATE_TOPIC, SportModeState_)
        # queueLen > 0 enables the SDK-internal dispatch thread; shutdown via Close().
        self._state_sub.Init(self._on_state_update, queueLen=10)
        self._low_state_sub = ChannelSubscriber(_LOW_STATE_TOPIC, LowState_)
        self._low_state_sub.Init(self._on_low_state_update, queueLen=10)

        self._sport = SportClient()
        self._sport.SetTimeout(10.0)
        self._sport.Init()
        self._obstacle_avoid = ObstaclesAvoidClient()
        self._obstacle_avoid.SetTimeout(10.0)
        self._obstacle_avoid.Init()
        self._init_robot_state_client()
        self._init_camera_clients()
        with self._motion_lock:
            self._motion_ready = False
            self._manual_mode_active = False
            self._remote_commands_from_api = False
            self._manual_mode_switch_original = None
            self._obstacle_avoid_usable = True
            self._locomotion_state = "idle"
        self._next_service_refresh_at = 0.0
        _log.info("go2 connected, locomotion_state=idle", extra={"adapter": "go2", "op": "connect"})
        self._maybe_refresh_service_states(force=True)

    def disconnect(self) -> None:
        """Close subscriber and release camera. Sport client has no teardown API."""
        self._release_manual_command_source(restore_switch=True)
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
        self._obstacle_avoid = None
        self._robot_state_client = None
        with self._motion_lock:
            self._motion_ready = False
            self._manual_mode_active = False
            self._remote_commands_from_api = False
            self._manual_mode_switch_original = None
            self._locomotion_state = "disconnected"
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

    def activate(self) -> None:
        """Prepare a standing motion-ready posture.

        This is intentionally explicit instead of being done at connect time so
        the operator controls when the robot stands up.
        """
        with self._motion_lock:
            if self._sport is None:
                raise RuntimeError("Go2 sport client is not connected.")
            snapshot = self._get_locomotion_snapshot()
            if (
                snapshot.locomotion_state in ("ready", "moving")
                and snapshot.motion_mode in _DDS_READY_MOTION_MODES
                and snapshot.sport_mode_error in (None, 0)
            ):
                return  # idempotent

            _log.info(
                "go2 activate() called, locomotion_state=%s → activating",
                snapshot.locomotion_state,
                extra={"adapter": "go2", "op": "activate"},
            )
            self._locomotion_state = "activating"
            self._motion_ready = False
            try:
                self.stop_move()
                self._run_activation_sequence()
                self.ensure_motion_ready(timeout=15.0, allow_recovery=True)
                self._locomotion_state = "ready"
                self._motion_ready = True
                _log.info("go2 activate() completed, locomotion_state=ready", extra={"adapter": "go2", "op": "activate"})
            except Exception:
                failed_snapshot = self._get_locomotion_snapshot()
                self._locomotion_state = failed_snapshot.locomotion_state if failed_snapshot.locomotion_state not in ("ready", "moving") else "fault"
                self._motion_ready = False
                raise

    def ensure_motion_ready(self, timeout: float = 5.0, allow_recovery: bool = False) -> None:
        """Block until locomotion_state is ready/moving, or raise on timeout/fault."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            snapshot = self._get_locomotion_snapshot()
            state = snapshot.locomotion_state
            if state in ("ready", "moving"):
                # The Unitree SDK publishes SportModeState.mode over DDS; require it
                # to reach a ready motion mode before we report readiness.
                if snapshot.motion_mode in _DDS_READY_MOTION_MODES:
                    return
            if allow_recovery and self._locomotion_state == "activating":
                time.sleep(0.05)
                continue
            if state == "fault":
                raise RuntimeError(
                    "Robot has an active fault "
                    f"(motion_mode={snapshot.motion_mode!r}, sport_mode_error={snapshot.sport_mode_error!r}); "
                    "call activate() after resolving."
                )
            if state in ("damped", "disconnected"):
                raise RuntimeError(
                    "Robot requires activation "
                    f"(locomotion_state={state!r}, motion_mode={snapshot.motion_mode!r}, "
                    f"sport_mode_error={snapshot.sport_mode_error!r}); call activate() first."
                )
            time.sleep(0.05)
        snapshot = self._get_locomotion_snapshot()
        with self._service_state_lock:
            sport_svc = self._service_states.get("sport_mode")
        raise TimeoutError(
            f"ensure_motion_ready() timed out after {timeout}s "
            f"(locomotion_state={snapshot.locomotion_state!r}, motion_mode={snapshot.motion_mode!r}, "
            f"sport_mode_error={snapshot.sport_mode_error!r}, sport_service_status={sport_svc!r})."
        )

    # ------------------------------------------------------------------
    # Motion
    # ------------------------------------------------------------------

    def enter_manual_mode(self) -> None:
        with self._motion_lock:
            self._claim_manual_command_source()
            self._manual_mode_active = True

    def exit_manual_mode(self) -> None:
        with self._motion_lock:
            try:
                if self._remote_commands_from_api:
                    self._send_manual_move(0.0, 0.0, 0.0)
            finally:
                self._release_manual_command_source(restore_switch=True)
                self._manual_mode_active = False

    def send_velocity(self, vx: float, vy: float, vyaw: float) -> None:
        """Send velocity through the active high-level motion path."""
        with self._motion_lock:
            if self._manual_mode_active:
                self._send_manual_move(vx, vy, vyaw)
                return

        if self._sport is None:
            return
        try:
            result = self._sport.Move(vx, vy, vyaw)
            if result not in (None, 0):
                raise RuntimeError(f"SportClient.Move failed with code={result}.")
            with self._motion_lock:
                if self._locomotion_state == "ready":
                    self._locomotion_state = "moving"
        except Exception as exc:
            _log.warning(
                "go2 Move failed",
                extra={"adapter": "go2", "op": "send_velocity", "err": str(exc)},
            )

    def stop_move(self) -> None:
        """Call StopMove() only — preserves posture, does not damp."""
        if self._sport is None:
            return
        try:
            result = self._sport.StopMove()
            if result not in (None, 0):
                raise RuntimeError(f"SportClient.StopMove failed with code={result}.")
            with self._motion_lock:
                if self._locomotion_state == "moving":
                    self._locomotion_state = "ready"
        except Exception as exc:
            _log.warning(
                "go2 StopMove failed",
                extra={"adapter": "go2", "op": "stop_move", "err": str(exc)},
            )

    def stop(self) -> None:
        """Zero velocity while preserving the current standing posture."""
        with self._motion_lock:
            if self._manual_mode_active:
                try:
                    self._send_manual_move(0.0, 0.0, 0.0)
                except Exception as exc:
                    _log.warning(
                        "go2 manual stop failed",
                        extra={"adapter": "go2", "op": "stop.manual_move", "err": str(exc)},
                    )
        self.stop_move()

    def damp(self) -> None:
        """StopMove() + Damp() — transitions to damped state, requires activate() to recover."""
        self.stop_move()
        if self._sport is None:
            return
        try:
            result = self._sport.Damp()
            if result not in (None, 0):
                raise RuntimeError(f"SportClient.Damp failed with code={result}.")
            with self._motion_lock:
                self._locomotion_state = "damped"
                self._motion_ready = False
                self._manual_mode_active = False
        except Exception as exc:
            _log.warning(
                "go2 Damp failed",
                extra={"adapter": "go2", "op": "damp", "err": str(exc)},
            )

    def sit_down(self) -> None:
        """Best-effort transition to a seated posture before shutdown."""
        self._release_manual_command_source(restore_switch=True)
        self._best_effort_sit_down()
        self._motion_ready = False
        self._manual_mode_active = False

    def emergency_stop(self) -> None:
        """Best-effort software e-stop: StopMove + Damp + latch damped state.

        Go2 has no dedicated hardware e-stop API through SportClient.
        Requires reset_estop() + activate() before motion can resume.
        """
        _log.warning(
            "go2 emergency_stop triggered, locomotion_state=%s",
            self._locomotion_state,
            extra={"adapter": "go2", "op": "emergency_stop"},
        )
        self._release_manual_command_source(restore_switch=True)
        with self._motion_lock:
            self._manual_mode_active = False
        self.damp()

    # ------------------------------------------------------------------
    # Locomotion readiness
    # ------------------------------------------------------------------

    @property
    def locomotion_state(self) -> str:
        return self._get_locomotion_snapshot().locomotion_state

    @property
    def can_move(self) -> bool:
        return self._get_locomotion_snapshot().can_move

    @property
    def block_reason(self) -> str | None:
        return self._get_locomotion_snapshot().block_reason

    # ------------------------------------------------------------------
    # State & telemetry
    # ------------------------------------------------------------------

    def get_state(self) -> RobotState:
        """Return the latest motion state, battery data, and human-readable faults."""
        with self._state_lock:
            state = self._latest_state
            low_state = self._latest_low_state

        self._maybe_refresh_service_states()

        battery_percent: float | None = None
        battery_voltage_v: float | None = None
        battery_current_a: float | None = None
        battery_cycles: int | None = None
        imu_yaw: float | None = None

        faults: list[str] = []
        sport_mode_error: int | None = None
        motion_mode: int | None = None
        bms_status_raw: int | None = None

        if state is None:
            faults.append("No rt/sportmodestate sample received from the robot yet.")
        else:
            imu_yaw = float(state.imu_state.rpy[2])
            sport_mode_error = int(state.error_code)
            motion_mode = int(state.mode)
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

        service_states_snap: dict[str, int] = {}
        with self._service_state_lock:
            service_states_snap = dict(self._service_states)
        sport_svc = service_states_snap.get("sport_mode")
        loco_snapshot = self._get_locomotion_snapshot(latest_state=state, sport_service_status=sport_svc)

        return RobotState(
            battery_percent=battery_percent,
            battery_voltage_v=battery_voltage_v,
            battery_current_a=battery_current_a,
            battery_cycles=battery_cycles,
            imu_yaw=imu_yaw,
            camera_status=self._get_camera_status(),
            faults=faults,
            sport_mode_error=sport_mode_error,
            motion_mode=motion_mode,
            bms_status=bms_status_raw,
            locomotion_state=loco_snapshot.locomotion_state,
            can_move=loco_snapshot.can_move,
            block_reason=loco_snapshot.block_reason,
        )

    def get_pose(self) -> Pose | None:
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

    def capture_frame(self) -> np.ndarray | None:
        """Return latest camera frame as ndarray, or None.

        Called by streaming.py and mission.py (existing interface).
        Internally decodes the JPEG returned by get_camera_frame().
        """
        data = self.get_camera_frame()
        if data is None:
            return None
        buf = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def get_camera_frame(self) -> bytes | None:
        """Return latest camera frame as JPEG bytes, or None.

        Prefer the SDK VideoClient, then fall back to the UDP/GStreamer path.
        """
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
    # SDK callback (called from SDK-internal dispatch thread)
    # ------------------------------------------------------------------

    def _on_state_update(self, msg: SportModeState_) -> None:
        with self._state_lock:
            self._latest_state = msg

    def _on_low_state_update(self, msg: LowState_) -> None:
        with self._state_lock:
            self._latest_low_state = msg

    def _best_effort_sit_down(self) -> None:
        if self._sport is None:
            return

        method_name = "StandDown"
        method = getattr(self._sport, method_name, None)
        if method is not None:
            try:
                method()
                with self._motion_lock:
                    self._motion_ready = False
                    if self._locomotion_state != "disconnected":
                        self._locomotion_state = "idle"
                return
            except Exception as exc:
                _log.warning(
                    "go2 %s failed",
                    method_name,
                    extra={"adapter": "go2", "op": f"shutdown.{method_name}", "err": str(exc)},
                )
        with self._motion_lock:
            self._motion_ready = False
            if self._locomotion_state != "disconnected":
                self._locomotion_state = "idle"

    def _call_activation_step(self, method_name: str, settle_seconds: float) -> None:
        if self._sport is None:
            raise RuntimeError("Go2 sport client is not connected.")

        method = getattr(self._sport, method_name, None)
        if method is None:
            raise RuntimeError(f"SportClient.{method_name} is not available in this SDK build.")

        result = method()
        if result not in (None, 0):
            raise RuntimeError(f"SportClient.{method_name} failed with code={result}.")
        if settle_seconds > 0:
            time.sleep(settle_seconds)

    def _run_activation_sequence(self) -> None:
        motion_mode, sport_mode_error = self._get_latest_motion_flags()

        if self._needs_recovery_stand(motion_mode, sport_mode_error) or self._needs_fault_recovery_stand(
            motion_mode, sport_mode_error
        ):
            if self._needs_fault_recovery_stand(motion_mode, sport_mode_error):
                # Damp resets motor controllers; StandDown is skipped because
                # motion_mode=0 means the robot is already idle/seated and
                # StandDown silently no-ops in that state on Go2 firmware.
                self._call_activation_step("Damp", settle_seconds=2.0)
            self._call_activation_step("RecoveryStand", settle_seconds=2.5)
            self._call_activation_step("BalanceStand", settle_seconds=1.0)
        elif self._needs_balance_stand(motion_mode, sport_mode_error):
            self._call_activation_step("BalanceStand", settle_seconds=1.0)
        else:
            self._call_activation_step("StandUp", settle_seconds=1.5)

        motion_mode, sport_mode_error = self._get_latest_motion_flags()
        if self._needs_recovery_stand(motion_mode, sport_mode_error) or self._needs_fault_recovery_stand(
            motion_mode, sport_mode_error
        ):
            self._call_activation_step("RecoveryStand", settle_seconds=2.5)
            self._call_activation_step("BalanceStand", settle_seconds=1.0)
            motion_mode, sport_mode_error = self._get_latest_motion_flags()

        if self._needs_balance_stand(motion_mode, sport_mode_error):
            self._call_activation_step("BalanceStand", settle_seconds=1.0)

    def _get_latest_motion_flags(self) -> tuple[int | None, int | None]:
        with self._state_lock:
            latest_state = self._latest_state
        if latest_state is None:
            return None, None
        return int(latest_state.mode), int(latest_state.error_code)

    def _needs_recovery_stand(self, motion_mode: int | None, sport_mode_error: int | None) -> bool:
        return (
            sport_mode_error == _SPORT_ERROR_DAMPING
            or motion_mode in _DDS_DAMPING_MOTION_MODES
            or self._locomotion_state == "damped"
        )

    def _needs_balance_stand(self, motion_mode: int | None, sport_mode_error: int | None) -> bool:
        return (
            sport_mode_error == _SPORT_ERROR_STANDING_LOCK
            or motion_mode in _DDS_STANDING_LOCK_MOTION_MODES
        )

    def _needs_fault_recovery_stand(self, motion_mode: int | None, sport_mode_error: int | None) -> bool:
        """Use RecoveryStand for generic sport faults that still report an idle posture.

        This catches post-fall or partially-cleared states where DDS no longer
        reports damping/standing-lock but the robot is not actually motion-ready.
        """
        return (
            sport_mode_error not in (None, 0, _SPORT_ERROR_DAMPING, _SPORT_ERROR_STANDING_LOCK)
            and motion_mode in _DDS_IDLE_MOTION_MODES
        )

    def _claim_manual_command_source(self) -> None:
        if self._obstacle_avoid is None:
            raise RuntimeError("Go2 obstacle-avoid client is not connected.")

        if not self._obstacle_avoid_usable:
            return

        if self._manual_mode_switch_original is None:
            try:
                current_enabled = self._get_obstacle_avoid_enabled()
                self._manual_mode_switch_original = current_enabled
                if not current_enabled:
                    self._set_obstacle_avoid_enabled(True)
            except Exception as exc:
                _log.warning(
                    "go2 obstacle-avoid not available — manual drive will use SportClient fallback",
                    extra={"adapter": "go2", "op": "claim_manual.switch", "err": str(exc)},
                )
                self._manual_mode_switch_original = False
                self._obstacle_avoid_usable = False
                return

        if not self._remote_commands_from_api:
            try:
                self._set_remote_command_source(True)
            except Exception as exc:
                _log.warning(
                    "go2 UseRemoteCommandFromApi failed — manual drive will use SportClient fallback",
                    extra={"adapter": "go2", "op": "claim_manual.api_source", "err": str(exc)},
                )
                self._obstacle_avoid_usable = False

    def _release_manual_command_source(self, restore_switch: bool) -> None:
        with self._motion_lock:
            if self._remote_commands_from_api:
                try:
                    self._set_remote_command_source(False)
                except Exception as exc:
                    _log.warning(
                        "go2 UseRemoteCommandFromApi(false) failed",
                        extra={"adapter": "go2", "op": "manual_release", "err": str(exc)},
                    )

            if restore_switch and self._manual_mode_switch_original is not None:
                if self._obstacle_avoid_usable:
                    try:
                        self._set_obstacle_avoid_enabled(self._manual_mode_switch_original)
                    except Exception as exc:
                        _log.warning(
                            "go2 obstacle avoid restore failed",
                            extra={"adapter": "go2", "op": "manual_restore_switch", "err": str(exc)},
                        )
                self._manual_mode_switch_original = None

    def _send_manual_move(self, vx: float, vy: float, vyaw: float) -> None:
        self._claim_manual_command_source()
        if self._obstacle_avoid_usable and self._obstacle_avoid is not None:
            result = self._obstacle_avoid.Move(vx, vy, vyaw)
            if result not in (None, 0):
                raise RuntimeError(f"ObstaclesAvoidClient.Move failed with code={result}.")
        else:
            if self._sport is None:
                raise RuntimeError("Go2 sport client is not connected.")
            result = self._sport.Move(vx, vy, vyaw)
            if result not in (None, 0):
                raise RuntimeError(f"SportClient.Move (manual fallback) failed with code={result}.")

    def _get_obstacle_avoid_enabled(self) -> bool:
        if self._obstacle_avoid is None:
            raise RuntimeError("Go2 obstacle-avoid client is not connected.")
        code, enabled = self._obstacle_avoid.SwitchGet()
        if code != 0 or enabled is None:
            raise RuntimeError(f"ObstaclesAvoidClient.SwitchGet failed with code={code}.")
        return bool(enabled)

    def _set_obstacle_avoid_enabled(self, enabled: bool) -> None:
        if self._obstacle_avoid is None:
            raise RuntimeError("Go2 obstacle-avoid client is not connected.")
        code = self._obstacle_avoid.SwitchSet(enabled)
        if code not in (None, 0):
            raise RuntimeError(f"ObstaclesAvoidClient.SwitchSet failed with code={code}.")

    def _set_remote_command_source(self, enabled: bool) -> None:
        if self._obstacle_avoid is None:
            raise RuntimeError("Go2 obstacle-avoid client is not connected.")
        code = self._obstacle_avoid.UseRemoteCommandFromApi(enabled)
        if code not in (None, 0):
            raise RuntimeError(f"ObstaclesAvoidClient.UseRemoteCommandFromApi failed with code={code}.")
        self._remote_commands_from_api = enabled

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

    def _get_locomotion_snapshot(
        self,
        *,
        latest_state: SportModeState_ | None = None,
        sport_service_status: int | None | object = _UNSET,
    ) -> _LocomotionSnapshot:
        with self._motion_lock:
            command_state = self._locomotion_state
            sport_connected = self._sport is not None
        if latest_state is None:
            with self._state_lock:
                latest_state = self._latest_state
        if sport_service_status is _UNSET:
            with self._service_state_lock:
                sport_service_status = self._service_states.get("sport_mode")

        motion_mode = int(latest_state.mode) if latest_state is not None else None
        sport_mode_error = int(latest_state.error_code) if latest_state is not None else None
        locomotion_state = self._derive_locomotion_state(
            command_state=command_state,
            sport_connected=sport_connected,
            motion_mode=motion_mode,
            sport_mode_error=sport_mode_error,
            sport_service_status=sport_service_status,
        )
        can_move = locomotion_state in ("ready", "moving")
        return _LocomotionSnapshot(
            locomotion_state=locomotion_state,
            can_move=can_move,
            block_reason=self._block_reason_for_state(locomotion_state, sport_connected),
            motion_mode=motion_mode,
            sport_mode_error=sport_mode_error,
        )

    def _derive_locomotion_state(
        self,
        *,
        command_state: str,
        sport_connected: bool,
        motion_mode: int | None,
        sport_mode_error: int | None,
        sport_service_status: int | None | object,
    ) -> str:
        if not sport_connected or command_state == "disconnected":
            return "disconnected"
        if sport_service_status not in (_UNSET, None, 1):
            return "fault"
        if command_state == "fault":
            return "fault"
        if sport_mode_error == _SPORT_ERROR_DAMPING or motion_mode in _DDS_DAMPING_MOTION_MODES or command_state == "damped":
            return "damped"
        if sport_mode_error is not None and sport_mode_error != 0:
            return "fault"
        if motion_mode in _DDS_READY_MOTION_MODES:
            if motion_mode == 3 and command_state == "moving":
                return "moving"
            return "ready"
        if motion_mode in _DDS_IDLE_MOTION_MODES:
            return "idle"
        if command_state == "activating":
            return "activating"
        return command_state

    def _block_reason_for_state(self, locomotion_state: str, sport_connected: bool) -> str | None:
        if locomotion_state in ("ready", "moving"):
            return None
        if locomotion_state == "disconnected" or not sport_connected:
            return "sdk_not_connected"
        if locomotion_state in ("idle", "activating"):
            return "robot_idle"
        if locomotion_state == "damped":
            return "robot_damped"
        if locomotion_state == "fault":
            return "fault_present"
        return "sdk_not_connected"
