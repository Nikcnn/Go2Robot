from __future__ import annotations

import math
import sys
import types

import numpy as np

from tests import ROOT


BRIDGE_PACKAGE_ROOT = ROOT / "ros_ws" / "src" / "go2_bridge"
if str(BRIDGE_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(BRIDGE_PACKAGE_ROOT))

from go2_bridge import unitree_lidar as unitree_lidar_module
from go2_bridge.pointcloud_utils import (
    FLOAT32_POINTFIELD,
    PointCloudFieldSpec,
    depth_image_to_points,
    extract_xyz_points,
    project_points_to_scan,
)
from go2_bridge.unitree_lidar import MockLidarSource


def test_mock_lidar_source_produces_finite_xyz_points() -> None:
    source = MockLidarSource(frame_id="utlidar_lidar")

    started, status = source.start()

    assert started is True
    assert "Mock lidar" in status
    frame = source.get_latest_frame()
    assert frame is not None
    assert frame.frame_id == "utlidar_lidar"
    assert frame.source_name == "mock_lidar"
    assert frame.points.ndim == 2
    assert frame.points.shape[1] == 3
    assert frame.points.shape[0] > 100
    assert np.isfinite(frame.points).all()

    source.stop()
    assert source.get_latest_frame() is None


def test_project_points_to_scan_keeps_nearest_obstacle_per_bin() -> None:
    points = np.array(
        [
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [1.0, -1.0, 0.0],
            [0.5, 0.0, 1.0],
        ],
        dtype=np.float32,
    )

    scan = project_points_to_scan(
        points,
        angle_min=-math.pi / 4.0,
        angle_max=math.pi / 4.0,
        angle_increment=math.pi / 4.0,
        range_min=0.1,
        range_max=10.0,
        min_height=-0.1,
        max_height=0.1,
    )

    assert scan.shape == (3,)
    assert scan[0] == np.float32(math.sqrt(2.0))
    assert scan[1] == np.float32(1.0)
    assert scan[2] == np.float32(math.sqrt(2.0))


def test_extract_xyz_points_reads_pointcloud2_layout() -> None:
    structured = np.array(
        [
            (1.0, 2.0, 0.1, 99.0),
            (3.0, 4.0, 0.2, 88.0),
        ],
        dtype=[
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("intensity", "<f4"),
        ],
    )

    points = extract_xyz_points(
        data=structured.tobytes(),
        width=2,
        height=1,
        point_step=structured.dtype.itemsize,
        fields=[
            PointCloudFieldSpec(name="x", offset=0, datatype=FLOAT32_POINTFIELD),
            PointCloudFieldSpec(name="y", offset=4, datatype=FLOAT32_POINTFIELD),
            PointCloudFieldSpec(name="z", offset=8, datatype=FLOAT32_POINTFIELD),
            PointCloudFieldSpec(name="intensity", offset=12, datatype=FLOAT32_POINTFIELD),
        ],
        is_bigendian=False,
    )

    assert points.shape == (2, 3)
    assert np.allclose(points, np.array([[1.0, 2.0, 0.1], [3.0, 4.0, 0.2]], dtype=np.float32))


def test_depth_image_to_points_projects_valid_depth_pixels() -> None:
    depth_image = np.array(
        [
            [0, 1000],
            [2000, 3000],
        ],
        dtype=np.uint16,
    )

    points = depth_image_to_points(
        depth_image,
        fx=2.0,
        fy=2.0,
        cx=0.5,
        cy=0.5,
        depth_scale=0.001,
        stride=1,
        min_depth=0.5,
        max_depth=2.5,
    )

    assert points.shape == (2, 3)
    assert np.allclose(
        points,
        np.array(
            [
                [0.25, -0.25, 1.0],
                [-0.5, 0.5, 2.0],
            ],
            dtype=np.float32,
        ),
    )


def test_resolve_pointcloud_message_type_uses_explicit_override() -> None:
    fake_module_name = "fake_unitree_pointcloud"
    fake_module = types.ModuleType(fake_module_name)

    class FakePointCloud2:
        pass

    fake_module.CustomPointCloud2 = FakePointCloud2
    sys.modules[fake_module_name] = fake_module
    try:
        resolved = unitree_lidar_module._resolve_pointcloud_message_type(
            message_module=fake_module_name,
            message_type="CustomPointCloud2",
        )
    finally:
        sys.modules.pop(fake_module_name, None)

    assert resolved is FakePointCloud2
