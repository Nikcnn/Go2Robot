from __future__ import annotations

import json

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from go2_interfaces.srv import MissionControl

from .mission_executor import MissionExecutorNode


class MissionApiNode(Node):
    """Service entrypoint for FastAPI -> ROS 2 mission control.

    FastAPI via rclpy client:
    request.command = "start"
    request.mission_path = "/absolute/path/to/shared_missions/missions/inspect_line_a.json"
    request.mission_json = ""

    FastAPI via rosbridge WebSocket call_service:
    {
      "op": "call_service",
      "service": "/go2_mission/command",
      "type": "go2_interfaces/srv/MissionControl",
      "args": {
        "command": "status",
        "mission_path": "",
        "mission_json": ""
      }
    }
    """

    def __init__(self, mission_executor: MissionExecutorNode) -> None:
        super().__init__("go2_mission_api")
        self.declare_parameter("service_name", "/go2_mission/command")
        service_name = self.get_parameter("service_name").get_parameter_value().string_value
        self._mission_executor = mission_executor
        self._service = self.create_service(MissionControl, service_name, self._handle_command)
        self.get_logger().info(f"Mission API ready on {service_name}.")

    def _handle_command(
        self,
        request: MissionControl.Request,
        response: MissionControl.Response,
    ) -> MissionControl.Response:
        command = request.command.strip().lower()

        try:
            if command == "start":
                ok, message, mission_id = self._mission_executor.start_mission(
                    mission_path=request.mission_path or None,
                    mission_json=request.mission_json or None,
                )
                response.success = ok
                response.message = message
                response.mission_id = mission_id or ""
            elif command == "cancel":
                ok, message = self._mission_executor.cancel_mission()
                response.success = ok
                response.message = message
                response.mission_id = self._mission_executor.get_state_dict().get("mission_id") or ""
            elif command == "status":
                response.success = True
                response.message = "Mission status returned."
                response.mission_id = self._mission_executor.get_state_dict().get("mission_id") or ""
            else:
                response.success = False
                response.message = f"Unsupported command '{request.command}'. Use start, cancel, or status."
                response.mission_id = ""
        except Exception as exc:
            response.success = False
            response.message = str(exc)
            response.mission_id = self._mission_executor.get_state_dict().get("mission_id") or ""

        response.state_json = json.dumps(self._mission_executor.get_state_dict())
        return response


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    mission_executor: MissionExecutorNode | None = None
    api_node: MissionApiNode | None = None
    executor: MultiThreadedExecutor | None = None
    try:
        mission_executor = MissionExecutorNode()
        api_node = MissionApiNode(mission_executor)
        executor = MultiThreadedExecutor()
        executor.add_node(mission_executor)
        executor.add_node(api_node)
        executor.spin()
    except KeyboardInterrupt:
        return
    finally:
        if executor is not None:
            executor.shutdown()
        if api_node is not None:
            api_node.destroy_node()
        if mission_executor is not None:
            mission_executor.shutdown()
            mission_executor.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
