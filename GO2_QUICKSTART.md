# Go2 Quickstart

This repo now has two runnable paths:

- Python MVP only: FastAPI + dashboard + scripted motion in `src/`
- ROS 2 stack: `ros_ws/` with `go2_bridge`, `go2_mission`, and `go2_nav_bringup`

Use the Python path when you want the existing dashboard and scripted routes. Use the ROS 2 path only on Ubuntu 22.04 with ROS 2 Humble.

## 1. Python MVP on the real robot

Use this when the robot is already connected by LAN on `enp0s20f0u1c2` and you want the existing operator dashboard plus the current scripted route executor.

Install Python deps:

```bash
cd /home/nikcnn/Go2Robot/Go2_MVP
pip install -r requirements.txt
```

If `unitree_sdk2py` is not installed yet, install it first. The server fails fast if the SDK is missing in `go2` mode.

Start the server:

```bash
python -m src.main --config config/app_config.go2.enp0s20f0u1c2.yaml
```

Open:

```text
http://127.0.0.1:8000/
```

The dashboard shows:

- live robot camera frames
- battery percent, voltage/current, and cycle count
- fault text derived from `rt/sportmodestate` and `rt/lowstate`

Run the short scripted route:

```text
short_walk_20cm
```

Or by API:

```bash
curl -X POST http://127.0.0.1:8000/api/mission/start \
  -H "Content-Type: application/json" \
  -d '{"route_id":"short_walk_20cm"}'
```

Manual/ESTOP reminders:

- Manual takeover uses a posture-preserving stop and pauses the mission.
- Manual release does not auto-resume the mission.
- `ESTOP` uses passive damping. After reset, activate the robot before moving again:

```bash
curl -X POST http://127.0.0.1:8000/api/robot/activate
```

## 2. ROS 2 Humble stack

Use this path for the new architecture:

```text
web/FastAPI -> ROS 2 mission service -> Nav2 -> go2_bridge -> unitreesdk2py -> robot
```

Platform requirements:

- Ubuntu 22.04
- ROS 2 Humble
- Python 3.10
- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`

Build instructions are in [BUILD.md](</D:/Go2Robot/BUILD.md>).

Typical sequence:

```bash
cd /path/to/Go2Robot/ros_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
export GO2_OPERATOR_APP_ROOT=/path/to/Go2Robot
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

Mapping bringup:

```bash
ros2 launch go2_nav_bringup mapping.launch.py \
  robot_mode:=go2 \
  interface_name:=enp0s20f0u1c2 \
  use_realsense:=false \
  require_realsense:=false \
  lidar_mode:=auto
```

Navigation bringup:

```bash
ros2 launch go2_nav_bringup navigation.launch.py \
  robot_mode:=go2 \
  interface_name:=enp0s20f0u1c2 \
  map:=/path/to/shared_missions/maps/site_a_floor_1.yaml \
  use_realsense:=false \
  require_realsense:=false \
  lidar_mode:=auto
```

If the built-in lidar DDS topic on your robot is not `utlidar/cloud`, add `lidar_sdk_topic:=<topic_name>` to either launch command. If the SDK-generated PointCloud2 message import path differs on Ubuntu, add `lidar_sdk_msg_module:=<module> lidar_sdk_msg_type:=<type>` as well.

To expose the D435i as an auxiliary ROS point cloud source in addition to color/depth images, add `use_realsense:=true realsense_publish_pointcloud:=true`.

The launch files now publish a static `base_link -> utlidar_lidar` transform. If the physical lidar mount is not at the base origin, override `lidar_tf_x`, `lidar_tf_y`, `lidar_tf_z`, `lidar_tf_roll`, `lidar_tf_pitch`, and `lidar_tf_yaw`.

Mission file example:

```text
shared_missions/missions/inspect_line_a.json
```

Important limitation:

- `go2_bridge` is the only process allowed to touch `unitreesdk2py` because `ChannelFactory` is a process singleton.
- Built-in Go2 lidar is now intended to be the primary navigation sensor path. `base_bridge` publishes `/points` and `lidar_bridge` converts it to `/scan` for SLAM, AMCL, and Nav2.
- Optional D435i ROS topics come from `camera_bridge`: `/camera/color/image_raw`, `/camera/depth/image_rect_raw`, and `/camera/depth/points` when `realsense_publish_pointcloud:=true`.
- The exact built-in lidar SDK message import path still has to be validated on Ubuntu 22.04 + ROS 2 Humble with the robot connected.
- The ROS stack was generated from this Windows workspace but not runtime-validated here; validate on Ubuntu 22.04 + Humble.
