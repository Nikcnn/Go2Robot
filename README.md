# Go2 Inspection MVP

## What This Is
A safe test-environment MVP for scripted inspection on a Unitree Go2. It runs end-to-end in mock mode with a FastAPI server, a plain HTML dashboard, a scripted JSON route executor, synthetic telemetry, a synthetic camera stream, per-mission storage, and fast hardware-free tests.

## What This Is Not
This is not full autonomous navigation. It does not implement ROS, ROS2, Nav2, SLAM, RViz, Gazebo, obstacle avoidance, production safety systems, fleet management, or a frontend build pipeline.

---

## Architecture

```
HTTP / WebSocket clients
        │
        ▼
  FastAPI (src/api.py)
        │
        ▼
  ControlCore (src/control.py)
  ┌─────────────────────────────────────┐
  │  Priority: ESTOP > MANUAL > AUTO    │
  │  Watchdog: zeroes velocity on       │
  │  stale teleop commands              │
  └─────────────────────────────────────┘
        │ send_velocity / stop / get_state
        ▼
  RobotAdapterProtocol (src/robot/robot_adapter.py)
       ╱                    ╲
MockRobotAdapter        Go2RobotAdapter
(always available)      (requires SDK + hardware)
```

**Control layer rules:**
- `ESTOP` is latched; all motion commands are blocked until explicitly reset
- `MANUAL` mode pauses any running mission; release does not auto-resume
- `AUTO` is the only mode where mission steps issue `send_velocity`
- A teleop watchdog thread fires `stop()` if no MANUAL command arrives within `watchdog_timeout_ms`

**Mission executor (`src/mission.py`):**
- Loads a JSON route file, executes steps sequentially
- Calls `send_velocity` only when `ControlCore.wait_until_runnable()` returns True
- Checkpoint steps call `capture_frame` + telemetry snapshot + analysis + storage
- When enabled, checkpoint steps also capture Intel RealSense D435i RGB-D artifacts without replacing the existing robot camera path

---

## Mock Mode vs Go2 Mode

|                     | Mock mode              | Go2 mode                              |
|---------------------|------------------------|---------------------------------------|
| Hardware required   | No                     | Yes                                   |
| SDK required        | No                     | Yes (`unitree_sdk2py`)                |
| Camera              | Synthesised (always)   | Optional (SDK VideoClient, with GStreamer fallback) |
| Telemetry           | Simulated              | Real (DDS `rt/sportmodestate`)        |
| Pose                | Dead-reckoned          | Real (`SportModeState_.position`)     |
| Battery             | Simulated              | Real (`rt/lowstate` BMS + power data) |
| CI compatible       | Yes                    | No (hardware-dependent)               |

---

## SDK / Environment Requirements (Go2 mode only)

- Python >= 3.8
- `cyclonedds == 0.10.2` — may require manual build; see the upstream README at `unitreerobotics/unitree_sdk2_python`
- GStreamer with H264 decode support — camera only, fully optional
- Physical ethernet connection to Go2 (`interface_name` is an interface name such as `enp2s0`, **not** an IP address)

**SDK install (source, recommended):**
```bash
git clone https://github.com/unitreerobotics/unitree_sdk2_python
pip install -e unitree_sdk2_python
```

**SDK install (PyPI — verify version compatibility first):**
```bash
pip install unitree_sdk2py
```

---

## Config Reference

`config/app_config.yaml` — all fields shown with defaults:

```yaml
robot:
  mode: mock            # mock | go2
  interface_name: eth0  # network interface name (NOT an IP) — go2 mode only
  camera_enabled: false # enables the dashboard camera stream in go2 mode
  max_vx: 0.5           # m/s clamp applied by ControlCore
  max_vyaw: 1.0         # rad/s clamp applied by ControlCore

telemetry:
  hz: 5                 # telemetry poll and WebSocket push rate

camera:
  fps: 10
  width: 640
  height: 480
  jpeg_quality: 70

realsense:
  enabled: false           # optional Intel RealSense D435i service
  width: 640
  height: 480
  fps: 15
  enable_color: true
  enable_depth: true
  startup_required: false  # fail server startup if the camera is required but unavailable

control:
  watchdog_timeout_ms: 500   # manual teleop dead-man timeout

analysis:
  frame_diff_threshold: 0.25

server:
  host: 0.0.0.0
  port: 8000

storage:
  runs_dir: runs

logging:
  level: INFO
```

---

## Install

Create a Python 3.11+ environment and install:

```bash
pip install -r requirements.txt
```

For Go2 hardware mode, also install the SDK (see above).

For Intel RealSense D435i support, install `pyrealsense2` in the same environment:

```bash
pip install pyrealsense2
```

---

## Running in Mock Mode

```bash
python -m src.main
# or with an explicit config path:
python -m src.main --config config/app_config.yaml
```

The default config has `robot.mode: mock`, so no hardware or SDK is required.

---

## Running in Go2 Mode

```bash
# 1. Ensure Go2 is connected via ethernet on interface enp2s0
# 2. Ensure unitree_sdk2py is installed
# 3. Optionally install pyrealsense2 if you want D435i support
# 4. Set mode in config/app_config.yaml:
#      robot:
#        mode: go2
#        interface_name: enp2s0
#        camera_enabled: true    # enables the dashboard camera stream
#      realsense:
#        enabled: true
#        startup_required: false # set true only if the external camera must be present

python -m src.main --config config/app_config.yaml
```

If the SDK is missing, the server exits immediately with a clear error message before any port is bound.

---

## Open The Dashboard

```
http://127.0.0.1:8000/
```

---

## Start A Mission

Use the dashboard or:

```bash
curl -X POST http://127.0.0.1:8000/api/mission/start \
  -H "Content-Type: application/json" \
  -d '{"route_id":"demo_route"}'
```

The demo route lives at `config/routes/demo_route.json`.

---

## Manual Override Flow

1. Take manual mode: dashboard button or `POST /api/mode/manual/take`
2. If the robot is seated or was previously damped by ESTOP, activate it first: `POST /api/robot/activate`
3. Teleop commands: `POST /api/teleop/cmd`
4. Manual takeover pauses the active mission
5. Releasing manual mode does **not** resume the mission
6. Resume requires: `POST /api/mission/resume`

---

## ESTOP Flow

1. Trigger: `POST /api/mode/estop`
2. All motion commands are blocked centrally and the robot is stopped with passive damping
3. Reset: `POST /api/mode/reset-estop`
4. Re-activate posture before moving again: `POST /api/robot/activate`
5. If ESTOP interrupted a mission, start a new mission explicitly

---

## Run Folder Layout

```
runs/mission_<id>/
├── mission_meta.json
├── event_log.jsonl
├── telemetry.jsonl
├── images/
├── analysis/
├── realsense/
└── final_report.json
```

When `realsense.enabled: true`, each checkpoint can add:
- `realsense/<waypoint>_<timestamp>_color.jpg`
- `realsense/<waypoint>_<timestamp>_depth.npy`
- `realsense/<waypoint>_<timestamp>_depth_preview.png`

The checkpoint entry in `final_report.json` also includes structured `sensor_captures.realsense` metadata with status, timestamps, frame ids, relative artifact paths, resolution, and any available intrinsics.

---

## Tests

```bash
pytest
```

All tests are hardware-free and run against mock adapters. Go2-specific paths are covered by patching `SDK_AVAILABLE`.

---

## Known Limitations

- **Scripted motion only** — no autonomous navigation, SLAM, or obstacle avoidance
- **Normal stop vs ESTOP are different** — normal stop uses `StopMove()` to keep posture; ESTOP adds `Damp()`, which requires `POST /api/robot/activate` before motion resumes
- **Camera reliability depends on robot services** — the adapter now prefers Unitree `VideoClient` and falls back to the older UDP/GStreamer path when SDK camera frames are unavailable
- **RealSense is an additional sensor, not a replacement camera path** — checkpoint analysis still uses the existing robot/mock frame path; the D435i adds optional RGB-D artifacts and reports a clear unavailable status when `pyrealsense2` is missing or the device is disconnected
- **Detailed fault text is still partly generic** — Unitree exposes `SportModeState_.error_code`, but this repo does not have an official per-bit decoder, so the dashboard shows the raw code, hex value, active bits, and related service/BMS warnings
- **Timed velocity pulses, not waypoints** — each mission step issues `Move(vx, vy, vyaw)` for a fixed `duration_sec`; actual displacement depends on floor friction and robot state
- **ChannelFactory is a process singleton** — `interface_name` is set on first `connect()` call and cannot be changed without restarting the process

---

## What "Compatible with Go2 through Python SDK" Means

This repo controls Go2 via `SportClient.Move(vx, vy, vyaw)` from `unitree_sdk2py`. It does **not** use ROS, Nav2, or any localisation stack. Motion is scripted: each mission step issues a velocity command for a fixed duration, then stops. State feedback comes from DDS subscriptions to `rt/sportmodestate` (`SportModeState_`) and `rt/lowstate` (`LowState_`), while the dashboard camera prefers the SDK `VideoClient`. All SDK work is isolated to `src/robot/go2_adapter.py`.
