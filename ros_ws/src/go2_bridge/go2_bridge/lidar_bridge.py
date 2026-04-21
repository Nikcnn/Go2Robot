from __future__ import annotations

import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, PointCloud2

from .pointcloud_utils import PointCloudFieldSpec, extract_xyz_points, project_points_to_scan


class LidarBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("go2_lidar_bridge")

        self.declare_parameter("input_points_topic", "/points")
        self.declare_parameter("output_scan_topic", "/scan")
        self.declare_parameter("angle_min", -math.pi)
        self.declare_parameter("angle_max", math.pi)
        self.declare_parameter("angle_increment", math.radians(1.0))
        self.declare_parameter("range_min", 0.10)
        self.declare_parameter("range_max", 12.0)
        self.declare_parameter("min_height", -0.20)
        self.declare_parameter("max_height", 0.20)
        self.declare_parameter("scan_time", 0.1)
        self.declare_parameter("diagnostic_stale_after_sec", 5.0)

        input_points_topic = self.get_parameter("input_points_topic").get_parameter_value().string_value
        output_scan_topic = self.get_parameter("output_scan_topic").get_parameter_value().string_value

        self._scan_pub = self.create_publisher(LaserScan, output_scan_topic, qos_profile_sensor_data)
        self._points_sub = self.create_subscription(
            PointCloud2,
            input_points_topic,
            self._handle_points,
            qos_profile_sensor_data,
        )

        self._first_cloud_logged = False
        self._first_scan_logged = False
        self._parse_warning_emitted = False
        self._stale_warning_emitted = False
        self._last_cloud_at: float | None = None
        stale_after = self.get_parameter("diagnostic_stale_after_sec").get_parameter_value().double_value
        self._diagnostic_timer = self.create_timer(max(1.0, stale_after / 2.0), self._emit_diagnostics)

        self.get_logger().info(
            f"Lidar bridge ready: converting {input_points_topic} PointCloud2 samples into "
            f"{output_scan_topic} LaserScan."
        )

    def _handle_points(self, msg: PointCloud2) -> None:
        try:
            points = extract_xyz_points(
                data=msg.data,
                width=msg.width,
                height=msg.height,
                point_step=msg.point_step,
                fields=[
                    PointCloudFieldSpec(
                        name=str(field.name),
                        offset=int(field.offset),
                        datatype=int(field.datatype),
                    )
                    for field in msg.fields
                ],
                is_bigendian=bool(msg.is_bigendian),
            )
        except Exception as exc:
            if not self._parse_warning_emitted:
                self.get_logger().warning(
                    f"Failed to convert PointCloud2 on {self.get_parameter('input_points_topic').value} "
                    f"into LaserScan: {exc}"
                )
                self._parse_warning_emitted = True
            return

        scan_ranges = project_points_to_scan(
            points,
            angle_min=float(self.get_parameter("angle_min").value),
            angle_max=float(self.get_parameter("angle_max").value),
            angle_increment=float(self.get_parameter("angle_increment").value),
            range_min=float(self.get_parameter("range_min").value),
            range_max=float(self.get_parameter("range_max").value),
            min_height=float(self.get_parameter("min_height").value),
            max_height=float(self.get_parameter("max_height").value),
        )

        scan_msg = LaserScan()
        scan_msg.header = msg.header
        scan_msg.angle_min = float(self.get_parameter("angle_min").value)
        scan_msg.angle_max = float(self.get_parameter("angle_max").value)
        scan_msg.angle_increment = float(self.get_parameter("angle_increment").value)
        scan_msg.time_increment = 0.0
        scan_msg.scan_time = float(self.get_parameter("scan_time").value)
        scan_msg.range_min = float(self.get_parameter("range_min").value)
        scan_msg.range_max = float(self.get_parameter("range_max").value)
        scan_msg.ranges = scan_ranges.tolist()
        scan_msg.intensities = []
        self._scan_pub.publish(scan_msg)

        self._last_cloud_at = time.monotonic()
        self._stale_warning_emitted = False
        self._parse_warning_emitted = False

        if not self._first_cloud_logged:
            self.get_logger().info(
                f"Received first lidar point cloud on {self.get_parameter('input_points_topic').value} "
                f"with frame_id={msg.header.frame_id}."
            )
            self._first_cloud_logged = True

        if not self._first_scan_logged:
            self.get_logger().info(
                f"Lidar bridge is publishing LaserScan on {self.get_parameter('output_scan_topic').value}."
            )
            self._first_scan_logged = True

    def _emit_diagnostics(self) -> None:
        if self._last_cloud_at is None:
            if not self._stale_warning_emitted:
                self.get_logger().warning(
                    "No built-in lidar point clouds received yet. "
                    f"Expected PointCloud2 on {self.get_parameter('input_points_topic').value} "
                    f"before {self.get_parameter('output_scan_topic').value} can be published."
                )
                self._stale_warning_emitted = True
            return

        stale_after = float(self.get_parameter("diagnostic_stale_after_sec").value)
        if (time.monotonic() - self._last_cloud_at) >= stale_after and not self._stale_warning_emitted:
            self.get_logger().warning(
                f"Built-in lidar input on {self.get_parameter('input_points_topic').value} is stale; "
                f"no fresh cloud received for {stale_after:.1f}s."
            )
            self._stale_warning_emitted = True


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node: LidarBridgeNode | None = None
    try:
        node = LidarBridgeNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        return
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
