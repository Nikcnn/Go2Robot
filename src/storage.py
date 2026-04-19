from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import cv2
from pydantic import BaseModel

from .models import AnalysisResult


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


@dataclass
class RunContext:
    mission_id: str
    route_id: str
    run_dir: Path
    started_at: datetime
    report: dict


class StorageManager:
    def __init__(self, runs_dir: str | Path) -> None:
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._active_run: RunContext | None = None
        self.last_report_path: Path | None = None

    def start_run(self, route_id: str) -> RunContext:
        with self._lock:
            if self._active_run is not None:
                raise RuntimeError("A mission run is already active.")

            started_at = utc_now()
            mission_id = started_at.strftime("%Y%m%dT%H%M%S%fZ")
            run_dir = self.runs_dir / f"mission_{mission_id}"
            (run_dir / "images").mkdir(parents=True, exist_ok=True)
            (run_dir / "analysis").mkdir(parents=True, exist_ok=True)

            report = {
                "mission_id": mission_id,
                "route_id": route_id,
                "mission_status": "STARTING",
                "started_at": started_at,
                "finished_at": None,
                "steps_executed": 0,
                "checkpoints": [],
                "analysis_results": [],
                "mode_transitions": [],
                "errors": [],
                "warnings": [],
            }
            context = RunContext(
                mission_id=mission_id,
                route_id=route_id,
                run_dir=run_dir,
                started_at=started_at,
                report=report,
            )
            self._active_run = context
            self._write_json(
                run_dir / "mission_meta.json",
                {"mission_id": mission_id, "route_id": route_id, "started_at": started_at},
            )
            return context

    def record_event(self, event: str, details: dict | None = None) -> dict:
        details = details or {}
        record = {"ts": utc_now(), "event": event, "details": details}
        with self._lock:
            if self._active_run is not None:
                self._append_jsonl(self._active_run.run_dir / "event_log.jsonl", record)
                if event == "mode_changed":
                    self._active_run.report["mode_transitions"].append(record)
                elif event == "warning":
                    self._active_run.report["warnings"].append(record)
                elif event == "error":
                    self._active_run.report["errors"].append(record)
        return record

    def append_telemetry(self, snapshot: dict) -> None:
        with self._lock:
            if self._active_run is None:
                return
            self._append_jsonl(self._active_run.run_dir / "telemetry.jsonl", snapshot)

    def save_checkpoint(
        self,
        waypoint_id: str,
        frame,
        analysis_result: AnalysisResult | dict,
        telemetry_snapshot: dict,
    ) -> dict | None:
        with self._lock:
            if self._active_run is None:
                return None

            timestamp = utc_now()
            image_rel_path = None
            if frame is not None:
                image_name = f"{waypoint_id}_{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.jpg"
                image_path = self._active_run.run_dir / "images" / image_name
                cv2.imwrite(str(image_path), frame)
                image_rel_path = image_path.relative_to(self._active_run.run_dir).as_posix()

            # Serialize AnalysisResult dataclass or accept legacy dict
            if isinstance(analysis_result, AnalysisResult):
                analysis_dict = analysis_result.to_dict()
                if image_rel_path and not analysis_result.image_path:
                    analysis_dict["image_path"] = image_rel_path
            else:
                analysis_dict = analysis_result

            analysis_payload = {
                "waypoint_id": waypoint_id,
                "timestamp": timestamp,
                "mission_id": self._active_run.mission_id,
                "route_id": self._active_run.route_id,
                "robot_pose": telemetry_snapshot.get("pose"),
                "telemetry_snapshot": telemetry_snapshot,
                "image_path": image_rel_path,
                "analysis_result": analysis_dict,
                "mission_status": self._active_run.report.get("mission_status"),
            }
            self._write_json(self._active_run.run_dir / "analysis" / f"{waypoint_id}.json", analysis_payload)

            checkpoint = {
                "waypoint_id": waypoint_id,
                "timestamp": timestamp,
                "image_path": image_rel_path,
                "telemetry": telemetry_snapshot,
                "analysis": analysis_dict,
            }
            self._active_run.report["checkpoints"].append(checkpoint)
            self._active_run.report["analysis_results"].append(analysis_payload)
            self._append_jsonl(
                self._active_run.run_dir / "event_log.jsonl",
                {"ts": timestamp, "event": "checkpoint_captured", "details": {"waypoint_id": waypoint_id}},
            )
            return checkpoint

    def finalize_run(self, mission_status: str, steps_executed: int) -> Path | None:
        with self._lock:
            if self._active_run is None:
                return None

            self._active_run.report["mission_status"] = mission_status
            self._active_run.report["steps_executed"] = steps_executed
            self._active_run.report["finished_at"] = utc_now()

            report_path = self._active_run.run_dir / "final_report.json"
            self._write_json(report_path, self._active_run.report)
            self.last_report_path = report_path
            self._active_run = None
            return report_path

    def active_mission_id(self) -> str | None:
        with self._lock:
            return self._active_run.mission_id if self._active_run else None

    def _append_jsonl(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=_json_default) + "\n")

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, default=_json_default, indent=2), encoding="utf-8")
