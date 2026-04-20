from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RobotConfig(StrictModel):
    mode: str = "mock"
    max_vx: float = 0.5
    max_vy: float = 0.3
    max_vyaw: float = 1.0
    # go2-mode only — ignored in mock mode
    interface_name: str = "eth0"   # network interface name (NOT an IP) passed to ChannelFactory
    camera_enabled: bool = False   # set True to expose the robot camera stream on the dashboard


class TelemetryConfig(StrictModel):
    hz: int = 5


class CameraConfig(StrictModel):
    fps: int = 10
    width: int = 640
    height: int = 480
    jpeg_quality: int = 70


class RealsenseConfig(StrictModel):
    enabled: bool = False
    width: int = 640
    height: int = 480
    fps: int = 15
    enable_depth: bool = True
    enable_color: bool = True
    startup_required: bool = False


class ControlConfig(StrictModel):
    watchdog_timeout_ms: int = 500


class AnalysisConfig(StrictModel):
    frame_diff_threshold: float = 0.25


class ServerConfig(StrictModel):
    host: str = "0.0.0.0"
    port: int = 8000


class StorageConfig(StrictModel):
    runs_dir: str = "runs"


class LoggingConfig(StrictModel):
    level: str = "INFO"


class AppConfig(StrictModel):
    robot: RobotConfig = Field(default_factory=RobotConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    realsense: RealsenseConfig = Field(default_factory=RealsenseConfig)
    control: ControlConfig = Field(default_factory=ControlConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_app_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)
