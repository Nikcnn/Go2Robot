# Go2 Inspection MVP

## What This Is
A safe test-environment MVP for scripted inspection on a Unitree Go2. It runs end-to-end in mock mode with a FastAPI server, a plain HTML dashboard, a scripted JSON route executor, synthetic telemetry, a synthetic camera stream, per-mission storage, and fast hardware-free tests.

## What This Is Not
This is not full autonomous navigation. It does not implement ROS, ROS2, Nav2, SLAM, RViz, Gazebo, obstacle avoidance, production safety systems, fleet management, or a frontend build pipeline.

---

## Architecture

HTTP / WebSocket clients
│
▼
FastAPI (src/api.py)
│
▼
ControlCore (src/control.py)
┌─────────────────────────────────────────────────────┐
│ Priority: ESTOP > MANUAL > AUTO │
│ Watchdog: zeroes velocity on stale teleop commands │
│ can_move guard: blocks non-zero velocity when │
│ adapter reports locomotion not ready │
└─────────────────────────────────────────────────────┘
│ send_velocity / stop / ensure_motion_ready / get_state
▼
RobotAdapterProtocol (src/robot/robot_adapter.py)
╱ ╲
MockRobotAdapter Go2RobotAdapter
(always available) (requires SDK + hardware)

text

**Control layer rules:**
- `ESTOP` is latched; all motion commands are blocked until explicitly reset and the robot is re-activated
- `MANUAL` mode pauses any running mission; release does **not** auto-resume
- `AUTO` is the only mode where mission steps issue `send_velocity`
- `ControlCore.submit()` additionally checks `adapter.can_move` before forwarding any non-zero velocity command
- A teleop watchdog thread fires `stop()` if no MANUAL command arrives within `watchdog_timeout_ms`

**Locomotion state machine (`Go2RobotAdapter`):**

disconnected → idle → activating → ready ↔ moving → damped
↘ fault

text

| State         | can_move | Triggered by                            |
|---------------|----------|-----------------------------------------|
| `disconnected`| False    | Before `connect()`                      |
| `idle`        | False    | After connect, before `activate()`      |
| `activating`  | False    | During `StandUp` execution              |
| `ready`       | True     | `StandUp` complete / `reset_estop()`    |
| `moving`      | True     | `send_velocity()` with non-zero command |
| `damped`      | False    | `emergency_stop()` → `Damp()`           |
| `fault`       | False    | SDK error during motion                 |

**Mission executor (`src/mission.py`):**
- Loads a JSON route file, executes steps sequentially
- Calls `ensure_motion_ready()` before the first movement step and after any post-pause resumption
- Calls `send_velocity` only when `ControlCore.wait_until_runnable()` returns True
- Checkpoint steps call `capture_frame` + telemetry snapshot + `analyze()` → `AnalysisResult` + storage

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
| Locomotion states   | Tracked (mock)         | DDS-backed (`SportModeState_.mode`)   |
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
# 3. Set mode in config/app_config.yaml:
#      robot:
#        mode: go2
#        interface_name: enp2s0
#        camera_enabled: true

python -m src.main --config config/app_config.yaml
```

If the SDK is missing, the server exits immediately with a clear error message before any port is bound.

---

## Open The Dashboard

http://127.0.0.1:8000/

text

`GET /api/status` now includes: `control_mode`, `locomotion_state`, `can_move`, `block_reason`, `activation_required`.

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
5. Releasing manual mode (`POST /api/mode/manual/release`) sets mode back to `AUTO` but the mission stays `PAUSED_MANUAL`
6. Resume requires an explicit: `POST /api/mission/resume`

---

## ESTOP Flow

1. Trigger: `POST /api/mode/estop`
2. `emergency_stop()` issues `StopMove()` + `Damp()`; locomotion state → `damped`; `can_move = False`
3. All motion commands are blocked centrally (ESTOP latch + `can_move` guard)
4. Reset: `POST /api/mode/reset-estop` — clears the latch
5. Re-activate posture: `POST /api/robot/activate` → `StandUp` → locomotion state → `ready`; `can_move = True`
6. If ESTOP interrupted a mission, start a new mission explicitly

---

## Control & Mission Flow

The project's movement logic is centred around a hierarchical control system:

1. **Arbitration priority:** ESTOP (latched) > MANUAL > AUTO
   - **ESTOP:** Issues `StopMove + Damp`, sets `locomotion_state=damped`, blocks all commands until reset + re-activation
   - **MANUAL:** Allows teleop via `POST /api/teleop/cmd`. Watchdog zeroes velocity if no command arrives within 500 ms (configurable). Taking manual control pauses any active mission
   - **AUTO:** The only mode where `MissionExecutor` can issue commands; `ControlCore.submit()` additionally checks `adapter.can_move` before forwarding any non-zero velocity

2. **Mission execution:**
   - Missions follow a scripted JSON route (`config/routes/`)
   - `ensure_motion_ready()` is called before the first movement step and after any post-pause resumption
   - Each step issues `Move(vx, vy, vyaw)` for a fixed `duration_sec`
   - `ControlCore.wait_until_runnable()` gates every step

3. **Normal stop vs ESTOP:**
   - Normal stop: `stop()` → `StopMove()` only; posture preserved; `locomotion_state=ready`
   - ESTOP: `emergency_stop()` → `StopMove() + Damp()`; `locomotion_state=damped`; requires full re-activation before motion resumes

---

## Checkpoint Analysis

Every checkpoint step produces a typed `AnalysisResult`:

```python
@dataclass
class AnalysisResult:
    analyzer_name: str
    label: str
    score: float
    passed: bool
    threshold: float
    timestamp: str
```

- `FrameDiffAnalyzer` is the default implementation (frame-difference based)
- `NarrowClassifierHook` is a lightweight classical-CV presence classifier; with `reference_image` it uses histogram + edge similarity, otherwise it falls back to edge/contrast objectness
- `save_checkpoint()` accepts `AnalysisResult | dict`; existing dict callers still work
- Analysis events emit `analyzer_name`, `label`, `passed`, `score` fields

---

## Run Folder Layout

runs/mission_<id>/
├── mission_meta.json
├── event_log.jsonl
├── telemetry.jsonl
├── images/
├── analysis/
└── final_report.json

text

---

## API Status Fields

`GET /api/status` response includes these fields:

| Field                | Type    | Description                                      |
|----------------------|---------|--------------------------------------------------|
| `control_mode`       | string  | Current mode: `AUTO`, `MANUAL`, `ESTOP`          |
| `locomotion_state`   | string  | One of 7 states (see state machine above)        |
| `can_move`           | bool    | Whether the adapter accepts velocity commands    |
| `block_reason`       | string? | Human-readable reason when `can_move=False`      |
| `activation_required`| bool    | True when state is `idle` or `damped`            |

---

## Tests

```bash
pytest
```

85 tests, all hardware-free, run against mock adapters. Go2-specific paths are covered by patching `SDK_AVAILABLE`. Regression tests cover DDS-backed readiness and damping behaviour (`test_go2_adapter.py`) and `NarrowClassifierHook` classification (`test_lifecycle.py`).

---

## Known Limitations

- **Scripted motion only** — no autonomous navigation, SLAM, or obstacle avoidance
- **Normal stop vs ESTOP are different** — normal stop uses `StopMove()` to keep posture; ESTOP adds `Damp()`, which requires `POST /api/robot/activate` before motion resumes
- **`ensure_motion_ready()` checks DDS motion mode** — readiness consults `SportModeState_.mode` and only returns once the robot reaches a ready mode (`balanceStand`, `pose`, or `locomotion`)
- **`GET /api/status` uses synchronized adapter properties** — reads `locomotion_state`, `can_move`, and `block_reason` through locked adapter accessors
- **`NarrowClassifierHook` is lightweight, not task-specific ML** — real classical-CV classifier, but task-specific models may outperform it for narrow domains
- **Camera reliability depends on robot services** — adapter prefers Unitree `VideoClient`, falls back to UDP/GStreamer when SDK camera frames are unavailable
- **Detailed fault text is still partly generic** — `SportModeState_.error_code` is shown as raw code + hex + active bits; no official per-bit decoder
- **Timed velocity pulses, not waypoints** — actual displacement depends on floor friction and robot state
- **`ChannelFactory` is a process singleton** — `interface_name` is set on first `connect()` call; cannot change without restarting the process

---

## Migration Notes (from previous release)

- `RobotState` gains 3 new fields (`locomotion_state`, `can_move`, `block_reason`) with defaults — no config changes needed
- `StatusResponse` gains 5 new fields with defaults — existing API clients receive them automatically
- `save_checkpoint()` signature changed: `analysis_result` is now `AnalysisResult | dict`; existing dict callers still work
- Analysis events now emit `analyzer_name`/`label`/`passed`/`score` instead of `analyzer`/`result`

---

## What "Compatible with Go2 through Python SDK" Means

This repo controls Go2 via `SportClient.Move(vx, vy, vyaw)` from `unitree_sdk2py`. It does **not** use ROS, Nav2, or any localisation stack. Motion is scripted: each mission step issues a velocity command for a fixed duration, then stops. State feedback comes from DDS subscriptions to `rt/sportmodestate` (`SportModeState_`) and `rt/lowstate` (`LowState_`), while the dashboard camera prefers the SDK `VideoClient`. All SDK work is isolated to `src/robot/go2_adapter.py`.