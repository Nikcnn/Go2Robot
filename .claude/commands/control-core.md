---
allowed-tools: Read(src/control.py), Read(src/mission.py), Read(tests/test_control_priority.py), Edit(src/control.py), Edit(src/mission.py), Edit(tests/test_control_priority.py), Bash(pytest tests/test_control_priority.py:*)
description: Patch only ControlCore priority, watchdog, mode transitions, and related tests
argument-hint: [optional failing case]
model: claude-sonnet-4-0
---

Work only on control-priority semantics for this Go2 inspection MVP.

Hard constraints:
- Priority is `ESTOP > MANUAL > AUTO`
- Manual override never auto-resumes the mission
- Watchdog in MANUAL stops the robot on stale teleop
- Keep logic centralized in `ControlCore`
- Do not add abstractions or touch unrelated files
- Keep changes minimal and test-driven

Task:
1. Read only the allowed files.
2. Identify the smallest patch needed.
3. Implement only the control-path fix.
4. Run the targeted test.
5. Report changed files and the exact semantic fix.

Optional focus from user: $ARGUMENTS