from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable, Dict, List, Optional

from ..integrations.d1_client import D1BridgeClient, D1BridgeError


class D1Service:
    def __init__(self, client: Optional[D1BridgeClient] = None, allow_motion_commands: bool = False) -> None:
        self._client = client or D1BridgeClient()
        self._allow_motion_commands = allow_motion_commands

    def ping(self) -> Dict[str, Any]:
        return self._call(self._client.ping)

    def status(self) -> Dict[str, Any]:
        response = self._call(self._client.status, default={"status": self._offline_status()})
        response["status"] = self._normalize_status(response.get("status"))
        return response

    def joints(self) -> Dict[str, Any]:
        response = self._call(self._client.joints, default={"joint_state": self._offline_joint_state()})
        response["joint_state"] = self._normalize_joint_state(response.get("joint_state"))
        return response

    def stop(self) -> Dict[str, Any]:
        return self._call(self._client.stop)

    def halt(self) -> Dict[str, Any]:
        return self._call(self._client.halt)

    def enable_motion(self) -> Dict[str, Any]:
        blocked = self._reject_if_motion_disabled()
        if blocked:
            return blocked
        return self._call(self._client.enable_motion)

    def disable_motion(self) -> Dict[str, Any]:
        return self._call(self._client.disable_motion)

    def zero_arm(self) -> Dict[str, Any]:
        blocked = self._reject_if_motion_disabled()
        if blocked:
            return blocked
        return self._call(self._client.zero_arm)

    def set_joint_angle(self, joint_id: int, angle_deg: float, delay_ms: int = 0) -> Dict[str, Any]:
        blocked = self._reject_if_motion_disabled()
        if blocked:
            return blocked
        return self._call(lambda: self._client.set_joint_angle(joint_id=joint_id, angle_deg=angle_deg, delay_ms=delay_ms))

    def set_multi_joint_angle(self, angles_deg: List[float], mode: int = 1) -> Dict[str, Any]:
        blocked = self._reject_if_motion_disabled()
        if blocked:
            return blocked
        return self._call(lambda: self._client.set_multi_joint_angle(angles_deg=angles_deg, mode=mode))

    def dry_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {
                "ok": False,
                "bridge_online": False,
                "message": "dry_run payload must be a JSON object.",
                "error": {"kind": "bad_payload", "message": "dry_run payload must be a JSON object."},
            }
        return self._call(lambda: self._client.dry_run(payload))

    def _call(
        self,
        operation: Callable[[], Dict[str, Any]],
        default: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            payload = operation()
        except D1BridgeError as exc:
            response: Dict[str, Any] = {
                "ok": False,
                "bridge_online": False,
                "message": exc.message,
                "error": exc.as_dict(),
            }
            if default:
                response.update(default)
            return response

        if not isinstance(payload, dict):
            response = {
                "ok": False,
                "bridge_online": True,
                "message": "D1 bridge returned a non-object response.",
                "error": {"kind": "bad_response", "message": "D1 bridge returned a non-object response."},
            }
            if default:
                response.update(default)
            return response

        response = dict(payload)
        response["bridge_online"] = True
        response.setdefault("ok", True)
        response.setdefault("message", "")
        if default:
            for key, value in default.items():
                response.setdefault(key, value)
        return response

    def _reject_if_motion_disabled(self) -> Optional[Dict[str, Any]]:
        if self._allow_motion_commands:
            return None
        message = "d1.enable_motion is false; real D1 motion commands remain disabled."
        return {
            "ok": False,
            "bridge_online": True,
            "message": message,
            "error": {"kind": "motion_disabled_by_config", "message": message},
            "error_code": 1201,
            "error_kind": "motion_disabled_by_config",
            "accepted": False,
            "motion_enabled": False,
            "dry_run_only": True,
        }

    def _normalize_status(self, payload: Any) -> Dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        return {
            "connected": bool(data.get("connected", False)),
            "estop": bool(data.get("estop", False)),
            "motion_enabled": bool(data.get("motion_enabled", False)),
            "dry_run_only": bool(data.get("dry_run_only", True)),
            "controller_lock_held": bool(data.get("controller_lock_held", False)),
            "error_code": self._as_int(data.get("error_code", 0)),
            "error_kind": str(data.get("error_kind") or ""),
            "mode": str(data.get("mode") or "readonly"),
            "backend": str(data.get("backend") or "unavailable"),
            "controller_owner": str(data.get("controller_owner") or "d1_bridge"),
            "last_update_ms": self._as_int(data.get("last_update_ms", 0)),
            "last_error": str(data.get("last_error") or data.get("last_error_message") or ""),
            "last_error_message": str(data.get("last_error_message") or ""),
        }

    def _normalize_joint_state(self, payload: Any) -> Dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        return {
            "q": self._normalize_vector(data.get("q")),
            "dq": self._normalize_vector(data.get("dq")),
            "tau": self._normalize_vector(data.get("tau")),
            "valid": bool(data.get("valid", False)),
            "stamp_ms": self._as_int(data.get("stamp_ms", 0)),
        }

    def _normalize_vector(self, values: Any) -> list:
        if not isinstance(values, Iterable) or isinstance(values, (str, bytes, dict)):
            return [0.0] * 6

        result = []
        for item in list(values)[:6]:
            try:
                result.append(float(item))
            except (TypeError, ValueError):
                result.append(0.0)
        while len(result) < 6:
            result.append(0.0)
        return result

    def _offline_status(self) -> Dict[str, Any]:
        return {
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
        }

    def _offline_joint_state(self) -> Dict[str, Any]:
        return {
            "q": [0.0] * 6,
            "dq": [0.0] * 6,
            "tau": [0.0] * 6,
            "valid": False,
            "stamp_ms": 0,
        }

    def _as_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
