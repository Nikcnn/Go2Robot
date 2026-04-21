# Build and Environment Setup

This project targets Ubuntu 20.04, Python 3.8, and ROS 2 Foxy.

There are two build paths:

- Python app only: install `requirements.txt` and run `src.main`.
- ROS 2 layer: build `ros_ws/` with Foxy and source the install workspace.

## Python 3.8 App Setup

Use this path for the FastAPI app, browser dashboard, mock mode, scripted routes, direct Go2 adapter mode, storage, and reports.

```bash
cd /path/to/Go2Robot
python3.8 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run mock mode:

```bash
python3 -m src.main --config config/app_config.yaml
```

Run real Go2 mode after installing `unitree_sdk2py` manually:

```bash
python3 -m src.main --config config/app_config.go2.enp0s20f0u1c2.yaml
```

Optional hardware packages:

- `unitree_sdk2py`: required only for real Go2 mode.
- `pyrealsense2`: required only when RealSense support is enabled.

## ROS 2 Foxy System Packages

Install ROS 2 Foxy on Ubuntu 20.04 first. Then install the packages used by the workspace:

```bash
sudo apt update
sudo apt install \
  python3-colcon-common-extensions \
  python3-rosdep \
  ros-foxy-ament-cmake \
  ros-foxy-ament-python \
  ros-foxy-navigation2 \
  ros-foxy-nav2-bringup \
  ros-foxy-nav2-msgs \
  ros-foxy-slam-toolbox \
  ros-foxy-tf2-ros \
  ros-foxy-cv-bridge \
  ros-foxy-image-transport \
  ros-foxy-rmw-cyclonedds-cpp \
  ros-foxy-rviz2
```

Initialize rosdep if the machine has not done it before:

```bash
sudo rosdep init
rosdep update
```

## ROS 2 Workspace Build

```bash
cd /path/to/Go2Robot/ros_ws
source /opt/ros/foxy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

Source the workspace in every new ROS shell:

```bash
source /opt/ros/foxy/setup.bash
source /path/to/Go2Robot/ros_ws/install/setup.bash
export GO2_OPERATOR_APP_ROOT=/path/to/Go2Robot
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

`GO2_OPERATOR_APP_ROOT` lets ROS nodes import the existing Python app storage and adapter modules.

## ROS Packages

```text
go2_interfaces    Custom CheckpointCapture and MissionControl services
go2_bridge        /cmd_vel to adapter bridge, /odom, /tf, checkpoint capture, lidar, camera
go2_mission       Mission service and Nav2 FollowWaypoints client
go2_nav_bringup   Mapping and navigation launch files, Nav2 params, RViz config
```

## Mapping Launch

Mapping starts:

- `go2_bridge/base_bridge`
- static `base_link -> utlidar_lidar` transform
- `go2_bridge/lidar_bridge`
- optional `go2_bridge/camera_bridge`
- `slam_toolbox`
- optional RViz

```bash
ros2 launch go2_nav_bringup mapping.launch.py \
  robot_mode:=go2 \
  interface_name:=enp0s20f0u1c2 \
  use_lidar:=true \
  lidar_mode:=auto \
  use_realsense:=false \
  require_realsense:=false
```

Useful launch arguments:

```text
robot_mode                  mock or go2
interface_name              Unitree SDK network interface
camera_enabled              enables robot camera in the adapter
use_lidar                   starts /points and /scan bridge path
lidar_mode                  auto, sdk, or mock
lidar_sdk_topic             Unitree DDS lidar topic, default utlidar/cloud
lidar_sdk_msg_module        override SDK PointCloud2 message module
lidar_sdk_msg_type          override SDK PointCloud2 message type
use_realsense               start optional RealSense ROS bridge
require_realsense           fail if RealSense is unavailable
realsense_publish_pointcloud publish /camera/depth/points
use_rviz                    start RViz
```

## Navigation Launch

Navigation starts the bridge, `/scan`, AMCL, map server, Nav2 servers, waypoint follower, mission API node, and optional RViz.

```bash
ros2 launch go2_nav_bringup navigation.launch.py \
  robot_mode:=go2 \
  interface_name:=enp0s20f0u1c2 \
  map:=/path/to/Go2Robot/shared_missions/maps/site_a_floor_1.yaml \
  use_lidar:=true \
  lidar_mode:=auto
```

Send a mission through the ROS service after the launch is ready:

```bash
ros2 service call /go2_mission/command go2_interfaces/srv/MissionControl \
  "{command: start, mission_path: /path/to/Go2Robot/shared_missions/missions/inspect_line_a.json, mission_json: ''}"
```

Check status:

```bash
ros2 service call /go2_mission/command go2_interfaces/srv/MissionControl \
  "{command: status, mission_path: '', mission_json: ''}"
```

Cancel:

```bash
ros2 service call /go2_mission/command go2_interfaces/srv/MissionControl \
  "{command: cancel, mission_path: '', mission_json: ''}"
```

## Process Boundary Rules

- Do not run the Python app in `go2` mode and `go2_bridge` in `go2` mode at the same time.
- Only one process may own the Unitree SDK DDS `ChannelFactory`.
- Use `rmw_cyclonedds_cpp` for SDK-facing ROS processes.
- Keep mapping and Nav2 claims tied to a verified live `/scan`.

## Validation

From this Windows workspace, only static file edits and hardware-free tests can be run. Full ROS 2 Foxy build, Nav2 launch, Unitree SDK connection, lidar stream, and RealSense runtime behavior must be validated on Ubuntu 20.04.
