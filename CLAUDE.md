# Go2 Inspection System

## Hard scope
- Safe test-environment MVP only.
- Python 3.9+ only.
- Allowed stack: FastAPI, Uvicorn, OpenCV, numpy, PyYAML, pydantic v2, pytest.
- No ROS/ROS2, Nav2, SLAM, RViz, Gazebo, BIM, digital twin, manipulator, fleet management, auth framework, React/Vue, frontend build tools.

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
