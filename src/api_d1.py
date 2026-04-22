from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import Field

from .models import StrictModel


class D1DryRunRequest(StrictModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


class D1SingleJointRequest(StrictModel):
    joint_id: int
    angle_deg: float
    delay_ms: int = 0


class D1MultiJointRequest(StrictModel):
    angles_deg: List[float] = Field(default_factory=list)
    mode: int = 1


def register_d1_routes(app: FastAPI, runtime: Any) -> None:
    @app.get("/api/d1/ping")
    def d1_ping() -> Dict[str, Any]:
        return runtime.d1.ping()

    @app.get("/api/d1/status")
    def d1_status() -> Dict[str, Any]:
        return runtime.d1.status()

    @app.get("/api/d1/joints")
    def d1_joints() -> Dict[str, Any]:
        return runtime.d1.joints()

    @app.post("/api/d1/stop")
    def d1_stop() -> Dict[str, Any]:
        return runtime.d1.stop()

    @app.post("/api/d1/halt")
    def d1_halt() -> Dict[str, Any]:
        return runtime.d1.halt()

    @app.post("/api/d1/enable-motion")
    def d1_enable_motion() -> Dict[str, Any]:
        return runtime.d1.enable_motion()

    @app.post("/api/d1/disable-motion")
    def d1_disable_motion() -> Dict[str, Any]:
        return runtime.d1.disable_motion()

    @app.post("/api/d1/zero-arm")
    def d1_zero_arm() -> Dict[str, Any]:
        return runtime.d1.zero_arm()

    @app.post("/api/d1/set-joint-angle")
    def d1_set_joint_angle(payload: D1SingleJointRequest) -> Dict[str, Any]:
        return runtime.d1.set_joint_angle(
            joint_id=payload.joint_id,
            angle_deg=payload.angle_deg,
            delay_ms=payload.delay_ms,
        )

    @app.post("/api/d1/set-multi-joint-angle")
    def d1_set_multi_joint_angle(payload: D1MultiJointRequest) -> Dict[str, Any]:
        return runtime.d1.set_multi_joint_angle(
            angles_deg=payload.angles_deg,
            mode=payload.mode,
        )

    @app.post("/api/d1/dry-run")
    def d1_dry_run(payload: D1DryRunRequest) -> Dict[str, Any]:
        return runtime.d1.dry_run(payload.payload)
