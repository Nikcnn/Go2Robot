# Architecture

The project is split into a standalone Python application layer, a ROS 2 Foxy navigation layer, and a C++17 D1 Bridge daemon. Both layers share mission artifact storage under `runs/`.

## High-Level Shape

```text
Python app path:
Browser dashboard / REST client
  -> FastAPI app (src/api.py, src/api_d1.py)
  -> D1Service (src/services/d1_service.py)
  -> D1Client (src/integrations/d1_client.py)
  -> UNIX Socket (/run/d1_bridge.sock)
  -> D1 Bridge Daemon (cpp/d1_bridge/)
  -> Unitree SDK2 DDS (Feedback/Commands)

ROS 2 path:
Mission service client
  -> go2_mission
  -> Nav2 FollowWaypoints
  -> /cmd_vel
  -> go2_bridge
  -> MockRobotAdapter or Go2RobotAdapter
```

## Python Application Layer

The Python app lives in `src/` and targets Python 3.8.

Main components:

- `src/main.py`: bootstrap, config loading, and service orchestration.
- `src/api.py`: core FastAPI endpoints, WebSockets, and lifecycle.
- `src/api_d1.py`: D1 Arm specific endpoints for monitoring and explicit safe commands.
- `src/services/d1_service.py`: bridge-facing D1 service with an app-level motion gate.
- `src/integrations/d1_client.py`: low-level UNIX socket client for the D1 bridge.
- `src/control.py`: central motion arbiter and safety priority enforcement.
- `src/mission.py`: scripted route loading and execution.
- `src/robot/robot_adapter.py`: Go2 adapter protocol and mock implementation.
- `src/web/`: static dashboard with integrated D1 monitoring and motion-gating controls.

## D1 Bridge Daemon

The D1 bridge lives in `cpp/d1_bridge/` and targets C++17.

- **Purpose**: Low-latency boundary between the Python app and the Unitree SDK2 DDS feedback / command topics.
- **Protocol**: JSON-based messages over a UNIX domain socket.
- **Backend**:
  - `MockBackend`: Synthetic joint data for testing and local bring-up.
  - `DDSBackend`: Official Unitree SDK2 subscriptions plus gated command publishing.
- **Ownership**: The bridge is the only supported DDS / `ChannelFactory` owner for the D1 path.
- **Safety**: Motion publishing stays off by default and requires explicit app + bridge interlocks before any SDK command is emitted.

## Control Semantics

Motion commands go through `ControlCore` for Go2 and are gated in the D1 Bridge for the arm.

Priority is:
```text
ESTOP > MANUAL > AUTO
```

Rules:

- ESTOP blocks motion and aborts active automated work.
- Manual takeover pauses a mission.
- Manual release does not resume a mission automatically.
- D1 halt remains available at all times.
- D1 real commands are rejected unless the bridge is connected, ESTOP is clear, motion has been explicitly enabled, and command validation passes.

## ROS 2 Foxy Layer

The ROS workspace lives in `ros_ws/` and targets Ubuntu 20.04 and ROS 2 Foxy.

Packages:

- `go2_interfaces`: custom `CheckpointCapture` and `MissionControl` services.
- `go2_bridge`: adapter owner, `/cmd_vel` subscriber, `/odom`, `/tf`, and lidar source.
- `go2_mission`: coordinate mission loader and Nav2 `FollowWaypoints` client.
- `go2_nav_bringup`: launch files, Nav2 params, and maps.

## Sensor Paths

Robot camera:

- Python app uses the adapter path.
- ROS uses `go2_bridge`.

RealSense:

- Supported in both layers as an optional module.

Built-in lidar:

- Bridged from PointCloud2 to LaserScan on `/scan` for ROS-based navigation and mapping.

## Storage and Reports

All layers write run artifacts under `runs/`.

- `runs/mission_<id>/`: mission-specific telemetry, images, and reports.
- `runs/events.jsonl`: cross-run persistent event log.

## Configuration

- `config/app_config.yaml`: Main Python app configuration.
- `config/app_config.yaml` also carries `d1.enable_motion`, which defaults to `false`.
- `D1_BRIDGE_SOCKET`: Environment variable for D1 bridge socket path.
- `D1_ENABLE_MOTION`: Bridge-side environment flag that remains `false` by default.
- `ros_ws/src/go2_nav_bringup/params/nav2_params.yaml`: Nav2 parameters.

## Current Validation State

- **Mock Mode**: Fully wired and tested for both Go2 and D1.
- **ROS 2**: Files structured for Foxy; runtime validation requires Ubuntu 20.04.
- **D1 Arm**: Bridge builds without the SDK, mock mode remains supported, and real DDS feedback / command runtime validation still requires Ubuntu 20.04 and D1 hardware.
- **Go2 Real SDK**: Adapter boundary present; requires `unitree_sdk2py`.
