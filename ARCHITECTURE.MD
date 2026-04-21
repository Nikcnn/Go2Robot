# Architecture

## Overview

The repo now contains two layers:

- Application layer in `src/`: the existing FastAPI backend, operator dashboard, scripted mission executor, storage, reporting, image analysis, and mock/real Go2 adapter support.
- ROS 2 layer in `ros_ws/`: the new Humble workspace that introduces a bridge process, Nav2 mission execution, and launch/config assets for mapping and navigation.

The current repository layout is still centered on `src/` for the operator app. The ROS packages import selected pieces from that existing Python codebase instead of duplicating storage and analysis logic.

## Current Python MVP

The current application path is:

```text
dashboard/web client
  -> FastAPI in src/api.py
  -> ControlCore in src/control.py
  -> MissionManager in src/mission.py
  -> RobotAdapterProtocol in src/robot/robot_adapter.py
  -> MockRobotAdapter or Go2RobotAdapter
```

Key properties:

- Motion is scripted and time-based: `send_velocity(vx, vy, vyaw)` + wait + `stop()`.
- No localization, SLAM, or Nav2 is required for the current MVP.
- Mock mode runs end-to-end without hardware.
- All uncertain Unitree SDK integration remains isolated to `src/robot/go2_adapter.py`.
- Mission semantics are enforced in one place: `ESTOP > MANUAL > AUTO`.

## ROS 2 Target Layer

The new target flow is:

```text
web / FastAPI
  -> ROS 2 mission service
  -> Nav2 FollowWaypoints
  -> go2_bridge
  -> unitreesdk2py
  -> Go2 robot
```

The ROS workspace lives under `ros_ws/src/` and contains:

- `go2_interfaces`: custom services for mission control and checkpoint capture
- `go2_bridge`: the only ROS package allowed to touch the Go2 Python adapter and, by extension, `unitreesdk2py`
- `go2_mission`: mission execution and service bridge to Nav2
- `go2_nav_bringup`: launch files, Nav2 params, maps, and RViz config

## Process Boundaries

### `go2_bridge`

Responsibilities:

- subscribes to `/cmd_vel`
- calls `adapter.send_velocity()`
- publishes `/odom`
- publishes `/tf` from `odom -> base_link`
- publishes built-in Go2 lidar `PointCloud2` on `/points` from the same SDK-owning process
- keeps RealSense as an optional auxiliary ROS sensor source
- exposes a checkpoint capture service so camera/state capture stays in the same process as the DDS SDK connection

Important constraint:

- `ChannelFactory` is a process singleton, so `go2_bridge` must be the only process that owns the Unitree DDS connection.

### `go2_mission`

Responsibilities:

- loads coordinate missions from `shared_missions/missions/*.json`
- sends `nav2_msgs/action/FollowWaypoints` goals
- waits for arrival
- triggers checkpoint logic after each reached waypoint
- exposes a mission control service for FastAPI or rosbridge clients

Checkpoint handling deliberately reuses existing application logic:

- image capture and robot state are requested from `go2_bridge`
- analysis is routed through the existing `src.analysis` module
- storage/report writing is routed through the existing `src.storage.StorageManager`

### `go2_nav_bringup`

Responsibilities:

- `mapping.launch.py`: starts `go2_bridge`, the lidar conversion chain, optional RealSense bridge, and `slam_toolbox`, but not Nav2
- `navigation.launch.py`: starts `go2_bridge`, the lidar conversion chain, optional RealSense bridge, map server, AMCL, planner, controller, recoveries, BT navigator, waypoint follower, lifecycle managers, and mission API node
- sets `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` in launch
- carries a Humble-compatible `nav2_params.yaml`

## Mission Formats

Two mission styles now coexist in the repo.

### Scripted route format used by the current Python MVP

Stored under `config/routes/*.json`.

Supported steps:

- `move`
- `rotate`
- `checkpoint`
- `stop`

### Coordinate waypoint format used by the ROS 2 layer

Stored under `shared_missions/missions/*.json`.

Example:

```json
{
  "mission_id": "inspect_line_a",
  "map_id": "site_a_floor_1",
  "waypoints": [
    {"id": "panel_A", "x": 4.12, "y": 1.83, "yaw": 1.57, "task": "inspect_panel"},
    {"id": "switch_B", "x": 7.40, "y": 3.11, "yaw": 0.0, "task": "thermal_check"}
  ]
}
```

## Shared Data and Reports

The existing run/report path remains the system of record:

```text
runs/mission_<id>/
  mission_meta.json
  event_log.jsonl
  telemetry.jsonl
  images/
  analysis/
  final_report.json
```

The ROS mission layer writes into that same structure by importing the existing storage module instead of introducing a second reporting format.

## Sensors

Current state:

- Robot camera: supported through the existing adapter path
- RealSense D435i: supported in the Python MVP and exposed in ROS 2 through `go2_bridge/camera_bridge.py`
- Built-in Go2 lidar: ROS path now targets `base_bridge -> /points -> lidar_bridge -> /scan`

Practical implication:

- mapping, AMCL, and Nav2 now have an in-repo sensor chain, but the built-in lidar SDK import/topic assumptions still need runtime validation on Ubuntu + the robot

## Platform Assumptions

The ROS layer is written for:

- Ubuntu 22.04
- ROS 2 Humble
- Python 3.10
- apt-installed Nav2 and slam_toolbox
- `rmw_cyclonedds_cpp`

The existing application layer remains Python-first and continues to run in mock mode without ROS.

## What Is Verified vs Unverified

Verified in this repository:

- Python MVP in `src/`
- generated ROS package structure
- Python syntax for the new ROS nodes
- JSON/YAML syntax for the shared mission and Nav2 parameters

Not verified from this Windows workspace:

- runtime behavior on Ubuntu 22.04 + ROS 2 Humble
- Nav2 bringup with a real map and `/scan`
- live built-in lidar DDS integration inside the ROS bridge
- RealSense runtime inside ROS 2
