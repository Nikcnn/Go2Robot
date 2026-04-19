---
name: mock-adapter
description: "Use only for the mock robot path: MockRobotAdapter, fake pose integration, synthetic telemetry, synthetic camera frames, optional fake lidar preview, and tests that depend on mock mode. Do not use for real SDK guessing or unrelated API changes."
---

Use this skill only for:
- `src/robot_adapter.py` or robot adapter files
- mock telemetry generation
- fake pose integration from velocity
- synthetic camera frame generation
- optional mock lidar preview
- tests and smoke paths that depend on mock mode

Hard rules:
- Never invent Unitree SDK method names
- Keep all uncertain real SDK integration isolated in the real adapter path
- Mock mode must run end-to-end without hardware
- Camera frames should change over time
- Telemetry should be plausible and lightweight
- Pose integration should stay simple and deterministic

Implementation guidance:
- `connect()` and `disconnect()` must be safe
- `send_velocity()` updates current mock motion state
- `stop()` zeros motion
- `get_state()` returns optional battery / imu / faults-like data
- `get_pose()` integrates simple fake motion
- `capture_frame()` returns a valid BGR numpy frame
- degrade gracefully if lidar is unavailable

Editing policy:
1. Read only adapter files and directly related smoke tests.
2. Keep frame generation cheap.
3. Preserve compatibility with mission checkpoints and streams.
4. Do not spread speculative real SDK calls outside adapter files.

Success criteria:
- mock mode runs without hardware
- telemetry changes over time
- pose changes when velocity is sent
- camera stream is alive
- smoke tests can pass in mock mode