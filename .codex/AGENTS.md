# Go2 & D1 Inspection System Rules

## Scope

- Safe test-environment only.
- Supported execution paths:
  - `src/`: Python 3.8 app with FastAPI, dashboard, and D1 bridge integration.
  - `cpp/d1_bridge/`: C++17 daemon for the Unitree D1 arm.
  - `ros_ws/`: ROS 2 Foxy workspace for navigation and coordinate missions.

## Architecture & Boundaries

- **Go2 SDK**: In the Python app, all `unitree_sdk2py` calls must stay inside `src/robot/go2_adapter.py`.
- **D1 SDK**: All D1 arm SDK/DDS logic belongs in `cpp/d1_bridge/`. The Python app communicates with it ONLY via the UNIX socket client in `src/integrations/d1_client.py`.
- **D1 Safety**: Real arm motion is safety-gated and requires explicit bridge + app enablement. `can_publish_motion` in the bridge defaults to false.
- **DDS Singleton**: Only one process per hardware path should own the `ChannelFactory`.
- **Mock Mode**: Both Go2 and D1 paths must remain end-to-end runnable without hardware.

## Platform Expectations

- `src/` targets Python 3.8.
- `cpp/d1_bridge/` targets C++17 and Ubuntu 20.04.
- `ros_ws/` targets ROS 2 Foxy on Ubuntu 20.04.
- Use `rmw_cyclonedds_cpp` for all SDK-facing processes.

## Mission & Control Semantics

- Python app: scripted JSON routes (`config/routes/`).
- ROS layer: coordinate waypoint missions (`shared_missions/missions/`).
- Priority: `ESTOP > MANUAL > AUTO`.
- Manual takeover pauses missions and never auto-resumes.
- D1 Arm: Fully controllable via safety-gated commands in both mock and real modes.

## Editing Rules

- Patch minimum surface area.
- Do not redesign the bridge protocol or adapter boundaries without explicit request.
- Keep the Python app usable even if the C++ bridge or ROS stack is offline.
- Update tests when changing `src/integrations/d1_client.py` or `src/services/d1_service.py`.

## Communication & Validation

- Hardware-free testing via `pytest` and `--mock` bridge mode is mandatory.
- D1 real DDS feedback and ROS 2 runtime behavior must be validated on Ubuntu 20.04.
