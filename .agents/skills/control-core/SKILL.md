---
name: control-core
description: "Use only for control priority, ESTOP, MANUAL vs AUTO arbitration, watchdog behavior, mission pause and resume semantics, and D1 Arm safety gating. Do not use for route schema, dashboard UI, or robot SDK integration."
---

Use this skill only for:
- `src/control.py`
- `src/services/d1_service.py` (safety gating)
- `tests/test_control_priority.py` and `tests/test_d1_api.py` (safety parts)

Required semantics:
- Priority is `ESTOP > MANUAL > AUTO`
- ESTOP blocks all motion (Go2) and halts the D1 Arm bridge.
- MANUAL blocks AUTO commands.
- Manual takeover pauses Go2 missions.
- D1 Arm: Supports real motion control when explicitly enabled via bridge + app interlocks.
- Watchdog stops Go2 when manual teleop goes stale.

Implementation rules:
- Keep priority enforcement centralized in `ControlCore`.
- Ensure D1 Bridge client respects the global ESTOP state.
- Avoid adding abstractions; use explicit state transitions.
- Keep behavior deterministic and hardware-free for testing.

Editing policy:
1. Read only control files and safety-related tests.
2. Patch the smallest possible set of files.
3. Do not redesign the bridge protocol or mission architecture.

Success criteria:
- ESTOP blocks all motion and halts the D1 Bridge.
- D1 Arm real motion is safety-gated and requires explicit enablement.
- MANUAL blocks AUTO and pauses missions.
- Control and safety tests pass.