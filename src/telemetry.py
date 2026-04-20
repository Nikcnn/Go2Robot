from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

from .models import MissionStatus, TelemetrySnapshot


_log = logging.getLogger(__name__)


class TelemetryService:
    def __init__(
        self,
        adapter,
        control,
        storage,
        hz: int,
        state_machine=None,
        get_connected: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.adapter = adapter
        self.control = control
        self.storage = storage
        self.hz = max(1, hz)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest: Optional[TelemetrySnapshot] = None
        self._state_machine = state_machine
        # Injected after AppRuntime is created so we can read runtime.adapter_connected
        self._get_connected: Callable[[], bool] = get_connected or (lambda: True)

    def start(self) -> None:
        self._latest = self._capture_snapshot()
        self._thread = threading.Thread(target=self._run, name="telemetry-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def get_latest(self) -> TelemetrySnapshot:
        with self._lock:
            if self._latest is not None:
                return self._latest
        snapshot = self._capture_snapshot()
        with self._lock:
            self._latest = snapshot
        return snapshot

    def _run(self) -> None:
        period = 1.0 / float(self.hz)
        while not self._stop_event.wait(period):
            try:
                snapshot = self._capture_snapshot()
                with self._lock:
                    self._latest = snapshot
                self.storage.append_telemetry(snapshot.model_dump(mode="json"))
                self._update_state_machine(snapshot)
            except Exception as exc:
                _log.warning("telemetry poll failed", extra={"err": str(exc)})

    def _update_state_machine(self, snapshot: TelemetrySnapshot) -> None:
        if self._state_machine is None:
            return
        current = self.control.current()
        is_paused = current.mission_status == MissionStatus.PAUSED_MANUAL
        self._state_machine.update(
            connected=self._get_connected(),
            robot_state=snapshot.robot_state,
            estop_latched=current.estop_latched,
            is_paused=is_paused,
        )

    def _capture_snapshot(self) -> TelemetrySnapshot:
        current = self.control.current()
        return TelemetrySnapshot(
            timestamp=datetime.now(timezone.utc),
            mode=current.robot_mode,
            mission_status=current.mission_status,
            route_id=current.route_id,
            active_step_id=current.active_step_id,
            mission_id=current.mission_id,
            pose=self.adapter.get_pose(),
            robot_state=self.adapter.get_state(),
        )
