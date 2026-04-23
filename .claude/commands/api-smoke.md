---
allowed-tools: Read(src/api.py), Read(src/api_d1.py), Read(src/main.py), Read(src/models.py), Read(tests/test_api_smoke.py), Read(tests/test_d1_api.py), Edit(src/api.py), Edit(src/api_d1.py), Edit(src/main.py), Edit(src/models.py), Edit(tests/test_api_smoke.py), Edit(tests/test_d1_api.py), Bash(pytest tests/test_api_smoke.py:* tests/test_d1_api.py:*)
description: Fix API smoke behavior for Go2 status/mission and D1 monitoring/dry-run
argument-hint: [optional failing endpoint]
model: claude-sonnet-4-0
---

Work only on API smoke-path behavior for the Go2 & D1 inspection system.

Hard constraints:
- FastAPI only.
- All request/response bodies must be Pydantic models.
- D1 API must use the bridge client in `src/integrations/d1_client.py`.
- Keep API surface exactly within project scope.
- Do not add auth or unrelated routes.

Task:
1. Read only the allowed files.
2. Fix `/api/status`, `/api/mission/*`, and `/api/d1/*` behavior as needed.
3. Preserve mock-first execution for both Go2 and D1.
4. Run the smoke tests.
5. Return changed files and behavior summary.

Optional focus from user: $ARGUMENTS