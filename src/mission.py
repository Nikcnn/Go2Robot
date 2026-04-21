from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from pydantic import ValidationError

from .analysis import analyze
from .models import CheckpointStep, CommandSource, MissionStatus, MotionCommand, RouteModel


def load_route_file(path: Union[str, Path]) -> RouteModel:
    route_path = Path(path)
    data = json.loads(route_path.read_text(encoding="utf-8"))
    try:
        return RouteModel.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid route file {route_path}: {exc}") from exc


def resolve_route_path(routes_dir: Union[str, Path], route_id: str) -> Path:
    routes_path = Path(routes_dir)
    direct_candidate = routes_path / route_id
    if direct_candidate.exists():
        return direct_candidate

    filename_candidate = routes_path / f"{route_id}.json"
    if filename_candidate.exists():
        return filename_candidate

    for candidate in sorted(routes_path.glob("*.json")):
        route = load_route_file(candidate)
        if route.route_id == route_id:
            return candidate

    raise FileNotFoundError(f"Route '{route_id}' was not found under {routes_path}.")


class MissionManager:
    def __init__(
        self,
        routes_dir: Union[str, Path],
        project_root: Union[str, Path],
        control,
        adapter,
        telemetry,
        storage,
        analysis_threshold: float,
        event_callback,
        realsense_camera=None,
    ) -> None:
        self.routes_dir = Path(routes_dir)
        self.project_root = Path(project_root)
        self.control = control
        self.adapter = adapter
        self.telemetry = telemetry
        self.storage = storage
        self.analysis_threshold = analysis_threshold
        self.event_callback = event_callback
        self.realsense_camera = realsense_camera
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def start(self, route_id: str) -> str:
        route_path = resolve_route_path(self.routes_dir, route_id)
        route = load_route_file(route_path)
        return self.start_route(route)

    def start_route(self, route: RouteModel) -> str:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("A mission is already running.")
            if not self.control.can_start_mission():
                raise RuntimeError("Mission cannot start in the current control state.")
            run = self.storage.start_run(route.route_id)
            self.control.begin_mission(run.mission_id, route.route_id)
            self._thread = threading.Thread(target=self._run_mission, args=(route,), name="mission-executor", daemon=True)
            self._thread.start()
            return run.mission_id

    def shutdown(self) -> None:
        thread = None
        with self._lock:
            thread = self._thread
        if thread and thread.is_alive():
            self.control.abort_mission()
            thread.join(timeout=2.0)

    def _run_mission(self, route: RouteModel) -> None:
        try:
            self.control.mark_running()
            for step in route.steps:
                if not self.control.wait_until_runnable():
                    break
                self.control.set_active_step(step.id)
                self.event_callback("step_started", {"step_id": step.id, "step_type": step.type})

                if step.type == "stand_up":
                    self.control.stand_up()
                    if not self.control.wait_for_settle():
                        break
                elif step.type in {"move", "move_velocity", "rotate"}:
                    if not self._execute_motion(step.vx, step.vy, step.vyaw, step.duration_sec):
                        break
                elif step.type in {"wait", "settle"}:
                    if not self._sleep_with_checks(step.duration_sec):
                        break
                elif step.type == "checkpoint":
                    if not self._handle_checkpoint(step):
                        break
                elif step.type == "stop":
                    self.control.stop_motion("mission stop step")

                self.control.mark_step_completed()
                self.event_callback("step_completed", {"step_id": step.id, "step_type": step.type})

            current = self.control.current()
            if current.mission_status == MissionStatus.RUNNING:
                self.control.complete_mission()
        except Exception as exc:
            self.control.fail_mission(str(exc))
        finally:
            final_state = self.control.current()
            self.storage.finalize_run(final_state.mission_status.value, final_state.steps_executed)
            with self._lock:
                self._thread = None

    def _execute_motion(self, vx: float, vy: float, vyaw: float, duration_sec: float) -> bool:
        remaining = duration_sec
        period = 0.05
        while remaining > 0:
            if not self.control.wait_until_runnable():
                self.control.stop_motion("mission blocked")
                current = self.control.current()
                self.event_callback("movement_blocked", {
                    "reason": f"mission_status={current.mission_status.value}",
                    "vx": vx, "vy": vy, "vyaw": vyaw,
                    "mission_id": current.mission_id,
                })
                return False
            self.control.submit(MotionCommand(vx=vx, vy=vy, vyaw=vyaw), CommandSource.AUTO)
            chunk = min(period, remaining)
            time.sleep(chunk)
            remaining -= chunk
        self.control.stop_motion("mission step completed")
        return True

    def _handle_checkpoint(self, step: CheckpointStep) -> bool:
        self.control.stop_motion("checkpoint settle")
        if not self._sleep_with_checks(step.settle_time_sec):
            return False

        frame = self.adapter.capture_frame()
        telemetry_snapshot = self.telemetry.get_latest().model_dump(mode="json")
        analysis_result = analyze(
            frame,
            step.analyzer,
            {
                "reference_image": self._resolve_reference_image(step.reference_image),
                "threshold": self.analysis_threshold,
            },
        )
        sensor_captures = self._capture_sensor_snapshots(step.waypoint_id)
        self.storage.save_checkpoint(
            step.waypoint_id,
            frame,
            analysis_result,
            telemetry_snapshot,
            sensor_captures=sensor_captures,
        )
        self.event_callback(
            "checkpoint_processed",
            {"waypoint_id": step.waypoint_id, "analyzer": analysis_result.get("analyzer"), "result": analysis_result.get("result")},
        )
        return True

    def _sleep_with_checks(self, duration_sec: float) -> bool:
        remaining = duration_sec
        while remaining > 0:
            if not self.control.wait_until_runnable():
                return False
            chunk = min(0.05, remaining)
            time.sleep(chunk)
            remaining -= chunk
        return True

    def _resolve_reference_image(self, reference_image: Optional[str]) -> Optional[str]:
        if not reference_image:
            return None
        candidate = Path(reference_image)
        if candidate.is_absolute():
            return str(candidate)
        return str((self.project_root / candidate).resolve())

    def _capture_sensor_snapshots(self, waypoint_id: str) -> dict[str, dict]:
        if self.realsense_camera is None or not self.realsense_camera.is_enabled():
            return {}

        run_dir = self.storage.active_run_dir()
        if run_dir is None:
            return {
                "realsense": {
                    "sensor": "realsense_d435i",
                    "status": "error",
                    "error": "No active mission run directory is available for RealSense artifacts.",
                    "timestamp": datetime.now(timezone.utc),
                    "waypoint_id": waypoint_id,
                }
            }

        try:
            snapshot = self.realsense_camera.capture_snapshot(run_dir=run_dir, waypoint_id=waypoint_id)
        except Exception as exc:
            snapshot = {
                "sensor": "realsense_d435i",
                "status": "error",
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc),
                "waypoint_id": waypoint_id,
            }

        if snapshot.get("status") not in {"ok", "disabled"}:
            self.event_callback(
                "warning",
                {
                    "reason": snapshot.get("error") or "RealSense checkpoint capture unavailable.",
                    "sensor": "realsense_d435i",
                    "status": snapshot.get("status"),
                    "waypoint_id": waypoint_id,
                },
            )

        return {"realsense": snapshot}
