from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


FLOAT32_POINTFIELD = 7


@dataclass(frozen=True)
class PointCloudFieldSpec:
    name: str
    offset: int
    datatype: int


def generate_mock_lidar_points(
    *,
    sequence_id: int,
    points_per_ring: int = 360,
    wall_distance_m: float = 4.0,
) -> np.ndarray:
    angles = np.linspace(-math.pi, math.pi, points_per_ring, endpoint=False, dtype=np.float32)
    ranges = np.full(points_per_ring, wall_distance_m, dtype=np.float32)

    # Add two deterministic closer obstacles so the mock cloud is useful in smoke tests.
    front_center = points_per_ring // 2
    left_center = int(points_per_ring * 0.75)
    ranges[max(0, front_center - 4): front_center + 5] = 1.1 + 0.05 * math.sin(sequence_id * 0.1)
    ranges[max(0, left_center - 3): left_center + 4] = 1.8

    x = ranges * np.cos(angles)
    y = ranges * np.sin(angles)
    z = np.zeros(points_per_ring, dtype=np.float32)
    return np.column_stack((x, y, z)).astype(np.float32, copy=False)


def extract_xyz_points(
    *,
    data: bytes | bytearray | memoryview,
    width: int,
    height: int,
    point_step: int,
    fields: list[PointCloudFieldSpec],
    is_bigendian: bool = False,
) -> np.ndarray:
    if point_step <= 0:
        raise ValueError(f"Invalid point_step={point_step}.")

    expected_points = max(0, int(width) * int(height))
    if expected_points == 0:
        return np.empty((0, 3), dtype=np.float32)

    xyz_offsets = _resolve_xyz_offsets(fields)
    if xyz_offsets is None:
        raise ValueError("Point cloud does not contain float32 x/y/z fields.")
    if max(xyz_offsets) + 4 > point_step:
        raise ValueError(
            f"Point cloud x/y/z field offsets {xyz_offsets} exceed point_step={point_step}."
        )

    required_bytes = expected_points * point_step
    raw = memoryview(data)
    if raw.nbytes < required_bytes:
        raise ValueError(
            f"Point cloud buffer too small: got {raw.nbytes} bytes, expected at least {required_bytes}."
        )

    dtype_prefix = ">" if is_bigendian else "<"
    structured_dtype = np.dtype(
        {
            "names": ["x", "y", "z"],
            "formats": [f"{dtype_prefix}f4", f"{dtype_prefix}f4", f"{dtype_prefix}f4"],
            "offsets": list(xyz_offsets),
            "itemsize": point_step,
        }
    )
    structured = np.frombuffer(raw[:required_bytes], dtype=structured_dtype, count=expected_points)
    points = np.empty((expected_points, 3), dtype=np.float32)
    points[:, 0] = structured["x"]
    points[:, 1] = structured["y"]
    points[:, 2] = structured["z"]

    finite_mask = np.isfinite(points).all(axis=1)
    return points[finite_mask]


def project_points_to_scan(
    points: np.ndarray,
    *,
    angle_min: float,
    angle_max: float,
    angle_increment: float,
    range_min: float,
    range_max: float,
    min_height: float,
    max_height: float,
) -> np.ndarray:
    if angle_increment <= 0:
        raise ValueError("angle_increment must be positive.")
    if angle_max <= angle_min:
        raise ValueError("angle_max must be greater than angle_min.")

    sample_count = int(math.floor((angle_max - angle_min) / angle_increment)) + 1
    ranges = np.full(sample_count, np.inf, dtype=np.float32)
    if points.size == 0:
        return ranges

    xyz = np.asarray(points, dtype=np.float32)
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise ValueError(f"Expected points shaped (N, 3), got {xyz.shape}.")

    finite_mask = np.isfinite(xyz).all(axis=1)
    height_mask = (xyz[:, 2] >= min_height) & (xyz[:, 2] <= max_height)
    planar = xyz[finite_mask & height_mask]
    if planar.size == 0:
        return ranges

    distances = np.hypot(planar[:, 0], planar[:, 1])
    angles = np.arctan2(planar[:, 1], planar[:, 0])

    valid_mask = (
        np.isfinite(distances)
        & (distances >= range_min)
        & (distances <= range_max)
        & (angles >= angle_min)
        & (angles <= angle_max)
    )
    if not np.any(valid_mask):
        return ranges

    valid_points = planar[valid_mask]
    valid_distances = distances[valid_mask]
    valid_angles = angles[valid_mask]

    bin_indices = np.floor((valid_angles - angle_min) / angle_increment).astype(np.int32)
    bin_indices = np.clip(bin_indices, 0, sample_count - 1)

    for index, distance in zip(bin_indices, valid_distances):
        if distance < ranges[index]:
            ranges[index] = float(distance)

    return ranges


def depth_image_to_points(
    depth_image: np.ndarray,
    *,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    depth_scale: float,
    stride: int = 1,
    min_depth: float = 0.10,
    max_depth: float = 10.0,
) -> np.ndarray:
    if fx <= 0 or fy <= 0:
        raise ValueError("Camera intrinsics fx and fy must be positive.")
    if depth_scale <= 0:
        raise ValueError("depth_scale must be positive.")
    if stride <= 0:
        raise ValueError("stride must be positive.")

    depth = np.asarray(depth_image)
    if depth.ndim != 2:
        raise ValueError(f"Expected depth image shaped (H, W), got {depth.shape}.")

    sampled_depth = depth[::stride, ::stride].astype(np.float32, copy=False) * float(depth_scale)
    if sampled_depth.size == 0:
        return np.empty((0, 3), dtype=np.float32)

    rows = np.arange(0, depth.shape[0], stride, dtype=np.float32)
    cols = np.arange(0, depth.shape[1], stride, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(cols, rows)

    valid_mask = (
        np.isfinite(sampled_depth)
        & (sampled_depth >= min_depth)
        & (sampled_depth <= max_depth)
    )
    if not np.any(valid_mask):
        return np.empty((0, 3), dtype=np.float32)

    z = sampled_depth[valid_mask]
    x = (grid_x[valid_mask] - float(cx)) * z / float(fx)
    y = (grid_y[valid_mask] - float(cy)) * z / float(fy)
    return np.column_stack((x, y, z)).astype(np.float32, copy=False)


def _resolve_xyz_offsets(fields: list[PointCloudFieldSpec]) -> tuple[int, int, int] | None:
    offsets: dict[str, int] = {}
    for field in fields:
        if field.datatype == FLOAT32_POINTFIELD and field.name in {"x", "y", "z"}:
            offsets[field.name] = int(field.offset)

    if {"x", "y", "z"} <= offsets.keys():
        return offsets["x"], offsets["y"], offsets["z"]
    return None
