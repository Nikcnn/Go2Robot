from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, Optional, Union

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


class MotionMode(str, Enum):
    IDLE = "idle"
    MANUAL = "manual"
    MISSION = "mission"
    SETTLING = "settling"
    STOPPED = "stopped"


class CommandSource(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    SYSTEM = "SYSTEM"


class Pose(StrictModel):
    x: float
    y: float
    yaw: float


class RobotState(StrictModel):
    battery_percent: Optional[float] = None
    battery_voltage_v: Optional[float] = None
    battery_current_a: Optional[float] = None
    battery_cycles: Optional[int] = None
    imu_yaw: Optional[float] = None
    camera_status: Optional[str] = None
    faults: list[str] = Field(default_factory=list)


class MotionCommand(StrictModel):
    vx: float = 0.0
    vy: float = 0.0
    vyaw: float = 0.0
    ts: Optional[float] = None


class MoveStep(StrictModel):
    id: str
    type: Literal["move", "move_velocity"]
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
    analyzer: Optional[str] = None
    reference_image: Optional[str] = None


class StopStep(StrictModel):
    id: str
    type: Literal["stop"]


class StandUpStep(StrictModel):
    id: str
    type: Literal["stand_up"]


class WaitStep(StrictModel):
    id: str
    type: Literal["wait", "settle"]
    duration_sec: float = Field(gt=0)


RouteStep = Annotated[
    Union[MoveStep, RotateStep, CheckpointStep, StopStep, StandUpStep, WaitStep],
    Field(discriminator="type"),
]


class RouteModel(StrictModel):
    route_id: str
    steps: list[RouteStep]


class TelemetrySnapshot(StrictModel):
    timestamp: datetime
    mode: RobotMode
    mission_status: MissionStatus
    route_id: Optional[str] = None
    active_step_id: Optional[str] = None
    mission_id: Optional[str] = None
    pose: Optional[Pose] = None
    robot_state: RobotState = Field(default_factory=RobotState)


class MissionStartRequest(StrictModel):
    route_id: str


class MissionRunRequest(StrictModel):
    route_id: str
    steps: list[RouteStep]


class TeleopCommandRequest(StrictModel):
    vx: float = 0.0
    vy: float = 0.0
    vyaw: float = 0.0
    ts: Optional[float] = None


class ApiMessage(StrictModel):
    ok: bool
    message: str


class StatusResponse(StrictModel):
    robot_mode: str
    mission_status: str
    adapter_mode: str
    route_id: Optional[str] = None
    mission_id: Optional[str] = None
    active_step_id: Optional[str] = None
    sensor_statuses: dict[str, dict[str, object]] = Field(default_factory=dict)


class MissionCurrentResponse(StrictModel):
    mission_id: Optional[str] = None
    route_id: Optional[str] = None
    mission_status: MissionStatus
    robot_mode: RobotMode
    active_step_id: Optional[str] = None
    steps_executed: int = 0
    paused: bool = False
    estop_latched: bool = False


class VelocityTriplet(StrictModel):
    vx: float = 0.0
    vy: float = 0.0
    vyaw: float = 0.0


class MotionDiagnosticsResponse(StrictModel):
    current_mode: MotionMode = MotionMode.IDLE
    target: VelocityTriplet = Field(default_factory=VelocityTriplet)
    current: VelocityTriplet = Field(default_factory=VelocityTriplet)
    last_nonzero_command: Optional[VelocityTriplet] = None
    last_move_return_code: Optional[int] = None
    last_stop_return_code: Optional[int] = None
    last_stand_up_return_code: Optional[int] = None
    last_action_message: str = ""
    standup_settle_remaining_sec: float = 0.0
    manual_control_active: bool = False
    mission_control_active: bool = False


class MotionStateResponse(StrictModel):
    robot_mode: RobotMode
    mission_status: MissionStatus
    mission_id: Optional[str] = None
    route_id: Optional[str] = None
    active_step_id: Optional[str] = None
    steps_executed: int = 0
    paused: bool = False
    estop_latched: bool = False
    motion: MotionDiagnosticsResponse


class EventRecord(StrictModel):
    sequence: Optional[int] = None
    ts: datetime
    event: str
    details: dict = Field(default_factory=dict)


class AnalyzerResult(StrictModel):
    analyzer: str
    status: str
    result: str
    score: Optional[float] = None
    details: dict = Field(default_factory=dict)


class FinalReport(StrictModel):
    mission_id: str
    route_id: str
    mission_status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
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
