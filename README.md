# Go2 Inspection System

This repository contains a safe test-environment inspection stack for a Unitree Go2 robot.
It has two supported execution paths:

- `src/`: standalone Python 3.8 application with FastAPI, a vanilla browser dashboard, scripted JSON routes, telemetry, camera streaming, storage, reporting, mock mode, and direct Go2 adapter support.
- `ros_ws/`: ROS 2 Foxy workspace for Ubuntu 20.04 with `go2_bridge`, `go2_mission`, `go2_interfaces`, and Nav2 bringup for coordinate waypoint missions.

The Python app can run without ROS. The ROS layer requires Ubuntu 20.04, ROS 2 Foxy, Python 3.8, and `rmw_cyclonedds_cpp`.

## Repository Layout

```text
src/                  Python application layer and dashboard
src/robot/            Mock and Go2 robot adapter boundary
src/sensors/          Optional RealSense support for the Python app
src/web/              Static dashboard HTML, CSS, and JavaScript
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

- Ubuntu 20.04 for real deployment and ROS 2 work.
- Python 3.8 for both the Python app and ROS Python nodes.
- ROS 2 Foxy for `ros_ws/`.
- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` when touching the Unitree SDK.

Windows is used here as a workspace, but ROS 2 Foxy and Nav2 runtime behavior must be validated on Ubuntu 20.04.

## Python App Quick Start

Create a Python 3.8 environment and install the app dependencies:

```bash
python3.8 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the mock app:

```bash
python3 -m src.main --config config/app_config.yaml
```

Open:

```text
http://127.0.0.1:8000/
```

The default config uses `robot.mode: mock`, so it does not need a real robot, Unitree SDK, ROS, or RealSense camera.

## Real Go2 Python App

Install `unitree_sdk2py` manually in the same Python 3.8 environment. It is intentionally not pinned in `requirements.txt` because installation depends on the Unitree SDK package source and target machine.

Then run a Go2 config with the correct network interface:

```bash
python3 -m src.main --config config/app_config.go2.enp0s20f0u1c2.yaml
```

Do not run this at the same time as `go2_bridge` in `robot_mode:=go2`. The Unitree DDS `ChannelFactory` is treated as a process singleton.

## ROS 2 Foxy Quick Start

On Ubuntu 20.04:

```bash
cd /path/to/Go2Robot/ros_ws
source /opt/ros/foxy/setup.bash
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
  use_lidar:=true \
  lidar_mode:=auto
```

Navigation bringup:

```bash
ros2 launch go2_nav_bringup navigation.launch.py \
  robot_mode:=go2 \
  interface_name:=enp0s20f0u1c2 \
  map:=/path/to/Go2Robot/shared_missions/maps/site_a_floor_1.yaml \
  use_lidar:=true \
  lidar_mode:=auto
```

The ROS lidar code is present: `base_bridge` publishes `/points`, and `lidar_bridge` converts PointCloud2 to `/scan`. The exact Unitree built-in lidar SDK message import path still needs target validation on Ubuntu 20.04 with the robot connected. Mapping, AMCL, and Nav2 require a live and correct `/scan`.

## Missions

The Python app uses scripted route files in `config/routes/`. Supported route steps include:

- `move`
- `move_velocity`
- `rotate`
- `checkpoint`
- `stop`
- `stand_up`
- `wait`
- `settle`

The ROS layer uses coordinate waypoint missions in `shared_missions/missions/`, for example `inspect_line_a.json`. Those missions are sent to Nav2 through `FollowWaypoints`.

## Safety Rules

- Control priority is always `ESTOP > MANUAL > AUTO`.
- Manual takeover pauses an active mission.
- Manual release does not auto-resume a mission.
- Keep one active motion controller at a time.
- Keep all uncertain Unitree SDK work inside the adapter or `go2_bridge`.
- Mock mode must stay end-to-end runnable without hardware.

## Tests

Run hardware-free Python tests:

```bash
pytest
```

ROS package build and runtime checks must be run on Ubuntu 20.04 with ROS 2 Foxy.

## More Docs

- [BUILD.md](BUILD.md): dependency, build, and launch details.
- [GO2_QUICKSTART.md](GO2_QUICKSTART.md): short operator workflow.
- [ARCHITECTURE.MD](ARCHITECTURE.MD): current architecture and boundaries.
- [GO2_MVP_TECHNOLOGY_RU.md](GO2_MVP_TECHNOLOGY_RU.md): Russian technical overview.
