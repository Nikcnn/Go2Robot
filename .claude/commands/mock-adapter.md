---
allowed-tools: Read(src/robot_adapter.py), Read(src/telemetry.py), Read(src/streaming.py), Read(tests/test_api_smoke.py), Edit(src/robot_adapter.py), Edit(src/telemetry.py), Edit(src/streaming.py), Edit(tests/test_api_smoke.py), Bash(pytest tests/test_api_smoke.py:*)
description: Patch mock adapter, fake pose, synthetic telemetry, and generated camera frames
argument-hint: [optional issue]
model: claude-sonnet-4-0
---

Work only on the mock robot path for this Go2 inspection MVP.

Hard constraints:
- Real SDK uncertainty must stay only in `src/robot_adapter.py`
- Never invent Unitree SDK methods
- Mock mode must work end-to-end without hardware
- Keep frame generation cheap and deterministic enough for tests
- Do not change unrelated architecture

Task:
1. Read only the allowed files.
2. Patch the minimum needed for mock runtime correctness.
3. Preserve API compatibility.
4. Run the targeted smoke test.
5. Report only what changed and why.

Optional focus from user: $ARGUMENTS