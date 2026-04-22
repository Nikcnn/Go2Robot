from __future__ import annotations

import json

import pytest

from src.integrations import d1_client
from src.integrations.d1_client import D1BridgeClient, D1BridgeError


class _FakeUnixSocket:
    def __init__(self, response: bytes = b"", connect_exc: Exception = None) -> None:
        self._response = response
        self._connect_exc = connect_exc
        self.sent = b""
        self.timeout = None
        self.connected_path = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def settimeout(self, timeout):
        self.timeout = timeout

    def connect(self, path):
        self.connected_path = path
        if self._connect_exc is not None:
            raise self._connect_exc

    def sendall(self, data):
        self.sent += data

    def recv(self, size):
        if not self._response:
            return b""
        chunk = self._response[:size]
        self._response = self._response[size:]
        return chunk

    def close(self):
        return None


class _SocketFactory:
    def __init__(self, sockets):
        self._sockets = list(sockets)

    def __call__(self, *args, **kwargs):
        return self._sockets.pop(0)


def test_d1_client_sends_json_requests_and_parses_joint_state(monkeypatch) -> None:
    ping_socket = _FakeUnixSocket(response=b'{"ok":true,"message":"pong"}\n')
    joints_socket = _FakeUnixSocket(
        response=(
            b'{"ok":true,"joint_state":{"q":[1,2,3,4,5,6],"dq":[0,0,0,0,0,0],'
            b'"tau":[0.1,0.2,0.3,0.4,0.5,0.6],"valid":true,"stamp_ms":123}}\n'
        )
    )
    monkeypatch.setattr(
        d1_client.socket,
        "socket",
        _SocketFactory([ping_socket, joints_socket]),
    )

    client = D1BridgeClient(socket_path="/tmp/test_d1_bridge.sock", timeout_sec=0.25)
    ping = client.ping()
    joints = client.joints()

    assert ping["message"] == "pong"
    assert joints["joint_state"]["q"] == [1, 2, 3, 4, 5, 6]
    assert joints["joint_state"]["valid"] is True
    assert ping_socket.connected_path == "/tmp/test_d1_bridge.sock"
    assert joints_socket.connected_path == "/tmp/test_d1_bridge.sock"
    assert json.loads(ping_socket.sent.decode("utf-8").strip()) == {"cmd": "ping"}
    assert json.loads(joints_socket.sent.decode("utf-8").strip()) == {"cmd": "joints"}


def test_d1_client_reports_offline_bridge_cleanly(monkeypatch) -> None:
    offline_socket = _FakeUnixSocket(connect_exc=FileNotFoundError("missing"))
    monkeypatch.setattr(d1_client.socket, "socket", _SocketFactory([offline_socket]))

    client = D1BridgeClient(socket_path="/tmp/missing.sock", timeout_sec=0.1)

    with pytest.raises(D1BridgeError) as exc_info:
        client.status()

    assert exc_info.value.kind == "offline"
    assert "not available" in exc_info.value.message


def test_d1_client_sends_typed_motion_commands(monkeypatch) -> None:
    enable_socket = _FakeUnixSocket(response=b'{"ok":true,"message":"motion enabled"}\n')
    joint_socket = _FakeUnixSocket(response=b'{"ok":true,"message":"command published"}\n')
    zero_socket = _FakeUnixSocket(response=b'{"ok":true,"message":"zero requested"}\n')
    monkeypatch.setattr(
        d1_client.socket,
        "socket",
        _SocketFactory([enable_socket, joint_socket, zero_socket]),
    )

    client = D1BridgeClient(socket_path="/tmp/test_d1_bridge.sock", timeout_sec=0.25)
    enable = client.enable_motion()
    joint = client.set_joint_angle(joint_id=2, angle_deg=15.5, delay_ms=25)
    zero = client.zero_arm()

    assert enable["message"] == "motion enabled"
    assert joint["message"] == "command published"
    assert zero["message"] == "zero requested"
    assert json.loads(enable_socket.sent.decode("utf-8").strip()) == {"cmd": "enable_motion"}
    assert json.loads(joint_socket.sent.decode("utf-8").strip()) == {
        "cmd": "set_joint_angle",
        "payload": {"joint_id": 2, "angle_deg": 15.5, "delay_ms": 25},
    }
    assert json.loads(zero_socket.sent.decode("utf-8").strip()) == {"cmd": "zero_arm"}
