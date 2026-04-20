# Go2 Inspection System

## What This Is

This repo now contains:

- a working Python MVP in `src/` with FastAPI, a plain HTML dashboard, scripted mission execution, per-mission storage, reports, mock mode, and direct Go2 SDK integration
- a new ROS 2 Humble workspace in `ros_ws/` for `go2_bridge`, `go2_mission`, and Nav2-based bringup

The Python MVP still runs end-to-end without ROS. The ROS workspace is the next architectural layer for waypoint navigation and service-based mission execution.

## What This Is Not

This is not a production autonomy stack. It is not validated here as a complete field-ready Nav2 deployment, and the new built-in lidar ROS path still needs runtime verification on Ubuntu 22.04 with the real robot.

## Repo Layout

```text
src/                 existing FastAPI app, dashboard, storage, analysis, adapters
ros_ws/              ROS 2 Humble workspace
shared_missions/     coordinate missions and shared maps
config/routes/       scripted JSON routes for the current Python MVP
runs/                per-mission outputs
BUILD.md             ROS 2 Humble build and launch notes
```

## Current Application Layer

The existing application path is:

```text
dashboard -> FastAPI -> ControlCore -> MissionManager -> RobotAdapter
```

Main characteristics:

- scripted motion only in the current Python MVP
- mock mode runs without hardware
- real Go2 mode uses `unitree_sdk2py`
- all uncertain SDK code remains isolated to `src/robot/go2_adapter.py`
- control priority is `ESTOP > MANUAL > AUTO`
- manual override pauses missions and never auto-resumes

## ROS 2 Layer

The new target path is:

```text
web / FastAPI -> ROS 2 mission service -> Nav2 -> go2_bridge -> unitreesdk2py -> robot
```

ROS packages:

- `go2_interfaces`: custom ROS services
- `go2_bridge`: `/cmd_vel` subscriber, `/odom` publisher, `/tf` broadcaster, built-in lidar `/points` publisher, optional RealSense bridge, checkpoint capture service
- `go2_mission`: `FollowWaypoints` action client, checkpoint tasks, mission control service
- `go2_nav_bringup`: launch files, Humble Nav2 params, RViz config

Important constraint:

- `go2_bridge` must be the only process that touches `unitreesdk2py` because `ChannelFactory` is a process singleton.

## Install The Python MVP

Create a Python 3.11+ environment and install:

```bash
pip install -r requirements.txt
```

Optional extras:

- `unitree_sdk2py` for real Go2 control
- `pyrealsense2` for D435i capture in the Python app

## Run Mock Mode

```bash
python -m src.main --config config/app_config.yaml
```

Open:

```text
http://127.0.0.1:8000/
```

The default config uses `robot.mode: mock`, so no robot, SDK, or ROS installation is required.

## Run Go2 Mode In The Existing Python App

Update config for `robot.mode: go2`, set the correct `interface_name`, and start:

```bash
python -m src.main --config config/app_config.go2.enp0s20f0u1c2.yaml
```

If the SDK is missing, startup fails before binding the port.

## Build The ROS 2 Workspace

The ROS layer targets Ubuntu 22.04 + ROS 2 Humble and is documented in [BUILD.md](</D:/Go2Robot/BUILD.md>).

At a high level:

```bash
cd /path/to/Go2Robot/ros_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
export GO2_OPERATOR_APP_ROOT=/path/to/Go2Robot
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

Bringup examples:

```bash
ros2 launch go2_nav_bringup mapping.launch.py robot_mode:=go2 interface_name:=enp0s20f0u1c2 use_realsense:=false require_realsense:=false lidar_mode:=auto
ros2 launch go2_nav_bringup navigation.launch.py robot_mode:=go2 interface_name:=enp0s20f0u1c2 map:=/path/to/site_a_floor_1.yaml use_realsense:=false require_realsense:=false lidar_mode:=auto
```

Optional ROS sensor overrides:

- `lidar_sdk_topic:=<topic_name>` if the built-in Go2 lidar DDS topic is not `utlidar/cloud`
- `lidar_sdk_msg_module:=<module> lidar_sdk_msg_type:=<type>` if the SDK exposes the built-in lidar PointCloud2 type from a different generated module/class
- `lidar_frame:=<frame> lidar_tf_x:=... lidar_tf_y:=... lidar_tf_z:=... lidar_tf_roll:=... lidar_tf_pitch:=... lidar_tf_yaw:=...` to override the static `base_link -> lidar_frame` transform used by SLAM/Nav2
- `use_realsense:=true realsense_publish_pointcloud:=true` to expose the D435i as an auxiliary `/camera/depth/points` source alongside its color and depth topics

## Start A Mission

### Current Python MVP

Use the dashboard or:

```bash
curl -X POST http://127.0.0.1:8000/api/mission/start \
  -H "Content-Type: application/json" \
  -d '{"route_id":"demo_route"}'
```

### ROS 2 coordinate mission

Use:

```text
shared_missions/missions/inspect_line_a.json
```

Through ROS 2, missions are started via the `go2_interfaces/srv/MissionControl` service exposed by `go2_mission`.

## Manual Override Flow

For the current Python app:

1. Take manual mode with the dashboard or `POST /api/mode/manual/take`.
2. Send teleop commands with `POST /api/teleop/cmd`.
3. The running mission pauses immediately.
4. Releasing manual mode does not resume the mission.
5. Resume requires `POST /api/mission/resume`.

## ESTOP Flow

For the current Python app:

1. Trigger `POST /api/mode/estop`.
2. Motion is blocked centrally and the robot is stopped.
3. Reset with `POST /api/mode/reset-estop`.
4. Re-activate posture before moving again:

```bash
curl -X POST http://127.0.0.1:8000/api/robot/activate
```

## Run Folder Layout

```text
runs/mission_<id>/
  mission_meta.json
  event_log.jsonl
  telemetry.jsonl
  images/
  analysis/
  final_report.json
```

The ROS mission layer reuses the same storage/report pipeline through the existing `src.storage` module.

## Tests

Python MVP tests:

```bash
pytest
```

The new ROS workspace was not runtime-tested here because this environment is Windows, not Ubuntu 22.04 + Humble.

## Current Limits

- The Python MVP is still scripted motion, not waypoint localization.
- The ROS layer exists, but full Nav2 runtime validation must happen on Ubuntu 22.04.
- The built-in Go2 lidar path now targets `/points -> /scan`, and the exact remaining SDK uncertainty is limited to the generated PointCloud2 import path inside `go2_bridge/go2_bridge/unitree_lidar.py`.
- `go2_bridge` is the only process that may own the Unitree DDS connection.
