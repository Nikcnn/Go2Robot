from __future__ import annotations

import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2, PointField
from tf2_ros import TransformBroadcaster

from go2_interfaces.srv import CheckpointCapture
from .unitree_lidar import MockLidarSource, UnitreeLidarSource

_LOG = logging.getLogger(__name__)


def _resolve_operator_app_root() -> Path:
    candidates: list[Path] = []
    env_value = os.environ.get("GO2_OPERATOR_APP_ROOT")
    if env_value:
        candidates.append(Path(env_value).expanduser().resolve())

    here = Path(__file__).resolve()
    candidates.extend(parent.resolve() for parent in here.parents)

    for candidate in candidates:
        if (candidate / "src" / "robot" / "robot_adapter.py").exists():
            return candidate

    raise RuntimeError(
        "Unable to locate the existing operator app package under src/. "
        "Set GO2_OPERATOR_APP_ROOT to the Go2Robot repository root "
        "or build the workspace with --symlink-install."
    )


def _load_adapter_factory() -> Callable[..., object]:
    operator_root = _resolve_operator_app_root()
    if str(operator_root) not in sys.path:
        sys.path.insert(0, str(operator_root))
    from src.robot.robot_adapter import build_robot_adapter

    return build_robot_adapter


def _yaw_to_quaternion(yaw: float) -> tuple[float, float, float, float]:
    half_yaw = yaw * 0.5
    return (0.0, 0.0, math.sin(half_yaw), math.cos(half_yaw))


class BaseBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("go2_bridge")

        self.declare_parameter("robot_mode", "mock")
        self.declare_parameter("interface_name", "eth0")
        self.declare_parameter("camera_enabled", False)
        self.declare_parameter("publish_rate_hz", 20.0)
        self.declare_parameter("cmd_vel_topic", "/cmd_vel")
        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("capture_service_name", "capture_checkpoint")
        self.declare_parameter("odom_frame", "odom")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("lidar_enabled", True)
        self.declare_parameter("lidar_mode", "auto")
        self.declare_parameter("lidar_publish_rate_hz", 10.0)
        self.declare_parameter("lidar_points_topic", "/points")
        self.declare_parameter("lidar_frame", "utlidar_lidar")
        self.declare_parameter("sdk_lidar_topic", "utlidar/cloud")
        self.declare_parameter("sdk_lidar_msg_module", "")
        self.declare_parameter("sdk_lidar_msg_type", "")

        robot_mode = self.get_parameter("robot_mode").get_parameter_value().string_value
        interface_name = self.get_parameter("interface_name").get_parameter_value().string_value
        build_robot_adapter = _load_adapter_factory()
        self._adapter = build_robot_adapter(
            mode=robot_mode,
            interface_name=interface_name,
            camera_enabled=self.get_parameter("camera_enabled").get_parameter_value().bool_value,
        )
        self._adapter.connect()

        self._odom_frame = self.get_parameter("odom_frame").get_parameter_value().string_value
        self._base_frame = self.get_parameter("base_frame").get_parameter_value().string_value
        self._last_cmd = Twist()
        self._lidar_source = None
        self._lidar_timer = None
        self._lidar_first_publish_logged = False

        qos = QoSProfile(depth=10)
        cmd_vel_topic = self.get_parameter("cmd_vel_topic").get_parameter_value().string_value
        odom_topic = self.get_parameter("odom_topic").get_parameter_value().string_value
        capture_service_name = self.get_parameter("capture_service_name").get_parameter_value().string_value
        lidar_points_topic = self.get_parameter("lidar_points_topic").get_parameter_value().string_value

        self._odom_pub = self.create_publisher(Odometry, odom_topic, qos)
        self._points_pub = self.create_publisher(PointCloud2, lidar_points_topic, qos_profile_sensor_data)
        self._tf_broadcaster = TransformBroadcaster(self)
        self._cmd_sub = self.create_subscription(Twist, cmd_vel_topic, self._handle_cmd_vel, qos)
        self._capture_service = self.create_service(
            CheckpointCapture,
            capture_service_name,
            self._handle_capture_request,
        )

        publish_rate_hz = self.get_parameter("publish_rate_hz").get_parameter_value().double_value
        timer_period = 1.0 / max(1.0, publish_rate_hz)
        self._publish_timer = self.create_timer(timer_period, self._publish_pose)
        self._configure_lidar_source(robot_mode=robot_mode, interface_name=interface_name)

        self.get_logger().info(
            f"Bridge connected with robot_mode={self.get_parameter('robot_mode').value}, "
            f"cmd_vel_topic={cmd_vel_topic}, odom_topic={odom_topic}."
        )

    def _handle_cmd_vel(self, msg: Twist) -> None:
        self._last_cmd = msg
        result = self._adapter.send_velocity(
            float(msg.linear.x),
            float(msg.linear.y),
            float(msg.angular.z),
        )
        if result not in (None, 0):
            self.get_logger().warning(f"Adapter send_velocity returned code {result}.")

    def _publish_pose(self) -> None:
        pose = self._adapter.get_pose()
        if pose is None:
            return

        stamp = self.get_clock().now().to_msg()
        qx, qy, qz, qw = _yaw_to_quaternion(float(pose.yaw))

        odom_msg = Odometry()
        odom_msg.header.stamp = stamp
        odom_msg.header.frame_id = self._odom_frame
        odom_msg.child_frame_id = self._base_frame
        odom_msg.pose.pose.position.x = float(pose.x)
        odom_msg.pose.pose.position.y = float(pose.y)
        odom_msg.pose.pose.position.z = 0.0
        odom_msg.pose.pose.orientation.x = qx
        odom_msg.pose.pose.orientation.y = qy
        odom_msg.pose.pose.orientation.z = qz
        odom_msg.pose.pose.orientation.w = qw
        odom_msg.twist.twist.linear.x = float(self._last_cmd.linear.x)
        odom_msg.twist.twist.linear.y = float(self._last_cmd.linear.y)
        odom_msg.twist.twist.angular.z = float(self._last_cmd.angular.z)
        self._odom_pub.publish(odom_msg)

        tf_msg = TransformStamped()
        tf_msg.header.stamp = stamp
        tf_msg.header.frame_id = self._odom_frame
        tf_msg.child_frame_id = self._base_frame
        tf_msg.transform.translation.x = float(pose.x)
        tf_msg.transform.translation.y = float(pose.y)
        tf_msg.transform.translation.z = 0.0
        tf_msg.transform.rotation.x = qx
        tf_msg.transform.rotation.y = qy
        tf_msg.transform.rotation.z = qz
        tf_msg.transform.rotation.w = qw
        self._tf_broadcaster.sendTransform(tf_msg)

    def _configure_lidar_source(self, *, robot_mode: str, interface_name: str) -> None:
        if not self.get_parameter("lidar_enabled").get_parameter_value().bool_value:
            self.get_logger().info("Built-in lidar bridge disabled by parameter.")
            return

        lidar_frame = self.get_parameter("lidar_frame").get_parameter_value().string_value
        requested_mode = self.get_parameter("lidar_mode").get_parameter_value().string_value
        resolved_mode = requested_mode
        if requested_mode == "auto":
            resolved_mode = "mock" if robot_mode == "mock" else "sdk"

        if resolved_mode == "mock":
            self._lidar_source = MockLidarSource(frame_id=lidar_frame)
        elif resolved_mode == "sdk":
            sdk_topic = self.get_parameter("sdk_lidar_topic").get_parameter_value().string_value
            sdk_lidar_msg_module = self.get_parameter("sdk_lidar_msg_module").get_parameter_value().string_value
            sdk_lidar_msg_type = self.get_parameter("sdk_lidar_msg_type").get_parameter_value().string_value
            self._lidar_source = UnitreeLidarSource(
                logger=self.get_logger(),
                topic_name=sdk_topic,
                frame_id=lidar_frame,
                message_module=sdk_lidar_msg_module or None,
                message_type=sdk_lidar_msg_type or None,
            )
        else:
            self.get_logger().warning(
                f"Unsupported lidar_mode='{requested_mode}'. Use auto, sdk, or mock."
            )
            return

        started, status = self._lidar_source.start()
        if not started:
            self.get_logger().warning(
                f"Built-in lidar source unavailable in mode={resolved_mode}: {status}. "
                "/points will stay idle and /scan will not publish."
            )
            return

        lidar_publish_rate_hz = self.get_parameter("lidar_publish_rate_hz").get_parameter_value().double_value
        self._lidar_timer = self.create_timer(
            1.0 / max(1.0, lidar_publish_rate_hz),
            self._publish_lidar_points,
        )
        topic = self.get_parameter("lidar_points_topic").get_parameter_value().string_value
        self.get_logger().info(
            f"Built-in lidar source active in mode={resolved_mode}; publishing PointCloud2 on {topic}."
        )

    def _publish_lidar_points(self) -> None:
        if self._lidar_source is None:
            return

        frame = self._lidar_source.get_latest_frame()
        if frame is None or frame.points.size == 0:
            return

        msg = _build_pointcloud2_message(
            points=frame.points,
            stamp=self.get_clock().now().to_msg(),
            frame_id=frame.frame_id,
        )
        self._points_pub.publish(msg)

        if not self._lidar_first_publish_logged:
            topic = self.get_parameter("lidar_points_topic").get_parameter_value().string_value
            self.get_logger().info(
                f"Built-in lidar bridge is publishing {frame.source_name} samples on {topic} "
                f"with frame_id={frame.frame_id}."
            )
            self._lidar_first_publish_logged = True

    def _handle_capture_request(
        self,
        request: CheckpointCapture.Request,
        response: CheckpointCapture.Response,
    ) -> CheckpointCapture.Response:
        try:
            frame = self._adapter.capture_frame()
            robot_state = self._adapter.get_state()
            pose = self._adapter.get_pose()
        except Exception as exc:
            response.success = False
            response.message = f"Bridge capture failed for waypoint {request.waypoint_id}: {exc}"
            response.image_jpeg = []
            response.robot_state_json = ""
            response.pose_json = ""
            return response

        encoded_bytes = b""
        message = f"Checkpoint capture completed for {request.waypoint_id}."
        if frame is None:
            message = f"Checkpoint capture for {request.waypoint_id} returned no image."
        else:
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if ok:
                encoded_bytes = bytes(encoded)
            else:
                message = (
                    f"Checkpoint capture for {request.waypoint_id} returned a frame, "
                    "but JPEG encoding failed."
                )

        response.success = True
        response.message = message
        response.image_jpeg = list(encoded_bytes)
        response.robot_state_json = json.dumps(robot_state.model_dump(mode="json"))
        response.pose_json = "" if pose is None else json.dumps(pose.model_dump(mode="json"))
        return response

    def shutdown(self) -> None:
        if self._lidar_source is not None:
            try:
                self._lidar_source.stop()
            except Exception as exc:
                self.get_logger().warning(f"Built-in lidar shutdown failed: {exc}")

        try:
            self._adapter.stop()
        except Exception as exc:
            self.get_logger().warning(f"Adapter stop during shutdown failed: {exc}")

        try:
            self._adapter.disconnect()
        except Exception as exc:
            self.get_logger().warning(f"Adapter disconnect during shutdown failed: {exc}")


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node: BaseBridgeNode | None = None
    try:
        node = BaseBridgeNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        return
    except Exception as exc:
        _LOG.exception("go2 bridge failed: %s", exc)
        raise
    finally:
        if node is not None:
            node.shutdown()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()


def _build_pointcloud2_message(*, points: np.ndarray, stamp, frame_id: str) -> PointCloud2:
    xyz = np.asarray(points, dtype=np.float32)
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise ValueError(f"Expected points with shape (N, 3), got {xyz.shape}.")

    msg = PointCloud2()
    msg.header.stamp = stamp
    msg.header.frame_id = frame_id
    msg.height = 1
    msg.width = int(xyz.shape[0])
    msg.fields = [
        PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
    ]
    msg.is_bigendian = False
    msg.point_step = 12
    msg.row_step = msg.point_step * msg.width
    msg.is_dense = bool(np.isfinite(xyz).all())
    msg.data = xyz.astype(np.float32, copy=False).tobytes()
    return msg
