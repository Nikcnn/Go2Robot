# ROS 2 Build Notes

This ROS 2 layer targets Ubuntu 22.04 with ROS 2 Humble and is not runtime-verified from this Windows workspace. The generated packages are laid out for `colcon build --symlink-install` so they can import the existing Python operator app under `src/`.

## Apt dependencies

Install the Humble packages exactly as noted:

```bash
sudo apt install ros-humble-navigation2 ros-humble-nav2-bringup
sudo apt install ros-humble-slam-toolbox
sudo apt install \
  ros-humble-nav2-msgs \
  ros-humble-tf2-ros \
  ros-humble-tf2-geometry-msgs \
  ros-humble-cv-bridge \
  ros-humble-image-transport \
  ros-humble-rosbridge-suite \
  ros-humble-map-server \
  ros-humble-amcl \
  ros-humble-rviz2 \
  ros-humble-rmw-cyclonedds-cpp
```

Recommended tooling if it is not already present:

```bash
sudo apt install python3-colcon-common-extensions python3-rosdep
```

## Build

From Ubuntu 22.04:

```bash
cd /path/to/Go2Robot/ros_ws
source /opt/ros/humble/setup.bash
sudo rosdep init || true
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

## Environment

Source in this order for every new shell:

```bash
source /opt/ros/humble/setup.bash
source /path/to/Go2Robot/ros_ws/install/setup.bash
export GO2_OPERATOR_APP_ROOT=/path/to/Go2Robot
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

`GO2_OPERATOR_APP_ROOT` is required when the ROS workspace is launched from an installed path that is not the repo source tree. The launch files also set `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`.

## Launch

Mapping without Nav2:

```bash
ros2 launch go2_nav_bringup mapping.launch.py \
  robot_mode:=go2 \
  interface_name:=enp0s31f6 \
  use_realsense:=false \
  require_realsense:=false \
  lidar_mode:=auto
```

Navigation with Nav2 + mission service:

```bash
ros2 launch go2_nav_bringup navigation.launch.py \
  robot_mode:=go2 \
  interface_name:=enp0s31f6 \
  map:=/path/to/shared_missions/maps/site_a_floor_1.yaml \
  use_realsense:=false \
  require_realsense:=false \
  lidar_mode:=auto
```

If your installed `unitree_sdk2py` exposes the built-in lidar on a different DDS topic than `utlidar/cloud`, override it at launch time with `lidar_sdk_topic:=<topic_name>`.

If the SDK-generated PointCloud2 type is exposed from a different module or class name on Ubuntu, override that narrow uncertainty without touching the rest of the bridge:

```bash
lidar_sdk_msg_module:=unitree_sdk2py.idl.sensor_msgs.msg.dds_ lidar_sdk_msg_type:=PointCloud2_
```

If you want the D435i to publish an auxiliary ROS point cloud in addition to color and depth images, add:

```bash
use_realsense:=true realsense_publish_pointcloud:=true
```

Both launch files now also publish a static `base_link -> utlidar_lidar` transform. Override `lidar_frame` and the `lidar_tf_x/y/z/roll/pitch/yaw` arguments once you measure the real sensor extrinsics on Ubuntu + the robot.

For mock end-to-end bringup, set `robot_mode:=mock`.

## Notes

- `go2_bridge` is the only process that touches `unitreesdk2py` and the DDS `ChannelFactory` singleton.
- Built-in Go2 lidar is now wired as the primary ROS navigation sensor path: `base_bridge` publishes `/points` and `lidar_bridge` converts that PointCloud2 stream into `/scan`.
- Optional D435i ROS topics come from `go2_bridge/camera_bridge.py`: `/camera/color/image_raw`, `/camera/depth/image_rect_raw`, camera info topics, and `/camera/depth/points` when `realsense_publish_pointcloud:=true`.
- The exact built-in lidar SDK message import path is still the narrow remaining uncertainty inside `go2_bridge/go2_bridge/unitree_lidar.py`.
- `go2_mission` uses `nav2_msgs/action/FollowWaypoints` and writes reports through the existing `src.storage.StorageManager`.
- `go2_mission` checkpoint tasks call the bridge capture service so `capture_frame()` and `get_state()` stay in the bridge process.
