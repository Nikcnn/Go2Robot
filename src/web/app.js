const state = {
  overview: null,
  missionDraft: null,
  originalMissionId: "",
  selectedLogCategory: "",
  activeCamera: "built_in",
  loadingMission: false,
  d1: null,
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
  updatePoseHint(overview.pose);
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

  if (!state.missionDraft && missions.length > 0 && !state.loadingMission) {
    loadMission(missions[0].id || missions[0].mission_id, false);
  }
}

function renderMissionProgress(progress) {
  text("activeWaypoint", progress.active_waypoint || "None");
  text("completedWaypoints", `${progress.completed_waypoints || 0} / ${progress.total_waypoints || 0}`);
  text("currentTask", progress.current_task || "None");
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
  $("missionMapSelect").value = mission.map_id || $("missionMapSelect").value;
  const list = $("waypointList");
  list.innerHTML = "";

  if (!mission.waypoints || mission.waypoints.length === 0) {
    list.innerHTML = '<p class="empty-state">No waypoints yet. Add one from the robot pose or use the JSON editor.</p>';
  } else {
    mission.waypoints.forEach((waypoint, index) => {
      const card = document.createElement("article");
      card.className = "waypoint-card";
      card.dataset.index = String(index);
      card.innerHTML = `
        <div class="waypoint-card-header">
          <span class="step-number">${index + 1}</span>
          <div class="compact-actions">
            <button class="icon-action" data-waypoint-action="up" ${index === 0 ? "disabled" : ""}>Up</button>
            <button class="icon-action" data-waypoint-action="down" ${index === mission.waypoints.length - 1 ? "disabled" : ""}>Down</button>
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
  $("builtInCameraCard").classList.toggle("active-sensor", which === "built_in");
  $("realsenseCard").classList.toggle("active-sensor", which === "realsense");
  $("useBuiltInCameraBtn").classList.toggle("active", which === "built_in");
  $("useRealsenseCameraBtn").classList.toggle("active", which === "realsense");
  if (which === "realsense" && !$("realsenseFeed").src) {
    $("realsenseFeed").src = "/stream/realsense/color";
  }
}

function bindTabs() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-button").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
      button.classList.add("active");
      $(button.dataset.tab).classList.add("active");
    });
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
    mutateWaypoints(button.dataset.waypointAction, Number(card.dataset.index));
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

  $("useBuiltInCameraBtn").addEventListener("click", () => setActiveCamera("built_in"));
  $("useRealsenseCameraBtn").addEventListener("click", () => setActiveCamera("realsense"));

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
    try { await sendJson("/api/mode/manual/take"); showToast("Manual mode active."); refreshOverview(); }
    catch (e) { showToast(e.message, "error"); }
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

function renderLidarCanvas(points) {
  const canvas = $("lidarCanvas");
  if (!canvas) return;
  const w = canvas.clientWidth || 300;
  const h = canvas.clientHeight || 300;
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  const cx = w / 2, cy = h / 2;
  const maxRange = 3.5;
  const scale = Math.min(w, h) / 2 * 0.85;
  const ppm = scale / maxRange;

  ctx.fillStyle = "#080d0d";
  ctx.fillRect(0, 0, w, h);

  // Rings + labels
  ctx.strokeStyle = "rgba(255,255,255,0.07)";
  ctx.lineWidth = 1;
  ctx.fillStyle = "rgba(255,255,255,0.20)";
  ctx.font = `${Math.max(9, Math.round(w * 0.034))}px monospace`;
  ctx.textBaseline = "middle";
  for (let r = 1; r <= Math.ceil(maxRange); r++) {
    ctx.beginPath();
    ctx.arc(cx, cy, r * ppm, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillText(r + "m", cx + r * ppm + 3, cy - 6);
  }

  // Crosshairs
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.beginPath();
  ctx.moveTo(cx, cy - scale); ctx.lineTo(cx, cy + scale);
  ctx.moveTo(cx - scale, cy); ctx.lineTo(cx + scale, cy);
  ctx.stroke();

  // Scan points
  ctx.fillStyle = "#00c9be";
  for (const p of points) {
    if (p.distance > maxRange) continue;
    const px = cx + Math.cos(p.angle) * p.distance * ppm;
    const py = cy - Math.sin(p.angle) * p.distance * ppm;
    ctx.beginPath();
    ctx.arc(px, py, 1.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // Robot marker
  ctx.fillStyle = "rgba(255,255,255,0.90)";
  ctx.beginPath();
  ctx.arc(cx, cy, 4, 0, Math.PI * 2);
  ctx.fill();

  // Forward arrow (90° = up in canvas coords)
  ctx.strokeStyle = "rgba(255,255,255,0.45)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx, cy - 18);
  ctx.stroke();
}

async function refreshLidar() {
  const panel = $("sensors");
  if (!panel || !panel.classList.contains("active")) return;
  try {
    const data = await getJson("/api/robot/lidar/scan");
    if (data.available && data.points && data.points.length > 0) {
      renderLidarCanvas(data.points);
      setDot("lidarStatus", "Active", true);
      const note = $("lidarViewerNote");
      if (note) note.textContent = data.points.length + " scan points";
    } else {
      setDot("lidarStatus", "Waiting", false);
    }
  } catch (_) {
    // silent
  }
}

function bootstrap() {
  bindTabs();
  bindActions();
  bindControlActions();
  bindDpad();
  initKeyboard();
  setActiveCamera("built_in");
  renderMissionEditor();
  $("d1DryRunPayload").textContent = JSON.stringify(buildD1DryRunPayload(), null, 2);
  refreshOverview();
  refreshD1();
  refreshLogs();
  window.setInterval(refreshOverview, 2500);
  window.setInterval(refreshD1, 2500);
  window.setInterval(refreshLogs, 6000);
  window.setInterval(refreshLidar, 400);
}

bootstrap();
