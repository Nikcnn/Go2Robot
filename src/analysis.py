from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .models import AnalyzerResult


def analyze(frame: Optional[np.ndarray], analyzer: Optional[str], params: Optional[dict] = None) -> dict:
    params = params or {}
    if analyzer == "frame_diff":
        return _frame_diff(frame, params).model_dump(mode="json")
    if analyzer == "simple_presence":
        return _simple_presence(frame).model_dump(mode="json")
    return AnalyzerResult(
        analyzer=analyzer or "none",
        status="not_configured",
        result="not_configured",
        details={"reason": "unknown_or_missing_analyzer"},
    ).model_dump(mode="json")


def _frame_diff(frame: Optional[np.ndarray], params: dict) -> AnalyzerResult:
    if frame is None:
        return AnalyzerResult(
            analyzer="frame_diff",
            status="error",
            result="capture_failed",
            details={"reason": "no_frame"},
        )

    reference_image = params.get("reference_image")
    if not reference_image:
        return AnalyzerResult(
            analyzer="frame_diff",
            status="not_configured",
            result="not_configured",
            details={"reason": "missing_reference_image"},
        )

    reference_path = Path(reference_image)
    if not reference_path.exists():
        return AnalyzerResult(
            analyzer="frame_diff",
            status="not_configured",
            result="not_configured",
            details={"reason": "reference_image_not_found", "reference_image": str(reference_path)},
        )

    reference = cv2.imread(str(reference_path))
    if reference is None:
        return AnalyzerResult(
            analyzer="frame_diff",
            status="error",
            result="reference_load_failed",
            details={"reference_image": str(reference_path)},
        )

    if frame.shape[:2] != reference.shape[:2]:
        frame = cv2.resize(frame, (reference.shape[1], reference.shape[0]))

    threshold = float(params.get("threshold", 0.25))
    diff = np.mean(np.abs(frame.astype(np.float32) - reference.astype(np.float32))) / 255.0
    result = "changed" if diff > threshold else "stable"
    return AnalyzerResult(
        analyzer="frame_diff",
        status="ok",
        result=result,
        score=float(diff),
        details={"threshold": threshold, "reference_image": str(reference_path)},
    )


def _simple_presence(frame: Optional[np.ndarray]) -> AnalyzerResult:
    if frame is None:
        return AnalyzerResult(
            analyzer="simple_presence",
            status="error",
            result="capture_failed",
            details={"reason": "no_frame"},
        )

    return AnalyzerResult(
        analyzer="simple_presence",
        status="not_configured",
        result="not_configured",
        details={"reason": "simple_presence_is_a_stub"},
    )
