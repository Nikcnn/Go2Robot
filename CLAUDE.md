# Go2 Inspection System

## Project shape
- This repo now has two active layers:
- `src/`: the existing Python operator app with FastAPI, vanilla dashboard, scripted missions, storage, reports, image analysis, mock mode, RealSense support, and direct Go2 SDK integration.
- `ros_ws/`: the ROS 2 Humble workspace with `go2_interfaces`, `go2_bridge`, `go2_mission`, and `go2_nav_bringup`.
- `shared_missions/`: coordinate missions and shared maps for the ROS 2 layer.

## Scope
- Safe test-environment only.
- Keep the current Python app runnable end-to-end in mock mode.
- Keep the ROS 2 layer aligned with Ubuntu 22.04 + ROS 2 Humble.
- Do not present the system as production-ready autonomy.

## Non-negotiables
- Never invent Unitree SDK method names.
- In the Python app, uncertain SDK work stays isolated to `src/robot/go2_adapter.py`.
- In the ROS 2 stack, `go2_bridge` is the only process allowed to touch the Go2 adapter and `unitreesdk2py`.
- `ChannelFactory` is a process singleton; do not create a second SDK-owning process.
- Mock mode must continue to work without hardware.
- Keep tests hardware-free unless a task explicitly requires otherwise.

## Mission model
- `src/` still uses scripted JSON steps such as `move`, `rotate`, `checkpoint`, and `stop`.
- `ros_ws/` uses coordinate waypoint missions from `shared_missions/missions/*.json`.
- Control priority is always `ESTOP > MANUAL > AUTO`.
- Manual override pauses missions and never auto-resumes them.

## Working style
- Read the minimum number of files needed.
- Patch the minimum possible surface area.
- Prefer direct modules over large abstractions.
- Match the layer you are editing: do not pull ROS assumptions into the pure Python MVP unless requested.
- For ROS changes, stay on Humble APIs and package conventions.
