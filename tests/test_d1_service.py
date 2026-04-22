from __future__ import annotations

from src.services.d1_service import D1Service


class _FakeClient:
    def __init__(self) -> None:
        self.enable_motion_calls = 0
        self.multi_joint_calls = 0

    def status(self):
        return {
            "ok": True,
            "bridge_online": True,
            "status": {
                "connected": True,
                "estop": False,
                "motion_enabled": False,
                "dry_run_only": True,
                "controller_lock_held": True,
                "error_code": 12,
                "error_kind": "feedback_fault",
                "mode": "dds-feedback",
                "backend": "dds",
                "controller_owner": "d1_bridge",
                "last_update_ms": 1234,
                "last_error": "publisher unavailable",
                "last_error_message": "publisher unavailable",
            },
        }

    def enable_motion(self):
        self.enable_motion_calls += 1
        return {"ok": True, "message": "motion enabled"}

    def set_multi_joint_angle(self, angles_deg, mode=1):
        self.multi_joint_calls += 1
        return {"ok": True, "message": "command published", "angles_deg": angles_deg, "mode": mode}


def test_d1_service_normalizes_extended_status_fields() -> None:
    service = D1Service(client=_FakeClient(), allow_motion_commands=False)

    response = service.status()

    assert response["ok"] is True
    assert response["status"]["controller_lock_held"] is True
    assert response["status"]["backend"] == "dds"
    assert response["status"]["controller_owner"] == "d1_bridge"
    assert response["status"]["last_error"] == "publisher unavailable"


def test_d1_service_blocks_motion_commands_when_config_disables_them() -> None:
    client = _FakeClient()
    service = D1Service(client=client, allow_motion_commands=False)

    response = service.enable_motion()

    assert response["ok"] is False
    assert response["error"]["kind"] == "motion_disabled_by_config"
    assert client.enable_motion_calls == 0


def test_d1_service_forwards_motion_commands_when_enabled() -> None:
    client = _FakeClient()
    service = D1Service(client=client, allow_motion_commands=True)

    response = service.set_multi_joint_angle([0.0, 0.1, 0.2, 0.3, 0.4, 0.5], mode=1)

    assert response["ok"] is True
    assert client.multi_joint_calls == 1
