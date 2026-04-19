from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RobotMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    ESTOP = "ESTOP"
    SERVICE = "SERVICE"


class MissionStatus(str, Enum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED_MANUAL = "PAUSED_MANUAL"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"
    ESTOPPED = "ESTOPPED"


class CommandSource(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    SYSTEM = "SYSTEM"


class Pose(StrictModel):
    x: float
    y: float
    yaw: float


class RobotState(StrictModel):
    battery_percent: float | None = None
    battery_voltage_v: float | None = None
    battery_current_a: float | None = None
    battery_cycles: int | None = None
    imu_yaw: float | None = None
    camera_status: str | None = None
    faults: list[str] = Field(default_factory=list)
    # Raw telemetry fields populated by the real Go2 adapter.
    # None means no DDS sample received yet (not "no error").
    sport_mode_error: int | None = None   # SportModeState_.error_code; 0 = no error
    motion_mode: int | None = None        # SportModeState_.mode; 0 = idle
    bms_status: int | None = None         # LowState_.bms_state.status; 0x08 = abnormal


class MotionCommand(StrictModel):
    vx: float = 0.0
    vy: float = 0.0
    vyaw: float = 0.0
    ts: float | None = None


class MoveStep(StrictModel):
    id: str
    type: Literal["move"]
    vx: float
    vy: float = 0.0
    vyaw: float = 0.0
    duration_sec: float = Field(gt=0)


class RotateStep(StrictModel):
    id: str
    type: Literal["rotate"]
    vyaw: float
    duration_sec: float = Field(gt=0)
    vx: float = 0.0
    vy: float = 0.0


class CheckpointStep(StrictModel):
    id: str
    type: Literal["checkpoint"]
    waypoint_id: str
    settle_time_sec: float = Field(default=0.0, ge=0)
    analyzer: str | None = None
    reference_image: str | None = None


class StopStep(StrictModel):
    id: str
    type: Literal["stop"]


RouteStep = Annotated[
    MoveStep | RotateStep | CheckpointStep | StopStep,
    Field(discriminator="type"),
]


class RouteModel(StrictModel):
    route_id: str
    steps: list[RouteStep]


class TelemetrySnapshot(StrictModel):
    timestamp: datetime
    mode: RobotMode
    mission_status: MissionStatus
    route_id: str | None = None
    active_step_id: str | None = None
    mission_id: str | None = None
    pose: Pose | None = None
    robot_state: RobotState = Field(default_factory=RobotState)


class MissionStartRequest(StrictModel):
    route_id: str


class TeleopCommandRequest(StrictModel):
    vx: float = 0.0
    vy: float = 0.0
    vyaw: float = 0.0
    ts: float | None = None


class ApiMessage(StrictModel):
    ok: bool
    message: str


class StatusResponse(StrictModel):
    robot_mode: str
    mission_status: str
    adapter_mode: str
    route_id: str | None = None
    mission_id: str | None = None
    active_step_id: str | None = None


class MissionCurrentResponse(StrictModel):
    mission_id: str | None = None
    route_id: str | None = None
    mission_status: MissionStatus
    robot_mode: RobotMode
    active_step_id: str | None = None
    steps_executed: int = 0
    paused: bool = False
    estop_latched: bool = False


class EventRecord(StrictModel):
    sequence: int | None = None
    ts: datetime
    event: str
    details: dict = Field(default_factory=dict)


class AnalyzerResult(StrictModel):
    analyzer: str
    status: str
    result: str
    score: float | None = None
    details: dict = Field(default_factory=dict)


class FinalReport(StrictModel):
    mission_id: str
    route_id: str
    mission_status: str
    started_at: datetime
    finished_at: datetime | None = None
    steps_executed: int = 0
    checkpoints: list[dict] = Field(default_factory=list)
    analysis_results: list[dict] = Field(default_factory=list)
    mode_transitions: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)


class RouteFile(StrictModel):
    route_id: str
    path: Path


_VALID_ACTIONS = Literal[
    "connect", "disconnect", "stand_up", "stop_motion", "pause",
    "resume", "damping_on", "reset_fault", "manual_mode", "auto_mode",
]


class ActionRequest(StrictModel):
    action: _VALID_ACTIONS


class ActionResponse(StrictModel):
    action: str
    prev_state: str
    new_state: str
    success: bool
    reason: str
