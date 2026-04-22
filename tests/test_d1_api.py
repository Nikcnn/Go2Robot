from __future__ import annotations

from src.api import create_app
from src.api_d1 import D1DryRunRequest, D1MultiJointRequest, D1SingleJointRequest
from tests.test_api_smoke import _route_endpoint, write_test_config


class _FakeD1Service:
    def __init__(self) -> None:
        self.stop_calls = 0
        self.halt_calls = 0
        self.enable_motion_calls = 0
        self.disable_motion_calls = 0
        self.zero_arm_calls = 0
        self.dry_run_payloads = []
        self.joint_commands = []
        self.multi_joint_commands = []

    def ping(self):
        return {"ok": True, "bridge_online": True, "message": "pong"}

    def status(self):
        return {
            "ok": False,
            "bridge_online": False,
            "message": "D1 bridge socket is not available at /run/d1_bridge.sock.",
            "status": {
                "connected": False,
                "estop": False,
                "motion_enabled": False,
                "dry_run_only": True,
                "controller_lock_held": False,
                "error_code": 0,
                "error_kind": "",
                "mode": "offline",
                "backend": "unavailable",
                "controller_owner": "d1_bridge",
                "last_update_ms": 0,
                "last_error": "",
                "last_error_message": "",
            },
        }

    def joints(self):
        return {
            "ok": True,
            "bridge_online": True,
            "joint_state": {
                "q": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
                "dq": [0.0] * 6,
                "tau": [0.0] * 6,
                "valid": True,
                "stamp_ms": 123456789,
            },
        }

    def stop(self):
        self.stop_calls += 1
        return {"ok": True, "bridge_online": True, "message": "halt requested"}

    def halt(self):
        self.halt_calls += 1
        return {"ok": True, "bridge_online": True, "message": "halt requested"}

    def enable_motion(self):
        self.enable_motion_calls += 1
        return {"ok": True, "bridge_online": True, "message": "motion enabled"}

    def disable_motion(self):
        self.disable_motion_calls += 1
        return {"ok": True, "bridge_online": True, "message": "motion disabled"}

    def zero_arm(self):
        self.zero_arm_calls += 1
        return {"ok": True, "bridge_online": True, "message": "zero requested"}

    def set_joint_angle(self, joint_id, angle_deg, delay_ms=0):
        self.joint_commands.append((joint_id, angle_deg, delay_ms))
        return {"ok": True, "bridge_online": True, "message": "command published"}

    def set_multi_joint_angle(self, angles_deg, mode=1):
        self.multi_joint_commands.append((angles_deg, mode))
        return {"ok": True, "bridge_online": True, "message": "command published"}

    def dry_run(self, payload):
        self.dry_run_payloads.append(payload)
        return {"ok": True, "bridge_online": True, "message": "accepted in dry-run only"}


def test_d1_api_status_exposes_structured_offline_payload() -> None:
    config_path = write_test_config()
    app = create_app(config_path=config_path)
    app.state.runtime.d1 = _FakeD1Service()

    status_endpoint = _route_endpoint(app, "/api/d1/status")
    response = status_endpoint()

    assert response["ok"] is False
    assert response["bridge_online"] is False
    assert response["status"]["dry_run_only"] is True
    assert response["status"]["mode"] == "offline"


def test_d1_api_joints_returns_joint_telemetry() -> None:
    config_path = write_test_config()
    app = create_app(config_path=config_path)
    app.state.runtime.d1 = _FakeD1Service()

    joints_endpoint = _route_endpoint(app, "/api/d1/joints")
    response = joints_endpoint()

    assert response["ok"] is True
    assert response["joint_state"]["valid"] is True
    assert response["joint_state"]["q"][5] == 0.5


def test_d1_api_stop_and_dry_run_use_safe_service_calls() -> None:
    config_path = write_test_config()
    app = create_app(config_path=config_path)
    fake_service = _FakeD1Service()
    app.state.runtime.d1 = fake_service

    stop_endpoint = _route_endpoint(app, "/api/d1/stop", "POST")
    halt_endpoint = _route_endpoint(app, "/api/d1/halt", "POST")
    enable_endpoint = _route_endpoint(app, "/api/d1/enable-motion", "POST")
    disable_endpoint = _route_endpoint(app, "/api/d1/disable-motion", "POST")
    zero_endpoint = _route_endpoint(app, "/api/d1/zero-arm", "POST")
    joint_endpoint = _route_endpoint(app, "/api/d1/set-joint-angle", "POST")
    multi_endpoint = _route_endpoint(app, "/api/d1/set-multi-joint-angle", "POST")
    dry_run_endpoint = _route_endpoint(app, "/api/d1/dry-run", "POST")

    stop_response = stop_endpoint()
    halt_response = halt_endpoint()
    enable_response = enable_endpoint()
    disable_response = disable_endpoint()
    zero_response = zero_endpoint()
    joint_response = joint_endpoint(D1SingleJointRequest(joint_id=2, angle_deg=12.5, delay_ms=30))
    multi_response = multi_endpoint(D1MultiJointRequest(angles_deg=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5], mode=1))
    dry_run_response = dry_run_endpoint(
        D1DryRunRequest(
            payload={
                "kind": "ui_dry_run_probe",
                "data": {"source": "pytest", "note": "no motion"},
            }
        )
    )

    assert stop_response["ok"] is True
    assert halt_response["ok"] is True
    assert enable_response["message"] == "motion enabled"
    assert disable_response["message"] == "motion disabled"
    assert zero_response["message"] == "zero requested"
    assert joint_response["message"] == "command published"
    assert multi_response["message"] == "command published"
    assert stop_response["message"] == "halt requested"
    assert dry_run_response["ok"] is True
    assert dry_run_response["message"] == "accepted in dry-run only"
    assert fake_service.stop_calls == 1
    assert fake_service.halt_calls == 1
    assert fake_service.enable_motion_calls == 1
    assert fake_service.disable_motion_calls == 1
    assert fake_service.zero_arm_calls == 1
    assert fake_service.joint_commands == [(2, 12.5, 30)]
    assert fake_service.multi_joint_commands == [([0.0, 0.1, 0.2, 0.3, 0.4, 0.5], 1)]
    assert fake_service.dry_run_payloads == [
        {
            "kind": "ui_dry_run_probe",
            "data": {"source": "pytest", "note": "no motion"},
        }
    ]
