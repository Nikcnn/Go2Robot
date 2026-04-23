const state = {
  overview: null,
  missionDraft: null,
  originalMissionId: "",
  selectedLogCategory: "",
  activeCamera: "built_in",
  loadingMission: false,
  d1: null,
  // Map workspace
  mapMetadata: null,
  mapImage: null,
  mapImageLoadedFor: "",
  mapTool: "place",
  mapView: { offsetX: 0, offsetY: 0, zoom: 1 },
  selectedWaypointIndex: -1,
  yawDrag: null,
  // Mapping mode
  mappingMode: "manual",
  autonomousAvailable: false,
  // Lidar
  lidarFollow: true,
  lidarPreset: "default",
  // Manual takeover tracking
  manualAutoSwitched: false,
  currentMode: null,
};

/* ── Theme (dark / light) ────────────────────────────── */
function initTheme() {
  const saved = localStorage.getItem("go2_theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
  updateThemeIcon(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("go2_theme", next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const btn = $("themeToggleBtn");
  if (!btn) return;
  btn.innerHTML = theme === "dark"
    ? '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>'
    : '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';
  btn.title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
}

initTheme();

function $(id) {
  return document.getElementById(id);
}

function text(id, value) {
  const node = $(id);
  if (node) node.textContent = value == null || value === "" ? "None" : String(value);
}

function showToast(message, type = "info") {
  const item = document.createElement("div");
  item.className = `toast toast-${type}`;
  item.textContent = message;
  $("toastStack").appendChild(item);
  window.setTimeout(() => item.remove(), 5200);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.detail || payload.message || "Request failed.";
    throw new Error(message);
  }
  return payload;
}

function getJson(url) {
  return requestJson(url);
}

function sendJson(url, body = {}, method = "POST") {
  return requestJson(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function setHealthClass(node, ok) {
  node.classList.remove("is-ok", "is-warn", "is-bad");
  node.classList.add(ok ? "is-ok" : "is-bad");
}

function setPill(id, label, ok) {
  const node = $(id);
  node.textContent = label;
  setHealthClass(node, ok);
}

function setDot(id, label, ok) {
  const node = $(id);
  node.textContent = label;
  setHealthClass(node, ok);
}

function safeFixed(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "0.00";
}

function formatTimestampMs(value) {
  const stamp = Number(value);
  if (!Number.isFinite(stamp) || stamp <= 0) return "None";
  return new Date(stamp).toLocaleString();
}

function optionLabel(item) {
  if (!item) return "";
  const count = item.waypoint_count != null ? ` (${item.waypoint_count})` : "";
  return `${item.name || item.id || item.mission_id}${count}`;
}

function setSelectOptions(select, items, emptyLabel) {
  const previous = select.value;
  select.innerHTML = "";
  if (!items || items.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = emptyLabel;
    select.appendChild(option);
    return "";
  }
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.id || item.mission_id || item.name;
    option.textContent = optionLabel(item);
    select.appendChild(option);
  }
  if ([...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  }
  return select.value;
}

function renderOverview(overview) {
  $("statusSentence").textContent = overview.status_sentence || "Checking system...";
  setPill("connectionBadge", `Connection: ${overview.connection.label}`, overview.connection.online);
  setPill("modeBadge", `Mode: ${overview.mode.label}`, !overview.mode.estop_latched);

  $("robotSummary").textContent = overview.connection.online ? "Robot connected" : "Robot not connected";
  $("robotDetail").textContent = `App mode: ${overview.connection.adapter_mode}. Battery: ${
    overview.battery_percent == null ? "unknown" : `${safeFixed(overview.battery_percent, 1)}%`
  }.`;
  setHealthClass($("robotStatusCard"), overview.connection.online);

  const ros = overview.ros || {};
  const mappingRunning = Boolean(ros.mapping && ros.mapping.running);
  const navigationRunning = Boolean(ros.navigation && ros.navigation.running);
  const rosReady = Boolean(ros.ros2_available);
  $("rosSummary").textContent = rosReady ? "ROS command line available" : "ROS command line not found";
  $("rosDetail").textContent = mappingRunning
    ? "Mapping is running."
    : navigationRunning
      ? "Navigation is running."
      : "Mapping and navigation are stopped.";
  setHealthClass($("rosStatusCard"), rosReady);
  setPill("mappingBadge", mappingRunning ? "Mapping: running" : "Mapping: stopped", mappingRunning);
  setPill("navigationBadge", navigationRunning ? "Navigation: running" : "Navigation: stopped", navigationRunning);

  const sensors = overview.sensors || {};
  const sensorList = Object.values(sensors);
  const onlineCount = sensorList.filter((sensor) => sensor.online).length;
  $("sensorSummary").textContent = `${onlineCount} of ${sensorList.length} online`;
  $("sensorDetail").textContent = [
    sensors.built_in_camera?.online ? "Built-in camera online" : "Built-in camera waiting",
    sensors.realsense_d435i?.online ? "D435i online" : "D435i offline",
    sensors.built_in_lidar?.online ? "Lidar path active" : "Lidar waiting",
  ].join(". ");
  setHealthClass($("sensorStatusCard"), onlineCount > 0);

  const ctrlBadge = $("controlModeBadge");
  if (ctrlBadge) {
    ctrlBadge.textContent = `Mode: ${overview.mode.label}`;
    setHealthClass(ctrlBadge, !overview.mode.estop_latched);
  }
  $("technicalDetails").textContent = JSON.stringify(overview, null, 2);
  renderSelectors(overview);
  renderMissionProgress(overview.mission_progress || {});
  renderSensors(sensors);
  renderMappingMode(ros);
  renderTelemetryTile(overview);
  updatePoseHint(overview.pose);
  handleModeChange(overview.mode);
  renderMapCanvas();
}

function renderMappingMode(ros) {
  if (ros && typeof ros.autonomous_exploration_available === "boolean") {
    state.autonomousAvailable = ros.autonomous_exploration_available;
  }
  const running = Boolean(ros && ros.mapping && ros.mapping.running);
  const actualMode = ros && ros.mapping_mode ? ros.mapping_mode : (running ? state.mappingMode : "idle");
  const hint = $("mappingModeHint");
  const banner = $("autonomousRuntimeBanner");
  const mode = state.mappingMode;
  document.querySelectorAll("[data-mapping-mode]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mappingMode === mode);
  });
  if (hint) {
    if (mode === "autonomous") {
      hint.textContent = state.autonomousAvailable
        ? "Autonomous exploration is supported: the robot will drive itself to grow the map."
        : "Autonomous exploration runtime is not yet wired in; SLAM will still launch and you must drive manually.";
    } else {
      hint.textContent = "Operator-guided mapping uses manual driving to build the SLAM map.";
    }
  }
  if (banner) {
    banner.classList.toggle("hidden", mode !== "autonomous" || state.autonomousAvailable);
  }
  if (running && actualMode && ros.mapping_mode_note) {
    const note = $("mappingModeHint");
    if (note && ros.mapping_mode_note) note.textContent = ros.mapping_mode_note;
  }
  const badge = $("mappingBadge");
  if (badge) {
    let label = running ? `Mapping: running (${actualMode})` : "Mapping: stopped";
    badge.textContent = label;
  }
}

function renderTelemetryTile(overview) {
  const pose = overview.pose || {};
  text("tileBattery",
    overview.battery_percent == null ? "—" : `${safeFixed(overview.battery_percent, 1)}%`);
  text("tileMode", overview.mode?.label || "—");
  text("tilePoseX", pose.x != null ? safeFixed(pose.x, 2) : "—");
  text("tilePoseY", pose.y != null ? safeFixed(pose.y, 2) : "—");
  text("tilePoseYaw", pose.yaw != null ? safeFixed(pose.yaw, 2) : "—");
  const tileFaults = $("tileFaults");
  if (tileFaults) {
    const faults = (overview && overview.sensors && overview.sensors.built_in_camera && overview.sensors.built_in_camera.faults) || [];
    tileFaults.textContent = faults.length ? faults.join(", ") : "None";
  }
}

function handleModeChange(mode) {
  if (!mode) return;
  const label = mode.label;
  if (state.currentMode && state.currentMode !== label && label === "MANUAL" && !state.manualAutoSwitched) {
    // Auto-switch to the sensor workspace whenever the operator takes manual control.
    switchTab("sensors");
    state.manualAutoSwitched = true;
  }
  if (label !== "MANUAL") {
    state.manualAutoSwitched = false;
  }
  state.currentMode = label;
}

function renderSelectors(overview) {
  const maps = overview.maps || [];
  const missions = overview.missions || [];
  const selectedMap = setSelectOptions($("missionMapSelect"), maps, "No maps saved yet");
  setSelectOptions($("navigationMapSelect"), maps, "No maps saved yet");
  setSelectOptions($("missionSelect"), missions, "No routes saved yet");
  setSelectOptions($("navigationMissionSelect"), missions, "No routes saved yet");

  if (state.missionDraft && state.missionDraft.map_id) {
    $("missionMapSelect").value = state.missionDraft.map_id;
  } else if (selectedMap) {
    $("missionMapSelect").value = selectedMap;
  }
  const chosen = $("missionMapSelect").value || "";
  if (chosen && chosen !== state.mapImageLoadedFor) {
    loadMapMetadata(chosen);
  } else if (!chosen && state.mapMetadata) {
    state.mapMetadata = null;
    state.mapImage = null;
    state.mapImageLoadedFor = "";
    renderMapCanvas();
  }

  if (!state.missionDraft && missions.length > 0 && !state.loadingMission) {
    loadMission(missions[0].id || missions[0].mission_id, false);
  }
}

function renderMissionProgress(progress) {
  text("activeWaypoint", progress.active_waypoint || "None");
  text("completedWaypoints", `${progress.completed_waypoints || 0} / ${progress.total_waypoints || 0}`);
  text("currentTask", progress.current_task || "None");
  const stateNode = $("missionState");
  const stateLabel = progress.manual_takeover ? "paused by manual takeover" : (progress.state || "idle");
  if (stateNode) stateNode.textContent = stateLabel;
  text("missionManualTakeover", progress.manual_takeover ? "yes" : "no");
  const note = $("missionStateNote");
  if (note) note.textContent = progress.note || "";
}

function updatePoseHint(pose) {
  $("poseHint").textContent = pose
    ? `Current pose: x ${safeFixed(pose.x)}, y ${safeFixed(pose.y)}, yaw ${safeFixed(pose.yaw)}`
    : "Pose is not available yet.";
}

function renderSensors(sensors) {
  const builtIn = sensors.built_in_camera || {};
  const d435i = sensors.realsense_d435i || {};
  const lidar = sensors.built_in_lidar || {};
  setDot("builtInCameraStatus", builtIn.online ? "Online" : "Offline", builtIn.online);
  setDot("realsenseStatus", d435i.online ? "Online" : d435i.enabled ? "Enabled" : "Disabled", d435i.online);
  setDot("lidarStatus", lidar.online ? "Active" : "Waiting", lidar.online);
  $("realsenseNote").textContent = d435i.error || d435i.status || d435i.runtime_note || "Waiting for RealSense status.";

  if (d435i.enabled && !$("realsenseFeed").src) {
    $("realsenseFeed").src = d435i.stream_url || "/stream/realsense/color";
  }
  if (!d435i.enabled) {
    $("realsenseFeed").removeAttribute("src");
  }
}

async function refreshOverview() {
  try {
    const overview = await getJson("/api/operator/overview");
    state.overview = overview;
    renderOverview(overview);
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function refreshLogs() {
  const params = new URLSearchParams({ limit: "100" });
  const level = $("logLevel").value;
  if (level) params.set("level", level);
  if (state.selectedLogCategory) params.set("category", state.selectedLogCategory);
  try {
    const payload = await getJson(`/api/operator/logs?${params.toString()}`);
    renderLogs(payload);
  } catch (error) {
    showToast(error.message, "error");
  }
}

function renderLogs(payload) {
  const container = $("operatorLogSummaries");
  container.innerHTML = "";
  const summaries = payload.summaries || [];
  if (summaries.length === 0) {
    container.innerHTML = '<p class="empty-state">No operator events match the current filters.</p>';
  } else {
    for (const item of summaries) {
      const row = document.createElement("div");
      row.className = `log-summary log-${item.level || "info"}`;
      row.innerHTML = `<span>${new Date(item.ts).toLocaleString()}</span><strong>${item.summary}</strong>`;
      container.appendChild(row);
    }
  }
  $("rawLogView").textContent = JSON.stringify(payload.records || [], null, 2);
  renderEventTile(payload.records);
}

function buildD1DryRunPayload() {
  return {
    kind: "ui_dry_run_probe",
    data: {
      source: "go2_operator_dashboard",
      requested_at_ms: Date.now(),
      note: "validation only; no arm motion",
    },
  };
}

function renderD1(payload) {
  const statusPayload = payload && payload.statusPayload ? payload.statusPayload : {};
  const jointsPayload = payload && payload.jointsPayload ? payload.jointsPayload : {};
  const status = statusPayload.status || {};
  const jointState = jointsPayload.joint_state || {};
  const bridgeOnline = Boolean(statusPayload.bridge_online);
  const d1Connected = Boolean(status.connected);
  const estop = Boolean(status.estop);
  const dryRunOnly = Boolean(status.dry_run_only);
  const controllerLockHeld = Boolean(status.controller_lock_held);
  const jointValid = Boolean(jointState.valid);

  const phaseBadge = $("d1PhaseBadge");
  if (phaseBadge) {
    phaseBadge.textContent = dryRunOnly ? "Dry-run only" : "Real command path";
    phaseBadge.classList.remove("is-ok", "is-warn", "is-bad");
    phaseBadge.classList.add(dryRunOnly ? "is-warn" : "is-ok");
  }
  setPill("d1BridgeBadge", `Bridge: ${bridgeOnline ? "online" : "offline"}`, bridgeOnline);
  $("d1BridgeState").textContent = bridgeOnline ? "Online" : "Offline";
  $("d1ConnectedState").textContent = d1Connected ? "Connected" : "Disconnected";
  $("d1EstopState").textContent = estop ? "Latched" : "Clear";
  $("d1MotionEnabled").textContent = status.motion_enabled ? "Allowed" : "Blocked";
  $("d1ExecutionPath").textContent = dryRunOnly ? "Dry-run" : "Real";
  $("d1Mode").textContent = status.mode || "readonly";
  $("d1ControllerLock").textContent = controllerLockHeld ? "Held" : "Missing";
  $("d1ErrorCode").textContent = String(status.error_code == null ? 0 : status.error_code);
  $("d1LastUpdate").textContent = formatTimestampMs(status.last_update_ms);
  $("d1LastError").textContent = status.last_error || status.last_error_message || "None";
  setHealthClass($("d1BridgeCard"), bridgeOnline);
  setDot("d1JointValidity", jointValid ? "Valid" : "Invalid", jointValid);

  const zeroBtn = $("d1ZeroArmBtn");
  if (zeroBtn) zeroBtn.disabled = !bridgeOnline || !d1Connected || estop || dryRunOnly;
  const enableBtn = $("d1EnableMotionBtn");
  if (enableBtn) enableBtn.disabled = !bridgeOnline || !d1Connected || estop || !dryRunOnly;
  const disableBtn = $("d1DisableMotionBtn");
  if (disableBtn) disableBtn.disabled = !bridgeOnline;

  const q = Array.isArray(jointState.q) ? jointState.q : [];
  const dq = Array.isArray(jointState.dq) ? jointState.dq : [];
  const tau = Array.isArray(jointState.tau) ? jointState.tau : [];
  $("d1JointRows").innerHTML = Array.from({ length: 6 }, (_, index) => {
    return `
      <tr>
        <th>J${index + 1}</th>
        <td>${safeFixed(q[index], 4)}</td>
        <td>${safeFixed(dq[index], 4)}</td>
        <td>${safeFixed(tau[index], 4)}</td>
      </tr>
    `;
  }).join("");

  $("d1RawStatus").textContent = JSON.stringify(
    {
      status: statusPayload,
      joints: jointsPayload,
    },
    null,
    2,
  );
}

async function refreshD1(showToastOnSuccess = false) {
  try {
    const [statusPayload, jointsPayload] = await Promise.all([
      getJson("/api/d1/status"),
      getJson("/api/d1/joints"),
    ]);
    state.d1 = { statusPayload, jointsPayload };
    renderD1(state.d1);
    if (showToastOnSuccess) showToast("D1 panel refreshed.");
  } catch (error) {
    renderD1({
      statusPayload: {
        ok: false,
        bridge_online: false,
        message: error.message,
        status: {
          connected: false,
          estop: false,
          motion_enabled: false,
          dry_run_only: true,
          error_code: 0,
          mode: "offline",
          last_update_ms: 0,
          last_error_message: error.message,
        },
      },
      jointsPayload: {
        ok: false,
        bridge_online: false,
        message: error.message,
        joint_state: {
          q: [0, 0, 0, 0, 0, 0],
          dq: [0, 0, 0, 0, 0, 0],
          tau: [0, 0, 0, 0, 0, 0],
          valid: false,
          stamp_ms: 0,
        },
      },
    });
    if (showToastOnSuccess) showToast(error.message, "error");
  }
}

function defaultMission() {
  const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
  return {
    mission_id: `operator_route_${stamp}`,
    map_id: $("missionMapSelect").value || $("navigationMapSelect").value || "",
    waypoints: [],
  };
}

async function loadMission(missionId, notify = true) {
  if (!missionId) return;
  state.loadingMission = true;
  try {
    const mission = await getJson(`/api/missions/${encodeURIComponent(missionId)}`);
    state.missionDraft = mission;
    state.originalMissionId = mission.mission_id;
    $("missionSelect").value = mission.mission_id;
    $("navigationMissionSelect").value = mission.mission_id;
    renderMissionEditor();
    if (notify) showToast(`Loaded route ${mission.mission_id}.`);
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.loadingMission = false;
  }
}

function renderMissionEditor() {
  const mission = state.missionDraft || defaultMission();
  $("missionIdInput").value = mission.mission_id || "";
  $("missionIdInput").readOnly = Boolean(state.originalMissionId);
  if (mission.map_id) $("missionMapSelect").value = mission.map_id;
  const list = $("waypointList");
  list.innerHTML = "";

  const waypoints = mission.waypoints || [];
  const count = waypoints.length;
  const countLabel = $("waypointCountLabel");
  if (countLabel) countLabel.textContent = `${count} waypoint${count === 1 ? "" : "s"}`;

  if (count === 0) {
    list.innerHTML = '<p class="empty-state">No waypoints yet. Use the form, click on the map, or capture the current robot pose.</p>';
  } else {
    waypoints.forEach((waypoint, index) => {
      const card = document.createElement("article");
      card.className = "waypoint-card";
      card.dataset.index = String(index);
      if (index === state.selectedWaypointIndex) card.classList.add("is-selected");
      card.innerHTML = `
        <div class="waypoint-card-header">
          <span class="step-number">${index + 1}</span>
          <div class="compact-actions">
            <button class="icon-action" data-waypoint-action="select" title="Highlight on map">Select</button>
            <button class="icon-action" data-waypoint-action="up" ${index === 0 ? "disabled" : ""}>Up</button>
            <button class="icon-action" data-waypoint-action="down" ${index === count - 1 ? "disabled" : ""}>Down</button>
            <button class="icon-action danger-text" data-waypoint-action="delete">Delete</button>
          </div>
        </div>
        <div class="waypoint-fields">
          <label class="field"><span>Name</span><input data-field="id" value="${escapeHtml(waypoint.id)}" /></label>
          <label class="field"><span>Task</span><input data-field="task" value="${escapeHtml(waypoint.task || "inspect")}" /></label>
          <label class="field"><span>X</span><input data-field="x" type="number" step="0.01" value="${Number(waypoint.x || 0)}" /></label>
          <label class="field"><span>Y</span><input data-field="y" type="number" step="0.01" value="${Number(waypoint.y || 0)}" /></label>
          <label class="field"><span>Yaw</span><input data-field="yaw" type="number" step="0.01" value="${Number(waypoint.yaw || 0)}" /></label>
        </div>
      `;
      list.appendChild(card);
    });
  }
  $("missionJsonEditor").value = JSON.stringify(
    {
      mission_id: mission.mission_id,
      map_id: mission.map_id || "",
      waypoints: mission.waypoints || [],
    },
    null,
    2,
  );
  renderMapCanvas();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
  });
}

function collectMissionDraft() {
  const mission = {
    mission_id: $("missionIdInput").value.trim(),
    map_id: $("missionMapSelect").value || "",
    waypoints: [],
  };
  if (!mission.mission_id) {
    throw new Error("Route name is required.");
  }
  document.querySelectorAll(".waypoint-card").forEach((card) => {
    const waypoint = {};
    card.querySelectorAll("[data-field]").forEach((input) => {
      const field = input.dataset.field;
      waypoint[field] = ["x", "y", "yaw"].includes(field) ? Number(input.value || 0) : input.value.trim();
    });
    if (!waypoint.id) throw new Error("Every waypoint needs a name.");
    waypoint.task = waypoint.task || "inspect";
    mission.waypoints.push(waypoint);
  });
  state.missionDraft = mission;
  return mission;
}

async function saveMission(showSuccess = true) {
  const mission = collectMissionDraft();
  const saved = state.originalMissionId
    ? await sendJson(`/api/missions/${encodeURIComponent(state.originalMissionId)}`, mission, "PUT")
    : await sendJson("/api/missions", mission, "POST");
  state.missionDraft = saved;
  state.originalMissionId = saved.mission_id;
  renderMissionEditor();
  await refreshOverview();
  if (showSuccess) showToast(`Route ${saved.mission_id} saved.`);
  return saved;
}

function mutateWaypoints(action, index) {
  const mission = collectMissionDraft();
  const waypoints = mission.waypoints;
  if (action === "delete") {
    waypoints.splice(index, 1);
  }
  if (action === "up" && index > 0) {
    [waypoints[index - 1], waypoints[index]] = [waypoints[index], waypoints[index - 1]];
  }
  if (action === "down" && index < waypoints.length - 1) {
    [waypoints[index + 1], waypoints[index]] = [waypoints[index], waypoints[index + 1]];
  }
  state.missionDraft = mission;
  renderMissionEditor();
}

function setActiveCamera(which) {
  state.activeCamera = which;
  $("builtInCameraCard")?.classList.toggle("active-sensor", which === "built_in");
  $("realsenseCard")?.classList.toggle("active-sensor", which === "realsense");
  $("useBuiltInCameraBtn")?.classList.toggle("active", which === "built_in");
  $("useRealsenseCameraBtn")?.classList.toggle("active", which === "realsense");
  if (which === "realsense" && $("realsenseFeed") && !$("realsenseFeed").src) {
    $("realsenseFeed").src = "/stream/realsense/color";
  }
}

function switchTab(tabId) {
  const target = $(tabId);
  const button = document.querySelector(`.tab-button[data-tab="${tabId}"]`);
  if (!target || !button) return;
  document.querySelectorAll(".tab-button").forEach((item) => item.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
  button.classList.add("active");
  target.classList.add("active");
  if (tabId === "waypoints") requestAnimationFrame(renderMapCanvas);
}

function bindTabs() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
}

function bindActions() {
  $("themeToggleBtn").addEventListener("click", toggleTheme);

  $("estopBtn").addEventListener("click", async () => {
    try {
      await sendJson("/api/mode/estop");
      showToast("Emergency stop active.", "error");
      refreshOverview();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("resetEstopBtn").addEventListener("click", async () => {
    try {
      await sendJson("/api/mode/reset-estop");
      showToast("Emergency stop reset.");
      refreshOverview();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("checkSystemBtn").addEventListener("click", async () => {
    try {
      await sendJson("/api/operator/check-system");
      await refreshOverview();
      showToast("System check complete.");
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("activateRobotBtn").addEventListener("click", async () => {
    try {
      await sendJson("/api/robot/activate");
      showToast("Robot activation requested.");
      refreshOverview();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("startMappingBtn").addEventListener("click", async () => {
    const result = await sendJson("/api/ros/mapping/start", {
      session_name: $("mappingSessionName").value,
      mode: state.mappingMode,
    });
    showToast(result.message, result.ok ? "info" : "error");
    refreshOverview();
  });

  $("stopMappingBtn").addEventListener("click", async () => {
    if (!window.confirm("Stop mapping now? Unsaved map data may be lost.")) return;
    const result = await sendJson("/api/ros/mapping/stop");
    showToast(result.message, result.ok ? "info" : "error");
    refreshOverview();
  });

  $("saveMapBtn").addEventListener("click", async () => {
    try {
      const result = await sendJson("/api/ros/mapping/save", { map_name: $("mapSaveName").value.trim() });
      $("mapSaveResult").textContent = result.message;
      showToast(result.message, result.ok ? "info" : "error");
      await refreshOverview();
    } catch (error) {
      $("mapSaveResult").textContent = error.message;
      showToast(error.message, "error");
    }
  });

  $("startNavigationBtn").addEventListener("click", async () => {
    const result = await sendJson("/api/ros/navigation/start", { map_id: $("navigationMapSelect").value });
    showToast(result.message, result.ok ? "info" : "error");
    refreshOverview();
  });

  $("stopNavigationBtn").addEventListener("click", async () => {
    if (!window.confirm("Stop navigation now?")) return;
    const result = await sendJson("/api/ros/navigation/stop");
    showToast(result.message, result.ok ? "info" : "error");
    refreshOverview();
  });

  $("loadMissionBtn").addEventListener("click", () => loadMission($("missionSelect").value));
  $("missionSelect").addEventListener("change", () => loadMission($("missionSelect").value));

  $("newMissionBtn").addEventListener("click", () => {
    state.missionDraft = defaultMission();
    state.originalMissionId = "";
    renderMissionEditor();
    showToast("New route ready.");
  });

  $("saveMissionBtn").addEventListener("click", async () => {
    try {
      await saveMission(true);
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("deleteMissionBtn").addEventListener("click", async () => {
    if (!state.originalMissionId) {
      showToast("This route has not been saved yet.", "error");
      return;
    }
    if (!window.confirm(`Delete route ${state.originalMissionId}?`)) return;
    try {
      const result = await requestJson(`/api/missions/${encodeURIComponent(state.originalMissionId)}`, { method: "DELETE" });
      showToast(result.message);
      state.missionDraft = null;
      state.originalMissionId = "";
      await refreshOverview();
      renderMissionEditor();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("addWaypointCoordBtn")?.addEventListener("click", () => {
    try {
      if (!state.missionDraft) state.missionDraft = defaultMission();
      const mission = state.missionDraft;
      const defaultName = `waypoint_${(mission.waypoints.length + 1).toString().padStart(2, "0")}`;
      const waypoint = {
        id: $("newWaypointName").value.trim() || defaultName,
        task: $("newWaypointTask").value.trim() || "inspect",
        x: Number($("newWaypointX").value || 0),
        y: Number($("newWaypointY").value || 0),
        yaw: Number($("newWaypointYaw").value || 0),
      };
      if (mission.waypoints.some((wp) => wp.id === waypoint.id)) {
        throw new Error(`Waypoint name "${waypoint.id}" already exists in this route.`);
      }
      if (!Number.isFinite(waypoint.x) || !Number.isFinite(waypoint.y) || !Number.isFinite(waypoint.yaw)) {
        throw new Error("x, y, and yaw must be numbers.");
      }
      mission.waypoints.push(waypoint);
      state.selectedWaypointIndex = mission.waypoints.length - 1;
      renderMissionEditor();
      showToast("Waypoint added.");
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("saveAsMissionBtn")?.addEventListener("click", async () => {
    try {
      const current = collectMissionDraft();
      const next = window.prompt("Save as new route name:", `${current.mission_id}_copy`);
      if (!next) return;
      const copy = { ...current, mission_id: next };
      state.missionDraft = copy;
      state.originalMissionId = "";
      renderMissionEditor();
      await saveMission(true);
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("clearMissionBtn")?.addEventListener("click", () => {
    if (!state.missionDraft || !state.missionDraft.waypoints?.length) return;
    if (!window.confirm("Remove all waypoints from this route?")) return;
    state.missionDraft.waypoints = [];
    state.selectedWaypointIndex = -1;
    renderMissionEditor();
  });

  $("missionMapSelect")?.addEventListener("change", () => {
    if (state.missionDraft) state.missionDraft.map_id = $("missionMapSelect").value;
    loadMapMetadata($("missionMapSelect").value);
  });

  $("addWaypointPoseBtn").addEventListener("click", async () => {
    try {
      const missionId = $("missionIdInput").value.trim() || defaultMission().mission_id;
      const payload = {
        mission_id: missionId,
        map_id: $("missionMapSelect").value,
        waypoint_id: $("newWaypointName").value.trim(),
        task: $("newWaypointTask").value.trim() || "inspect",
      };
      const response = await sendJson("/api/waypoints/from-current-pose", payload);
      state.missionDraft = response.result;
      state.originalMissionId = response.result.mission_id;
      renderMissionEditor();
      await refreshOverview();
      showToast("Waypoint added from current pose.");
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("waypointList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-waypoint-action]");
    if (!button || button.disabled) return;
    const card = button.closest(".waypoint-card");
    const index = Number(card.dataset.index);
    if (button.dataset.waypointAction === "select") {
      state.selectedWaypointIndex = index;
      renderMissionEditor();
      return;
    }
    mutateWaypoints(button.dataset.waypointAction, index);
  });

  $("runRouteBtn").addEventListener("click", async () => {
    try {
      const saved = await saveMission(false);
      const result = await sendJson(`/api/missions/${encodeURIComponent(saved.mission_id)}/start`);
      showToast(result.message, result.ok ? "info" : "error");
      refreshOverview();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("stopRouteBtn").addEventListener("click", async () => {
    if (!state.originalMissionId) return;
    if (!window.confirm("Stop the current route?")) return;
    const result = await sendJson(`/api/missions/${encodeURIComponent(state.originalMissionId)}/cancel`);
    showToast(result.message, result.ok ? "info" : "error");
    refreshOverview();
  });

  $("startSelectedMissionBtn").addEventListener("click", async () => {
    const missionId = $("navigationMissionSelect").value;
    if (!missionId) return showToast("Choose a route first.", "error");
    const result = await sendJson(`/api/missions/${encodeURIComponent(missionId)}/start`);
    showToast(result.message, result.ok ? "info" : "error");
    refreshOverview();
  });

  $("cancelSelectedMissionBtn").addEventListener("click", async () => {
    const missionId = $("navigationMissionSelect").value;
    if (!missionId) return showToast("Choose a route first.", "error");
    if (!window.confirm("Cancel the selected route?")) return;
    const result = await sendJson(`/api/missions/${encodeURIComponent(missionId)}/cancel`);
    showToast(result.message, result.ok ? "info" : "error");
    refreshOverview();
  });

  $("applyMissionJsonBtn").addEventListener("click", () => {
    try {
      state.missionDraft = JSON.parse($("missionJsonEditor").value);
      state.originalMissionId = state.originalMissionId && state.originalMissionId === state.missionDraft.mission_id
        ? state.originalMissionId
        : "";
      renderMissionEditor();
      showToast("JSON applied.");
    } catch (error) {
      showToast(`Invalid JSON: ${error.message}`, "error");
    }
  });

  $("copyMissionJsonBtn").addEventListener("click", () => {
    navigator.clipboard.writeText($("missionJsonEditor").value).then(
      () => showToast("Route JSON copied."),
      () => showToast("Copy failed.", "error"),
    );
  });

  $("useBuiltInCameraBtn")?.addEventListener("click", () => setActiveCamera("built_in"));
  $("useRealsenseCameraBtn")?.addEventListener("click", () => setActiveCamera("realsense"));

  $("logLevel").addEventListener("change", refreshLogs);
  $("logCategoryChips").addEventListener("click", (event) => {
    const chip = event.target.closest("[data-category]");
    if (!chip) return;
    state.selectedLogCategory = chip.dataset.category;
    document.querySelectorAll("#logCategoryChips .chip").forEach((item) => item.classList.remove("active"));
    chip.classList.add("active");
    refreshLogs();
  });

  $("copyLogsBtn").addEventListener("click", () => {
    navigator.clipboard.writeText($("rawLogView").textContent).then(
      () => showToast("Logs copied."),
      () => showToast("Copy failed.", "error"),
    );
  });

  $("refreshD1Btn").addEventListener("click", async () => {
    await refreshD1(true);
  });

  $("d1EnableMotionBtn").addEventListener("click", async () => {
    const result = await sendJson("/api/d1/enable-motion");
    $("d1ActionResult").textContent = result.message || "D1 motion enable requested.";
    showToast(result.message || "D1 motion enable requested.", result.ok ? "info" : "error");
    refreshD1();
  });

  $("d1DisableMotionBtn").addEventListener("click", async () => {
    const result = await sendJson("/api/d1/disable-motion");
    $("d1ActionResult").textContent = result.message || "D1 motion disabled.";
    showToast(result.message || "D1 motion disabled.", result.ok ? "info" : "error");
    refreshD1();
  });

  $("d1ZeroArmBtn").addEventListener("click", async () => {
    const result = await sendJson("/api/d1/zero-arm");
    $("d1ActionResult").textContent = result.message || "D1 zero-arm requested.";
    showToast(result.message || "D1 zero-arm requested.", result.ok ? "info" : "error");
    refreshD1();
  });

  $("d1StopBtn").addEventListener("click", async () => {
    const result = await sendJson("/api/d1/halt");
    $("d1ActionResult").textContent = result.message || "D1 halt requested.";
    showToast(result.message || "D1 halt requested.", result.ok ? "info" : "error");
    refreshD1();
  });

  $("d1DryRunBtn").addEventListener("click", async () => {
    const payload = buildD1DryRunPayload();
    $("d1DryRunPayload").textContent = JSON.stringify(payload, null, 2);
    const result = await sendJson("/api/d1/dry-run", { payload });
    $("d1ActionResult").textContent = result.message || "D1 dry-run sent.";
    showToast(result.message || "D1 dry-run sent.", result.ok ? "info" : "error");
    refreshD1();
  });
}

/* ── Manual teleop ─────────────────────────────────── */

function teleopSpeed() {
  return parseFloat($("speedSlider") ? $("speedSlider").value : "0.4") || 0.4;
}

function teleopSendCmd(vx, vy, vyaw) {
  sendJson("/api/robot/manual/cmd", { vx, vy, vyaw, ts: Date.now() / 1000 }).catch(() => {});
}

function teleopSendStop() {
  sendJson("/api/robot/manual/stop").catch(() => {});
}

function bindDpad() {
  const dirs = [
    ["dpadFwd",    1,  0,  0],
    ["dpadBack",  -1,  0,  0],
    ["dpadLeft",   0,  1,  0],
    ["dpadRight",  0, -1,  0],
    ["dpadRotCCW", 0,  0,  1],
    ["dpadRotCW",  0,  0, -1],
  ];
  for (const [id, dx, dy, dyaw] of dirs) {
    const btn = $(id);
    if (!btn) continue;
    let iv = null;
    const startSend = () => {
      btn.classList.add("pressed");
      const s = teleopSpeed();
      const go = () => teleopSendCmd(dx * s, dy * s, dyaw * s);
      go();
      iv = setInterval(go, 100);
    };
    const stopSend = () => {
      btn.classList.remove("pressed");
      if (iv) { clearInterval(iv); iv = null; }
      teleopSendStop();
    };
    btn.addEventListener("mousedown", startSend);
    btn.addEventListener("touchstart", (e) => { e.preventDefault(); startSend(); }, { passive: false });
    btn.addEventListener("mouseup", stopSend);
    btn.addEventListener("mouseleave", stopSend);
    btn.addEventListener("touchend", stopSend);
    btn.addEventListener("touchcancel", stopSend);
  }
  const stopBtn = $("dpadStop");
  if (stopBtn) {
    stopBtn.addEventListener("mousedown", () => { stopBtn.classList.add("pressed"); teleopSendStop(); });
    stopBtn.addEventListener("mouseup",   () => stopBtn.classList.remove("pressed"));
    stopBtn.addEventListener("mouseleave",() => stopBtn.classList.remove("pressed"));
    stopBtn.addEventListener("touchstart", (e) => { e.preventDefault(); stopBtn.classList.add("pressed"); teleopSendStop(); }, { passive: false });
    stopBtn.addEventListener("touchend",  () => stopBtn.classList.remove("pressed"));
  }
}

const keysHeld = new Set();
let keyInterval = null;
const KEY_MAP = {
  w: [1, 0, 0], arrowup: [1, 0, 0],
  s: [-1, 0, 0], arrowdown: [-1, 0, 0],
  a: [0, 1, 0], arrowleft: [0, 1, 0],
  d: [0, -1, 0], arrowright: [0, -1, 0],
  q: [0, 0, 1],
  e: [0, 0, -1],
};

function isControlTabActive() {
  const panel = $("control");
  return panel && panel.classList.contains("active");
}

function isInputFocused() {
  const tag = (document.activeElement && document.activeElement.tagName || "").toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select";
}

function sendFromKeys() {
  const s = teleopSpeed();
  let vx = 0, vy = 0, vyaw = 0;
  for (const k of keysHeld) {
    const v = KEY_MAP[k];
    if (v) { vx += v[0]; vy += v[1]; vyaw += v[2]; }
  }
  if (vx === 0 && vy === 0 && vyaw === 0) return;
  const mag = Math.sqrt(vx * vx + vy * vy) || 1;
  if (mag > 1) { vx /= mag; vy /= mag; }
  teleopSendCmd(vx * s, vy * s, vyaw * s);
}

function initKeyboard() {
  document.addEventListener("keydown", (e) => {
    if (!isControlTabActive() || isInputFocused()) return;
    const key = e.key.toLowerCase();
    if (key === " ") { e.preventDefault(); teleopSendStop(); return; }
    if (!KEY_MAP[key]) return;
    e.preventDefault();
    if (keysHeld.has(key)) return;
    keysHeld.add(key);
    if (!keyInterval) {
      sendFromKeys();
      keyInterval = setInterval(sendFromKeys, 100);
    }
  });
  document.addEventListener("keyup", (e) => {
    const key = e.key.toLowerCase();
    keysHeld.delete(key);
    if (keysHeld.size === 0 && keyInterval) {
      clearInterval(keyInterval);
      keyInterval = null;
      if (isControlTabActive()) teleopSendStop();
    }
  });
}

function bindControlActions() {
  $("takeManualBtn") && $("takeManualBtn").addEventListener("click", async () => {
    try {
      await sendJson("/api/mode/manual/take");
      showToast("Manual mode active — opening operator workspace.");
      switchTab("sensors");
      state.manualAutoSwitched = true;
      state.currentMode = "MANUAL";
      refreshOverview();
    } catch (e) { showToast(e.message, "error"); }
  });
  $("releaseManualBtn") && $("releaseManualBtn").addEventListener("click", async () => {
    try { await sendJson("/api/mode/manual/release"); showToast("Manual mode released."); refreshOverview(); }
    catch (e) { showToast(e.message, "error"); }
  });
  $("ctrlStandUpBtn") && $("ctrlStandUpBtn").addEventListener("click", async () => {
    try { await sendJson("/api/robot/manual/stand-up"); showToast("Stand-up requested."); }
    catch (e) { showToast(e.message, "error"); }
  });
  $("ctrlSitBtn") && $("ctrlSitBtn").addEventListener("click", async () => {
    try { await sendJson("/api/robot/manual/sit"); showToast("Sit requested."); }
    catch (e) { showToast(e.message, "error"); }
  });
  $("ctrlStopBtn") && $("ctrlStopBtn").addEventListener("click", async () => {
    try { await sendJson("/api/robot/manual/stop"); showToast("Motion stopped."); }
    catch (e) { showToast(e.message, "error"); }
  });
  const slider = $("speedSlider");
  const label = $("speedLabel");
  if (slider && label) {
    slider.addEventListener("input", () => {
      label.textContent = parseFloat(slider.value).toFixed(2) + " m/s";
    });
  }
}

/* ── Lidar canvas renderer ─────────────────────────── */

function lidarPresetConfig() {
  switch (state.lidarPreset) {
    case "dense":   return { pointSize: 1.0, alpha: 0.65, step: 1 };
    case "sparse":  return { pointSize: 2.4, alpha: 0.9, step: 3 };
    default:        return { pointSize: 1.7, alpha: 0.8, step: 1 };
  }
}

function renderLidarCanvas(points) {
  state.lastLidarPoints = points || [];
  const canvas = $("lidarCanvas");
  if (!canvas) return;
  const bounding = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const wantW = Math.max(260, Math.floor(bounding.width * dpr));
  const wantH = Math.max(260, Math.floor(bounding.height * dpr));
  if (canvas.width !== wantW || canvas.height !== wantH) {
    canvas.width = wantW;
    canvas.height = wantH;
  }
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2;
  const cy = h / 2;

  // Compute dynamic range so we follow the robot when enabled.
  let maxRange = 3.5;
  if (state.lidarFollow && points && points.length > 0) {
    let max = 1.0;
    for (const p of points) {
      if (p.distance > max && p.distance < 20) max = p.distance;
    }
    maxRange = Math.min(20, Math.max(2.5, max * 1.1));
  }
  const scale = Math.min(w, h) / 2 * 0.88;
  const ppm = scale / maxRange;

  // Background with subtle radial gradient.
  const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, scale * 1.2);
  bg.addColorStop(0, "#0a1517");
  bg.addColorStop(1, "#040809");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  // Rings.
  ctx.strokeStyle = "rgba(0, 201, 190, 0.18)";
  ctx.fillStyle = "rgba(0, 201, 190, 0.38)";
  ctx.lineWidth = 1;
  ctx.font = `${Math.max(10, Math.round(w * 0.028))}px "JetBrains Mono", monospace`;
  ctx.textBaseline = "middle";
  const ringStep = maxRange <= 5 ? 1 : 2;
  for (let r = ringStep; r <= maxRange; r += ringStep) {
    ctx.beginPath();
    ctx.arc(cx, cy, r * ppm, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillText(`${r.toFixed(0)} m`, cx + r * ppm + 4, cy - 8);
  }

  // Crosshairs.
  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  ctx.beginPath();
  ctx.moveTo(cx, cy - scale);
  ctx.lineTo(cx, cy + scale);
  ctx.moveTo(cx - scale, cy);
  ctx.lineTo(cx + scale, cy);
  ctx.stroke();

  // Points colored by distance (near = teal, far = warm).
  const config = lidarPresetConfig();
  if (points && points.length > 0) {
    ctx.globalAlpha = config.alpha;
    for (let i = 0; i < points.length; i += config.step) {
      const p = points[i];
      if (!p || p.distance <= 0.05 || p.distance > maxRange) continue;
      const px = cx + Math.cos(p.angle) * p.distance * ppm;
      const py = cy - Math.sin(p.angle) * p.distance * ppm;
      const t = Math.min(1, p.distance / maxRange);
      const r = Math.round(0 + 200 * t);
      const g = Math.round(201 - 90 * t);
      const b = Math.round(190 - 150 * t);
      ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
      ctx.beginPath();
      ctx.arc(px, py, config.pointSize, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  // Robot marker.
  ctx.fillStyle = "#ffd23f";
  ctx.strokeStyle = "rgba(0, 0, 0, 0.6)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.strokeStyle = "#ffd23f";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx, cy - 22);
  ctx.stroke();

  // HUD: show current range label.
  ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
  ctx.textAlign = "left";
  ctx.fillText(`range ${maxRange.toFixed(1)} m · ${state.lidarFollow ? "follow" : "fixed"}`, 10, 14);
}

async function refreshLidar() {
  const panel = $("sensors");
  if (!panel || !panel.classList.contains("active")) return;
  try {
    const data = await getJson("/api/robot/lidar/scan");
    const points = (data && data.points) || [];
    const note = $("lidarViewerNote");
    if (data && data.available && points.length > 0) {
      renderLidarCanvas(points);
      setDot("lidarStatus", "Live", true);
      if (note) {
        const total = data.total != null ? data.total : points.length;
        note.textContent = `${points.length} / ${total} points · ${data.source || "adapter"}`;
      }
    } else {
      renderLidarCanvas([]);
      setDot("lidarStatus", data && data.source === "unavailable" ? "No data" : "Waiting", false);
      if (note && data) note.textContent = data.note || "Waiting for scan data.";
    }
  } catch (error) {
    setDot("lidarStatus", "Error", false);
    const note = $("lidarViewerNote");
    if (note) note.textContent = error.message || "Stream error.";
  }
}

/* ── Map canvas (mission map + graphical waypoint placement) ── */

async function loadMapMetadata(mapId) {
  if (!mapId) {
    state.mapMetadata = null;
    state.mapImage = null;
    state.mapImageLoadedFor = "";
    renderMapCanvas();
    return;
  }
  try {
    const metadata = await getJson(`/api/maps/${encodeURIComponent(mapId)}`);
    state.mapMetadata = metadata;
    if (state.mapImageLoadedFor !== mapId) {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        state.mapImage = img;
        state.mapImageLoadedFor = mapId;
        resetMapView();
        renderMapCanvas();
      };
      img.onerror = () => {
        state.mapImage = null;
        renderMapCanvas();
      };
      // Prefer browser-friendly PNG; the PGM endpoint is a fallback.
      img.src = `/api/maps/${encodeURIComponent(mapId)}/image.png?t=${Date.now()}`;
    } else {
      renderMapCanvas();
    }
  } catch (error) {
    state.mapMetadata = null;
    state.mapImage = null;
    state.mapImageLoadedFor = "";
    renderMapCanvas();
  }
}

function resetMapView() {
  state.mapView = { offsetX: 0, offsetY: 0, zoom: 1 };
}

function worldToPixel(x, y) {
  const meta = state.mapMetadata;
  if (!meta || !meta.height_px) return null;
  const origin = meta.origin || [0, 0, 0];
  const u = (x - origin[0]) / meta.resolution;
  const v = meta.height_px - (y - origin[1]) / meta.resolution;
  return [u, v];
}

function pixelToWorld(u, v) {
  const meta = state.mapMetadata;
  if (!meta || !meta.height_px) return null;
  const origin = meta.origin || [0, 0, 0];
  const x = origin[0] + u * meta.resolution;
  const y = origin[1] + (meta.height_px - v) * meta.resolution;
  return [x, y];
}

function canvasToImagePixel(cx, cy, canvas) {
  const meta = state.mapMetadata;
  if (!meta || !state.mapImage) return null;
  const view = state.mapView;
  const scale = computeMapBaseScale(canvas) * view.zoom;
  const width = state.mapImage.width;
  const height = state.mapImage.height;
  const drawWidth = width * scale;
  const drawHeight = height * scale;
  const centerX = canvas.width / 2 + view.offsetX;
  const centerY = canvas.height / 2 + view.offsetY;
  const left = centerX - drawWidth / 2;
  const top = centerY - drawHeight / 2;
  const u = (cx - left) / scale;
  const v = (cy - top) / scale;
  return [u, v];
}

function computeMapBaseScale(canvas) {
  if (!state.mapImage) return 1;
  const img = state.mapImage;
  return Math.min(canvas.width / img.width, canvas.height / img.height);
}

function imagePixelToCanvas(u, v, canvas) {
  if (!state.mapImage) return null;
  const view = state.mapView;
  const scale = computeMapBaseScale(canvas) * view.zoom;
  const width = state.mapImage.width;
  const height = state.mapImage.height;
  const drawWidth = width * scale;
  const drawHeight = height * scale;
  const centerX = canvas.width / 2 + view.offsetX;
  const centerY = canvas.height / 2 + view.offsetY;
  const left = centerX - drawWidth / 2;
  const top = centerY - drawHeight / 2;
  return [left + u * scale, top + v * scale];
}

function renderMapCanvas() {
  const canvas = $("missionMapCanvas");
  if (!canvas) return;
  const panel = $("waypoints");
  if (!panel || !panel.classList.contains("active")) return;
  const bounding = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const wantW = Math.max(320, Math.floor(bounding.width * dpr));
  const wantH = Math.max(240, Math.floor(bounding.height * dpr));
  if (canvas.width !== wantW || canvas.height !== wantH) {
    canvas.width = wantW;
    canvas.height = wantH;
  }
  const ctx = canvas.getContext("2d");
  ctx.save();
  ctx.fillStyle = "#0a0e10";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const overlay = $("mapEmptyOverlay");
  if (!state.mapMetadata) {
    if (overlay) overlay.classList.remove("hidden");
    ctx.restore();
    return;
  }
  if (overlay) overlay.classList.add("hidden");

  // Draw map image if available.
  if (state.mapImage) {
    const scale = computeMapBaseScale(canvas) * state.mapView.zoom;
    const drawWidth = state.mapImage.width * scale;
    const drawHeight = state.mapImage.height * scale;
    const cx = canvas.width / 2 + state.mapView.offsetX - drawWidth / 2;
    const cy = canvas.height / 2 + state.mapView.offsetY - drawHeight / 2;
    ctx.imageSmoothingEnabled = state.mapView.zoom < 1.5;
    ctx.drawImage(state.mapImage, cx, cy, drawWidth, drawHeight);
  } else {
    ctx.fillStyle = "#c3c3c3";
    ctx.textAlign = "center";
    ctx.fillText("Map image unavailable — placement uses yaml origin only", canvas.width / 2, canvas.height / 2);
  }

  // Robot pose.
  const pose = state.overview && state.overview.pose;
  if (pose) {
    const point = worldToPixel(pose.x, pose.y);
    if (point) {
      const canvasPoint = imagePixelToCanvas(point[0], point[1], canvas);
      if (canvasPoint) {
        drawRobotMarker(ctx, canvasPoint[0], canvasPoint[1], pose.yaw || 0);
      }
    }
  }

  // Waypoints + path.
  const mission = state.missionDraft;
  if (mission && mission.waypoints && mission.waypoints.length > 0) {
    const canvasPoints = mission.waypoints
      .map((waypoint) => {
        const pix = worldToPixel(waypoint.x, waypoint.y);
        return pix ? imagePixelToCanvas(pix[0], pix[1], canvas) : null;
      })
      .filter(Boolean);
    if (canvasPoints.length >= 2) {
      ctx.strokeStyle = "rgba(0, 201, 190, 0.55)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(canvasPoints[0][0], canvasPoints[0][1]);
      for (let i = 1; i < canvasPoints.length; i += 1) {
        ctx.lineTo(canvasPoints[i][0], canvasPoints[i][1]);
      }
      ctx.stroke();
    }
    mission.waypoints.forEach((waypoint, index) => {
      const pix = worldToPixel(waypoint.x, waypoint.y);
      const canvasPoint = pix ? imagePixelToCanvas(pix[0], pix[1], canvas) : null;
      if (!canvasPoint) return;
      drawWaypointMarker(ctx, canvasPoint[0], canvasPoint[1], waypoint.yaw || 0, index + 1, index === state.selectedWaypointIndex);
    });
  }
  ctx.restore();
}

function drawRobotMarker(ctx, x, y, yaw) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(-yaw);
  ctx.fillStyle = "#ffd23f";
  ctx.strokeStyle = "rgba(0, 0, 0, 0.55)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(10, 0);
  ctx.lineTo(-7, 6);
  ctx.lineTo(-7, -6);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function drawWaypointMarker(ctx, x, y, yaw, index, selected) {
  const radius = selected ? 10 : 7;
  ctx.save();
  ctx.translate(x, y);
  ctx.beginPath();
  ctx.arc(0, 0, radius, 0, Math.PI * 2);
  ctx.fillStyle = selected ? "#00e6d7" : "#00c9be";
  ctx.fill();
  ctx.lineWidth = selected ? 2.5 : 1.5;
  ctx.strokeStyle = "rgba(8, 12, 14, 0.85)";
  ctx.stroke();

  ctx.rotate(-yaw);
  ctx.strokeStyle = selected ? "#ffd23f" : "#00c9be";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(18, 0);
  ctx.stroke();
  ctx.rotate(yaw);

  ctx.fillStyle = "#041618";
  ctx.font = "bold 10px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(String(index), 0, 0);
  ctx.restore();
}

function bindMapCanvas() {
  const canvas = $("missionMapCanvas");
  if (!canvas) return;
  const container = canvas.parentElement;
  let panning = null;

  canvas.addEventListener("mousemove", (event) => {
    const bounds = canvas.getBoundingClientRect();
    const cx = (event.clientX - bounds.left) * (canvas.width / bounds.width);
    const cy = (event.clientY - bounds.top) * (canvas.height / bounds.height);
    const imgPixel = canvasToImagePixel(cx, cy, canvas);
    const readout = $("mapCoordReadout");
    if (imgPixel) {
      const world = pixelToWorld(imgPixel[0], imgPixel[1]);
      if (readout && world) {
        readout.textContent = `world (${world[0].toFixed(2)}, ${world[1].toFixed(2)})`;
      }
    } else if (readout) {
      readout.textContent = "world (–, –)";
    }

    if (state.yawDrag) {
      const dx = cx - state.yawDrag.startCanvas[0];
      const dy = cy - state.yawDrag.startCanvas[1];
      if (Math.hypot(dx, dy) > 6) {
        // Canvas y grows down; world y grows up → invert dy.
        state.yawDrag.currentYaw = Math.atan2(-dy, dx);
        const mission = state.missionDraft;
        if (mission && mission.waypoints[state.yawDrag.waypointIndex]) {
          mission.waypoints[state.yawDrag.waypointIndex].yaw = Number(state.yawDrag.currentYaw.toFixed(3));
          renderMissionEditor();
        }
      }
    }

    if (panning) {
      state.mapView.offsetX = panning.originalOffsetX + (cx - panning.startCanvas[0]);
      state.mapView.offsetY = panning.originalOffsetY + (cy - panning.startCanvas[1]);
      renderMapCanvas();
    }
  });

  canvas.addEventListener("mouseleave", () => {
    const readout = $("mapCoordReadout");
    if (readout) readout.textContent = "world (–, –)";
    panning = null;
    container.classList.remove("panning");
  });

  canvas.addEventListener("mousedown", (event) => {
    if (!state.mapMetadata) return;
    const bounds = canvas.getBoundingClientRect();
    const cx = (event.clientX - bounds.left) * (canvas.width / bounds.width);
    const cy = (event.clientY - bounds.top) * (canvas.height / bounds.height);

    if (state.mapTool === "pan") {
      panning = {
        startCanvas: [cx, cy],
        originalOffsetX: state.mapView.offsetX,
        originalOffsetY: state.mapView.offsetY,
      };
      container.classList.add("panning");
      return;
    }

    const imgPixel = canvasToImagePixel(cx, cy, canvas);
    if (!imgPixel) return;
    const world = pixelToWorld(imgPixel[0], imgPixel[1]);
    if (!world) return;

    if (state.mapTool === "select") {
      const mission = state.missionDraft;
      if (!mission) return;
      let closestIndex = -1;
      let closestDistance = Infinity;
      mission.waypoints.forEach((waypoint, index) => {
        const pix = worldToPixel(waypoint.x, waypoint.y);
        if (!pix) return;
        const canvasPoint = imagePixelToCanvas(pix[0], pix[1], canvas);
        if (!canvasPoint) return;
        const d = Math.hypot(canvasPoint[0] - cx, canvasPoint[1] - cy);
        if (d < closestDistance) {
          closestDistance = d;
          closestIndex = index;
        }
      });
      if (closestIndex !== -1 && closestDistance < 24) {
        state.selectedWaypointIndex = closestIndex;
        renderMissionEditor();
      }
      return;
    }

    // Place tool
    addWaypointFromWorld(world[0], world[1]);
    const mission = state.missionDraft;
    if (mission) {
      const wpIndex = mission.waypoints.length - 1;
      state.yawDrag = {
        startCanvas: [cx, cy],
        waypointIndex: wpIndex,
        currentYaw: mission.waypoints[wpIndex].yaw,
      };
      state.selectedWaypointIndex = wpIndex;
      renderMissionEditor();
    }
  });

  window.addEventListener("mouseup", () => {
    state.yawDrag = null;
    panning = null;
    container.classList.remove("panning");
  });

  canvas.addEventListener("wheel", (event) => {
    if (!state.mapMetadata) return;
    event.preventDefault();
    const direction = event.deltaY < 0 ? 1.12 : 1 / 1.12;
    state.mapView.zoom = Math.min(8, Math.max(0.25, state.mapView.zoom * direction));
    renderMapCanvas();
  }, { passive: false });

  document.querySelectorAll(".map-tool-group [data-tool]").forEach((button) => {
    button.addEventListener("click", () => {
      state.mapTool = button.dataset.tool;
      document.querySelectorAll(".map-tool-group [data-tool]").forEach((other) => other.classList.remove("active"));
      button.classList.add("active");
      container.classList.toggle("tool-pan", state.mapTool === "pan");
      container.classList.toggle("tool-select", state.mapTool === "select");
    });
  });

  $("mapZoomInBtn")?.addEventListener("click", () => {
    state.mapView.zoom = Math.min(8, state.mapView.zoom * 1.2);
    renderMapCanvas();
  });
  $("mapZoomOutBtn")?.addEventListener("click", () => {
    state.mapView.zoom = Math.max(0.25, state.mapView.zoom / 1.2);
    renderMapCanvas();
  });
  $("mapResetBtn")?.addEventListener("click", () => {
    resetMapView();
    renderMapCanvas();
  });

  window.addEventListener("resize", () => {
    if ($("waypoints")?.classList.contains("active")) renderMapCanvas();
  });
}

function addWaypointFromWorld(x, y) {
  if (!state.missionDraft) state.missionDraft = defaultMission();
  const mission = state.missionDraft;
  const defaultName = `waypoint_${(mission.waypoints.length + 1).toString().padStart(2, "0")}`;
  const waypoint = {
    id: $("newWaypointName").value.trim() || defaultName,
    task: ($("newWaypointTask").value.trim() || "inspect"),
    x: Number(x.toFixed(3)),
    y: Number(y.toFixed(3)),
    yaw: 0.0,
  };
  if (mission.waypoints.some((existing) => existing.id === waypoint.id)) {
    // Collision: append a suffix silently to avoid blocking click-placement.
    waypoint.id = `${waypoint.id}_${mission.waypoints.length + 1}`;
  }
  mission.waypoints.push(waypoint);
  renderMissionEditor();
}

/* ── Sensor tile fullscreen + drag rearrange ─────────── */

function bindSensorTiles() {
  const workspace = $("sensorWorkspace");
  if (!workspace) return;
  workspace.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-tile-fullscreen]");
    if (btn) {
      const tile = btn.closest(".sensor-tile");
      if (tile) openTileFullscreen(tile);
    }
  });

  // Basic drag rearrange: drag a tile header over another tile to swap order.
  let draggingTile = null;
  workspace.querySelectorAll(".sensor-tile").forEach((tile) => {
    const header = tile.querySelector(".sensor-tile-header");
    if (!header) return;
    header.addEventListener("dragstart", (event) => {
      draggingTile = tile;
      tile.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", tile.dataset.widget || "");
    });
    header.addEventListener("dragend", () => {
      if (draggingTile) draggingTile.classList.remove("dragging");
      draggingTile = null;
      workspace.querySelectorAll(".drag-over").forEach((node) => node.classList.remove("drag-over"));
      persistSensorLayout();
    });
    tile.addEventListener("dragover", (event) => {
      if (!draggingTile || draggingTile === tile) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      tile.classList.add("drag-over");
    });
    tile.addEventListener("dragleave", () => tile.classList.remove("drag-over"));
    tile.addEventListener("drop", (event) => {
      event.preventDefault();
      tile.classList.remove("drag-over");
      if (!draggingTile || draggingTile === tile) return;
      const rect = tile.getBoundingClientRect();
      const insertBefore = event.clientY < rect.top + rect.height / 2;
      if (insertBefore) {
        workspace.insertBefore(draggingTile, tile);
      } else {
        workspace.insertBefore(draggingTile, tile.nextSibling);
      }
    });
  });

  $("tileFullscreenClose")?.addEventListener("click", closeTileFullscreen);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("tileFullscreenOverlay").classList.contains("hidden")) {
      closeTileFullscreen();
    }
  });

  $("resetLayoutBtn")?.addEventListener("click", () => {
    localStorage.removeItem("go2_sensor_layout");
    location.reload();
  });
  applySensorLayout();
}

function persistSensorLayout() {
  const workspace = $("sensorWorkspace");
  if (!workspace) return;
  const order = Array.from(workspace.querySelectorAll(".sensor-tile"))
    .map((tile) => tile.dataset.widget)
    .filter(Boolean);
  localStorage.setItem("go2_sensor_layout", JSON.stringify({ order, version: 1 }));
  // Also best-effort push to backend for shared recall.
  fetch("/api/operator/layout/default", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order, version: 1 }),
  }).catch(() => {});
}

function applySensorLayout() {
  const workspace = $("sensorWorkspace");
  if (!workspace) return;
  try {
    const raw = localStorage.getItem("go2_sensor_layout");
    if (!raw) return;
    const { order } = JSON.parse(raw);
    if (!Array.isArray(order)) return;
    const tiles = Array.from(workspace.querySelectorAll(".sensor-tile"));
    const byWidget = Object.fromEntries(tiles.map((tile) => [tile.dataset.widget, tile]));
    order.forEach((widget) => {
      const tile = byWidget[widget];
      if (tile) workspace.appendChild(tile);
    });
  } catch (_) {}
}

function openTileFullscreen(tile) {
  const overlay = $("tileFullscreenOverlay");
  const mount = $("tileFullscreenMount");
  if (!overlay || !mount) return;
  tile._restoreParent = tile.parentElement;
  tile._restoreNext = tile.nextSibling;
  mount.appendChild(tile);
  overlay.classList.remove("hidden");
  if (tile.id === "lidarCard") renderLidarCanvas(state.lastLidarPoints || []);
}

function closeTileFullscreen() {
  const overlay = $("tileFullscreenOverlay");
  const mount = $("tileFullscreenMount");
  if (!overlay || !mount) return;
  const tile = mount.firstElementChild;
  if (tile && tile._restoreParent) {
    tile._restoreParent.insertBefore(tile, tile._restoreNext || null);
    tile._restoreParent = null;
    tile._restoreNext = null;
  }
  overlay.classList.add("hidden");
  if (tile && tile.id === "lidarCard") renderLidarCanvas(state.lastLidarPoints || []);
}

/* ── Mapping mode bindings ───────────────────────────── */

function bindMappingMode() {
  document.querySelectorAll("[data-mapping-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.mappingMode = btn.dataset.mappingMode;
      document.querySelectorAll("[data-mapping-mode]").forEach((other) => other.classList.remove("active"));
      btn.classList.add("active");
      renderMappingMode(state.overview && state.overview.ros);
    });
  });
}

/* ── Lidar presets + follow / reset ──────────────────── */

function bindLidarControls() {
  document.querySelectorAll("[data-lidar-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.lidarPreset = btn.dataset.lidarPreset;
      document.querySelectorAll("[data-lidar-preset]").forEach((other) => other.classList.remove("active"));
      btn.classList.add("active");
      renderLidarCanvas(state.lastLidarPoints || []);
    });
  });
  $("lidarFollowBtn")?.addEventListener("click", (event) => {
    state.lidarFollow = !state.lidarFollow;
    event.currentTarget.setAttribute("aria-pressed", String(state.lidarFollow));
  });
  $("lidarResetViewBtn")?.addEventListener("click", () => {
    state.lidarFollow = true;
    $("lidarFollowBtn")?.setAttribute("aria-pressed", "true");
    renderLidarCanvas(state.lastLidarPoints || []);
  });
}

/* ── Event tile ──────────────────────────────────────── */

function renderEventTile(records) {
  const container = $("eventTileList");
  if (!container) return;
  const list = (records || []).slice(0, 12);
  if (list.length === 0) {
    container.innerHTML = '<p class="empty-state">No events yet.</p>';
    return;
  }
  container.innerHTML = list
    .map((record) => {
      const when = new Date(record.ts).toLocaleTimeString();
      return `<div class="log-summary log-${record.level || "info"}"><span>${when}</span><strong>${escapeHtml(record.message || record.event || "")}</strong></div>`;
    })
    .join("");
}

async function refreshMissionStatus() {
  try {
    const status = await getJson("/api/ros/mission/status");
    renderMissionProgress(status);
  } catch (_) {
    // silent — /api/operator/overview already feeds the main view.
  }
}

function bootstrap() {
  bindTabs();
  bindActions();
  bindControlActions();
  bindDpad();
  bindMapCanvas();
  bindSensorTiles();
  bindMappingMode();
  bindLidarControls();
  initKeyboard();
  renderMissionEditor();
  $("d1DryRunPayload").textContent = JSON.stringify(buildD1DryRunPayload(), null, 2);
  refreshOverview();
  refreshD1();
  refreshLogs();
  window.setInterval(refreshOverview, 2500);
  window.setInterval(refreshD1, 2500);
  window.setInterval(refreshLogs, 6000);
  window.setInterval(refreshLidar, 400);
  window.setInterval(refreshMissionStatus, 2500);
}

bootstrap();
