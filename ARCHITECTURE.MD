You are generating a runnable Python MVP for autonomous inspection on Unitree Go2.

# Hard scope
Python 3.11+ only. FastAPI, Uvicorn, OpenCV, numpy, PyYAML, pydantic v2, pytest.
No ROS/ROS2, Nav2, SLAM, RViz, Gazebo, BIM, digital twin, manipulator, fleet
management, custom navigation stack, auth framework, React/Vue, or build tools
for the frontend.

This is a safe test-environment MVP. Do not claim production or industrial
readiness. Do not invent Unitree SDK methods; isolate every uncertain SDK call
behind one adapter and provide a working mock.

# What the system does
1. Loads a scripted JSON route.
2. Executes steps sequentially: `move`, `rotate`, `checkpoint`, `stop`.
3. At checkpoints: settle, capture camera frame, capture telemetry snapshot,
   run one image analyzer, log results.
4. Streams live telemetry + events over WebSocket and live camera over MJPEG
   to a plain HTML/JS operator console.
5. Supports manual override (pauses mission, explicit resume required), ESTOP
   (highest priority, blocks all motion until reset), and a watchdog that stops
   the robot if manual teleop commands stop arriving.
6. Writes a per-mission run folder and a final JSON report.

# Priority and modes
Modes: AUTO, MANUAL, ESTOP. (SERVICE is a stub state only.)
Priority enforced in one place: ESTOP > MANUAL > AUTO.
Manual override never auto-resumes the mission.

# Mission states
IDLE, STARTING, RUNNING, PAUSED_MANUAL, COMPLETED, ABORTED, FAILED, ESTOPPED.

# Route schema
{
  "route_id": "demo_route_v1",
  "steps": [
    {"id":"s1","type":"move","vx":0.2,"vy":0.0,"vyaw":0.0,"duration_sec":1.5},
    {"id":"s2","type":"checkpoint","waypoint_id":"panel_A","settle_time_sec":1.0,
     "analyzer":"frame_diff","reference_image":"config/reference_images/panel_A_ref.jpg"},
    {"id":"s3","type":"rotate","vyaw":0.5,"duration_sec":1.0},
    {"id":"s4","type":"stop"}
  ]
}
Velocities are in robot body frame. Validate with pydantic.

# File layout (exact — do not add files)
project/
  requirements.txt
  README.md
  config/
    app_config.yaml
    routes/demo_route.json
    reference_images/panel_A_ref.jpg   # placeholder; README explains
  src/
    main.py              # entrypoint: parse args, build app, run uvicorn
    config.py            # YAML -> pydantic settings
    models.py            # enums, route/step models, telemetry snapshot, report
    robot_adapter.py     # ONLY place SDK-specific code lives; Mock + Real stubs
    telemetry.py         # polls adapter, keeps latest snapshot, JSONL writer
    control.py           # ModeManager + CommandArbiter + Watchdog + ESTOP in one module
    mission.py           # route loader, state machine, step executor, checkpoint handler
    analysis.py          # frame_diff analyzer + simple_presence stub, normalized result
    storage.py           # run folder layout, event log, image writer, final report
    streaming.py         # WS telemetry, WS events, MJPEG camera
    api.py               # FastAPI app, all routes, WS handlers
    web/
      index.html
      app.js
      styles.css
  runs/                  # created at runtime
  tests/
    test_route_loader.py
    test_control_priority.py
    test_report_builder.py
    test_api_smoke.py

# RobotAdapter interface (the ONLY SDK surface)
class RobotAdapter(Protocol):
    def connect(self) -> None
    def disconnect(self) -> None
    def send_velocity(self, vx: float, vy: float, vyaw: float) -> None
    def stop(self) -> None
    def get_state(self) -> RobotState       # battery, imu, faults; all Optional
    def get_pose(self) -> Optional[Pose]    # body-frame odometry if available
    def capture_frame(self) -> Optional[np.ndarray]  # BGR
    # LiDAR deferred: method exists, returns None in MVP

Provide two implementations:
- MockRobotAdapter: synthesizes telemetry, generates a moving-pattern camera
  frame at configured FPS, integrates simple velocity into a fake pose.
- Go2RobotAdapter: imports unitree_sdk2_python lazily inside connect(); every
  uncertain call wrapped with a precise `# TODO(sdk):` comment and a safe
  fallback that raises NotImplementedError with a clear message. Do NOT guess
  method names — document exactly what the integrator must fill in.

Selection via config: `robot.mode: mock | real`.

# Control module contract
One class `ControlCore` owns: current mode, mission state, last teleop
timestamp, ESTOP latch. Every motion command (auto or manual) passes through
`ControlCore.submit(cmd, source)`. Rules:
- ESTOP latched → drop all, call adapter.stop() once.
- Mode == MANUAL → drop AUTO commands.
- Mode == AUTO → drop MANUAL commands unless source triggers mode switch
  (explicit "take manual" endpoint).
Watchdog: if MANUAL and no teleop cmd received for `watchdog_timeout_ms`,
adapter.stop() and log event. Mission is NOT auto-resumed.

# Mission executor
Sequential step loop running in a background thread (not the event loop).
- `move`/`rotate`: submit velocity at ~10 Hz for `duration_sec`, then stop.
- `checkpoint`: stop, sleep `settle_time_sec`, capture frame + telemetry,
  run configured analyzer, write image + analysis JSON + event.
- `stop`: ensure velocity zero.
Between every step check: pause/abort/ESTOP flags. On manual override, drop
into PAUSED_MANUAL and wait for explicit resume or abort.

# Analyzer contract
def analyze(frame: np.ndarray, params: dict) -> dict
Return:
{"analyzer": "...", "status": "ok|error|not_configured",
 "result": "...", "score": float|None, "details": {...}}
Implement `frame_diff` (mean abs diff vs reference, threshold from config).
`simple_presence` returns `{"result":"not_configured"}`.

# Storage
runs/mission_<id>/
  mission_meta.json
  event_log.jsonl
  telemetry.jsonl
  images/<waypoint_id>_<ts>.jpg
  analysis/<waypoint_id>.json
  final_report.json

Final report fields: mission_id, route_id, mission_status, started_at,
finished_at, steps_executed, checkpoints[], analysis_results[],
mode_transitions[], errors[], warnings[].

# API (FastAPI)
GET  /api/status
GET  /api/mission/current
POST /api/mission/start           body: {route_id}
POST /api/mission/pause
POST /api/mission/resume
POST /api/mission/abort
POST /api/mode/manual/take
POST /api/mode/manual/release
POST /api/mode/estop
POST /api/mode/reset-estop
POST /api/teleop/cmd              body: {vx,vy,vyaw,ts}  (refreshes watchdog)
WS   /ws/telemetry                ~5 Hz push
WS   /ws/events                   push on change
GET  /stream/camera               MJPEG (multipart/x-mixed-replace)
GET  /                            serves web/index.html

All request/response bodies are pydantic models.

# Operator console (single HTML file + app.js + styles.css)
Panels: mode + mission state + active route + step, battery, faults, MJPEG
camera preview, event log (last 50). Buttons: Start, Pause, Resume, Abort,
Take Manual, Release Manual, ESTOP, Reset ESTOP. Keyboard teleop active only
while Manual is held: W/S forward-back, A/D yaw, Space stop, X estop. Send
/api/teleop/cmd at 10 Hz while keys are down; stop sending on keyup.

No frontend build step. No frameworks. Vanilla fetch + WebSocket.

# Concurrency model
- FastAPI/uvicorn owns the asyncio loop.
- One background thread: telemetry polling.
- One background thread: camera capture → latest-frame slot (single-slot,
  overwrite, lock-protected).
- One background thread: mission executor.
- WebSocket pushers are async tasks reading latest slots.
- Every thread has a stop event and joins on shutdown.

# Config (app_config.yaml)
robot: {mode: mock, max_vx: 0.5, max_vyaw: 1.0}
telemetry: {hz: 5}
camera: {fps: 10, width: 640, height: 480, jpeg_quality: 70}
control: {watchdog_timeout_ms: 500}
analysis: {frame_diff_threshold: 0.25}
server: {host: 0.0.0.0, port: 8000}
storage: {runs_dir: runs}
logging: {level: INFO}

# Tests (pytest, fast, no hardware)
- test_route_loader: valid + invalid route JSON.
- test_control_priority: ESTOP blocks all; MANUAL blocks AUTO; resume needs
  explicit call; watchdog stops on stale teleop.
- test_report_builder: required fields present after a mock mission.
- test_api_smoke: TestClient hits /api/status, /api/mission/start with mock
  adapter, verifies state transitions via /api/mission/current.

# README
One file. Sections: what this is / what it is not; install; run mock
(`python -m src.main --config config/app_config.yaml`); open dashboard;
start mission; manual override flow; ESTOP flow; where real SDK goes
(`robot_adapter.py::Go2RobotAdapter` TODOs); run folder layout; tests.

# Output rules
- Generate every listed file with full contents.
- No placeholder "..." bodies. Either implement or raise NotImplementedError
  with a clear TODO comment.
- No speculative SDK calls outside `robot_adapter.py`.
- Keep total code small and readable; favor directness over abstraction.
In this MVP, “autonomous route” means scripted execution in a known safe test area using predefined motion steps and checkpoints. This MVP does not implement full waypoint localization, obstacle avoidance, SLAM, or production-grade navigation. Do not describe it as general autonomous navigation.
If real Go2 SDK integration is incomplete, the whole system must still run end-to-end in mock mode, including dashboard, mission execution, telemetry, camera stream, storage, and tests.
