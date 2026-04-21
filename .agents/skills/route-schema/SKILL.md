---
name: route-schema
description: "Use only for route JSON, pydantic route validation, route loading, and test_route_loader.py. Do not use for control logic, streaming, dashboard, or SDK integration."
---

Use this skill only for:
- `config/routes/*.json`
- `src/models.py` or route/step schema files
- route loading and validation code
- `tests/test_route_loader.py`

Project rules:
- Python 3.8 only
- pydantic v2 only
- Scripted route execution only
- No ROS, ROS2, Nav2, SLAM, RViz, Gazebo
- Do not expand the project into a generic robotics framework

Supported route step types:
- `move`
- `rotate`
- `checkpoint`
- `stop`

Validation rules:
- Reject unknown step types
- Reject missing required fields
- Keep schema strict and explicit
- Prefer simple validators and direct models
- Keep JSON shape aligned with tests

Editing policy:
1. Read only the route JSON, schema/model files, loader files, and route tests.
2. Patch the minimum required surface area.
3. Do not touch mission execution logic unless validation depends on it.
4. Keep errors clear and deterministic.

Success criteria:
- valid route JSON loads
- invalid route JSON fails clearly
- route tests remain fast and hardware-free