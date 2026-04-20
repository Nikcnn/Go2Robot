from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from go2_interfaces.srv import CheckpointCapture

TASK_TO_ANALYZER = {
    "inspect_panel": "simple_presence",
    "thermal_check": "simple_presence",
}


def _resolve_operator_app_root() -> Path:
    candidates: list[Path] = []
    env_value = os.environ.get("GO2_OPERATOR_APP_ROOT")
    if env_value:
        candidates.append(Path(env_value).expanduser().resolve())

    here = Path(__file__).resolve()
    candidates.extend(parent.resolve() for parent in here.parents)

    for candidate in candidates:
        if (candidate / "src" / "storage.py").exists() and (candidate / "src" / "analysis.py").exists():
            return candidate

    raise RuntimeError(
        "Unable to locate the existing operator app package under src/. "
        "Set GO2_OPERATOR_APP_ROOT to the Go2Robot repository root "
        "or build the workspace with --symlink-install."
    )


@lru_cache(maxsize=1)
def _load_operator_components() -> dict[str, object]:
    operator_root = _resolve_operator_app_root()
    if str(operator_root) not in sys.path:
        sys.path.insert(0, str(operator_root))

    from src.analysis import analyze
    from src.models import MissionStatus, Pose, RobotMode, RobotState, TelemetrySnapshot
    from src.storage import StorageManager

    return {
        "analyze": analyze,
        "MissionStatus": MissionStatus,
        "Pose": Pose,
        "RobotMode": RobotMode,
        "RobotState": RobotState,
        "StorageManager": StorageManager,
        "TelemetrySnapshot": TelemetrySnapshot,
    }


class CheckpointInspector:
    def __init__(self) -> None:
        components = _load_operator_components()
        self._analyze = components["analyze"]

    def inspect(
        self,
        *,
        waypoint_id: str,
        task: str,
        frame: np.ndarray | None,
        robot_state,
        pose,
    ) -> dict:
        analyzer = TASK_TO_ANALYZER.get(task, "simple_presence")
        result = self._analyze(frame, analyzer, {"task": task})
        details = result.setdefault("details", {})
        details["task"] = task
        details["waypoint_id"] = waypoint_id
        details["robot_faults"] = list(getattr(robot_state, "faults", []))
        details["pose"] = None if pose is None else pose.model_dump(mode="json")
        return result


class CheckpointTaskRunner:
    def __init__(self, node, runs_dir: Path, bridge_service_name: str = "capture_checkpoint") -> None:
        components = _load_operator_components()
        self._node = node
        self._MissionStatus = components["MissionStatus"]
        self._Pose = components["Pose"]
        self._RobotMode = components["RobotMode"]
        self._RobotState = components["RobotState"]
        self._StorageManager = components["StorageManager"]
        self._TelemetrySnapshot = components["TelemetrySnapshot"]
        self._storage = self._StorageManager(runs_dir)
        self._inspector = CheckpointInspector()
        self._capture_client = node.create_client(CheckpointCapture, bridge_service_name)

    def wait_for_bridge(self, timeout_sec: float) -> bool:
        return self._capture_client.wait_for_service(timeout_sec=timeout_sec)

    def start_run(self, route_id: str):
        return self._storage.start_run(route_id)

    def active_run_id(self) -> str | None:
        return self._storage.active_mission_id()

    def record_event(self, event: str, details: dict | None = None) -> dict:
        return self._storage.record_event(event, details)

    def finalize_run(self, mission_status: str, steps_executed: int):
        return self._storage.finalize_run(mission_status, steps_executed)

    def process_waypoint(self, mission_id: str, waypoint_id: str, task: str) -> dict:
        request = CheckpointCapture.Request()
        request.waypoint_id = waypoint_id
        future = self._capture_client.call_async(request)

        deadline = time.monotonic() + 15.0
        while not future.done():
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for bridge checkpoint capture at {waypoint_id}.")
            time.sleep(0.05)

        response = future.result()
        if response is None or not response.success:
            message = "no response" if response is None else response.message
            raise RuntimeError(f"Bridge checkpoint capture failed for {waypoint_id}: {message}")

        frame = None
        if response.image_jpeg:
            buffer = np.frombuffer(bytes(response.image_jpeg), dtype=np.uint8)
            frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)

        robot_state = self._RobotState.model_validate(json.loads(response.robot_state_json))
        pose = None
        if response.pose_json:
            pose = self._Pose.model_validate(json.loads(response.pose_json))

        analysis_result = self._inspector.inspect(
            waypoint_id=waypoint_id,
            task=task,
            frame=frame,
            robot_state=robot_state,
            pose=pose,
        )

        telemetry_snapshot = self._TelemetrySnapshot(
            timestamp=datetime.now(timezone.utc),
            mode=self._RobotMode.AUTO,
            mission_status=self._MissionStatus.RUNNING,
            route_id=mission_id,
            active_step_id=waypoint_id,
            mission_id=self.active_run_id(),
            pose=pose,
            robot_state=robot_state,
        )

        checkpoint_record = self._storage.save_checkpoint(
            waypoint_id,
            frame,
            analysis_result,
            telemetry_snapshot.model_dump(mode="json"),
        )
        self.record_event(
            "checkpoint_processed",
            {
                "waypoint_id": waypoint_id,
                "task": task,
                "bridge_message": response.message,
                "result": analysis_result.get("result"),
            },
        )
        return {
            "checkpoint": checkpoint_record,
            "analysis": analysis_result,
        }
