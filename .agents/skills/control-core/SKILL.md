---
name: control-core
description: "Use only for control priority, ESTOP, MANUAL vs AUTO arbitration, watchdog behavior, mission pause and resume semantics, and related control tests. Do not use for route schema, dashboard UI, or robot SDK integration."
---

Use this skill only for:
- `src/control.py`
- closely related mission pause/resume wiring
- `tests/test_control_priority.py`
- other small control-specific tests

Required semantics:
- Priority is `ESTOP > MANUAL > AUTO`
- ESTOP blocks all motion until reset
- MANUAL blocks AUTO commands
- manual takeover pauses mission
- mission never auto-resumes after manual release
- watchdog stops the robot when manual teleop goes stale

Implementation rules:
- Keep priority enforcement centralized
- Prefer explicit state transitions
- Avoid adding abstractions unless required
- Preserve public API names where possible
- Keep behavior deterministic and easy to test

Editing policy:
1. Read only control files and directly related failing tests.
2. Patch the smallest possible set of files.
3. Do not redesign mission architecture.
4. Do not touch SDK code unless a stop path requires a tiny adapter-facing call.

Success criteria:
- ESTOP blocks all motion
- MANUAL blocks AUTO
- watchdog stop works correctly
- resume requires an explicit call
- control tests pass