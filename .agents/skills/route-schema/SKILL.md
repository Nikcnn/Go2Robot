---
name: route-schema
description: "Use only for Go2 scripted routes, pydantic validation, and related tests. Do not use for D1 Arm commands or ROS missions."
---

Use this skill only for:
- `config/routes/*.json`
- `src/models.py` (Go2 route schemas)
- `tests/test_route_loader.py`

Project rules:
- Python 3.8 and Pydantic v2 only.
- Go2 scripted route execution only (time/velocity based).
- **Not for D1 Arm**: The D1 integration uses its own JSON bridge protocol, not scripted routes.
- **Not for ROS**: Coordinate missions in `shared_missions/` use their own schema.

Supported step types (Go2):
- `move`, `rotate`, `checkpoint`, `stop`, `stand_up`, `wait`, `settle`.

Validation rules:
- Reject unknown Go2 step types.
- Keep JSON schema strict and aligned with Pydantic models.
- Reject missions if required fields are missing.

Editing policy:
1. Read only the route JSON, schema files, and route tests.
2. Patch the minimum required surface area.
3. Keep errors clear and deterministic.

Success criteria:
- Go2 scripted routes load and validate correctly.
- Invalid Go2 JSON fails validation with clear errors.
- Route tests pass without hardware.