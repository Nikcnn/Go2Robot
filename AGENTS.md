# Go2 inspection system rules

## Scope
- Safe test-environment only.
- The repo now contains two supported execution paths:
- `src/`: Python application layer with FastAPI, vanilla dashboard, scripted route executor, storage, reports, image analysis, mock mode, and direct Go2 adapter support.
- `ros_ws/`: ROS 2 Humble workspace for `go2_bridge`, `go2_mission`, Nav2 bringup, and shared coordinate missions.
- `shared_missions/`: coordinate waypoint missions and shared maps for the ROS 2 layer.

## Platform expectations
- `src/` remains Python 3.11+ oriented and must stay runnable on its own.
- `ros_ws/` targets Ubuntu 22.04, ROS 2 Humble, and Python 3.10 via `rclpy`.
- When changing ROS files, use Humble APIs only. Do not introduce Jazzy, Iron, Rolling, or source-built Nav2 assumptions unless explicitly required.

## Architecture
- All uncertain Unitree SDK integration in the Python app must stay inside `src/robot/go2_adapter.py` and closely related robot files.
- In the ROS stack, `go2_bridge` is the only process allowed to touch the adapter / `unitreesdk2py`.
- Never invent SDK method names.
- `ChannelFactory` is a process singleton, so do not create a second SDK-owning process.
- Mock mode must run end-to-end without real hardware.
- Keep the rest of the application usable even if some real robot paths remain incomplete.
- Prefer simple, direct modules over framework-like abstractions.

## Mission semantics
- The Python app still uses scripted JSON routes from `config/routes/`.
- Supported scripted steps remain `move`, `rotate`, `checkpoint`, `stop`, plus existing lifecycle helpers already in the codebase.
- The ROS layer uses coordinate waypoint missions from `shared_missions/missions/` and sends them through Nav2 `FollowWaypoints`.
- Priority is always `ESTOP > MANUAL > AUTO`.
- Manual override pauses the mission and never auto-resumes it.
- Keep a single active controller for robot motion.

## Sensors and integration boundaries
- Robot camera support stays on the existing adapter path.
- RealSense support may exist in both layers, but do not let it break the base mock/robot camera path.
- `ros_ws/src/go2_bridge/go2_bridge/lidar_bridge.py` is currently a stub. Do not pretend the system has a real lidar bridge unless you are explicitly implementing one.
- Mapping, AMCL, and Nav2 require a real `/scan` source before claiming runtime completeness.

## Editing rules
- Read the minimum number of files needed.
- Patch the minimum possible surface area.
- Do not redesign the whole project unless explicitly asked.
- Preserve the separation between the application layer and the ROS layer.
- Keep tests fast and hardware-free where possible.
- If you update docs, keep them aligned with the actual repo layout: `src/`, `ros_ws/`, `shared_missions/`, and `BUILD.md`.

## Communication and validation
- Be explicit about what is statically updated versus what is runtime-verified.
- From a Windows workspace, do not imply that ROS 2 Humble or Nav2 runtime behavior was fully tested unless it actually was.
- When adding ROS configuration, keep `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` in mind and preserve existing launch/build guidance.
