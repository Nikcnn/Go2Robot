---
allowed-tools: Read(src/control.py), Read(src/services/d1_service.py), Read(tests/test_control_priority.py), Read(tests/test_d1_api.py), Edit(src/control.py), Edit(src/services/d1_service.py), Edit(tests/test_control_priority.py), Edit(tests/test_d1_api.py), Bash(pytest tests/test_control_priority.py:* tests/test_d1_api.py:*)
description: Patch Go2 control priority, D1 safety gating, watchdog, and related tests
argument-hint: [optional failing case]
model: claude-sonnet-4-0
---

Work only on control-priority and safety semantics for Go2 & D1.

Hard constraints:
- Priority is `ESTOP > MANUAL > AUTO`.
- ESTOP halts Go2 motion AND triggers the D1 software halt path.
- D1 Arm is restricted to **dry-run monitoring only** (real motion disabled).
- Manual takeover pauses missions and never auto-resumes.
- Keep logic centralized; do not redesign the whole mission executor.
- Do not touch hardware-facing SDK code directly.

Task:
1. Read only the allowed files.
2. Identify the smallest patch for Go2 or D1 safety/control logic.
3. Run the targeted tests.
4. Report changed files and exact semantic fix.

Optional focus from user: $ARGUMENTS