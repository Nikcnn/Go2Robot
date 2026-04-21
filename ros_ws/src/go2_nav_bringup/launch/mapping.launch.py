from __future__ import annotations

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _guess_operator_app_root() -> str:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "src" / "storage.py").exists():
            return str(parent)
    return str(here.parents[-1])


def generate_launch_description() -> LaunchDescription:
    bringup_share = get_package_share_directory("go2_nav_bringup")
    default_operator_root = os.environ.get("GO2_OPERATOR_APP_ROOT", _guess_operator_app_root())
    default_rviz = os.path.join(bringup_share, "rviz", "go2_nav.rviz")

    robot_mode = LaunchConfiguration("robot_mode")
    interface_name = LaunchConfiguration("interface_name")
    camera_enabled = LaunchConfiguration("camera_enabled")
    use_lidar = LaunchConfiguration("use_lidar")
    lidar_mode = LaunchConfiguration("lidar_mode")
    lidar_frame = LaunchConfiguration("lidar_frame")
    lidar_tf_x = LaunchConfiguration("lidar_tf_x")
    lidar_tf_y = LaunchConfiguration("lidar_tf_y")
    lidar_tf_z = LaunchConfiguration("lidar_tf_z")
    lidar_tf_roll = LaunchConfiguration("lidar_tf_roll")
    lidar_tf_pitch = LaunchConfiguration("lidar_tf_pitch")
    lidar_tf_yaw = LaunchConfiguration("lidar_tf_yaw")
    use_realsense = LaunchConfiguration("use_realsense")
    require_realsense = LaunchConfiguration("require_realsense")
    realsense_publish_pointcloud = LaunchConfiguration("realsense_publish_pointcloud")
    lidar_sdk_topic = LaunchConfiguration("lidar_sdk_topic")
    lidar_sdk_msg_module = LaunchConfiguration("lidar_sdk_msg_module")
    lidar_sdk_msg_type = LaunchConfiguration("lidar_sdk_msg_type")
    use_camera_bridge = LaunchConfiguration("use_camera_bridge")
    use_rviz = LaunchConfiguration("use_rviz")
    operator_app_root = LaunchConfiguration("operator_app_root")
    rviz_config = LaunchConfiguration("rviz_config")
    realsense_condition = PythonExpression(
        ["('", use_realsense, "' == 'true') or ('", use_camera_bridge, "' == 'true')"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_mode", default_value="go2"),
            DeclareLaunchArgument("interface_name", default_value="eth0"),
            DeclareLaunchArgument("camera_enabled", default_value="false"),
            DeclareLaunchArgument("use_lidar", default_value="true"),
            DeclareLaunchArgument("lidar_mode", default_value="auto"),
            DeclareLaunchArgument("lidar_frame", default_value="utlidar_lidar"),
            DeclareLaunchArgument("lidar_tf_x", default_value="0.0"),
            DeclareLaunchArgument("lidar_tf_y", default_value="0.0"),
            DeclareLaunchArgument("lidar_tf_z", default_value="0.0"),
            DeclareLaunchArgument("lidar_tf_roll", default_value="0.0"),
            DeclareLaunchArgument("lidar_tf_pitch", default_value="0.0"),
            DeclareLaunchArgument("lidar_tf_yaw", default_value="0.0"),
            DeclareLaunchArgument("use_realsense", default_value="false"),
            DeclareLaunchArgument("require_realsense", default_value="false"),
            DeclareLaunchArgument("realsense_publish_pointcloud", default_value="false"),
            DeclareLaunchArgument("lidar_sdk_topic", default_value="utlidar/cloud"),
            DeclareLaunchArgument("lidar_sdk_msg_module", default_value=""),
            DeclareLaunchArgument("lidar_sdk_msg_type", default_value=""),
            DeclareLaunchArgument("use_camera_bridge", default_value="false"),
            DeclareLaunchArgument("use_rviz", default_value="true"),
            DeclareLaunchArgument("operator_app_root", default_value=default_operator_root),
            DeclareLaunchArgument("rviz_config", default_value=default_rviz),
            SetEnvironmentVariable("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp"),
            SetEnvironmentVariable("GO2_OPERATOR_APP_ROOT", operator_app_root),
            Node(
                package="go2_bridge",
                executable="base_bridge",
                name="go2_bridge",
                output="screen",
                parameters=[
                    {
                        "robot_mode": robot_mode,
                        "interface_name": interface_name,
                        "camera_enabled": ParameterValue(camera_enabled, value_type=bool),
                        "publish_rate_hz": 20.0,
                        "cmd_vel_topic": "/cmd_vel",
                        "odom_topic": "/odom",
                        "odom_frame": "odom",
                        "base_frame": "base_link",
                        "capture_service_name": "capture_checkpoint",
                        "lidar_enabled": ParameterValue(use_lidar, value_type=bool),
                        "lidar_mode": lidar_mode,
                        "lidar_points_topic": "/points",
                        "lidar_frame": lidar_frame,
                        "sdk_lidar_topic": lidar_sdk_topic,
                        "sdk_lidar_msg_module": lidar_sdk_msg_module,
                        "sdk_lidar_msg_type": lidar_sdk_msg_type,
                    }
                ],
            ),
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                name="go2_lidar_static_tf",
                output="screen",
                condition=IfCondition(use_lidar),
                arguments=[
                    "--x", lidar_tf_x,
                    "--y", lidar_tf_y,
                    "--z", lidar_tf_z,
                    "--roll", lidar_tf_roll,
                    "--pitch", lidar_tf_pitch,
                    "--yaw", lidar_tf_yaw,
                    "--frame-id", "base_link",
                    "--child-frame-id", lidar_frame,
                ],
            ),
            Node(
                package="go2_bridge",
                executable="lidar_bridge",
                name="go2_lidar_bridge",
                output="screen",
                condition=IfCondition(use_lidar),
                parameters=[
                    {
                        "input_points_topic": "/points",
                        "output_scan_topic": "/scan",
                        "min_height": -0.20,
                        "max_height": 0.20,
                        "range_min": 0.10,
                        "range_max": 12.0,
                    }
                ],
            ),
            Node(
                package="go2_bridge",
                executable="camera_bridge",
                name="realsense_camera_bridge",
                output="screen",
                condition=IfCondition(realsense_condition),
                parameters=[
                    {
                        "width": 640,
                        "height": 480,
                        "fps": 15,
                        "enable_color": True,
                        "enable_depth": True,
                        "required": ParameterValue(require_realsense, value_type=bool),
                        "publish_camera_info": True,
                        "publish_point_cloud": ParameterValue(realsense_publish_pointcloud, value_type=bool),
                    }
                ],
            ),
            Node(
                package="slam_toolbox",
                executable="sync_slam_toolbox_node",
                name="slam_toolbox",
                output="screen",
                parameters=[
                    {
                        "use_sim_time": False,
                        "odom_frame": "odom",
                        "map_frame": "map",
                        "base_frame": "base_link",
                        "scan_topic": "/scan",
                        "mode": "mapping",
                        "resolution": 0.05,
                        "map_update_interval": 2.0,
                        "transform_publish_period": 0.02,
                        "max_laser_range": 20.0,
                    }
                ],
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                output="screen",
                condition=IfCondition(use_rviz),
                arguments=["-d", rviz_config],
            ),
        ]
    )
