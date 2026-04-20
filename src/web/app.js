// ── Element references ──────────────────────────────────────────────────────
const robotModeEl = document.getElementById("robotMode");
const missionStatusEl = document.getElementById("missionStatus");
const effectiveBadgeEl = document.getElementById("effectiveBadge");
const missionIdEl = document.getElementById("missionId");
const routeValueEl = document.getElementById("routeValue");
const activeStepEl = document.getElementById("activeStep");
const batteryEl = document.getElementById("battery");
const batteryPowerEl = document.getElementById("batteryPower");
const batteryCyclesEl = document.getElementById("batteryCycles");
const poseEl = document.getElementById("pose");
const faultsEl = document.getElementById("faults");
const cameraStatusEl = document.getElementById("cameraStatus");
const cameraFeedEl = document.getElementById("cameraFeed");
const eventLogEl = document.getElementById("eventLog");
const routeInput = document.getElementById("routeId");

// State panel
const stConnectionEl = document.getElementById("stConnection");
const stEffectiveEl = document.getElementById("stEffective");
const stRequestedEl = document.getElementById("stRequested");
const stMotionModeEl = document.getElementById("stMotionMode");
const stSportErrorEl = document.getElementById("stSportError");
const stBmsEl = document.getElementById("stBms");
const stBatteryEl = document.getElementById("stBattery");
const stPoseEl = document.getElementById("stPose");
const stLastOkEl = document.getElementById("stLastOk");
const stLastRejectedEl = document.getElementById("stLastRejected");
const stLastTsEl = document.getElementById("stLastTs");

// History panel
const historyLevelEl = document.getElementById("historyLevel");
const historyCategoryEl = document.getElementById("historyCategory");
const historyRefreshBtn = document.getElementById("historyRefreshBtn");
const historyCopyBtn = document.getElementById("historyCopyBtn");
const historyLogEl = document.getElementById("historyLog");

// ── State ───────────────────────────────────────────────────────────────────
const pressedKeys = new Set();
let manualActive = false;
let teleopTimer = null;
let currentEffectiveState = "";

// Teleop speed limits (adjustable at runtime)
let speedVx   = 0.40;  // m/s forward/back
let speedVy   = 0.30;  // m/s left/right
let speedVyaw = 0.60;  // rad/s yaw

const SPEED_LIMITS = {
  vx:   { min: 0.22, max: 0.80, step: 0.02 },
  vy:   { min: 0.22, max: 0.60, step: 0.02 },
  vyaw: { min: 0.45, max: 1.50, step: 0.05 },
};

function clampSpeed(val, axis) {
  const { min, max } = SPEED_LIMITS[axis];
  return Math.min(max, Math.max(min, val));
}

function updateSpeedDisplay() {
  const vxEl   = document.getElementById("vxInput");
  const vyEl   = document.getElementById("vyInput");
  const vyawEl = document.getElementById("vyawInput");
  if (vxEl)   vxEl.value   = speedVx.toFixed(2);
  if (vyEl)   vyEl.value   = speedVy.toFixed(2);
  if (vyawEl) vyawEl.value = speedVyaw.toFixed(2);
}

function bindSpeedControls() {
  const cfg = [
    { dec: "vxDec",   inc: "vxInc",   input: "vxInput",   axis: "vx",   get: () => speedVx,   set: v => { speedVx   = v; } },
    { dec: "vyDec",   inc: "vyInc",   input: "vyInput",   axis: "vy",   get: () => speedVy,   set: v => { speedVy   = v; } },
    { dec: "vyawDec", inc: "vyawInc", input: "vyawInput", axis: "vyaw", get: () => speedVyaw, set: v => { speedVyaw = v; } },
  ];
  for (const { dec, inc, input, axis, get, set } of cfg) {
    const { step } = SPEED_LIMITS[axis];
    document.getElementById(dec).addEventListener("click", () => {
      set(clampSpeed(get() - step, axis));
      updateSpeedDisplay();
    });
    document.getElementById(inc).addEventListener("click", () => {
      set(clampSpeed(get() + step, axis));
      updateSpeedDisplay();
    });
    document.getElementById(input).addEventListener("change", (e) => {
      const val = parseFloat(e.target.value);
      if (!isNaN(val)) set(clampSpeed(val, axis));
      updateSpeedDisplay();
    });
  }
}

// Actions that are valid per effective state
const ACTION_ALLOWED_STATES = {
  stand_up:     ["idle", "standing", "ready", "connecting"],
  stop_motion:  ["ready", "moving", "standing", "paused"],
  pause:        ["ready", "moving"],
  resume:       ["paused"],
  manual_mode:  ["ready", "standing", "moving"],
  auto_mode:    ["ready", "standing", "moving", "paused"],
  damping_on:   ["ready", "moving", "standing"],
  reset_fault:  ["error", "damping", "standing_lock", "estop"],
};

// CSS class applied to the state indicator based on effective state
const STATE_CSS = {
  disconnected:   "state-disconnected",
  connecting:     "state-connecting",
  idle:           "state-idle",
  standing:       "state-standing",
  ready:          "state-ready",
  moving:         "state-moving",
  paused:         "state-paused",
  damping:        "state-damping",
  standing_lock:  "state-standing-lock",
  error:          "state-error",
  estop:          "state-estop",
};

// ── Utilities ────────────────────────────────────────────────────────────────
function addEventLine(message) {
  const item = document.createElement("li");
  item.textContent = message;
  eventLogEl.prepend(item);
  while (eventLogEl.children.length > 50) {
    eventLogEl.removeChild(eventLogEl.lastChild);
  }
}

async function postJson(url, body = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || payload.message || "request failed";
    addEventLine(`error: ${detail}`);
    throw new Error(detail);
  }
  if (payload.message) {
    addEventLine(payload.message);
  }
  return payload;
}

// ── State panel ──────────────────────────────────────────────────────────────
function updateStatePanel(data) {
  if (!data) return;
  currentEffectiveState = data.effective_state || "";

  stConnectionEl.textContent = data.connection || "—";

  // Effective state with color class
  const cssClass = STATE_CSS[currentEffectiveState] || "";
  stEffectiveEl.textContent = currentEffectiveState || "—";
  stEffectiveEl.className = "state-indicator " + cssClass;

  // Header badge
  effectiveBadgeEl.textContent = `State: ${currentEffectiveState || "—"}`;
  effectiveBadgeEl.className = "badge state-badge " + cssClass;

  stRequestedEl.textContent = data.requested_state || "—";
  stMotionModeEl.textContent = data.motion_mode || "—";

  const se = data.sport_mode_error;
  if (se) {
    const raw = se.code != null ? `0x${se.code.toString(16).toUpperCase()}` : "—";
    stSportErrorEl.textContent = `${raw} → ${se.decoded || "—"}`;
    stSportErrorEl.className = se.decoded && se.decoded !== "none" ? "fault-text" : "";
  } else {
    stSportErrorEl.textContent = "—";
  }

  const bms = data.bms_flags;
  if (bms) {
    stBmsEl.textContent = `${bms.raw || "—"} → ${bms.decoded || "—"}`;
    stBmsEl.className = bms.decoded && bms.decoded !== "ok" ? "fault-text" : "";
  } else {
    stBmsEl.textContent = "—";
  }

  const bat = data.battery;
  if (bat) {
    const pct = bat.percent != null ? `${Number(bat.percent).toFixed(1)}%` : "—";
    const v = bat.voltage != null ? `${Number(bat.voltage).toFixed(2)}V` : "—";
    const a = bat.current != null ? `${Number(bat.current).toFixed(2)}A` : "—";
    stBatteryEl.textContent = `${pct}  ${v} / ${a}`;
  } else {
    stBatteryEl.textContent = "—";
  }

  if (data.pose) {
    stPoseEl.textContent = `x=${data.pose.x.toFixed(2)} y=${data.pose.y.toFixed(2)} yaw=${data.pose.yaw.toFixed(2)}`;
  } else {
    stPoseEl.textContent = "—";
  }

  stLastOkEl.textContent = data.last_command_ok || "—";
  stLastRejectedEl.textContent = data.last_command_rejected || "—";
  stLastTsEl.textContent = data.last_transition_ts ? new Date(data.last_transition_ts).toLocaleString() : "—";

  updateActionButtonStates();
}

function updateActionButtonStates() {
  document.querySelectorAll("[data-action]").forEach((btn) => {
    const action = btn.dataset.action;
    const allowed = (btn.dataset.allow || "").split(",");
    btn.disabled = !allowed.includes(currentEffectiveState);
  });
}

async function refreshStatePanel() {
  try {
    const resp = await fetch("/api/robot/status");
    if (resp.ok) {
      updateStatePanel(await resp.json());
    }
  } catch (_e) {}
}

// ── Control panel actions ─────────────────────────────────────────────────────
function bindActionButtons() {
  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.action;
      try {
        const result = await postJson("/api/robot/action", { action });
        addEventLine(`[action] ${action}: ${result.success ? "ok" : "rejected"} — ${result.reason || result.new_state}`);
        await refreshStatePanel();
      } catch (_e) {}
    });
  });
}

// ── History panel ──────────────────────────────────────────────────────────────
function renderHistoryEntry(record) {
  const li = document.createElement("li");
  li.className = `history-entry history-level-${record.level}`;
  const ts = new Date(record.ts).toLocaleString();
  const detailStr = record.details && Object.keys(record.details).length
    ? " | " + JSON.stringify(record.details)
    : "";
  li.textContent = `[${ts}] [${record.level.toUpperCase()}] [${record.category}] ${record.message}${detailStr}`;

  // Single entry copy button
  const copyBtn = document.createElement("button");
  copyBtn.textContent = "Copy";
  copyBtn.className = "copy-entry-btn";
  copyBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(JSON.stringify(record, null, 2)).catch(() => {});
  });
  li.appendChild(copyBtn);
  return li;
}

async function refreshHistory() {
  const level = historyLevelEl.value;
  const category = historyCategoryEl.value;
  const params = new URLSearchParams({ limit: "100" });
  if (level) params.set("level", level);
  if (category) params.set("category", category);
  try {
    const resp = await fetch(`/api/robot/history?${params}`);
    if (!resp.ok) return;
    const data = await resp.json();
    historyLogEl.innerHTML = "";
    (data.records || []).forEach((r) => historyLogEl.appendChild(renderHistoryEntry(r)));
  } catch (_e) {}
}

function bindHistoryPanel() {
  historyRefreshBtn.addEventListener("click", refreshHistory);
  historyCopyBtn.addEventListener("click", async () => {
    const items = Array.from(historyLogEl.querySelectorAll("li")).map((li) => li.textContent.replace(/Copy$/, "").trim());
    navigator.clipboard.writeText(items.join("\n")).catch(() => {});
  });
  historyLevelEl.addEventListener("change", refreshHistory);
  historyCategoryEl.addEventListener("change", refreshHistory);
}

// ── Telemetry (existing) ────────────────────────────────────────────────────
function updateTelemetry(data) {
  const robotState = data.robot_state || {};
  manualActive = data.mode === "MANUAL";
  robotModeEl.textContent = `Mode: ${data.mode}`;
  missionStatusEl.textContent = `Mission: ${data.mission_status}`;
  missionIdEl.textContent = data.mission_id || "-";
  routeValueEl.textContent = data.route_id || "-";
  activeStepEl.textContent = data.active_step_id || "-";
  batteryEl.textContent = robotState.battery_percent != null ? `${Number(robotState.battery_percent).toFixed(1)}%` : "-";
  batteryPowerEl.textContent =
    robotState.battery_voltage_v != null || robotState.battery_current_a != null
      ? `${robotState.battery_voltage_v != null ? Number(robotState.battery_voltage_v).toFixed(2) : "-"} V / ${
          robotState.battery_current_a != null ? Number(robotState.battery_current_a).toFixed(2) : "-"
        } A`
      : "-";
  batteryCyclesEl.textContent = robotState.battery_cycles != null ? String(robotState.battery_cycles) : "-";
  faultsEl.textContent = robotState.faults?.length ? robotState.faults.join("\n") : "No active faults.";
  cameraStatusEl.textContent = robotState.camera_status || "Waiting for camera frames.";
  if (data.pose) {
    poseEl.textContent = `x=${data.pose.x.toFixed(2)} y=${data.pose.y.toFixed(2)} yaw=${data.pose.yaw.toFixed(2)}`;
  } else {
    poseEl.textContent = "-";
  }
}

async function refreshMissionStatus() {
  const response = await fetch("/api/mission/current");
  const payload = await response.json();
  robotModeEl.textContent = `Mode: ${payload.robot_mode}`;
  missionStatusEl.textContent = `Mission: ${payload.mission_status}`;
  missionIdEl.textContent = payload.mission_id || "-";
  routeValueEl.textContent = payload.route_id || "-";
  activeStepEl.textContent = payload.active_step_id || "-";
  manualActive = payload.robot_mode === "MANUAL";
}

function computeTeleopCommand() {
  let vx = 0.0;
  let vy = 0.0;
  let vyaw = 0.0;
  // vx=0.4 is above the BalanceStand→Locomotion trigger threshold (~0.3 m/s).
  // At 0.2 the attitude controller just leans the body forward without engaging the gait.
  if (pressedKeys.has("KeyW") || pressedKeys.has("ArrowUp")) vx += speedVx;
  if (pressedKeys.has("KeyS") || pressedKeys.has("ArrowDown")) vx -= speedVx;
  if (pressedKeys.has("KeyA") || pressedKeys.has("ArrowLeft")) vy += speedVy;
  if (pressedKeys.has("KeyD") || pressedKeys.has("ArrowRight")) vy -= speedVy;
  if (pressedKeys.has("KeyQ")) vyaw += speedVyaw;
  if (pressedKeys.has("KeyE")) vyaw -= speedVyaw;
  if (pressedKeys.has("Space")) {
    vx = 0.0;
    vy = 0.0;
    vyaw = 0.0;
  }
  return { vx, vy, vyaw, ts: Date.now() / 1000 };
}

function startTeleopLoop() {
  if (teleopTimer) return;
  teleopTimer = window.setInterval(async () => {
    if (!manualActive || pressedKeys.size === 0) return;
    try {
      await postJson("/api/teleop/cmd", computeTeleopCommand());
    } catch (_error) {
      stopTeleopLoop();
    }
  }, 100);
}

function stopTeleopLoop(sendStop = true) {
  if (teleopTimer) {
    window.clearInterval(teleopTimer);
    teleopTimer = null;
  }
  if (sendStop && manualActive) {
    postJson("/api/teleop/cmd", { vx: 0.0, vy: 0.0, vyaw: 0.0, ts: Date.now() / 1000 }).catch(() => {});
  }
}

function bindButtons() {
  document.getElementById("startBtn").addEventListener("click", () => postJson("/api/mission/start", { route_id: routeInput.value }));
  document.getElementById("pauseBtn").addEventListener("click", () => postJson("/api/mission/pause"));
  document.getElementById("resumeBtn").addEventListener("click", () => postJson("/api/mission/resume"));
  document.getElementById("abortBtn").addEventListener("click", () => postJson("/api/mission/abort"));
  document.getElementById("takeManualBtn").addEventListener("click", async () => {
    await postJson("/api/mode/manual/take");
    manualActive = true;
  });
  document.getElementById("releaseManualBtn").addEventListener("click", async () => {
    await postJson("/api/mode/manual/release");
    manualActive = false;
    stopTeleopLoop(false);
  });
  document.getElementById("activateRobotBtn").addEventListener("click", () => postJson("/api/robot/activate"));
  document.getElementById("estopBtn").addEventListener("click", () => postJson("/api/mode/estop"));
  document.getElementById("resetEstopBtn").addEventListener("click", () => postJson("/api/mode/reset-estop"));
}

function bindKeyboard() {
  window.addEventListener("keydown", async (event) => {
    if (event.code === "KeyX") {
      await postJson("/api/mode/estop");
      return;
    }
    // Speed adjustments work even outside manual mode
    const { step: sVx }   = SPEED_LIMITS.vx;
    const { step: sVy }   = SPEED_LIMITS.vy;
    const { step: sVyaw } = SPEED_LIMITS.vyaw;
    if (event.code === "BracketLeft")  { speedVx   = clampSpeed(speedVx   - sVx,   "vx");   updateSpeedDisplay(); return; }
    if (event.code === "BracketRight") { speedVx   = clampSpeed(speedVx   + sVx,   "vx");   updateSpeedDisplay(); return; }
    if (event.code === "Comma")        { speedVy   = clampSpeed(speedVy   - sVy,   "vy");   updateSpeedDisplay(); return; }
    if (event.code === "Period")       { speedVy   = clampSpeed(speedVy   + sVy,   "vy");   updateSpeedDisplay(); return; }
    if (event.code === "Minus")        { speedVyaw = clampSpeed(speedVyaw - sVyaw, "vyaw"); updateSpeedDisplay(); return; }
    if (event.code === "Equal")        { speedVyaw = clampSpeed(speedVyaw + sVyaw, "vyaw"); updateSpeedDisplay(); return; }

    if (!manualActive) return;
    if (["KeyW", "KeyS", "KeyA", "KeyD", "KeyQ", "KeyE", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(event.code)) {
      event.preventDefault();
      pressedKeys.add(event.code);
      startTeleopLoop();
    }
  });

  window.addEventListener("keyup", (event) => {
    if (!["KeyW", "KeyS", "KeyA", "KeyD", "KeyQ", "KeyE", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(event.code)) return;
    pressedKeys.delete(event.code);
    if (pressedKeys.size === 0) {
      stopTeleopLoop(true);
    }
  });
}

function connectTelemetry() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws/telemetry`);
  ws.onmessage = (message) => updateTelemetry(JSON.parse(message.data));
  ws.onclose = () => window.setTimeout(connectTelemetry, 1000);
}

function connectEvents() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws/events`);
  ws.onmessage = (message) => {
    const event = JSON.parse(message.data);
    addEventLine(`${event.ts} | ${event.event}`);
  };
  ws.onclose = () => window.setTimeout(connectEvents, 1000);
}

function bindCameraFeed() {
  cameraFeedEl.addEventListener("error", () => {
    cameraStatusEl.textContent = "Camera stream endpoint is reachable but no MJPEG frames are arriving.";
  });
}

// ── Bootstrap ───────────────────────────────────────────────────────────────
updateSpeedDisplay();
bindSpeedControls();
bindButtons();
bindActionButtons();
bindKeyboard();
bindCameraFeed();
bindHistoryPanel();
connectTelemetry();
connectEvents();
refreshMissionStatus();
refreshStatePanel();
refreshHistory();
window.setInterval(refreshMissionStatus, 1000);
window.setInterval(refreshStatePanel, 1000);
window.setInterval(refreshHistory, 5000);
