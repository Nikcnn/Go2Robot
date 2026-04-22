from __future__ import annotations

import importlib
import pkgutil
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np

from .pointcloud_utils import PointCloudFieldSpec, extract_xyz_points, generate_mock_lidar_points


@dataclass(frozen=True)
class LidarPointFrame:
    points: np.ndarray
    frame_id: str
    source_name: str
    received_at: float


class MockLidarSource:
    def __init__(self, *, frame_id: str = "utlidar_lidar") -> None:
        self._frame_id = frame_id
        self._sequence_id = 0
        self._active = False

    def start(self) -> tuple[bool, str]:
        self._active = True
        return True, "Mock lidar source active."

    def stop(self) -> None:
        self._active = False

    def is_active(self) -> bool:
        return self._active

    def get_latest_frame(self) -> LidarPointFrame | None:
        if not self._active:
            return None
        self._sequence_id += 1
        points = generate_mock_lidar_points(sequence_id=self._sequence_id)
        return LidarPointFrame(
            points=points,
            frame_id=self._frame_id,
            source_name="mock_lidar",
            received_at=time.monotonic(),
        )


class UnitreeLidarSource:
    def __init__(
        self,
        *,
        logger,
        topic_name: str = "utlidar/cloud",
        frame_id: str = "utlidar_lidar",
        message_module: str | None = None,
        message_type: str | None = None,
    ) -> None:
        self._logger = logger
        self._topic_name = topic_name
        self._frame_id = frame_id
        self._message_module = message_module
        self._message_type = message_type
        self._subscriber = None
        self._latest_frame: LidarPointFrame | None = None
        self._warned_parse_failure = False
        self._active = False
        self._status = "not_started"

    def start(self) -> tuple[bool, str]:
        try:
            channel_module = importlib.import_module("unitree_sdk2py.core.channel")
        except ImportError as exc:
            self._status = f"unitree_sdk2py missing: {exc}"
            return False, self._status

        try:
            msg_type = _resolve_pointcloud_message_type(
                message_module=self._message_module,
                message_type=self._message_type,
            )
        except RuntimeError as exc:
            self._status = str(exc)
            return False, self._status

        try:
            channel_subscriber = getattr(channel_module, "ChannelSubscriber")
            self._subscriber = channel_subscriber(self._topic_name, msg_type)
            self._subscriber.Init(self._on_message, queueLen=10)
        except Exception as exc:
            self._status = f"Failed to subscribe to built-in lidar topic '{self._topic_name}': {exc}"
            return False, self._status

        self._active = True
        self._status = (
            f"Subscribed to built-in lidar topic '{self._topic_name}'. "
            "Waiting for point cloud samples."
        )
        return True, self._status

    def stop(self) -> None:
        if self._subscriber is not None:
            try:
                self._subscriber.Close()
            except Exception as exc:
                self._logger.warning(f"Built-in lidar subscriber close failed: {exc}")
        self._subscriber = None
        self._active = False

    def is_active(self) -> bool:
        return self._active

    def status(self) -> str:
        return self._status

    def get_latest_frame(self) -> LidarPointFrame | None:
        return self._latest_frame

    def _on_message(self, msg: Any) -> None:
        try:
            points = _extract_pointcloud2_points(msg)
        except Exception as exc:
            if not self._warned_parse_failure:
                self._logger.warning(f"Failed to parse built-in lidar point cloud sample: {exc}")
                self._warned_parse_failure = True
            self._status = f"Built-in lidar samples received, but parsing failed: {exc}"
            return

        self._latest_frame = LidarPointFrame(
            points=points,
            frame_id=_read_frame_id(msg, default=self._frame_id),
            source_name="unitree_builtin_lidar",
            received_at=time.monotonic(),
        )
        self._status = "Built-in lidar samples are streaming."


def _resolve_pointcloud_message_type(
    *,
    message_module: str | None = None,
    message_type: str | None = None,
) -> Any:
    # TODO(sdk): Verify the exact generated PointCloud2 import path on the target
    # Ubuntu 20.04 + unitree_sdk2py installation. Until that is confirmed on the
    # robot, keep all import-path uncertainty isolated here and fail clearly.
    candidate_type_names = [message_type] if message_type else ["PointCloud2_", "PointCloud2"]
    for module_name in _candidate_pointcloud_modules(message_module=message_module):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for attr_name in candidate_type_names:
            msg_type = getattr(module, attr_name, None)
            if msg_type is not None:
                return msg_type
        if message_type is None:
            msg_type = _find_pointcloud_type_in_module(module)
            if msg_type is not None:
                return msg_type

    attempted_override = ""
    if message_module or message_type:
        attempted_override = (
            f" Override attempted with module={message_module or '<auto>'} "
            f"type={message_type or '<auto>'}."
        )
    raise RuntimeError(
        "Built-in lidar SDK message type could not be resolved. "
        "TODO(sdk): verify the generated PointCloud2 import path exposed by "
        "unitree_sdk2py, or override sdk_lidar_msg_module/sdk_lidar_msg_type at launch."
        f"{attempted_override}"
    )


def _candidate_pointcloud_modules(*, message_module: str | None) -> tuple[str, ...]:
    if message_module:
        return (message_module,)

    modules = ["unitree_sdk2py.idl.sensor_msgs.msg.dds_"]
    for discovered_module in _discover_idl_modules():
        if discovered_module not in modules:
            modules.append(discovered_module)
    return tuple(modules)


@lru_cache(maxsize=1)
def _discover_idl_modules() -> tuple[str, ...]:
    try:
        idl_package = importlib.import_module("unitree_sdk2py.idl")
    except ImportError:
        return ()

    package_paths = getattr(idl_package, "__path__", None)
    if package_paths is None:
        return ()

    discovered_modules = [
        module_info.name
        for module_info in pkgutil.walk_packages(
            path=package_paths,
            prefix=f"{idl_package.__name__}.",
        )
        if module_info.name.endswith(".dds_")
    ]
    discovered_modules.sort(key=_pointcloud_module_sort_key)
    return tuple(discovered_modules)


def _pointcloud_module_sort_key(module_name: str) -> tuple[int, int, str]:
    return (
        0 if "sensor_msgs" in module_name else 1,
        0 if module_name.endswith(".dds_") else 1,
        module_name,
    )


def _find_pointcloud_type_in_module(module) -> Any | None:
    for attr_name in dir(module):
        normalized = attr_name.rstrip("_").lower()
        if normalized != "pointcloud2":
            continue
        msg_type = getattr(module, attr_name, None)
        if msg_type is not None:
            return msg_type
    return None


def _extract_pointcloud2_points(msg: Any) -> np.ndarray:
    width = int(getattr(msg, "width"))
    height = int(getattr(msg, "height", 1))
    point_step = int(getattr(msg, "point_step"))
    raw_data = bytes(getattr(msg, "data"))
    is_bigendian = bool(getattr(msg, "is_bigendian", False))
    field_specs = [
        PointCloudFieldSpec(
            name=str(getattr(field, "name")),
            offset=int(getattr(field, "offset")),
            datatype=int(getattr(field, "datatype")),
        )
        for field in getattr(msg, "fields")
    ]
    return extract_xyz_points(
        data=raw_data,
        width=width,
        height=height,
        point_step=point_step,
        fields=field_specs,
        is_bigendian=is_bigendian,
    )


def _read_frame_id(msg: Any, *, default: str) -> str:
    header = getattr(msg, "header", None)
    if header is None:
        return default
    frame_id = getattr(header, "frame_id", "")
    return str(frame_id) if frame_id else default
