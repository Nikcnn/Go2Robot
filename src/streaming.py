from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone

import cv2


_log = logging.getLogger(__name__)


class EventBus:
    def __init__(self, history_limit: int = 200) -> None:
        self._lock = threading.Lock()
        self._events = deque(maxlen=history_limit)
        self._next_sequence = 1

    def publish(self, event: str, details: dict | None = None) -> dict:
        record = {
            "sequence": None,
            "ts": datetime.now(timezone.utc),
            "event": event,
            "details": details or {},
        }
        with self._lock:
            record["sequence"] = self._next_sequence
            self._next_sequence += 1
            self._events.append(record)
        return record

    def recent(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return list(self._events)[-limit:]

    def read_since(self, sequence: int) -> list[dict]:
        with self._lock:
            return [event for event in self._events if event["sequence"] and event["sequence"] > sequence]


class CameraStream:
    def __init__(self, adapter, fps: int, width: int, height: int, jpeg_quality: int) -> None:
        self.adapter = adapter
        self.fps = max(1, fps)
        self.width = width
        self.height = height
        self.jpeg_quality = jpeg_quality
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_jpeg: bytes | None = None

    def start(self) -> None:
        self._capture_once()
        self._thread = threading.Thread(target=self._run, name="camera-stream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def get_latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    def mjpeg_generator(self):
        boundary = b"--frame"
        while not self._stop_event.is_set():
            payload = self.get_latest_jpeg()
            if payload:
                yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"
            time.sleep(1.0 / self.fps)

    def _run(self) -> None:
        period = 1.0 / self.fps
        while not self._stop_event.wait(period):
            try:
                self._capture_once()
            except Exception as exc:
                _log.warning("camera stream update failed", extra={"err": str(exc)})

    def _capture_once(self) -> None:
        frame = self.adapter.capture_frame()
        if frame is None:
            return
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        if not ok:
            return
        with self._lock:
            self._latest_jpeg = encoded.tobytes()
