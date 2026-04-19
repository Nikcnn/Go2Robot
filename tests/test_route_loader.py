from __future__ import annotations

import json

import pytest

from tests import make_test_dir
from src.mission import load_route_file


def test_load_valid_demo_route() -> None:
    route = load_route_file("config/routes/demo_route.json")
    assert route.route_id == "demo_route_v1"
    assert [step.type for step in route.steps] == ["move", "checkpoint", "rotate", "stop"]


def test_reject_invalid_route_step() -> None:
    route_path = make_test_dir("route_loader") / "bad_route.json"
    route_path.write_text(
        json.dumps(
            {
                "route_id": "bad_route",
                "steps": [{"id": "broken", "type": "fly", "duration_sec": 1.0}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_route_file(route_path)
