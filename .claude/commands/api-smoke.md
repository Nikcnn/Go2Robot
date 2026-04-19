---
allowed-tools: Read(src/api.py), Read(src/main.py), Read(src/models.py), Read(src/mission.py), Read(tests/test_api_smoke.py), Edit(src/api.py), Edit(src/main.py), Edit(src/models.py), Edit(src/mission.py), Edit(tests/test_api_smoke.py), Bash(pytest tests/test_api_smoke.py:*)
description: Fix API smoke behavior for status, mission start, and current mission state
argument-hint: [optional failing endpoint]
model: claude-sonnet-4-0
---

Work only on API smoke-path behavior for this Go2 inspection MVP.

Hard constraints:
- FastAPI only
- All request/response bodies must be pydantic models
- Keep API surface exactly within project scope
- Do not add auth, frontend frameworks, or unrelated routes
- Keep patches minimal

Task:
1. Read only the allowed files.
2. Fix `/api/status`, `/api/mission/start`, and `/api/mission/current` behavior as needed.
3. Preserve mock-first execution.
4. Run the smoke test.
5. Return changed files and behavior summary.

Optional focus from user: $ARGUMENTS