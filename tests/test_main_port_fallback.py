from __future__ import annotations

from src.config import AppConfig, RobotConfig
from src.main import _resolve_server_port
import src.main as main_module


def test_resolve_server_port_skips_busy_port(monkeypatch) -> None:
    def fake_port_is_available(host: str, port: int) -> bool:
        return port == 8002

    monkeypatch.setattr("src.main._port_is_available", fake_port_is_available)

    resolved = _resolve_server_port("127.0.0.1", 8000, search_limit=5)

    assert resolved == 8002


def test_create_app_with_fallback_switches_go2_to_mock(monkeypatch) -> None:
    calls: list[str] = []

    def fake_create_app(*, config, config_path):
        calls.append(config.robot.mode)
        if config.robot.mode == "go2":
            raise RuntimeError("unitree_sdk2py missing")
        return {"mode": config.robot.mode, "path": str(config_path)}

    monkeypatch.setattr(main_module, "create_app", fake_create_app)

    config = AppConfig(robot=RobotConfig(mode="go2"))
    app, effective_mode = main_module._create_app_with_fallback(config, "config/app_config.yaml")

    assert effective_mode == "mock"
    assert app["mode"] == "mock"
    assert calls == ["go2", "mock"]
