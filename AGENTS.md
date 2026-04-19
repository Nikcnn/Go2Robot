# Go2 inspection MVP rules

## Scope
- Safe test-environment MVP only
- Python 3.11+ only
- Allowed stack: FastAPI, Uvicorn, OpenCV, numpy, PyYAML, pydantic v2, pytest
- No ROS, ROS2, Nav2, SLAM, RViz, Gazebo, BIM, digital twin, manipulator control, fleet management, React, Vue, frontend build tools

## Architecture
- All uncertain Unitree SDK integration must live only in `src/robot/robot_adapter.py` and closely related robot files
- Never invent SDK method names
- Mock mode must run end-to-end without real hardware
- Keep the rest of the app runnable even if real SDK calls are stubbed
- Prefer simple, direct modules over framework-like abstractions

## Mission semantics
- Scripted JSON route only
- Supported steps: move, rotate, checkpoint, stop
- Priority: ESTOP > MANUAL > AUTO
- Manual override pauses mission and never auto-resumes
- Single active controller only

## Editing rules
- Read the minimum number of files needed
- Patch the minimum possible surface area
- Do not redesign the whole project unless explicitly asked
- Keep tests fast and hardware-free