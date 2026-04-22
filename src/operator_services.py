from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CoordinateWaypoint(StrictModel):
    id: str
    x: float
    y: float
    yaw: float = 0.0
    task: str = "inspect"


class CoordinateMission(StrictModel):
    mission_id: str
    map_id: str = ""
    waypoints: List[CoordinateWaypoint] = Field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str, label: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{label} is required.")
    if not re.match(r"^[A-Za-z0-9_.-]+$", value):
        raise ValueError(f"{label} can use only letters, numbers, dash, underscore, and dot.")
    if value in {".", ".."}:
        raise ValueError(f"{label} is not valid.")
    return value


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


class CoordinateMissionStore:
    """Read/write shared ROS waypoint missions without changing the ROS mission schema."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.missions_dir = self.project_root / "shared_missions" / "missions"
        self.maps_dir = self.project_root / "shared_missions" / "maps"
        self.missions_dir.mkdir(parents=True, exist_ok=True)
        self.maps_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def list_maps(self) -> List[Dict[str, Any]]:
        maps: List[Dict[str, Any]] = []
        for path in sorted(self.maps_dir.glob("*.yaml")):
            item: Dict[str, Any] = {
                "id": path.stem,
                "name": path.stem,
                "path": str(path),
                "has_preview": False,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            }
            try:
                payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                image_name = payload.get("image")
                if image_name:
                    item["image"] = image_name
                    item["has_preview"] = (path.parent / image_name).exists()
                if payload.get("resolution") is not None:
                    item["resolution"] = payload.get("resolution")
            except Exception as exc:
                item["error"] = str(exc)
            maps.append(item)
        return maps

    def list_missions(self) -> List[Dict[str, Any]]:
        missions: List[Dict[str, Any]] = []
        for path in sorted(self.missions_dir.glob("*.json")):
            try:
                mission = self.load(path.stem)
                missions.append(
                    {
                        "id": mission["mission_id"],
                        "mission_id": mission["mission_id"],
                        "map_id": mission.get("map_id") or "",
                        "waypoint_count": len(mission.get("waypoints") or []),
                        "path": str(path),
                        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                    }
                )
            except Exception as exc:
                missions.append(
                    {
                        "id": path.stem,
                        "mission_id": path.stem,
                        "map_id": "",
                        "waypoint_count": 0,
                        "path": str(path),
                        "error": str(exc),
                    }
                )
        return missions

    def load(self, mission_id: str) -> Dict[str, Any]:
        path = self._mission_path(mission_id)
        if not path.exists():
            raise FileNotFoundError(f"Mission '{mission_id}' was not found.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        mission = self._validate(payload)
        result = mission.model_dump(mode="json")
        result["path"] = str(path)
        return result

    def save(self, payload: Dict[str, Any], mission_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            candidate = dict(payload)
            candidate.pop("path", None)
            if mission_id is not None:
                candidate["mission_id"] = mission_id
            mission = self._validate(candidate)
            path = self._mission_path(mission.mission_id)
            path.write_text(
                json.dumps(mission.model_dump(mode="json"), indent=2, default=_json_default) + "\n",
                encoding="utf-8",
            )
            result = mission.model_dump(mode="json")
            result["path"] = str(path)
            return result

    def delete(self, mission_id: str) -> None:
        with self._lock:
            path = self._mission_path(mission_id)
            if not path.exists():
                raise FileNotFoundError(f"Mission '{mission_id}' was not found.")
            path.unlink()

    def waypoint_from_pose(
        self,
        *,
        pose: Any,
        mission_id: Optional[str],
        map_id: Optional[str],
        waypoint_id: Optional[str],
        task: Optional[str],
    ) -> Dict[str, Any]:
        if pose is None:
            raise ValueError("Robot pose is not available yet.")
        wp_id = _safe_id(waypoint_id or f"waypoint_{datetime.now(timezone.utc).strftime('%H%M%S')}", "waypoint_id")
        waypoint = CoordinateWaypoint(
            id=wp_id,
            x=float(pose.x),
            y=float(pose.y),
            yaw=float(pose.yaw),
            task=(task or "inspect").strip() or "inspect",
        )
        if not mission_id:
            return waypoint.model_dump(mode="json")

        try:
            mission = self.load(mission_id)
        except FileNotFoundError:
            mission = {
                "mission_id": _safe_id(mission_id, "mission_id"),
                "map_id": map_id or "",
                "waypoints": [],
            }
        mission["map_id"] = mission.get("map_id") or map_id or ""
        waypoints = list(mission.get("waypoints") or [])
        if any(item.get("id") == waypoint.id for item in waypoints):
            raise ValueError(f"Waypoint '{waypoint.id}' already exists in this mission.")
        waypoints.append(waypoint.model_dump(mode="json"))
        mission["waypoints"] = waypoints
        return self.save(mission, mission_id=mission["mission_id"])

    def _mission_path(self, mission_id: str) -> Path:
        safe = _safe_id(mission_id, "mission_id")
        path = (self.missions_dir / f"{safe}.json").resolve()
        if self.missions_dir.resolve() not in path.parents:
            raise ValueError("Mission path escaped shared_missions/missions.")
        return path

    def _validate(self, payload: Dict[str, Any]) -> CoordinateMission:
        try:
            mission = CoordinateMission.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid waypoint mission: {exc}") from exc
        _safe_id(mission.mission_id, "mission_id")
        for waypoint in mission.waypoints:
            _safe_id(waypoint.id, "waypoint_id")
        return mission


@dataclass
class _ManagedProcess:
    process: subprocess.Popen
    command: List[str]
    started_at: str
    log_path: str
    log_handle: Any


class RosProcessService:
    """Minimal safe-test-environment ROS process manager for the web operator UI.

    The FastAPI app only starts/stops ROS 2 CLI subprocesses. It does not import
    rclpy or touch Unitree SDK objects, keeping SDK ownership inside go2_bridge.
    Runtime behavior still needs Ubuntu 20.04 / ROS 2 Foxy validation.
    """

    def __init__(self, project_root: Path, robot_mode: str, interface_name: str) -> None:
        self.project_root = Path(project_root)
        self.robot_mode = robot_mode
        self.interface_name = interface_name
        self.ros_ws_dir = self.project_root / "ros_ws"
        self.maps_dir = self.project_root / "shared_missions" / "maps"
        self.logs_dir = self.project_root / "runs" / "ros_processes"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._processes: Dict[str, _ManagedProcess] = {}
        self._last_results: Dict[str, Dict[str, Any]] = {}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "ros2_available": shutil.which("ros2") is not None,
                "mapping": self._process_status("mapping"),
                "navigation": self._process_status("navigation"),
                "last_results": dict(self._last_results),
                "runtime_verified": False,
                "note": "ROS launch wiring is present; full mapping, lidar, AMCL, Nav2, and mission runtime must be validated on Ubuntu 20.04 with a live /scan.",
            }

    def start_mapping(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        ros_mode = str(payload.get("robot_mode") or "go2")
        block = self._sdk_ownership_block(ros_mode)
        if block:
            return self._record_result("mapping_start", False, block)
        command = [
            "ros2",
            "launch",
            "go2_nav_bringup",
            "mapping.launch.py",
            f"robot_mode:={ros_mode}",
            f"interface_name:={payload.get('interface_name') or self.interface_name}",
            f"use_lidar:={str(payload.get('use_lidar', True)).lower()}",
            f"lidar_mode:={payload.get('lidar_mode') or 'auto'}",
            f"use_realsense:={str(payload.get('use_realsense', False)).lower()}",
            f"require_realsense:={str(payload.get('require_realsense', False)).lower()}",
            "use_rviz:=false",
            f"operator_app_root:={self.project_root}",
        ]
        return self._start_process("mapping", command)

    def stop_mapping(self) -> Dict[str, Any]:
        return self._stop_process("mapping")

    def save_map(self, map_name: str) -> Dict[str, Any]:
        safe_name = _safe_id(map_name, "map_name")
        self.maps_dir.mkdir(parents=True, exist_ok=True)
        prefix = self.maps_dir / safe_name
        command = ["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", str(prefix)]
        return self._run_command("map_save", command, timeout_sec=60)

    def start_navigation(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        ros_mode = str(payload.get("robot_mode") or "go2")
        block = self._sdk_ownership_block(ros_mode)
        if block:
            return self._record_result("navigation_start", False, block)
        map_id = str(payload.get("map_id") or "").strip()
        if not map_id:
            return self._record_result("navigation_start", False, "Choose a map before starting navigation.")
        map_path = self.maps_dir / f"{_safe_id(map_id, 'map_id')}.yaml"
        if not map_path.exists():
            return self._record_result("navigation_start", False, f"Map '{map_id}' was not found in shared_missions/maps.")
        command = [
            "ros2",
            "launch",
            "go2_nav_bringup",
            "navigation.launch.py",
            f"robot_mode:={ros_mode}",
            f"interface_name:={payload.get('interface_name') or self.interface_name}",
            f"map:={map_path}",
            f"use_lidar:={str(payload.get('use_lidar', True)).lower()}",
            f"lidar_mode:={payload.get('lidar_mode') or 'auto'}",
            f"use_realsense:={str(payload.get('use_realsense', False)).lower()}",
            f"require_realsense:={str(payload.get('require_realsense', False)).lower()}",
            "use_rviz:=false",
            f"operator_app_root:={self.project_root}",
        ]
        return self._start_process("navigation", command)

    def stop_navigation(self) -> Dict[str, Any]:
        return self._stop_process("navigation")

    def start_mission(self, mission_path: Path) -> Dict[str, Any]:
        if not self._is_running("navigation"):
            return self._record_result("mission_start", False, "Start navigation before running a waypoint route.")
        command = [
            "ros2",
            "service",
            "call",
            "/go2_mission/command",
            "go2_interfaces/srv/MissionControl",
            "{command: start, mission_path: " + mission_path.as_posix() + ", mission_json: ''}",
        ]
        return self._run_command("mission_start", command, timeout_sec=30)

    def cancel_mission(self) -> Dict[str, Any]:
        command = [
            "ros2",
            "service",
            "call",
            "/go2_mission/command",
            "go2_interfaces/srv/MissionControl",
            "{command: cancel, mission_path: '', mission_json: ''}",
        ]
        return self._run_command("mission_cancel", command, timeout_sec=20)

    def mission_status(self) -> Dict[str, Any]:
        return {
            "available": self._is_running("navigation"),
            "last_start": self._last_results.get("mission_start"),
            "last_cancel": self._last_results.get("mission_cancel"),
            "runtime_verified": False,
            "active_waypoint": None,
            "completed_waypoints": 0,
            "total_waypoints": 0,
            "current_task": "",
        }

    def _sdk_ownership_block(self, ros_mode: str) -> str:
        if self.robot_mode == "go2" and ros_mode == "go2":
            return (
                "Blocked: the Python app is already configured for real Go2 SDK ownership. "
                "Run the web app in mock mode before starting ROS go2_bridge in go2 mode."
            )
        return ""

    def _start_process(self, key: str, command: List[str]) -> Dict[str, Any]:
        with self._lock:
            existing = self._processes.get(key)
            if existing and existing.process.poll() is None:
                return self._record_result(f"{key}_start", True, f"{key} is already running.", self._process_status(key))
            self._cleanup_finished_locked(key)
            log_path = self.logs_dir / f"{key}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.log"
            try:
                log_handle = log_path.open("a", encoding="utf-8")
                process = subprocess.Popen(
                    command,
                    cwd=str(self.project_root),
                    env=self._ros_env(),
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    shell=False,
                )
            except FileNotFoundError:
                return self._record_result(f"{key}_start", False, "ros2 was not found on PATH. Source ROS 2 Foxy and the workspace before starting the app.")
            except Exception as exc:
                return self._record_result(f"{key}_start", False, str(exc))
            self._processes[key] = _ManagedProcess(
                process=process,
                command=command,
                started_at=utc_now_iso(),
                log_path=str(log_path),
                log_handle=log_handle,
            )
            return self._record_result(f"{key}_start", True, f"{key} launch started.", self._process_status(key))

    def _stop_process(self, key: str) -> Dict[str, Any]:
        with self._lock:
            managed = self._processes.get(key)
            if not managed or managed.process.poll() is not None:
                self._cleanup_finished_locked(key)
                return self._record_result(f"{key}_stop", True, f"{key} is not running.", self._process_status(key))
            managed.process.terminate()
        try:
            managed.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            managed.process.kill()
            managed.process.wait(timeout=5)
        with self._lock:
            self._cleanup_finished_locked(key)
            return self._record_result(f"{key}_stop", True, f"{key} stopped.", self._process_status(key))

    def _run_command(self, key: str, command: List[str], timeout_sec: int) -> Dict[str, Any]:
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.project_root),
                env=self._ros_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
                shell=False,
            )
        except FileNotFoundError:
            return self._record_result(key, False, "ros2 was not found on PATH. Source ROS 2 Foxy and the workspace before using this action.")
        except subprocess.TimeoutExpired:
            return self._record_result(key, False, f"Command timed out after {timeout_sec} seconds.")
        except Exception as exc:
            return self._record_result(key, False, str(exc))
        ok = completed.returncode == 0
        message = "Command completed." if ok else (completed.stderr.strip() or completed.stdout.strip() or "Command failed.")
        return self._record_result(
            key,
            ok,
            message,
            {
                "returncode": completed.returncode,
                "stdout": completed.stdout[-2000:],
                "stderr": completed.stderr[-2000:],
            },
        )

    def _record_result(
        self,
        key: str,
        ok: bool,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = {
            "ok": ok,
            "message": message,
            "details": details or {},
            "ts": utc_now_iso(),
        }
        with self._lock:
            self._last_results[key] = result
        return result

    def _process_status(self, key: str) -> Dict[str, Any]:
        self._cleanup_finished_locked(key)
        managed = self._processes.get(key)
        if not managed:
            return {"running": False, "pid": None, "started_at": None, "log_path": None}
        return {
            "running": managed.process.poll() is None,
            "pid": managed.process.pid,
            "started_at": managed.started_at,
            "log_path": managed.log_path,
            "command": managed.command,
        }

    def _cleanup_finished_locked(self, key: str) -> None:
        managed = self._processes.get(key)
        if managed and managed.process.poll() is not None:
            try:
                managed.log_handle.close()
            except Exception:
                pass
            self._processes.pop(key, None)

    def _is_running(self, key: str) -> bool:
        with self._lock:
            managed = self._processes.get(key)
            return bool(managed and managed.process.poll() is None)

    def _ros_env(self) -> Dict[str, str]:
        env = dict(os.environ)
        env.setdefault("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp")
        env["GO2_OPERATOR_APP_ROOT"] = str(self.project_root)
        return env

    def shutdown(self) -> None:
        for key in list(self._processes.keys()):
            self._stop_process(key)


def build_sensor_summary(runtime: Any) -> Dict[str, Any]:
    latest = runtime.telemetry.get_latest()
    robot_state = latest.robot_state
    camera_online = runtime.camera.get_latest_jpeg() is not None
    realsense_status = runtime.realsense.get_status()
    ros_status = runtime.ros.status()
    lidar_possible = bool(ros_status["mapping"]["running"] or ros_status["navigation"]["running"])
    lidar_preview = hasattr(runtime.adapter, "get_lidar_scan")

    return {
        "built_in_camera": {
            "name": "Built-in robot camera",
            "online": camera_online,
            "status": robot_state.camera_status or ("Live" if camera_online else "No frames yet"),
            "stream_url": "/stream/camera",
            "runtime_note": "Uses the Python adapter camera path. In ROS go2 mode, go2_bridge owns the SDK, so real camera streaming to this web app still needs target validation.",
        },
        "realsense_d435i": {
            "name": "Intel RealSense D435i",
            "online": bool(realsense_status.get("available")),
            "enabled": bool(realsense_status.get("enabled")),
            "status": realsense_status.get("status"),
            "error": realsense_status.get("error"),
            "stream_url": "/stream/realsense/color",
            "runtime_note": "Optional Python RealSense path; ROS RealSense bridge is launched with mapping/navigation only when requested.",
        },
        "built_in_lidar": {
            "name": "Built-in lidar",
            "online": lidar_preview or lidar_possible,
            "status": "Scan data available" if lidar_preview else ("ROS mapping/navigation running" if lidar_possible else "Waiting for ROS mapping or navigation"),
            "preview_available": lidar_preview,
        },
    }


def human_status_sentence(runtime: Any) -> str:
    current = runtime.control.current()
    ros_status = runtime.ros.status()
    mission = runtime.ros.mission_status()
    if current.estop_latched:
        return "Emergency stop active"
    if current.robot_mode.value == "MANUAL":
        return "Manual control active"
    if (mission.get("last_start") or {}).get("ok") and ros_status["navigation"]["running"]:
        return "Running waypoint mission"
    if ros_status["mapping"]["running"]:
        return "Building map"
    if ros_status["navigation"]["running"]:
        return "Ready to navigate"
    return "Ready for mapping"


def build_operator_overview(runtime: Any) -> Dict[str, Any]:
    current = runtime.control.current()
    latest = runtime.telemetry.get_latest()
    sensors = build_sensor_summary(runtime)
    ros_status = runtime.ros.status()
    maps = runtime.mission_store.list_maps()
    missions = runtime.mission_store.list_missions()
    connected = bool(runtime.adapter_connected)
    return {
        "status_sentence": human_status_sentence(runtime),
        "connection": {
            "online": connected,
            "label": "Connected" if connected else "Not connected",
            "adapter_mode": runtime.config.robot.mode,
        },
        "mode": {
            "label": current.robot_mode.value,
            "mission_status": current.mission_status.value,
            "estop_latched": current.estop_latched,
        },
        "battery_percent": latest.robot_state.battery_percent,
        "pose": latest.pose.model_dump(mode="json") if latest.pose else None,
        "ros": ros_status,
        "sensors": sensors,
        "maps": maps,
        "missions": missions,
        "mission_progress": runtime.ros.mission_status(),
        "technical_note": "Main screen hides low-level robot state. Use Technical details for raw state and ROS process information.",
    }
