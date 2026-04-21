from __future__ import annotations

import logging

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, PointCloud2, PointField

try:
    from cv_bridge import CvBridge
except ImportError:
    CvBridge = None

try:
    import numpy as np
    import pyrealsense2 as rs
except ImportError:
    np = None
    rs = None

from .pointcloud_utils import depth_image_to_points

_LOG = logging.getLogger(__name__)


class RealSenseCameraBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("realsense_camera_bridge")

        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("fps", 15)
        self.declare_parameter("enable_color", True)
        self.declare_parameter("enable_depth", True)
        self.declare_parameter("required", False)
        self.declare_parameter("retry_period_sec", 5.0)
        self.declare_parameter("publish_camera_info", True)
        self.declare_parameter("color_topic", "/camera/color/image_raw")
        self.declare_parameter("depth_topic", "/camera/depth/image_rect_raw")
        self.declare_parameter("color_info_topic", "/camera/color/camera_info")
        self.declare_parameter("depth_info_topic", "/camera/depth/camera_info")
        self.declare_parameter("publish_point_cloud", False)
        self.declare_parameter("pointcloud_topic", "/camera/depth/points")
        self.declare_parameter("pointcloud_stride", 4)
        self.declare_parameter("pointcloud_min_depth_m", 0.10)
        self.declare_parameter("pointcloud_max_depth_m", 10.0)
        self.declare_parameter("color_frame_id", "camera_color_optical_frame")
        self.declare_parameter("depth_frame_id", "camera_depth_optical_frame")

        self._bridge = CvBridge() if CvBridge is not None else None
        self._pipeline = None
        self._config = None
        self._started = False
        self._warned_unavailable = False
        self._status = "not_started"
        self._color_intrinsics = None
        self._depth_intrinsics = None
        self._depth_scale = 0.001
        self._first_color_logged = False
        self._first_depth_logged = False
        self._first_points_logged = False

        width = int(self.get_parameter("width").value)
        height = int(self.get_parameter("height").value)
        fps = int(self.get_parameter("fps").value)
        self._enable_color = bool(self.get_parameter("enable_color").value)
        self._enable_depth = bool(self.get_parameter("enable_depth").value)
        self._required = bool(self.get_parameter("required").value)
        self._publish_camera_info = bool(self.get_parameter("publish_camera_info").value)
        self._publish_point_cloud = bool(self.get_parameter("publish_point_cloud").value)
        self._pointcloud_stride = int(self.get_parameter("pointcloud_stride").value)
        self._pointcloud_min_depth_m = float(self.get_parameter("pointcloud_min_depth_m").value)
        self._pointcloud_max_depth_m = float(self.get_parameter("pointcloud_max_depth_m").value)
        self._color_frame_id = str(self.get_parameter("color_frame_id").value)
        self._depth_frame_id = str(self.get_parameter("depth_frame_id").value)

        if not self._enable_color and not self._enable_depth:
            raise RuntimeError("At least one of enable_color or enable_depth must be true.")
        if self._publish_point_cloud and not self._enable_depth:
            raise RuntimeError("publish_point_cloud requires enable_depth=true.")

        self._color_pub = self.create_publisher(
            Image,
            self.get_parameter("color_topic").get_parameter_value().string_value,
            qos_profile_sensor_data,
        )
        self._depth_pub = self.create_publisher(
            Image,
            self.get_parameter("depth_topic").get_parameter_value().string_value,
            qos_profile_sensor_data,
        )
        self._color_info_pub = self.create_publisher(
            CameraInfo,
            self.get_parameter("color_info_topic").get_parameter_value().string_value,
            qos_profile_sensor_data,
        )
        self._depth_info_pub = self.create_publisher(
            CameraInfo,
            self.get_parameter("depth_info_topic").get_parameter_value().string_value,
            qos_profile_sensor_data,
        )
        self._pointcloud_pub = self.create_publisher(
            PointCloud2,
            self.get_parameter("pointcloud_topic").get_parameter_value().string_value,
            qos_profile_sensor_data,
        )
        self._timer = self.create_timer(1.0 / max(1, fps), self._publish_frames)
        retry_period = float(self.get_parameter("retry_period_sec").value)
        self._retry_timer = self.create_timer(max(1.0, retry_period), self._ensure_pipeline)

        self._width = width
        self._height = height
        self._fps = fps
        self._ensure_pipeline()
        self.get_logger().info("RealSense camera bridge started.")

    def _ensure_pipeline(self) -> None:
        if self._started:
            return

        if CvBridge is None or rs is None or np is None:
            message = "cv_bridge, pyrealsense2, and numpy are required for go2_bridge.camera_bridge."
            if self._required:
                raise RuntimeError(message)
            if not self._warned_unavailable:
                self.get_logger().warning(f"RealSense unavailable: {message}")
                self._warned_unavailable = True
            self._status = message
            return

        try:
            context = rs.context()
            devices = context.query_devices()
            if _device_count(devices) == 0:
                raise RuntimeError("No Intel RealSense device detected.")

            self._pipeline = rs.pipeline()
            self._config = rs.config()
            if self._enable_color:
                self._config.enable_stream(rs.stream.color, self._width, self._height, rs.format.bgr8, self._fps)
            if self._enable_depth:
                self._config.enable_stream(rs.stream.depth, self._width, self._height, rs.format.z16, self._fps)

            profile = self._pipeline.start(self._config)
            self._capture_intrinsics(profile)
            self._depth_scale = _get_depth_scale(profile)
            self._started = True
            self._warned_unavailable = False
            self._status = "streaming"
            self.get_logger().info(
                "RealSense D435i connected and streaming. "
                f"color={self._enable_color} depth={self._enable_depth} "
                f"pointcloud={self._publish_point_cloud}."
            )
        except Exception as exc:
            if self._pipeline is not None:
                try:
                    self._pipeline.stop()
                except Exception:
                    pass
            self._pipeline = None
            self._config = None
            self._started = False
            self._status = str(exc)
            if self._required:
                raise RuntimeError(f"Required RealSense device is unavailable: {exc}") from exc
            if not self._warned_unavailable:
                self.get_logger().warning(f"RealSense unavailable: {exc}")
                self._warned_unavailable = True

    def _publish_frames(self) -> None:
        if not self._started or self._pipeline is None or self._bridge is None:
            return

        frames = self._pipeline.poll_for_frames()
        if not frames:
            return

        stamp = self.get_clock().now().to_msg()

        if self._enable_color:
            color_frame = frames.get_color_frame()
            if color_frame:
                color_image = np.asanyarray(color_frame.get_data())
                color_msg = self._bridge.cv2_to_imgmsg(color_image, encoding="bgr8")
                color_msg.header.stamp = stamp
                color_msg.header.frame_id = self._color_frame_id
                self._color_pub.publish(color_msg)
                if self._publish_camera_info and self._color_intrinsics is not None:
                    self._color_info_pub.publish(
                        _build_camera_info(
                            stamp=stamp,
                            frame_id=self._color_frame_id,
                            intrinsics=self._color_intrinsics,
                        )
                    )
                if not self._first_color_logged:
                    self.get_logger().info(
                        f"RealSense color images are publishing on "
                        f"{self.get_parameter('color_topic').value}."
                    )
                    self._first_color_logged = True

        if self._enable_depth:
            depth_frame = frames.get_depth_frame()
            if depth_frame:
                depth_image = np.asanyarray(depth_frame.get_data())
                depth_msg = self._bridge.cv2_to_imgmsg(depth_image, encoding="16UC1")
                depth_msg.header.stamp = stamp
                depth_msg.header.frame_id = self._depth_frame_id
                self._depth_pub.publish(depth_msg)
                if self._publish_camera_info and self._depth_intrinsics is not None:
                    self._depth_info_pub.publish(
                        _build_camera_info(
                            stamp=stamp,
                            frame_id=self._depth_frame_id,
                            intrinsics=self._depth_intrinsics,
                        )
                    )
                if not self._first_depth_logged:
                    self.get_logger().info(
                        f"RealSense depth images are publishing on "
                        f"{self.get_parameter('depth_topic').value}."
                    )
                    self._first_depth_logged = True
                if self._publish_point_cloud and self._depth_intrinsics is not None:
                    points = depth_image_to_points(
                        depth_image,
                        fx=float(self._depth_intrinsics.fx),
                        fy=float(self._depth_intrinsics.fy),
                        cx=float(self._depth_intrinsics.ppx),
                        cy=float(self._depth_intrinsics.ppy),
                        depth_scale=_frame_depth_scale(depth_frame, default=self._depth_scale),
                        stride=self._pointcloud_stride,
                        min_depth=self._pointcloud_min_depth_m,
                        max_depth=self._pointcloud_max_depth_m,
                    )
                    if points.size > 0:
                        points_msg = _build_xyz_pointcloud2_message(
                            stamp=stamp,
                            frame_id=self._depth_frame_id,
                            points=points,
                        )
                        self._pointcloud_pub.publish(points_msg)
                        if not self._first_points_logged:
                            self.get_logger().info(
                                f"RealSense auxiliary point cloud is publishing on "
                                f"{self.get_parameter('pointcloud_topic').value}."
                            )
                            self._first_points_logged = True

    def _capture_intrinsics(self, profile) -> None:
        if self._enable_color:
            color_profile = profile.get_stream(rs.stream.color).as_video_stream_profile()
            self._color_intrinsics = color_profile.get_intrinsics()
        if self._enable_depth:
            depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
            self._depth_intrinsics = depth_profile.get_intrinsics()

    def shutdown(self) -> None:
        if self._started:
            try:
                if self._pipeline is not None:
                    self._pipeline.stop()
            except Exception as exc:
                self.get_logger().warning(f"RealSense pipeline stop failed: {exc}")
            self._started = False


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node: RealSenseCameraBridgeNode | None = None
    try:
        node = RealSenseCameraBridgeNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        return
    except Exception as exc:
        _LOG.exception("camera bridge failed: %s", exc)
        raise
    finally:
        if node is not None:
            node.shutdown()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()


def _build_camera_info(*, stamp, frame_id: str, intrinsics) -> CameraInfo:
    msg = CameraInfo()
    msg.header.stamp = stamp
    msg.header.frame_id = frame_id
    msg.width = int(intrinsics.width)
    msg.height = int(intrinsics.height)
    msg.distortion_model = "plumb_bob"
    msg.d = list(intrinsics.coeffs[:5])
    msg.k = [
        float(intrinsics.fx), 0.0, float(intrinsics.ppx),
        0.0, float(intrinsics.fy), float(intrinsics.ppy),
        0.0, 0.0, 1.0,
    ]
    msg.r = [
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0.0, 0.0, 1.0,
    ]
    msg.p = [
        float(intrinsics.fx), 0.0, float(intrinsics.ppx), 0.0,
        0.0, float(intrinsics.fy), float(intrinsics.ppy), 0.0,
        0.0, 0.0, 1.0, 0.0,
    ]
    return msg


def _device_count(devices) -> int:
    try:
        return len(devices)
    except TypeError:
        if hasattr(devices, "size"):
            return int(devices.size())
        raise


def _get_depth_scale(profile) -> float:
    try:
        return float(profile.get_device().first_depth_sensor().get_depth_scale())
    except Exception:
        return 0.001


def _frame_depth_scale(depth_frame, *, default: float) -> float:
    try:
        return float(depth_frame.get_units())
    except Exception:
        return float(default)


def _build_xyz_pointcloud2_message(*, stamp, frame_id: str, points) -> PointCloud2:
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
