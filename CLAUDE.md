# Go2 inspection MVP

## Hard scope
- Safe test-environment MVP only.
- Python 3.9+ only.
- Allowed stack: FastAPI, Uvicorn, OpenCV, numpy, PyYAML, pydantic v2, pytest.
- No ROS/ROS2, Nav2, SLAM, RViz, Gazebo, BIM, digital twin, manipulator, fleet management, auth framework, React/Vue, frontend build tools.

## Non-negotiables
- Exact file layout is fixed.
- All uncertain Unitree SDK work lives only in `src/robot_adapter.py`.
- Never invent SDK methods.
- Mock mode must work end-to-end even if real adapter is incomplete.
- Operator console is plain HTML/JS/CSS only.
- Keep modules small and direct.
- Tests must be fast and hardware-free.

## Runtime semantics
- Modes priority: ESTOP > MANUAL > AUTO.
- Manual override never auto-resumes.
- Mission = scripted route, sequential steps only.
- Checkpoints capture frame + telemetry + analysis + storage event.

## Working style
- Read the minimum number of files.
- Patch minimally.
- Prefer exact diffs over refactors.
- For repeated work, use project skills instead of bloating this file.