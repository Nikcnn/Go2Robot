from __future__ import annotations

import argparse
import logging
import socket
import sys
from pathlib import Path
from typing import Tuple

import uvicorn

from .api import create_app
from .config import AppConfig, load_app_config


def _port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _resolve_server_port(host: str, preferred_port: int, search_limit: int = 100) -> int:
    for port in range(preferred_port, preferred_port + search_limit):
        if _port_is_available(host, port):
            return port
    raise RuntimeError(f"No free port found on {host} starting from {preferred_port}.")


def _create_app_with_fallback(config: AppConfig, config_path: Path) -> Tuple[object, str]:
    try:
        return create_app(config=config, config_path=config_path), config.robot.mode
    except RuntimeError as exc:
        if config.robot.mode != "go2":
            raise
        fallback_config = config.model_copy(update={"robot": config.robot.model_copy(update={"mode": "mock"})})
        logging.warning(
            "Failed to start Go2 adapter, falling back to mock mode: %s",
            exc,
        )
        return create_app(config=fallback_config, config_path=config_path), "mock"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Go2 inspection MVP server.")
    parser.add_argument("--config", default="config/app_config.yaml", help="Path to the YAML config file.")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_app_config(config_path)
    logging.basicConfig(level=getattr(logging, config.logging.level.upper(), logging.INFO))

    app, effective_mode = _create_app_with_fallback(config, config_path)
    logging.info("Server initialised with robot.mode=%s", effective_mode)

    port = _resolve_server_port(config.server.host, config.server.port)
    if port != config.server.port:
        logging.warning("Port %s is busy on %s, falling back to %s.", config.server.port, config.server.host, port)
    uvicorn.run(app, host=config.server.host, port=port)


if __name__ == "__main__":
    main()
