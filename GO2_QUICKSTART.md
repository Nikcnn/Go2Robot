# Go2 Quickstart

Use Ubuntu 20.04 and Python 3.8 for deployment. Use ROS 2 Foxy only for the `ros_ws/` path.

## Choose a Path

Use the Python app when you need:

- operator dashboard
- scripted JSON routes from `config/routes/`
- mock mode
- direct Go2 adapter mode
- checkpoint images, telemetry, and reports

Use the ROS 2 path when you need:

- coordinate waypoint missions from `shared_missions/missions/`
- Nav2 `FollowWaypoints`
- mapping or localization through `/scan`
- ROS graph integration

Do not run both paths as SDK owners at the same time in real `go2` mode.

## Python App in Mock Mode

```bash
cd /path/to/Go2Robot
python3.8 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python3 -m src.main --config config/app_config.yaml
```

Open:

```text
http://127.0.0.1:8000/
```

Start a route from the dashboard or by API:

```bash
curl -X POST http://127.0.0.1:8000/api/mission/start \
  -H "Content-Type: application/json" \
  -d '{"route_id":"short_walk_20cm"}'
```

Mock mode uses synthetic pose, telemetry, and camera frames. It does not need Go2 hardware, the Unitree SDK, ROS, or RealSense.

## Python App on Real Go2

Prerequisites:

- Ubuntu 20.04
- Python 3.8 environment with `requirements.txt` installed
- `unitree_sdk2py` installed manually
- robot connected on the configured network interface

Run:

```bash
python3 -m src.main --config config/app_config.go2.enp0s20f0u1c2.yaml
```

If your interface differs, copy the config and change:

```yaml
robot:
  mode: go2
  interface_name: eth0
```

Useful API commands:

```bash
curl -X POST http://127.0.0.1:8000/api/robot/activate
curl -X POST http://127.0.0.1:8000/api/mode/manual/take
curl -X POST http://127.0.0.1:8000/api/mode/manual/release
curl -X POST http://127.0.0.1:8000/api/mode/estop
curl -X POST http://127.0.0.1:8000/api/mode/reset-estop
```

Manual takeover pauses the mission. Manual release does not auto-resume it.

## ROS 2 Foxy Setup

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

## ROS Mapping

```bash
ros2 launch go2_nav_bringup mapping.launch.py \
  robot_mode:=go2 \
  interface_name:=enp0s20f0u1c2 \
  use_lidar:=true \
  lidar_mode:=auto \
  use_realsense:=false \
  require_realsense:=false
```

If the Unitree lidar SDK message type cannot be resolved, pass overrides:

```bash
lidar_sdk_msg_module:=<python_module> lidar_sdk_msg_type:=<message_type>
```

If the physical lidar is not mounted at `base_link`, override:

```bash
lidar_tf_x:=0.0 lidar_tf_y:=0.0 lidar_tf_z:=0.0 \
lidar_tf_roll:=0.0 lidar_tf_pitch:=0.0 lidar_tf_yaw:=0.0
```

## ROS Navigation

```bash
ros2 launch go2_nav_bringup navigation.launch.py \
  robot_mode:=go2 \
  interface_name:=enp0s20f0u1c2 \
  map:=/path/to/Go2Robot/shared_missions/maps/site_a_floor_1.yaml \
  use_lidar:=true \
  lidar_mode:=auto
```

Start a coordinate mission:

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

## Runtime Limits

- Mapping, AMCL, and Nav2 require a real `/scan` source.
- The PointCloud2-to-LaserScan bridge exists, but the real Unitree lidar SDK message path still needs target validation.
- The ROS stack must be runtime-tested on Ubuntu 20.04 with ROS 2 Foxy and the robot connected.
- The Python app remains the fastest hardware-free development path through mock mode.
