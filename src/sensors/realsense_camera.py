from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

import cv2
import numpy as np

from ..config import RealsenseConfig

try:
    import pyrealsense2 as rs  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised via service status tests
    rs = None


_DEFAULT_RS_MODULE = object()
_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _FrameBundle:
    timestamp: datetime
    sequence_id: int
    color_frame_id: Optional[int]
    depth_frame_id: Optional[int]
    color_frame: Optional[np.ndarray]
    depth_frame: Optional[np.ndarray]


class RealsenseCameraService:
    def __init__(self, config: RealsenseConfig, rs_module: Any = _DEFAULT_RS_MODULE) -> None:
        self.config = config
        self._rs = rs if rs_module is _DEFAULT_RS_MODULE else rs_module
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pipeline: Optional[Any] = None
        self._align: Optional[Any] = None
        self._running = False
        self._available = False
        self._status = "disabled" if not config.enabled else "waiting_to_start"
        self._error: Optional[str] = None
        self._sequence_id = 0
        self._last_frame_at: Optional[datetime] = None
        self._latest: Optional[_FrameBundle] = None
        self._color_intrinsics: Optional[dict[str, Any]] = None
        self._depth_intrinsics: Optional[dict[str, Any]] = None

    def start(self) -> None:
        with self._lock:
            if self._running:
                return

        if not self.config.enabled:
            self._set_status("disabled", available=False, error=None)
            return

        if not self.config.enable_color and not self.config.enable_depth:
            self._handle_start_failure("RealSense enabled but both color and depth streams are disabled.")
            return

        if self._rs is None:
            self._handle_start_failure("pyrealsense2 is not installed; RealSense camera is unavailable.")
            return

        pipeline = None
        try:
            pipeline = self._rs.pipeline()
            rs_config = self._rs.config()
            if self.config.enable_color:
                rs_config.enable_stream(
                    self._rs.stream.color,
                    self.config.width,
                    self.config.height,
                    self._rs.format.bgr8,
                    self.config.fps,
                )
            if self.config.enable_depth:
                rs_config.enable_stream(
                    self._rs.stream.depth,
                    self.config.width,
                    self.config.height,
                    self._rs.format.z16,
                    self.config.fps,
                )

            profile = pipeline.start(rs_config)
            align = None
            if self.config.enable_color and self.config.enable_depth:
                align = self._rs.align(self._rs.stream.color)

            with self._lock:
                self._pipeline = pipeline
                self._align = align
                self._color_intrinsics = self._read_intrinsics(profile, self._rs.stream.color) if self.config.enable_color else None
                self._depth_intrinsics = self._read_intrinsics(profile, self._rs.stream.depth) if self.config.enable_depth else None

            self._capture_once(timeout_ms=max(1000, int(3000 / max(1, self.config.fps))))

            with self._lock:
                self._running = True
                self._available = True
                self._stop_event.clear()
                self._thread = threading.Thread(target=self._run, name="realsense-poller", daemon=True)
                self._thread.start()
                self._status = "streaming"
                self._error = None
        except Exception as exc:
            try:
                if pipeline is not None:
                    pipeline.stop()
            except Exception:
                pass
            with self._lock:
                self._pipeline = None
                self._align = None
                self._running = False
                self._available = False
            self._handle_start_failure(f"Failed to start RealSense pipeline: {exc}", exc=exc)

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            pipeline = self._pipeline
            self._thread = None
            self._pipeline = None
            self._align = None
            self._running = False
            self._available = False
            self._stop_event.set()
            self._status = "disabled" if not self.config.enabled else "stopped"

        if thread is not None:
            thread.join(timeout=1.5)

        if pipeline is not None:
            try:
                pipeline.stop()
            except Exception as exc:
                _log.warning("realsense stop failed", extra={"err": str(exc)})

    def is_enabled(self) -> bool:
        return self.config.enabled

    def is_available(self) -> bool:
        with self._lock:
            return self._available

    def get_latest_color_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._latest is None or self._latest.color_frame is None:
                return None
            return self._latest.color_frame.copy()

    def get_latest_depth_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._latest is None or self._latest.depth_frame is None:
                return None
            return self._latest.depth_frame.copy()

    def capture_snapshot(self, run_dir: Union[str, Path], waypoint_id: str) -> dict[str, Any]:
        status = self.get_status()
        if not self.config.enabled:
            return self._snapshot_result(
                status="disabled",
                timestamp=datetime.now(timezone.utc),
                waypoint_id=waypoint_id,
                error=None,
            )

        bundle = self._get_latest_bundle_copy()
        if bundle is None and self._pipeline is not None:
            try:
                bundle = self._capture_once(timeout_ms=1000)
            except Exception as exc:
                status = self.get_status()
                return self._snapshot_result(
                    status="error",
                    timestamp=datetime.now(timezone.utc),
                    waypoint_id=waypoint_id,
                    error=str(exc) or status.get("status"),
                )

        if bundle is None:
            return self._snapshot_result(
                status="unavailable",
                timestamp=datetime.now(timezone.utc),
                waypoint_id=waypoint_id,
                error=status.get("error") or status.get("status"),
            )

        sensor_dir = Path(run_dir) / "realsense"
        sensor_dir.mkdir(parents=True, exist_ok=True)
        suffix = bundle.timestamp.strftime("%Y%m%dT%H%M%S%fZ")
        prefix = f"{waypoint_id}_{suffix}"

        color_rel_path = None
        depth_rel_path = None
        depth_preview_rel_path = None

        if bundle.color_frame is not None:
            color_name = f"{prefix}_color.jpg"
            color_path = sensor_dir / color_name
            if not cv2.imwrite(str(color_path), bundle.color_frame):
                raise RuntimeError(f"Failed to write RealSense color image to {color_path}.")
            color_rel_path = color_path.relative_to(run_dir).as_posix()

        if bundle.depth_frame is not None:
            depth_name = f"{prefix}_depth.npy"
            depth_path = sensor_dir / depth_name
            np.save(depth_path, bundle.depth_frame)
            depth_rel_path = depth_path.relative_to(run_dir).as_posix()

            preview = self._build_depth_preview(bundle.depth_frame)
            preview_name = f"{prefix}_depth_preview.png"
            preview_path = sensor_dir / preview_name
            if not cv2.imwrite(str(preview_path), preview):
                raise RuntimeError(f"Failed to write RealSense depth preview to {preview_path}.")
            depth_preview_rel_path = preview_path.relative_to(run_dir).as_posix()

        width, height = self._resolve_resolution(bundle)
        return self._snapshot_result(
            status="ok",
            timestamp=bundle.timestamp,
            waypoint_id=waypoint_id,
            error=None,
            sequence_id=bundle.sequence_id,
            color_frame_id=bundle.color_frame_id,
            depth_frame_id=bundle.depth_frame_id,
            color_image_path=color_rel_path,
            depth_npy_path=depth_rel_path,
            depth_preview_path=depth_preview_rel_path,
            resolution={"width": width, "height": height} if width is not None and height is not None else None,
            intrinsics={"color": self._copy_mapping(self._color_intrinsics), "depth": self._copy_mapping(self._depth_intrinsics)},
        )

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": "realsense_d435i",
                "source_name": "Intel RealSense D435i",
                "source_type": "rgbd_imu",
                "enabled": self.config.enabled,
                "startup_required": self.config.startup_required,
                "available": self._available,
                "running": self._running,
                "status": self._status,
                "error": self._error,
                "width": self.config.width,
                "height": self.config.height,
                "fps": self.config.fps,
                "color_enabled": self.config.enable_color,
                "depth_enabled": self.config.enable_depth,
                "last_frame_timestamp": self._last_frame_at,
            }

    def _run(self) -> None:
        period = 1.0 / float(max(1, self.config.fps))
        timeout_ms = max(1000, int(period * 4000))
        while not self._stop_event.wait(period):
            try:
                self._capture_once(timeout_ms=timeout_ms)
            except Exception as exc:
                self._set_status(f"stream_error: {exc}", available=False, error=str(exc))
                _log.warning("realsense frame poll failed", extra={"err": str(exc)})

    def _capture_once(self, timeout_ms: int) -> _FrameBundle:
        with self._lock:
            pipeline = self._pipeline
            align = self._align

        if pipeline is None:
            raise RuntimeError("RealSense pipeline is not started.")

        frames = pipeline.wait_for_frames(timeout_ms)
        if align is not None:
            frames = align.process(frames)

        color_frame = frames.get_color_frame() if self.config.enable_color else None
        depth_frame = frames.get_depth_frame() if self.config.enable_depth else None

        if self.config.enable_color and not color_frame:
            raise RuntimeError("RealSense color stream did not return a frame.")
        if self.config.enable_depth and not depth_frame:
            raise RuntimeError("RealSense depth stream did not return a frame.")

        bundle = _FrameBundle(
            timestamp=datetime.now(timezone.utc),
            sequence_id=self._next_sequence_id(),
            color_frame_id=int(color_frame.get_frame_number()) if color_frame else None,
            depth_frame_id=int(depth_frame.get_frame_number()) if depth_frame else None,
            color_frame=np.asanyarray(color_frame.get_data()).copy() if color_frame else None,
            depth_frame=np.asanyarray(depth_frame.get_data()).copy().astype(np.uint16, copy=False) if depth_frame else None,
        )

        with self._lock:
            self._latest = bundle
            self._available = True
            self._last_frame_at = bundle.timestamp
            if self.config.enabled:
                self._status = "streaming"
            self._error = None

        return bundle

    def _get_latest_bundle_copy(self) -> Optional[_FrameBundle]:
        with self._lock:
            if self._latest is None:
                return None
            return _FrameBundle(
                timestamp=self._latest.timestamp,
                sequence_id=self._latest.sequence_id,
                color_frame_id=self._latest.color_frame_id,
                depth_frame_id=self._latest.depth_frame_id,
                color_frame=self._latest.color_frame.copy() if self._latest.color_frame is not None else None,
                depth_frame=self._latest.depth_frame.copy() if self._latest.depth_frame is not None else None,
            )

    def _handle_start_failure(self, message: str, exc: Optional[Exception] = None) -> None:
        self._set_status(message, available=False, error=message)
        if self.config.startup_required:
            raise RuntimeError(message) from exc
        _log.warning("realsense unavailable", extra={"err": message})

    def _set_status(self, status: str, *, available: bool, error: Optional[str]) -> None:
        with self._lock:
            self._status = status
            self._available = available
            self._error = error

    def _read_intrinsics(self, profile: Any, stream: Any) -> Optional[dict[str, Any]]:
        try:
            stream_profile = profile.get_stream(stream).as_video_stream_profile()
            intrinsics = stream_profile.get_intrinsics()
        except Exception:
            return None
        return {
            "width": int(intrinsics.width),
            "height": int(intrinsics.height),
            "fx": float(intrinsics.fx),
            "fy": float(intrinsics.fy),
            "ppx": float(intrinsics.ppx),
            "ppy": float(intrinsics.ppy),
            "coeffs": [float(value) for value in intrinsics.coeffs],
        }

    def _next_sequence_id(self) -> int:
        with self._lock:
            self._sequence_id += 1
            return self._sequence_id

    def _snapshot_result(
        self,
        *,
        status: str,
        timestamp: datetime,
        waypoint_id: str,
        error: Optional[str],
        sequence_id: Optional[int] = None,
        color_frame_id: Optional[int] = None,
        depth_frame_id: Optional[int] = None,
        color_image_path: Optional[str] = None,
        depth_npy_path: Optional[str] = None,
        depth_preview_path: Optional[str] = None,
        resolution: Optional[dict[str, int]] = None,
        intrinsics: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return {
            "sensor": "realsense_d435i",
            "source_name": "Intel RealSense D435i",
            "source_type": "rgbd_imu",
            "waypoint_id": waypoint_id,
            "timestamp": timestamp,
            "status": status,
            "error": error,
            "sequence_id": sequence_id,
            "color_frame_id": color_frame_id,
            "depth_frame_id": depth_frame_id,
            "color_image_path": color_image_path,
            "depth_npy_path": depth_npy_path,
            "depth_preview_path": depth_preview_path,
            "resolution": resolution,
            "intrinsics": intrinsics,
        }

    def _resolve_resolution(self, bundle: _FrameBundle) -> tuple[Optional[int], Optional[int]]:
        frame = bundle.color_frame if bundle.color_frame is not None else bundle.depth_frame
        if frame is None:
            return None, None
        return int(frame.shape[1]), int(frame.shape[0])

    def _build_depth_preview(self, depth_frame: np.ndarray) -> np.ndarray:
        normalized = cv2.normalize(depth_frame, None, 0, 255, cv2.NORM_MINMAX)
        preview = cv2.applyColorMap(normalized.astype(np.uint8), cv2.COLORMAP_JET)
        return preview

    def _copy_mapping(self, value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if value is None:
            return None
        return {key: list(item) if isinstance(item, list) else item for key, item in value.items()}
