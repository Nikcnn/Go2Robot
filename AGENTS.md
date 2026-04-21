# Go2 Inspection System Rules

## Scope

- Safe test-environment only.
- The repository contains two supported execution paths:
  - `src/`: Python 3.8 application layer with FastAPI, vanilla dashboard, scripted route executor, storage, reports, image analysis, mock mode, and direct Go2 adapter support.
  - `ros_ws/`: Ubuntu 20.04 ROS 2 Foxy workspace for `go2_bridge`, `go2_mission`, `go2_interfaces`, Nav2 bringup, and shared coordinate missions.
  - `shared_missions/`: coordinate waypoint missions and maps for the ROS 2 layer.

## Platform Expectations

- `src/` remains Python 3.8 oriented and must stay runnable on its own.
- `ros_ws/` targets Ubuntu 20.04, ROS 2 Foxy, and Python 3.8 through `rclpy`.
- When changing ROS files, use Foxy APIs only. Do not introduce Humble, Galactic, Iron, or source-built Nav2 assumptions unless explicitly required.

## Architecture

- All uncertain Unitree SDK integration in the Python app must stay inside `src/robot/go2_adapter.py` and closely related robot files.
- In the ROS stack, `go2_bridge` is the only process allowed to touch the adapter or `unitree_sdk2py`.
- Never invent SDK method names.
- `ChannelFactory` is a process singleton, so do not create a second SDK-owning process.
- Mock mode must run end-to-end without real hardware.
- Keep the rest of the application usable even if some real robot paths remain incomplete.
- Prefer simple, direct modules over framework-like abstractions.

## Mission Semantics

- The Python app uses scripted JSON routes from `config/routes/`.
- Supported scripted steps include `move`, `move_velocity`, `rotate`, `checkpoint`, `stop`, `stand_up`, `wait`, and `settle`.
- The ROS layer uses coordinate waypoint missions from `shared_missions/missions/` and sends them through Nav2 `FollowWaypoints`.
- Priority is always `ESTOP > MANUAL > AUTO`.
- Manual override pauses the mission and never auto-resumes it.
- Keep a single active controller for robot motion.

## Sensors and Integration Boundaries

- Robot camera support stays on the existing adapter path.
- RealSense support may exist in both layers, but do not let it break the base mock or robot-camera path.
- The ROS lidar path has static code for `/points` to `/scan` conversion. The real Unitree lidar SDK message import path still needs validation on Ubuntu 20.04 with the robot connected.
- Mapping, AMCL, and Nav2 require a real valid `/scan` source before claiming runtime completeness.

## Editing Rules

- Read the minimum number of files needed.
- Patch the minimum possible surface area.
- Do not redesign the whole project unless explicitly asked.
- Preserve the separation between the application layer and the ROS layer.
- Keep tests fast and hardware-free where possible.
- If you update docs, keep them aligned with the actual repo layout: `src/`, `ros_ws/`, `shared_missions/`, and `BUILD.md`.

## Communication and Validation

- Be explicit about what is statically updated versus what is runtime-verified.
- From a Windows workspace, do not imply that ROS 2 Foxy or Nav2 runtime behavior was fully tested unless it actually was.
- When adding ROS configuration, keep `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` in mind and preserve existing launch and build guidance.
