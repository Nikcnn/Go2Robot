from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

import json
import math
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import FollowWaypoints
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rclpy.action import ActionClient
from rclpy.node import Node

from .checkpoint_tasks import CheckpointTaskRunner, _resolve_operator_app_root


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CoordinateWaypoint(StrictModel):
    id: str
    x: float
    y: float
    yaw: float
    task: str


class CoordinateMission(StrictModel):
    mission_id: str
    map_id: str
    waypoints: List[CoordinateWaypoint] = Field(default_factory=list)


@dataclass
class MissionRuntimeState:
    mission_id: Optional[str] = None
    run_id: Optional[str] = None
    map_id: Optional[str] = None
    mission_status: str = "IDLE"
    active_waypoint_id: Optional[str] = None
    completed_waypoints: int = 0
    total_waypoints: int = 0
    mission_path: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    last_error: Optional[str] = None


class MissionCancelled(RuntimeError):
    """Raised when a mission is cancelled externally."""


class MissionExecutorNode(Node):
    def __init__(self) -> None:
        super().__init__("go2_mission_executor")

        operator_root = _resolve_operator_app_root()
        self.declare_parameter("bridge_service_name", "capture_checkpoint")
        self.declare_parameter("follow_waypoints_action_name", "follow_waypoints")
        self.declare_parameter("mission_frame", "map")
        self.declare_parameter("runs_dir", str(operator_root / "runs"))
        self.declare_parameter("bridge_wait_timeout_sec", 5.0)
        self.declare_parameter("nav_server_wait_timeout_sec", 10.0)

        self._mission_frame = self.get_parameter("mission_frame").get_parameter_value().string_value
        self._action_name = self.get_parameter("follow_waypoints_action_name").get_parameter_value().string_value
        bridge_service_name = self.get_parameter("bridge_service_name").get_parameter_value().string_value
        runs_dir = Path(self.get_parameter("runs_dir").get_parameter_value().string_value)

        self._checkpoint_runner = CheckpointTaskRunner(
            self,
            runs_dir=runs_dir,
            bridge_service_name=bridge_service_name,
        )
        self._follow_waypoints_client = ActionClient(self, FollowWaypoints, self._action_name)

        self._state_lock = threading.Lock()
        self._runtime_state = MissionRuntimeState()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._active_goal_handle = None

    def start_mission(
        self,
        *,
        mission_path: Optional[str] = None,
        mission_json: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        mission, resolved_path = self._load_mission(mission_path=mission_path, mission_json=mission_json)

        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return False, "A ROS 2 mission is already running.", None

        bridge_wait_timeout = self.get_parameter("bridge_wait_timeout_sec").get_parameter_value().double_value
        if not self._checkpoint_runner.wait_for_bridge(timeout_sec=bridge_wait_timeout):
            return False, "go2_bridge capture service is unavailable.", None

        nav_wait_timeout = self.get_parameter("nav_server_wait_timeout_sec").get_parameter_value().double_value
        if not self._follow_waypoints_client.wait_for_server(timeout_sec=nav_wait_timeout):
            return False, f"Nav2 FollowWaypoints action server '{self._action_name}' is unavailable.", None

        run_context = self._checkpoint_runner.start_run(mission.mission_id)
        self._checkpoint_runner.record_event(
            "mission_started",
            {
                "mission_id": mission.mission_id,
                "map_id": mission.map_id,
                "waypoint_count": len(mission.waypoints),
                "mission_path": resolved_path,
            },
        )

        with self._state_lock:
            self._runtime_state = MissionRuntimeState(
                mission_id=mission.mission_id,
                run_id=run_context.mission_id,
                map_id=mission.map_id,
                mission_status="STARTING",
                completed_waypoints=0,
                total_waypoints=len(mission.waypoints),
                mission_path=resolved_path,
                started_at=datetime.now(timezone.utc).isoformat(),
                finished_at=None,
                last_error=None,
            )
            self._stop_event = threading.Event()
            self._thread = threading.Thread(
                target=self._run_mission,
                args=(mission,),
                name="go2-mission-executor",
                daemon=True,
            )
            self._thread.start()

        return True, f"Mission {mission.mission_id} accepted.", mission.mission_id

    def cancel_mission(self) -> Tuple[bool, str]:
        with self._state_lock:
            if self._thread is None or not self._thread.is_alive():
                return False, "No active ROS 2 mission is running."
            self._stop_event.set()
            goal_handle = self._active_goal_handle

        if goal_handle is not None:
            goal_handle.cancel_goal_async()

        return True, "Mission cancel requested."

    def get_state_dict(self) -> Dict:
        with self._state_lock:
            return asdict(self._runtime_state)

    def shutdown(self) -> None:
        self.cancel_mission()
        thread = None
        with self._state_lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)

    def _load_mission(
        self,
        *,
        mission_path: Optional[str],
        mission_json: Optional[str],
    ) -> Tuple[CoordinateMission, Optional[str]]:
        if mission_json:
            payload = json.loads(mission_json)
            try:
                return CoordinateMission.model_validate(payload), None
            except ValidationError as exc:
                raise ValueError(f"Invalid inline mission JSON: {exc}") from exc

        if not mission_path:
            raise ValueError("A mission_path or mission_json payload is required for command=start.")

        path = Path(mission_path).expanduser().resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        try:
            mission = CoordinateMission.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid mission file {path}: {exc}") from exc
        return mission, str(path)

    def _run_mission(self, mission: CoordinateMission) -> None:
        try:
            self._update_state(mission_status="RUNNING")
            for index, waypoint in enumerate(mission.waypoints, start=1):
                if self._stop_event.is_set():
                    raise MissionCancelled("Mission cancelled before waypoint dispatch.")

                self._update_state(active_waypoint_id=waypoint.id)
                self._checkpoint_runner.record_event(
                    "step_started",
                    {
                        "step_id": waypoint.id,
                        "step_type": "waypoint",
                        "task": waypoint.task,
                        "index": index,
                        "total": len(mission.waypoints),
                    },
                )

                nav_result = self._navigate_to_waypoint(waypoint)
                if nav_result["status"] == "canceled":
                    raise MissionCancelled(nav_result["message"])
                if nav_result["status"] != "succeeded":
                    raise RuntimeError(nav_result["message"])

                self._checkpoint_runner.record_event(
                    "waypoint_arrived",
                    {
                        "waypoint_id": waypoint.id,
                        "task": waypoint.task,
                        "index": index,
                    },
                )

                self._checkpoint_runner.process_waypoint(
                    mission_id=mission.mission_id,
                    waypoint_id=waypoint.id,
                    task=waypoint.task,
                )

                self._checkpoint_runner.record_event(
                    "step_completed",
                    {
                        "step_id": waypoint.id,
                        "step_type": "waypoint",
                        "task": waypoint.task,
                        "index": index,
                    },
                )
                self._update_state(completed_waypoints=index)

            self._checkpoint_runner.record_event(
                "mission_completed",
                {
                    "mission_id": mission.mission_id,
                    "completed_waypoints": len(mission.waypoints),
                },
            )
            self._checkpoint_runner.finalize_run("COMPLETED", len(mission.waypoints))
            self._update_state(
                mission_status="COMPLETED",
                active_waypoint_id=None,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
        except MissionCancelled as exc:
            completed = self.get_state_dict()["completed_waypoints"]
            self._checkpoint_runner.record_event(
                "mission_aborted",
                {
                    "mission_id": mission.mission_id,
                    "reason": str(exc),
                },
            )
            self._checkpoint_runner.finalize_run("ABORTED", completed)
            self._update_state(
                mission_status="ABORTED",
                active_waypoint_id=None,
                finished_at=datetime.now(timezone.utc).isoformat(),
                last_error=str(exc),
            )
        except Exception as exc:
            completed = self.get_state_dict()["completed_waypoints"]
            self._checkpoint_runner.record_event(
                "error",
                {
                    "mission_id": mission.mission_id,
                    "message": str(exc),
                },
            )
            self._checkpoint_runner.finalize_run("FAILED", completed)
            self._update_state(
                mission_status="FAILED",
                active_waypoint_id=None,
                finished_at=datetime.now(timezone.utc).isoformat(),
                last_error=str(exc),
            )
        finally:
            with self._state_lock:
                self._active_goal_handle = None
                self._thread = None

    def _navigate_to_waypoint(self, waypoint: CoordinateWaypoint) -> Dict[str, str]:
        goal = FollowWaypoints.Goal()
        goal.poses = [self._make_pose_stamped(waypoint)]

        send_goal_future = self._follow_waypoints_client.send_goal_async(goal)
        goal_handle = self._wait_for_future(send_goal_future, timeout_sec=15.0)
        if goal_handle is None or not goal_handle.accepted:
            return {"status": "aborted", "message": f"Nav2 rejected waypoint {waypoint.id}."}

        with self._state_lock:
            self._active_goal_handle = goal_handle

        result_future = goal_handle.get_result_async()
        wrapped_result = self._wait_for_future(result_future, timeout_sec=None, allow_cancel=True)

        with self._state_lock:
            self._active_goal_handle = None

        if wrapped_result.status == GoalStatus.STATUS_SUCCEEDED:
            if wrapped_result.result.missed_waypoints:
                return {
                    "status": "aborted",
                    "message": f"Nav2 reported missed waypoints for {waypoint.id}.",
                }
            return {"status": "succeeded", "message": f"Reached {waypoint.id}."}

        if wrapped_result.status == GoalStatus.STATUS_CANCELED:
            return {"status": "canceled", "message": f"Waypoint {waypoint.id} was canceled."}

        return {
            "status": "aborted",
            "message": f"Nav2 failed waypoint {waypoint.id} with status={wrapped_result.status}.",
        }

    def _wait_for_future(self, future, timeout_sec: Optional[float], allow_cancel: bool = False):
        deadline = None if timeout_sec is None else time.monotonic() + timeout_sec
        cancel_sent = False
        while rclpy.ok():
            if future.done():
                return future.result()
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("Timed out waiting for ROS 2 action future completion.")
            if allow_cancel and self._stop_event.is_set() and not cancel_sent:
                with self._state_lock:
                    goal_handle = self._active_goal_handle
                if goal_handle is not None:
                    goal_handle.cancel_goal_async()
                    cancel_sent = True
            time.sleep(0.05)
        raise RuntimeError("ROS 2 shutdown while waiting for mission future.")

    def _make_pose_stamped(self, waypoint: CoordinateWaypoint) -> PoseStamped:
        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = self._mission_frame
        pose.pose.position.x = waypoint.x
        pose.pose.position.y = waypoint.y
        pose.pose.position.z = 0.0
        half_yaw = waypoint.yaw * 0.5
        pose.pose.orientation.z = math.sin(half_yaw)
        pose.pose.orientation.w = math.cos(half_yaw)
        return pose

    def _update_state(self, **updates) -> None:
        with self._state_lock:
            for key, value in updates.items():
                setattr(self._runtime_state, key, value)


def main(args:Union[List[str], None ]= None) -> None:
    rclpy.init(args=args)
    node: Optional[MissionExecutorNode] = None
    try:
        node = MissionExecutorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        return
    finally:
        if node is not None:
            node.shutdown()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
