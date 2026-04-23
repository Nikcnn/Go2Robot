---
allowed-tools: Read(src/robot_adapter.py), Read(src/integrations/d1_client.py), Read(cpp/d1_bridge/), Read(tests/test_go2_adapter.py), Read(tests/test_d1_client.py), Edit(src/robot_adapter.py), Edit(src/integrations/d1_client.py), Edit(cpp/d1_bridge/), Edit(tests/test_go2_adapter.py), Edit(tests/test_d1_client.py), Bash(pytest tests/test_go2_adapter.py tests/test_d1_client.py)
description: Patch Go2 MockAdapter, D1 Bridge mock mode, and synthetic feedback
argument-hint: [optional issue]
model: claude-sonnet-4-0
---

Work only on the mock path (Go2 Adapter and D1 Bridge) for the inspection system.

Hard constraints:
- Mock mode must run end-to-end without real Go2/D1 hardware or SDKs.
- D1 Bridge `--mock` mode must generate plausible synthetic joint feedback.
- Go2 MockAdapter integrates simple velocity and generates camera frames.
- Keep frame generation and bridge mock logic cheap and deterministic.
- Do not spread real SDK calls into mock paths.

Task:
1. Read only the allowed files.
2. Patch Go2 mock behavior or D1 Bridge mock feedback as needed.
3. Preserve API/bridge protocol compatibility.
4. Run targeted tests in mock mode.
5. Report changes and why they improve mock correctness.

Optional focus from user: $ARGUMENTS