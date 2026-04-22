# Go2 & D1 Inspection System

This repository contains a safe test-environment inspection and manipulation stack for the Unitree Go2 robot and the Unitree D1 arm.
It supports multiple execution paths:

- `src/`: standalone Python 3.8 application with FastAPI, a vanilla browser dashboard, scripted JSON routes, telemetry, camera streaming, storage, reporting, mock mode, direct Go2 adapter support, and D1 bridge integration.
- `cpp/d1_bridge/`: C++17 local bridge daemon for the Unitree D1 arm, providing a UNIX socket JSON protocol and the only supported DDS owner for the D1 path.
- `ros_ws/`: ROS 2 Foxy workspace for Ubuntu 20.04 with `go2_bridge`, `go2_mission`, `go2_interfaces`, and Nav2 bringup for coordinate waypoint missions.

The Python app can run without ROS. The ROS layer and the real D1 bridge require Ubuntu 20.04.

## Repository Layout

```text
src/                  Python application layer and dashboard
src/robot/            Mock and Go2 robot adapter boundary
src/integrations/     D1 Bridge client and external integrations
src/services/         D1 Arm and other background services
src/web/              Static dashboard HTML, CSS, and JavaScript
cpp/d1_bridge/        C++17 local bridge daemon for D1 Arm
config/routes/        Scripted Python-app route JSON files
ros_ws/               ROS 2 Foxy workspace
ros_ws/src/go2_bridge ROS bridge for cmd_vel, odom/tf, checkpoint capture, lidar, camera
ros_ws/src/go2_mission ROS mission service and Nav2 FollowWaypoints client
ros_ws/src/go2_interfaces Custom ROS 2 service definitions
ros_ws/src/go2_nav_bringup Launch files, Nav2 params, RViz config, maps
shared_missions/      Coordinate waypoint missions and shared maps for ROS
runs/                 Runtime mission artifacts and event logs
tests/                Hardware-free pytest coverage
```

## Platform

- Ubuntu 20.04 for real deployment, ROS 2 work, and the D1 bridge.
- Python 3.8 for the main app and ROS Python nodes.
- C++17 for the D1 bridge daemon.
- ROS 2 Foxy for `ros_ws/`.
- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` when touching the Unitree SDK.

Windows is used for development, but ROS 2 and real hardware integration must be validated on Ubuntu 20.04.

## Quick Start (Mock Mode)

1. **Python App**: Create a Python 3.8 environment and install dependencies:
   ```bash
   python3.8 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python3 -m src.main --config config/app_config.yaml
   ```

2. **D1 Bridge (Optional)**: Build the C++ bridge in mock mode:
   ```bash
   cmake -S cpp/d1_bridge -B build/d1_bridge -DCMAKE_BUILD_TYPE=Release
   cmake --build build/d1_bridge -j
   ./build/d1_bridge/d1_bridge --mock --socket /tmp/d1_bridge.sock
   ```

3. **Open Dashboard**:
   ```text
   http://127.0.0.1:8000/
   ```

The default config uses `robot.mode: mock`, and the dashboard includes a **D1 Arm** tab for monitoring the arm bridge.

## Operator Web UI

The dashboard provides tabs for:

- **Setup**: robot, ROS, and sensor readiness.
- **D1 Arm**: bridge status, joint monitoring (`q`/`dq`/`tau`), explicit motion gating, halt, zero-arm, and real-time joint control.
- **Mapping**: ROS-based mapping control and map saving.
- **Waypoints**: mission CRUD and coordinate-based route management.
- **Navigation**: Nav2 stack control and waypoint route execution.
- **Sensors**: camera streams (Built-in / RealSense) and lidar status.
- **Logs**: operator-first event summaries and technical logs.

## D1 Arm Integration

The D1 path is fully integrated:

```text
Python app -> D1Client -> UNIX socket -> cpp/d1_bridge -> Unitree SDK2 DDS
```

The bridge supports:

- `--mock` mode for hardware-free synthetic feedback and command loops
- real DDS feedback from `current_servo_angle` and `rt/arm_Feedback` / `arm_Feedback`
- a typed DDS command path to `rt/arm_Command` for full joint control

Real arm motion is safety-gated:

- `config/app_config.yaml` can set `d1.enable_motion: true`
- the bridge requires `--enable-motion` or `D1_ENABLE_MOTION=true`
- an operator must still explicitly enable motion through the bridge API/UI before commands are published
- `stop` / `halt` remains available at all times
- full support for `set_joint_angle`, `set_multi_joint_angle`, and `zero_arm`

For more details, see [D1_BRIDGE_SETUP.md](D1_BRIDGE_SETUP.md).

## Real Go2 Integration

Install `unitree_sdk2py` manually and run:
```bash
python3 -m src.main --config config/app_config.go2.enp0s20f0u1c2.yaml
```

Do not run the Python app and `go2_bridge` as real SDK owners simultaneously.

## Safety Rules

- Control priority: `ESTOP > MANUAL > AUTO`.
- Manual takeover pauses active missions.
- Manual release does not auto-resume.
- D1 Arm real motion is disabled by default and requires explicit bridge + app interlocks before the bridge will publish commands.
- Mock mode must remain end-to-end runnable without hardware.

## Tests

Run hardware-free Python tests:
```bash
pytest
```

## What Is Wired vs What Needs Ubuntu 20.04

| Feature | Status | Requires |
|---|---|---|
| Mock mode end-to-end | Wired and tested | Python 3.8 |
| Operator dashboard | Wired and tested | Browser |
| D1 Arm Bridge (Mock) | Wired and tested | C++17, UNIX socket |
| D1 Arm Monitoring | Wired and tested | D1 Bridge online |
| Mission CRUD | Wired and tested | Python app |
| ROS mapping/nav | API contract ready | Ubuntu 20.04, ROS 2 Foxy |
| Real Go2 SDK | Adapter boundary present | `unitree_sdk2py`, Go2 hardware |
| Real D1 Arm SDK feedback | Bridge backend ready | Ubuntu 20.04, D1 hardware |
| Real D1 Arm SDK commands | Implemented but disabled by default | Ubuntu 20.04, D1 hardware, explicit motion enable |

## More Docs

- [BUILD.md](BUILD.md): build and launch details for all components.
- [D1_BRIDGE_SETUP.md](D1_BRIDGE_SETUP.md): D1 bridge bring-up and protocol.
- [ARCHITECTURE.MD](ARCHITECTURE.MD): system design and boundaries.
- [GO2_QUICKSTART.md](GO2_QUICKSTART.md): short operator workflow.
- [GO2_MVP_TECHNOLOGY_RU.md](GO2_MVP_TECHNOLOGY_RU.md): Russian technical overview.
