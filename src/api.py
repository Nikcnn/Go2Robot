from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import AppConfig, load_app_config
from .control import ControlCore
from .event_log import PersistentEventLog
from .mission import MissionManager
from .models import (
    ActionRequest, ActionResponse, ApiMessage, CommandSource,
    MissionCurrentResponse, MissionRunRequest, MissionStartRequest,
    MotionCommand, MotionStateResponse, RobotMode, RouteModel,
    StatusResponse, TeleopCommandRequest,
)
from .robot.robot_adapter import build_robot_adapter
from .sensors import RealsenseCameraService
from .state_machine import (
    EffectiveState, RobotStateMachine,
)
from .storage import StorageManager
from .streaming import CameraStream, EventBus
from .telemetry import TelemetryService


@dataclass
class AppRuntime:
    config: AppConfig
    config_path: Path
    project_root: Path
    adapter: object
    control: ControlCore
    telemetry: TelemetryService
    storage: StorageManager
    events: EventBus
    camera: CameraStream
    realsense: RealsenseCameraService
    mission: MissionManager
    state_machine: RobotStateMachine
    event_log: PersistentEventLog
    adapter_connected: bool = field(default=False)


def _start_runtime(runtime: AppRuntime, emit_event) -> bool:
    runtime.control.start()
    adapter_ready = True
    try:
        runtime.adapter.connect()
        runtime.adapter_connected = True
        # Prime the state machine immediately so the first HTTP request sees a valid state.
        try:
            robot_state = runtime.adapter.get_state()
            runtime.state_machine.update(connected=True, robot_state=robot_state, estop_latched=False)
        except Exception:
            pass  # non-fatal; telemetry poller will catch up
    except Exception as exc:
        adapter_ready = False
        emit_event("adapter_startup_failed", {"error": str(exc), "mode": runtime.config.robot.mode})
        runtime.control.latch_estop()
    realsense = getattr(runtime, "realsense", None)
    if realsense is not None:
        try:
            realsense.start()
        except Exception as exc:
            emit_event("realsense_startup_failed", {"error": str(exc)})
            raise
        realsense_status = realsense.get_status()
        if realsense_status.get("enabled") and not realsense_status.get("available"):
            emit_event(
                "warning",
                {
                    "reason": str(realsense_status.get("error") or realsense_status.get("status")),
                    "sensor": "realsense_d435i",
                    "status": realsense_status.get("status"),
                },
            )
    try:
        runtime.telemetry.start()
    except Exception as exc:
        emit_event("telemetry_startup_failed", {"error": str(exc)})
    try:
        runtime.camera.start()
    except Exception as exc:
        emit_event("camera_startup_failed", {"error": str(exc)})
    emit_event("server_started", {"adapter_mode": runtime.config.robot.mode, "adapter_ready": adapter_ready})
    return adapter_ready


_STRUCTURED_LOG_MAP: dict[str, tuple[str, str]] = {
    "mission_started": ("info", "mission"),
    "mission_running": ("info", "mission"),
    "mission_completed": ("info", "mission"),
    "mission_aborted": ("warn", "mission"),
    "mission_paused": ("info", "mission"),
    "mission_resumed": ("info", "mission"),
    "step_started": ("info", "mission"),
    "step_completed": ("info", "mission"),
    "checkpoint_processed": ("info", "mission"),
    "mode_changed": ("info", "state_transition"),
    "estop_latched": ("error", "state_transition"),
    "estop_reset": ("info", "state_transition"),
    "adapter_startup_failed": ("error", "connection"),
    "realsense_startup_failed": ("error", "connection"),
    "server_started": ("info", "connection"),
    "warning": ("warn", "fault"),
    "error": ("error", "fault"),
    "movement_blocked": ("warn", "movement_blocked"),
}


def create_app(config: AppConfig | None = None, config_path: str | Path = "config/app_config.yaml") -> FastAPI:
    config_file = Path(config_path).resolve()
    loaded_config = config or load_app_config(config_file)
    project_root = config_file.parent.parent
    routes_dir = config_file.parent / "routes"
    web_dir = Path(__file__).resolve().parent / "web"
    runs_dir = Path(loaded_config.storage.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = (project_root / runs_dir).resolve()

    events = EventBus()
    storage = StorageManager(runs_dir)
    state_machine = RobotStateMachine()
    event_log = PersistentEventLog(runs_dir / "events.jsonl")

    def emit_event(event: str, details: dict) -> None:
        storage.record_event(event, details)
        events.publish(event, details)
        mapping = _STRUCTURED_LOG_MAP.get(event)
        if mapping:
            level, category = mapping
            event_log.append(
                level=level,  # type: ignore[arg-type]
                category=category,  # type: ignore[arg-type]
                event=event,
                message=details.get("reason") or details.get("message") or event,
                details=details,
            )

    adapter = build_robot_adapter(
        loaded_config.robot.mode,
        width=loaded_config.camera.width,
        height=loaded_config.camera.height,
        interface_name=loaded_config.robot.interface_name,
        camera_enabled=loaded_config.robot.camera_enabled,
    )
    control = ControlCore(
        adapter=adapter,
        max_vx=loaded_config.robot.max_vx,
        max_vy=loaded_config.robot.max_vy,
        max_vyaw=loaded_config.robot.max_vyaw,
        watchdog_timeout_ms=loaded_config.control.watchdog_timeout_ms,
        event_callback=emit_event,
    )
    realsense = RealsenseCameraService(config=loaded_config.realsense)
    telemetry = TelemetryService(
        adapter=adapter,
        control=control,
        storage=storage,
        hz=loaded_config.telemetry.hz,
        state_machine=state_machine,
    )
    camera = CameraStream(
        adapter=adapter,
        fps=loaded_config.camera.fps,
        width=loaded_config.camera.width,
        height=loaded_config.camera.height,
        jpeg_quality=loaded_config.camera.jpeg_quality,
    )
    mission = MissionManager(
        routes_dir=routes_dir,
        project_root=project_root,
        control=control,
        adapter=adapter,
        telemetry=telemetry,
        storage=storage,
        analysis_threshold=loaded_config.analysis.frame_diff_threshold,
        event_callback=emit_event,
        realsense_camera=realsense,
    )
    runtime = AppRuntime(
        config=loaded_config,
        config_path=config_file,
        project_root=project_root,
        adapter=adapter,
        control=control,
        telemetry=telemetry,
        storage=storage,
        events=events,
        camera=camera,
        realsense=realsense,
        mission=mission,
        state_machine=state_machine,
        event_log=event_log,
    )
    # Late-bind the connected_fn so TelemetryService reads runtime.adapter_connected
    runtime.telemetry._get_connected = lambda: runtime.adapter_connected  # type: ignore[attr-defined]

    def motion_response() -> MotionStateResponse:
        current = runtime.control.current()
        return MotionStateResponse(
            robot_mode=current.robot_mode,
            mission_status=current.mission_status,
            mission_id=current.mission_id,
            route_id=current.route_id,
            active_step_id=current.active_step_id,
            steps_executed=current.steps_executed,
            paused=current.paused,
            estop_latched=current.estop_latched,
            motion=runtime.control.motion_state(),
        )

    def ensure_manual_control() -> None:
        current = runtime.control.current()
        if current.robot_mode == RobotMode.MANUAL:
            return
        try:
            if not runtime.control.take_manual():
                raise HTTPException(status_code=409, detail="Manual mode cannot be taken in the current state.")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            _start_runtime(runtime, emit_event)
        except Exception as exc:
            emit_event("startup_thread_failed", {"error": str(exc)})
            raise
        try:
            yield
        finally:
            runtime.mission.shutdown()
            runtime.realsense.stop()
            runtime.camera.stop()
            runtime.telemetry.stop()
            runtime.control.shutdown()
            runtime.adapter.disconnect()

    app = FastAPI(title="Go2 Inspection MVP", lifespan=lifespan)
    app.state.runtime = runtime
    app.mount("/web", StaticFiles(directory=web_dir), name="web")

    @app.get("/", response_class=HTMLResponse)
    def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    @app.get("/api/status", response_model=StatusResponse)
    def get_status() -> StatusResponse:
        current = runtime.control.current()
        return StatusResponse(
            robot_mode=current.robot_mode.value,
            mission_status=current.mission_status.value,
            adapter_mode=runtime.config.robot.mode,
            route_id=current.route_id,
            mission_id=current.mission_id,
            active_step_id=current.active_step_id,
            sensor_statuses={"realsense": jsonable_encoder(runtime.realsense.get_status())},
        )

    @app.get("/api/mission/current", response_model=MissionCurrentResponse)
    def get_mission_current() -> MissionCurrentResponse:
        return runtime.control.current()

    @app.get("/api/missions/state", response_model=MotionStateResponse)
    def get_missions_state() -> MotionStateResponse:
        return motion_response()

    @app.post("/api/mission/start", response_model=ApiMessage)
    def start_mission(payload: MissionStartRequest) -> ApiMessage:
        eff = runtime.state_machine.get_effective()
        can_move, block_reason = runtime.state_machine.can_move()
        if not can_move:
            event_log.append(
                "warn", "movement_blocked",  # type: ignore[arg-type]
                "mission_start_blocked",
                f"Mission start blocked ({eff.value}): {block_reason}",
                {"effective_state": eff.value, "reason": block_reason},
            )
            raise HTTPException(status_code=409, detail=f"Mission blocked ({eff.value}): {block_reason}")
        try:
            mission_id = runtime.mission.start(payload.route_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        event_log.append("info", "mission", "mission_start_accepted",  # type: ignore[arg-type]
                         f"Mission started: {mission_id}", {"route_id": payload.route_id})
        return ApiMessage(ok=True, message=f"Mission started: {mission_id}")

    @app.post("/api/missions/run", response_model=ApiMessage)
    def run_inline_mission(payload: MissionRunRequest) -> ApiMessage:
        eff = runtime.state_machine.get_effective()
        can_move, block_reason = runtime.state_machine.can_move()
        if not can_move:
            raise HTTPException(status_code=409, detail=f"Mission blocked ({eff.value}): {block_reason}")
        try:
            mission_id = runtime.mission.start_route(RouteModel(route_id=payload.route_id, steps=payload.steps))
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ApiMessage(ok=True, message=f"Mission started: {mission_id}")

    @app.post("/api/mission/pause", response_model=ApiMessage)
    def pause_mission() -> ApiMessage:
        if not runtime.control.pause_mission():
            raise HTTPException(status_code=409, detail="Mission is not running.")
        return ApiMessage(ok=True, message="Mission paused.")

    @app.post("/api/mission/resume", response_model=ApiMessage)
    def resume_mission() -> ApiMessage:
        if not runtime.control.resume_mission():
            raise HTTPException(status_code=409, detail="Mission cannot resume in the current state.")
        return ApiMessage(ok=True, message="Mission resumed.")

    @app.post("/api/mission/abort", response_model=ApiMessage)
    def abort_mission() -> ApiMessage:
        if not runtime.control.abort_mission():
            raise HTTPException(status_code=409, detail="No active mission to abort.")
        return ApiMessage(ok=True, message="Mission aborted.")

    @app.post("/api/missions/stop", response_model=ApiMessage)
    def stop_mission() -> ApiMessage:
        return abort_mission()

    @app.post("/api/mode/manual/take", response_model=ApiMessage)
    def take_manual() -> ApiMessage:
        try:
            if not runtime.control.take_manual():
                raise HTTPException(status_code=409, detail="Manual mode cannot be taken in the current state.")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ApiMessage(ok=True, message="Manual mode active.")

    @app.post("/api/mode/manual/release", response_model=ApiMessage)
    def release_manual() -> ApiMessage:
        try:
            if not runtime.control.release_manual():
                raise HTTPException(status_code=409, detail="Manual mode is not active.")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ApiMessage(ok=True, message="Manual mode released.")

    @app.get("/api/robot/manual/state", response_model=MotionStateResponse)
    def get_manual_state() -> MotionStateResponse:
        return motion_response()

    @app.post("/api/robot/manual/stand-up", response_model=ApiMessage)
    def manual_stand_up() -> ApiMessage:
        ensure_manual_control()
        try:
            runtime.control.stand_up()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ApiMessage(ok=True, message="Manual stand-up requested.")

    @app.post("/api/robot/manual/sit", response_model=ApiMessage)
    def manual_sit_down() -> ApiMessage:
        ensure_manual_control()
        runtime.control.sit_down()
        return ApiMessage(ok=True, message="Robot seated.")

    @app.post("/api/robot/manual/stop", response_model=ApiMessage)
    def manual_stop() -> ApiMessage:
        ensure_manual_control()
        runtime.control.stop_motion("manual_stop")
        return ApiMessage(ok=True, message="Manual motion stopped.")

    @app.post("/api/robot/manual/cmd", response_model=ApiMessage)
    def manual_command(payload: TeleopCommandRequest) -> ApiMessage:
        ensure_manual_control()
        accepted = runtime.control.submit(
            MotionCommand(vx=payload.vx, vy=payload.vy, vyaw=payload.vyaw, ts=payload.ts),
            source=CommandSource.MANUAL,
        )
        if not accepted:
            raise HTTPException(status_code=409, detail="Manual command was rejected by control priority.")
        return ApiMessage(ok=True, message="Manual command accepted.")

    @app.post("/api/robot/manual/clear", response_model=ApiMessage)
    def clear_manual_command() -> ApiMessage:
        if not runtime.control.clear_manual_target():
            raise HTTPException(status_code=409, detail="Manual mode is not active.")
        return ApiMessage(ok=True, message="Manual command cleared.")

    @app.post("/api/robot/manual/release", response_model=ApiMessage)
    def manual_release() -> ApiMessage:
        return release_manual()

    @app.post("/api/mode/estop", response_model=ApiMessage)
    def estop() -> ApiMessage:
        runtime.control.latch_estop()
        return ApiMessage(ok=True, message="ESTOP latched.")

    @app.post("/api/mode/reset-estop", response_model=ApiMessage)
    def reset_estop() -> ApiMessage:
        if not runtime.control.reset_estop():
            raise HTTPException(status_code=409, detail="ESTOP is not latched.")
        return ApiMessage(ok=True, message="ESTOP reset.")

    @app.post("/api/mode/sit", response_model=ApiMessage)
    def sit_down() -> ApiMessage:
        runtime.control.sit_down()
        return ApiMessage(ok=True, message="Robot seated.")

    @app.post("/api/robot/activate", response_model=ApiMessage)
    def activate_robot() -> ApiMessage:
        try:
            if not runtime.control.activate_robot():
                raise HTTPException(status_code=409, detail="Robot cannot be activated while ESTOP is latched.")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ApiMessage(ok=True, message="Robot activated.")

    @app.post("/api/teleop/cmd", response_model=ApiMessage)
    def teleop_command(payload: TeleopCommandRequest) -> ApiMessage:
        try:
            accepted = runtime.control.submit(
                MotionCommand(vx=payload.vx, vy=payload.vy, vyaw=payload.vyaw, ts=payload.ts),
                source=CommandSource.MANUAL,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not accepted:
            raise HTTPException(status_code=409, detail="Manual teleop command was rejected by control priority.")
        return ApiMessage(ok=True, message="Teleop command accepted.")

    @app.websocket("/ws/telemetry")
    async def telemetry_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                snapshot = runtime.telemetry.get_latest()
                await websocket.send_json(jsonable_encoder(snapshot.model_dump(mode="json")))
                await asyncio.sleep(1.0 / max(1, runtime.config.telemetry.hz))
        except WebSocketDisconnect:
            return

    @app.websocket("/ws/events")
    async def events_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        last_sequence = 0
        try:
            for event in runtime.events.recent():
                last_sequence = max(last_sequence, event["sequence"] or 0)
                await websocket.send_json(jsonable_encoder(event))
            while True:
                for event in runtime.events.read_since(last_sequence):
                    last_sequence = max(last_sequence, event["sequence"] or 0)
                    await websocket.send_json(jsonable_encoder(event))
                await asyncio.sleep(0.2)
        except WebSocketDisconnect:
            return

    @app.get("/stream/camera")
    def camera_stream() -> StreamingResponse:
        return StreamingResponse(
            runtime.camera.mjpeg_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    # ------------------------------------------------------------------ #
    # New: Task 2+4 — robot action endpoint and status endpoint           #
    # ------------------------------------------------------------------ #

    @app.post("/api/robot/action", response_model=ActionResponse)
    def robot_action(payload: ActionRequest) -> ActionResponse:
        sm = runtime.state_machine
        prev_state = sm.get_effective().value
        action = payload.action
        success = False
        reason = ""

        try:
            success, reason = _dispatch_action(action, runtime, emit_event)
        except Exception as exc:
            success = False
            reason = str(exc)

        new_state = sm.get_effective().value
        level: str = "info" if success else "warn"
        category: str = "action_accepted" if success else "action_rejected"
        event_log.append(
            level=level,  # type: ignore[arg-type]
            category=category,  # type: ignore[arg-type]
            event=f"action:{action}",
            message=f"Action '{action}' {'accepted' if success else 'rejected'}: {reason or 'ok'}",
            details={"action": action, "prev_state": prev_state, "new_state": new_state, "reason": reason},
        )
        if success:
            sm.record_command_ok(action)
        else:
            sm.record_command_rejected(f"{action}: {reason}")

        return ActionResponse(
            action=action,
            prev_state=prev_state,
            new_state=new_state,
            success=success,
            reason=reason,
        )

    @app.get("/api/robot/status")
    def get_robot_status() -> dict:
        snap = runtime.telemetry.get_latest()
        sm_snap = runtime.state_machine.snapshot()
        rs = snap.robot_state
        return {
            "connection": "connected" if runtime.adapter_connected else "disconnected",
            "battery": {
                "voltage": rs.battery_voltage_v,
                "current": rs.battery_current_a,
                "percent": rs.battery_percent,
                "cycles": rs.battery_cycles,
            },
            "faults": rs.faults,
            "pose": snap.pose.model_dump() if snap.pose else None,
            "motion": runtime.control.motion_state().model_dump(mode="json"),
            "last_command_ok": sm_snap["last_command_ok"],
            "last_command_rejected": sm_snap["last_command_rejected"],
            "last_transition_ts": sm_snap["last_transition"],
        }

    @app.get("/api/robot/history")
    def get_robot_history(
        level: str | None = Query(default=None),
        category: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        records = runtime.event_log.query(level=level, category=category, limit=limit)
        return {"records": records, "count": len(records)}

    return app


def _dispatch_action(action: str, runtime: AppRuntime, emit_event) -> tuple[bool, str]:
    """Execute a named operator action. Returns (success, reason)."""
    ctrl = runtime.control

    if action == "connect":
        if runtime.adapter_connected:
            return False, "already connected"
        try:
            runtime.adapter.connect()
            runtime.adapter_connected = True
            emit_event("server_started", {"adapter_mode": runtime.config.robot.mode, "adapter_ready": True})
        except Exception as exc:
            return False, f"connect failed: {exc}"
        return True, ""

    if action == "disconnect":
        try:
            runtime.adapter.disconnect()
            runtime.adapter_connected = False
        except Exception as exc:
            return False, f"disconnect failed: {exc}"
        return True, ""

    if action == "stand_up":
        if ctrl.estop_latched:
            return False, "ESTOP is latched"
        try:
            ok = ctrl.activate_robot()
            if not ok:
                return False, "robot cannot be activated in current state"
        except Exception as exc:
            return False, str(exc)
        return True, ""

    if action == "stop_motion":
        ctrl.stop_motion()
        return True, ""

    if action == "pause":
        ok = ctrl.pause_mission("operator_pause")
        if not ok:
            return False, "no active mission to pause"
        return True, ""

    if action == "resume":
        ok = ctrl.resume_mission()
        if not ok:
            return False, "mission cannot resume in current state (check mode and status)"
        return True, ""

    if action == "damping_on":
        # UNCERTAIN: Damp() puts the robot in a passive state; activate() is needed to recover.
        try:
            runtime.adapter.emergency_stop()
        except Exception as exc:
            return False, f"damping failed: {exc}"
        return True, ""

    if action == "reset_fault":
        if ctrl.estop_latched:
            ok = ctrl.reset_estop()
            return (True, "") if ok else (False, "ESTOP reset failed internally")
        # UNKNOWN: No SDK fault-reset API is available for sport mode errors.
        # Hardware-level faults (1001/1002) typically resolve after activate().
        return False, "UNKNOWN: no SDK fault-reset API; use stand_up to attempt recovery"

    if action == "manual_mode":
        try:
            ok = ctrl.take_manual()
            if not ok:
                return False, "cannot enter manual mode (already manual or ESTOP)"
        except Exception as exc:
            return False, str(exc)
        return True, ""

    if action == "auto_mode":
        try:
            ok = ctrl.release_manual()
            if not ok:
                return False, "not in manual mode"
        except Exception as exc:
            return False, str(exc)
        return True, ""

    return False, f"unknown action: {action!r}"
