---
name: mock-adapter
description: "Use only for Go2 MockAdapter and D1 Bridge mock mode. Do not use for real SDK guessing or unrelated API changes."
---

Use this skill only for:
- `src/robot_adapter.py` (Go2 mock mode)
- `cpp/d1_bridge/` (Bridge mock mode)
- `tests/test_go2_adapter.py` and `tests/test_d1_client.py` (mock paths)

Hard rules:
- Mock mode must run end-to-end without real hardware or SDKs.
- D1 Bridge `--mock` mode must generate plausible synthetic joint angles (q), velocities (dq), and torques (tau).
- Go2 MockAdapter integrates simple velocity to pose and generates moving camera frames.
- Degrade gracefully if the bridge or hardware is missing.

Implementation guidance:
- Go2 `send_velocity()` updates mock state; `get_pose()` integrates it.
- D1 Bridge mock mode serves synthetic JSON feedback over the UNIX socket.
- `capture_frame()` returns a valid BGR numpy frame (mock camera).
- Mock telemetry should be plausible and change over time.

Editing policy:
1. Read only mock-specific adapter or bridge code.
2. Keep generation logic cheap and deterministic.
3. Do not introduce real SDK dependencies into the mock path.

Success criteria:
- `python3 -m src.main --config config/app_config.yaml` runs without Go2 hardware.
- `d1_bridge --mock` provides feedback without a D1 arm.
- Web dashboard displays moving telemetry and camera frames in mock mode.