from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Any

import cv2
import numpy as np

from .models import AnalyzerResult, AnalysisResult


class FrameDiffAnalyzer:
    """Analyzer that compares the current frame with a reference image."""

    def analyze(self, frame: Optional[np.ndarray], params: Dict[str, Any]) -> AnalysisResult:
        res = _frame_diff(frame, params)
        threshold = float(params.get("threshold", 0.25))
        return AnalysisResult(
            analyzer_name="frame_diff",
            label=res.result,
            score=res.score or 0.0,
            passed=(res.result == "stable"),
            threshold=threshold,
            details=res.details,
            reference_image_path=params.get("reference_image"),
        )


class NarrowClassifierHook:
    """Analyzer that detects presence of a specific target, possibly using similarity."""

    def analyze(self, frame: Optional[np.ndarray], params: Dict[str, Any]) -> AnalysisResult:
        threshold = float(params.get("threshold", 0.5))
        if params.get("reference_image"):
            res = _reference_similarity(frame, params)
            label = "present" if (res.score or 0.0) >= threshold else "absent"
            passed = label == "present"
        else:
            # Otherwise use simple presence heuristic
            res = _simple_presence(frame, params)
            label = res.result
            passed = (res.result == "present")

        return AnalysisResult(
            analyzer_name="narrow_classifier",
            label=label,
            score=res.score or 0.0,
            passed=passed,
            threshold=threshold,
            details=res.details,
            reference_image_path=params.get("reference_image"),
        )


def analyze(frame: Optional[np.ndarray], analyzer: Optional[str], params: Optional[Dict[str, Any]] = None) -> AnalysisResult:
    """Top-level entry point for analysis, returns an AnalysisResult object."""
    params = params or {}
    if analyzer == "frame_diff":
        return FrameDiffAnalyzer().analyze(frame, params)
    if analyzer == "simple_presence" or analyzer == "narrow_classifier":
        return NarrowClassifierHook().analyze(frame, params)
    
    return AnalysisResult(
        analyzer_name=analyzer or "none",
        label="not_configured",
        score=0.0,
        passed=False,
        threshold=0.0,
        details={"reason": "unknown_or_missing_analyzer"},
    )


def _frame_diff(frame: Optional[np.ndarray], params: Dict[str, Any]) -> AnalyzerResult:
    """Internal helper for frame difference logic."""
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
    diff = float(np.mean(np.abs(frame.astype(np.float32) - reference.astype(np.float32))) / 255.0)
    result = "stable" if diff <= threshold else "changed"
    
    return AnalyzerResult(
        analyzer="frame_diff",
        status="ok",
        result=result,
        score=diff,
        details={"threshold": threshold, "reference_image": str(reference_path)},
    )


def _reference_similarity(frame: Optional[np.ndarray], params: Dict[str, Any]) -> AnalyzerResult:
    if frame is None:
        return AnalyzerResult(
            analyzer="reference_similarity",
            status="error",
            result="capture_failed",
            details={"reason": "no_frame"},
        )

    reference_image = params.get("reference_image")
    reference_path = Path(reference_image)
    if not reference_path.exists():
        return AnalyzerResult(
            analyzer="reference_similarity",
            status="not_configured",
            result="not_configured",
            details={"reason": "reference_image_not_found", "reference_image": str(reference_path)},
        )

    reference = cv2.imread(str(reference_path))
    if reference is None:
        return AnalyzerResult(
            analyzer="reference_similarity",
            status="error",
            result="reference_load_failed",
            details={"reference_image": str(reference_path)},
        )

    if frame.shape[:2] != reference.shape[:2]:
        frame = cv2.resize(frame, (reference.shape[1], reference.shape[0]))

    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32).reshape(-1)
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY).astype(np.float32).reshape(-1)
    frame_norm = float(np.linalg.norm(frame_gray))
    reference_norm = float(np.linalg.norm(reference_gray))
    if frame_norm <= 1e-6 and reference_norm <= 1e-6:
        similarity = 1.0
    elif frame_norm <= 1e-6 or reference_norm <= 1e-6:
        similarity = 0.0
    else:
        similarity = float(np.dot(frame_gray, reference_gray) / (frame_norm * reference_norm))

    threshold = float(params.get("threshold", 0.5))
    return AnalyzerResult(
        analyzer="reference_similarity",
        status="ok",
        result="present" if similarity >= threshold else "absent",
        score=max(0.0, min(1.0, similarity)),
        details={"threshold": threshold, "reference_image": str(reference_path)},
    )


def _simple_presence(frame: Optional[np.ndarray], params: Dict[str, Any]) -> AnalyzerResult:
    """Internal helper for simple presence (brightness-based) detection."""
    if frame is None:
        return AnalyzerResult(
            analyzer="simple_presence",
            status="error",
            result="capture_failed",
            details={"reason": "no_frame"},
        )

    threshold = float(params.get("threshold", 0.05))
    brightness = float(np.mean(frame.astype(np.float32)) / 255.0)
    result = "present" if brightness > threshold else "absent"
    
    return AnalyzerResult(
        analyzer="simple_presence",
        status="ok",
        result=result,
        score=brightness,
        details={"threshold": threshold},
    )
