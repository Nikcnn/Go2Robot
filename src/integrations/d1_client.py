from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


DEFAULT_D1_BRIDGE_SOCKET = os.environ.get("D1_BRIDGE_SOCKET", "/run/d1_bridge.sock")
DEFAULT_D1_TIMEOUT_SEC = float(os.environ.get("D1_BRIDGE_TIMEOUT_SEC", "1.0"))


@dataclass
class D1BridgeError(Exception):
    message: str
    kind: str

    def as_dict(self) -> Dict[str, str]:
        return {"kind": self.kind, "message": self.message}

    def __str__(self) -> str:
        return self.message


class D1BridgeClient:
    def __init__(self, socket_path: Optional[str] = None, timeout_sec: Optional[float] = None) -> None:
        self._socket_path = socket_path or DEFAULT_D1_BRIDGE_SOCKET
        self._timeout_sec = timeout_sec if timeout_sec is not None else DEFAULT_D1_TIMEOUT_SEC

    def ping(self) -> Dict[str, Any]:
        return self._request({"cmd": "ping"})

    def status(self) -> Dict[str, Any]:
        return self._request({"cmd": "status"})

    def joints(self) -> Dict[str, Any]:
        return self._request({"cmd": "joints"})

    def stop(self) -> Dict[str, Any]:
        return self._request({"cmd": "stop"})

    def halt(self) -> Dict[str, Any]:
        return self._request({"cmd": "halt"})

    def enable_motion(self) -> Dict[str, Any]:
        return self._request({"cmd": "enable_motion"})

    def disable_motion(self) -> Dict[str, Any]:
        return self._request({"cmd": "disable_motion"})

    def set_joint_angle(self, joint_id: int, angle_deg: float, delay_ms: int = 0) -> Dict[str, Any]:
        return self._request(
            {
                "cmd": "set_joint_angle",
                "payload": {"joint_id": joint_id, "angle_deg": angle_deg, "delay_ms": delay_ms},
            }
        )

    def set_multi_joint_angle(self, angles_deg: List[float], mode: int = 1) -> Dict[str, Any]:
        return self._request(
            {
                "cmd": "set_multi_joint_angle",
                "payload": {"angles_deg": angles_deg, "mode": mode},
            }
        )

    def zero_arm(self) -> Dict[str, Any]:
        return self._request({"cmd": "zero_arm"})

    def dry_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request({"cmd": "dry_run", "payload": payload})

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            request_bytes = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise D1BridgeError("D1 request payload is not JSON serializable.", "bad_payload") from exc

        try:
            socket_family = getattr(socket, "AF_UNIX", socket.AF_INET)
            with socket.socket(socket_family, socket.SOCK_STREAM) as sock:
                sock.settimeout(self._timeout_sec)
                sock.connect(self._socket_path)
                sock.sendall(request_bytes)

                chunks = []
                while True:
                    data = sock.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
        except FileNotFoundError as exc:
            raise D1BridgeError(
                "D1 bridge socket is not available at {path}.".format(path=self._socket_path),
                "offline",
            ) from exc
        except ConnectionRefusedError as exc:
            raise D1BridgeError("D1 bridge refused the connection.", "offline") from exc
        except socket.timeout as exc:
            raise D1BridgeError("Timed out waiting for the D1 bridge response.", "timeout") from exc
        except OSError as exc:
            raise D1BridgeError("D1 bridge socket error: {message}".format(message=str(exc)), "socket_error") from exc

        if not chunks:
            raise D1BridgeError("D1 bridge closed the socket without a response.", "empty_response")

        try:
            decoded = b"".join(chunks).decode("utf-8").strip()
            response = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise D1BridgeError("D1 bridge returned invalid JSON.", "bad_response") from exc

        if not isinstance(response, dict):
            raise D1BridgeError("D1 bridge returned an unexpected response type.", "bad_response")
        return response
