# Architecture

The project is split into a standalone Python application layer and a ROS 2 Foxy navigation layer. Both layers share mission artifact storage under `runs/`, but they have separate execution models.

## High-Level Shape

```text
Python app path:
Browser dashboard / REST client
  -> FastAPI app
  -> ControlCore
  -> MissionManager
  -> RobotAdapterProtocol
  -> MockRobotAdapter or Go2RobotAdapter

ROS 2 path:
Mission service client
  -> go2_mission
  -> Nav2 FollowWaypoints
  -> /cmd_vel
  -> go2_bridge
  -> MockRobotAdapter or Go2RobotAdapter
```

The direct Unitree SDK boundary is intentionally narrow. In the Python app it belongs in `src/robot/go2_adapter.py` and closely related robot adapter code. In ROS it belongs in `go2_bridge`, which is the only ROS process allowed to own the adapter.

## Python Application Layer

The Python app lives in `src/` and targets Python 3.8.

Main components:

- `src/main.py`: command-line bootstrap, config loading, port selection, Uvicorn startup.
- `src/api.py`: FastAPI app composition, HTTP endpoints, WebSockets, startup and shutdown lifecycle.
- `src/control.py`: central motion arbiter and safety priority enforcement.
- `src/mission.py`: scripted route loading, validation, execution, checkpoint handling.
- `src/models.py`: Pydantic v2 models for routes, API payloads, telemetry, reports, and actions.
- `src/robot/robot_adapter.py`: adapter protocol and mock implementation.
- `src/robot/go2_adapter.py`: real Go2 adapter boundary for `unitree_sdk2py`.
- `src/telemetry.py`: adapter polling and telemetry snapshots.
- `src/streaming.py`: camera stream and event stream support.
- `src/storage.py`: run directories, events, telemetry, checkpoint images, reports.
- `src/event_log.py`: cross-run event log.
- `src/state_machine.py`: effective robot state tracking for UI and API.
- `src/sensors/realsense_camera.py`: optional RealSense D435i capture path.
- `src/web/`: static dashboard.

## Python App Runtime

At startup the app:

1. Loads `config/app_config.yaml` or another supplied config file.
2. Builds the adapter in `mock` or `go2` mode.
3. Builds `ControlCore`, telemetry, camera streaming, storage, event log, and mission services.
4. Starts the adapter, telemetry poller, camera worker, and optional RealSense service.
5. Serves the dashboard, API endpoints, WebSockets, and MJPEG camera stream.

If adapter startup fails, the app remains safe: movement is blocked and the control state is latched accordingly.

## Control Semantics

Motion commands go through `ControlCore`.

Priority is:

```text
ESTOP > MANUAL > AUTO
```

Rules:

- ESTOP blocks motion and aborts active automated work.
- Manual takeover pauses a mission.
- Manual release does not resume a mission automatically.
- The manual watchdog stops motion if teleop commands stop arriving.
- A single active motion authority should control the robot at any time.

## Python Mission Model

Scripted routes live in `config/routes/*.json`.

Current route step types:

- `move`
- `move_velocity`
- `rotate`
- `checkpoint`
- `stop`
- `stand_up`
- `wait`
- `settle`

These are time and velocity based scripts. They are not map-relative navigation goals.

## ROS 2 Foxy Layer

The ROS workspace lives in `ros_ws/` and targets Ubuntu 20.04, ROS 2 Foxy, and Python 3.8.

Packages:

- `go2_interfaces`: custom `CheckpointCapture` and `MissionControl` services.
- `go2_bridge`: adapter owner, `/cmd_vel` subscriber, `/odom` and `/tf` publisher, checkpoint capture service, built-in lidar source, RealSense bridge.
- `go2_mission`: coordinate mission loader, mission service node, Nav2 `FollowWaypoints` client, checkpoint task runner.
- `go2_nav_bringup`: mapping and navigation launch files, Nav2 params, RViz config, maps.

ROS runtime shape:

```text
go2_mission
  -> nav2_msgs/action/FollowWaypoints
  -> Nav2 waypoint follower
  -> /cmd_vel
  -> go2_bridge
  -> robot adapter
```

## ROS Mission Model

Coordinate missions live in `shared_missions/missions/*.json`.

Example shape:

```json
{
  "mission_id": "inspect_line_a",
  "map_id": "site_a_floor_1",
  "waypoints": [
    {"id": "panel_A", "x": 4.12, "y": 1.83, "yaw": 1.57, "task": "inspect_panel"}
  ]
}
```

Each waypoint is converted to a `PoseStamped` in the `map` frame and sent to Nav2.

## Sensor Paths

Robot camera:

- The Python app uses the adapter camera path.
- ROS checkpoint capture also asks `go2_bridge` to capture through the adapter.

RealSense:

- Python app support is optional through `src/sensors/realsense_camera.py`.
- ROS support is optional through `go2_bridge/camera_bridge.py`.
- RealSense must not break mock mode or the base robot-camera path.

Built-in lidar:

- `base_bridge` can publish PointCloud2 on `/points`.
- `lidar_bridge` converts PointCloud2 into LaserScan on `/scan`.
- Mock lidar exists for local ROS graph testing.
- Real Unitree lidar needs the generated SDK PointCloud2 message import path verified on Ubuntu 20.04 with the robot connected.
- Mapping, AMCL, and Nav2 are not runtime-complete without a live valid `/scan`.

## Storage and Reports

Both layers write run artifacts under `runs/`.

Typical Python app run:

```text
runs/mission_<id>/
  mission_meta.json
  event_log.jsonl
  telemetry.jsonl
  images/
  analysis/
  final_report.json
```

With RealSense enabled, extra RGB-D files can be stored under a `realsense/` subdirectory.

The cross-run persistent event log is:

```text
runs/events.jsonl
```

## Configuration

Python app config:

- `config/app_config.yaml`: mock default.
- `config/app_config.go2.enp0s20f0u1c2.yaml`: real Go2 example.

ROS config:

- Launch arguments in `mapping.launch.py` and `navigation.launch.py`.
- Nav2 parameters in `ros_ws/src/go2_nav_bringup/params/nav2_params.yaml`.
- Shared maps and missions under `shared_missions/`.

## Current Validation State

Hardware-free Python tests exist under `tests/`.

The ROS files are structured for Foxy, but full `colcon build`, Unitree SDK startup, real lidar, mapping, AMCL, Nav2, and robot motion must be validated on Ubuntu 20.04. Do not infer that runtime validation happened from this Windows workspace.
