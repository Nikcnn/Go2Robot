from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from tests import make_test_dir
from src.control import ControlCore
from src.mission import MissionManager
from src.robot.robot_adapter import MockRobotAdapter
from src.storage import StorageManager
from src.telemetry import TelemetryService


class _StubRealsenseService:
    def is_enabled(self) -> bool:
        return True

    def capture_snapshot(self, run_dir, waypoint_id):
        return {
            "sensor": "realsense_d435i",
            "status": "ok",
            "timestamp": datetime.now(timezone.utc),
            "waypoint_id": waypoint_id,
            "color_image_path": "realsense/mock_color.jpg",
            "depth_npy_path": "realsense/mock_depth.npy",
            "depth_preview_path": "realsense/mock_depth_preview.png",
        }


def test_final_report_contains_required_fields() -> None:
    tmp_path = make_test_dir("report_builder")
    config_dir = tmp_path / "config"
    routes_dir = config_dir / "routes"
    routes_dir.mkdir(parents=True)
    route_path = routes_dir / "demo_route.json"
    route_path.write_text(
        json.dumps(
            {
                "route_id": "demo_route_v1",
                "steps": [
                    {"id": "move_1", "type": "move", "vx": 0.1, "vy": 0.0, "vyaw": 0.0, "duration_sec": 0.2},
                    {"id": "checkpoint_1", "type": "checkpoint", "waypoint_id": "panel_A", "settle_time_sec": 0.05, "analyzer": "simple_presence"},
                    {"id": "stop_1", "type": "stop"},
                ],
            }
        ),
        encoding="utf-8",
    )

    storage = StorageManager(tmp_path / "runs")
    adapter = MockRobotAdapter(width=320, height=240)
    adapter.connect()
    control = ControlCore(
        adapter=adapter,
        max_vx=0.5,
        max_vy=0.5,
        max_vyaw=1.0,
        watchdog_timeout_ms=200,
        event_callback=storage.record_event,
    )
    telemetry = TelemetryService(adapter=adapter, control=control, storage=storage, hz=5)
    mission = MissionManager(
        routes_dir=routes_dir,
        project_root=tmp_path,
        control=control,
        adapter=adapter,
        telemetry=telemetry,
        storage=storage,
        analysis_threshold=0.25,
        event_callback=storage.record_event,
        realsense_camera=_StubRealsenseService(),
    )

    control.start()
    telemetry.start()
    try:
        mission.start("demo_route")
        deadline = time.time() + 3.0
        while time.time() < deadline:
            current = control.current()
            if current.mission_status.value in {"COMPLETED", "FAILED", "ABORTED", "ESTOPPED"}:
                break
            time.sleep(0.05)

        assert storage.last_report_path is not None
        report = json.loads(storage.last_report_path.read_text(encoding="utf-8"))
        for key in [
            "mission_id",
            "route_id",
            "mission_status",
            "started_at",
            "finished_at",
            "steps_executed",
            "checkpoints",
            "analysis_results",
            "mode_transitions",
            "errors",
            "warnings",
        ]:
            assert key in report
        assert report["mission_status"] == "COMPLETED"
        assert report["steps_executed"] == 3
        assert len(report["checkpoints"]) == 1
        assert report["checkpoints"][0]["sensor_captures"]["realsense"]["status"] == "ok"
    finally:
        mission.shutdown()
        telemetry.stop()
        control.shutdown()
        adapter.disconnect()
