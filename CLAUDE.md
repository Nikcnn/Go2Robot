# Go2 Inspection System

## Scope

- Safe test-environment project only.
- Target Ubuntu 20.04 and Python 3.8.
- `src/` is the standalone Python app path.
- `ros_ws/` is the ROS 2 Foxy path.
- Keep mock mode runnable without hardware.

## Project Paths

- `src/`: FastAPI app, dashboard, scripted route executor, control core, telemetry, camera streaming, storage, reports, mock adapter, Go2 adapter.
- `config/routes/`: scripted JSON routes for the Python app.
- `ros_ws/`: ROS 2 Foxy workspace with `go2_bridge`, `go2_mission`, `go2_interfaces`, and Nav2 bringup.
- `shared_missions/`: coordinate waypoint missions and maps for the ROS layer.
- `runs/`: runtime artifacts.
- `tests/`: hardware-free pytest coverage.

## Non-Negotiables

- Never invent Unitree SDK method names.
- Keep uncertain Python app SDK integration in `src/robot/go2_adapter.py` and closely related adapter files.
- In ROS, `go2_bridge` is the only process allowed to touch the adapter or `unitree_sdk2py`.
- Treat `ChannelFactory` as a process singleton.
- Do not run the Python app and `go2_bridge` as real SDK owners at the same time.
- For ROS work, use Foxy APIs and Ubuntu 20.04 assumptions only.

## Mission Model

- Python app routes are scripted JSON files using steps such as `move`, `move_velocity`, `rotate`, `checkpoint`, `stop`, `stand_up`, `wait`, and `settle`.
- ROS missions are coordinate waypoint JSON files sent through Nav2 `FollowWaypoints`.
- Priority is always `ESTOP > MANUAL > AUTO`.
- Manual override pauses missions and does not auto-resume them.

## Sensors

- Robot camera support stays on the adapter path.
- RealSense is optional and must not break mock mode or robot-camera operation.
- ROS lidar code publishes `/points` and converts PointCloud2 to `/scan`, but real Unitree lidar message import details still need Ubuntu 20.04 target validation.
- Do not claim mapping, AMCL, or Nav2 runtime completeness without a verified live `/scan`.

## Working Style

- Read the minimum files needed.
- Patch the minimum surface area.
- Prefer direct modules over large abstractions.
- Keep Python app concerns and ROS concerns separated.
- Keep tests fast and hardware-free unless hardware testing is explicitly requested.
