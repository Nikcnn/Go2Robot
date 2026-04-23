# Go2 & D1 Inspection System

## Scope

- Safe test-environment project only.
- Target Ubuntu 20.04, Python 3.8, and C++17.
- `src/`: standalone Python app and dashboard.
- `cpp/d1_bridge/`: C++ daemon for the Unitree D1 arm.
- `ros_ws/`: ROS 2 Foxy path for navigation.
- Keep mock mode runnable without hardware.

## Project Paths

- `src/`: FastAPI app, dashboard, Go2 control, D1 service/client, telemetry, streaming, storage, mock/real Go2 adapters.
- `cpp/d1_bridge/`: C++17 bridge daemon for D1 Arm (UNIX socket JSON protocol).
- `ros_ws/`: ROS 2 Foxy workspace with bridge, mission, and Nav2 bringup.
- `config/routes/`: scripted JSON routes for the Go2 Python app.
- `shared_missions/`: coordinate missions and maps for the ROS layer.
- `runs/`: mission artifacts and reports.
- `tests/`: hardware-free pytest coverage for Python; C++ tests in the bridge build.

## Non-Negotiables

- **Go2 SDK**: In the Python app, isolate `unitree_sdk2py` in `src/robot/go2_adapter.py`.
- **D1 SDK**: All D1 arm SDK logic belongs in `cpp/d1_bridge/`. Python app uses the UNIX socket client.
- **D1 Safety**: Real arm motion is strictly disabled. `can_publish_motion` must stay false.
- **DDS Singleton**: Only one process should own the `ChannelFactory` per hardware path.
- **Mock Mode**: Both Go2 and D1 paths must work end-to-end without hardware.
- **ROS Layer**: Use Foxy APIs and Ubuntu 20.04 assumptions only.

## Mission & Control

- Go2 Python: scripted time/velocity JSON routes.
- Go2 ROS: coordinate waypoint JSON missions (Nav2).
- Priority: `ESTOP > MANUAL > AUTO`.
- Manual takeover pauses Go2 missions.
- D1 Arm: Full motion control supported with safety-gated interlocks and dry-run validation.

## Working Style

- Patch the minimum surface area.
- Do not spread SDK uncertainty outside adapter/bridge boundaries.
- Keep Python, C++, and ROS concerns separated.
- Keep tests fast and hardware-free.
