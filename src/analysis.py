from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from .models import AnalysisResult


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _resize_square(frame: np.ndarray, size: int = 96) -> np.ndarray:
    return cv2.resize(frame, (size, size), interpolation=cv2.INTER_AREA)


def _edge_map(gray: np.ndarray) -> np.ndarray:
    return cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)


def _load_reference_image(reference_image: str) -> tuple[Path, np.ndarray | None]:
    reference_path = Path(reference_image)
    if not reference_path.exists():
        return reference_path, None
    return reference_path, cv2.imread(str(reference_path))


class FrameDiffAnalyzer:
    """Crop → resize → normalize → diff → threshold.

    Use cases: door open/closed, panel changed/unchanged, indicator on/off.
    """

    name = "frame_diff"

    def analyze(self, frame: np.ndarray | None, params: dict) -> AnalysisResult:
        threshold = float(params.get("threshold", 0.25))
        reference_image = params.get("reference_image")

        if frame is None:
            return AnalysisResult(
                analyzer_name=self.name,
                label="capture_failed",
                score=0.0,
                passed=False,
                threshold=threshold,
                details={"reason": "no_frame"},
                timestamp=_utc_ts(),
            )

        if not reference_image:
            return AnalysisResult(
                analyzer_name=self.name,
                label="not_configured",
                score=0.0,
                passed=False,
                threshold=threshold,
                details={"reason": "missing_reference_image"},
                timestamp=_utc_ts(),
            )

        reference_path, reference = _load_reference_image(reference_image)
        if reference is None and not reference_path.exists():
            return AnalysisResult(
                analyzer_name=self.name,
                label="not_configured",
                score=0.0,
                passed=False,
                threshold=threshold,
                details={"reason": "reference_image_not_found", "reference_image": str(reference_path)},
                reference_image_path=str(reference_path),
                timestamp=_utc_ts(),
            )

        if reference is None:
            return AnalysisResult(
                analyzer_name=self.name,
                label="reference_load_failed",
                score=0.0,
                passed=False,
                threshold=threshold,
                details={"reference_image": str(reference_path)},
                reference_image_path=str(reference_path),
                timestamp=_utc_ts(),
            )

        # crop → resize → normalize → diff
        h, w = reference.shape[:2]
        live = cv2.resize(frame, (w, h)) if frame.shape[:2] != (h, w) else frame
        score = float(
            np.mean(np.abs(live.astype(np.float32) - reference.astype(np.float32))) / 255.0
        )
        label = "changed" if score > threshold else "stable"
        return AnalysisResult(
            analyzer_name=self.name,
            label=label,
            score=score,
            passed=(label == "stable"),
            threshold=threshold,
            details={"threshold": threshold, "reference_image": str(reference_path)},
            reference_image_path=str(reference_path),
            timestamp=_utc_ts(),
        )


class NarrowClassifierHook:
    """Lightweight classical-CV presence classifier.

    Uses reference-image similarity when available; otherwise falls back to an
    edge-and-contrast objectness score for simple presence checks.
    """

    name = "narrow_classifier"

    def analyze(self, frame: np.ndarray | None, params: dict) -> AnalysisResult:
        threshold = float(params.get("threshold", 0.5))
        if frame is None:
            return AnalysisResult(
                analyzer_name=self.name,
                label="capture_failed",
                score=0.0,
                passed=False,
                threshold=threshold,
                details={"reason": "no_frame"},
                timestamp=_utc_ts(),
            )
        gray = _resize_square(_to_gray(frame))
        reference_image = params.get("reference_image")
        if reference_image:
            reference_path, reference = _load_reference_image(reference_image)
            if reference is None and not reference_path.exists():
                return AnalysisResult(
                    analyzer_name=self.name,
                    label="not_configured",
                    score=0.0,
                    passed=False,
                    threshold=threshold,
                    details={"reason": "reference_image_not_found", "reference_image": str(reference_path)},
                    reference_image_path=str(reference_path),
                    timestamp=_utc_ts(),
                )
            if reference is None:
                return AnalysisResult(
                    analyzer_name=self.name,
                    label="reference_load_failed",
                    score=0.0,
                    passed=False,
                    threshold=threshold,
                    details={"reference_image": str(reference_path)},
                    reference_image_path=str(reference_path),
                    timestamp=_utc_ts(),
                )
            ref_gray = _resize_square(_to_gray(reference))
            live_hist = cv2.calcHist([gray], [0], None, [32], [0, 256])
            ref_hist = cv2.calcHist([ref_gray], [0], None, [32], [0, 256])
            cv2.normalize(live_hist, live_hist)
            cv2.normalize(ref_hist, ref_hist)
            hist_corr = float(cv2.compareHist(live_hist, ref_hist, cv2.HISTCMP_CORREL))
            hist_score = float(np.clip((hist_corr + 1.0) / 2.0, 0.0, 1.0))
            live_edges = _edge_map(gray) > 0
            ref_edges = _edge_map(ref_gray) > 0
            edge_union = int(np.count_nonzero(np.logical_or(live_edges, ref_edges)))
            edge_overlap = (
                1.0
                if edge_union == 0
                else float(np.count_nonzero(np.logical_and(live_edges, ref_edges))) / float(edge_union)
            )
            score = float(np.clip(0.5 * hist_score + 0.5 * edge_overlap, 0.0, 1.0))
            label = "present" if score >= threshold else "absent"
            return AnalysisResult(
                analyzer_name=self.name,
                label=label,
                score=score,
                passed=(label == "present"),
                threshold=threshold,
                details={
                    "model": "hist_edge_similarity",
                    "hist_score": round(hist_score, 4),
                    "edge_overlap": round(edge_overlap, 4),
                    "reference_image": str(reference_path),
                },
                reference_image_path=str(reference_path),
                timestamp=_utc_ts(),
            )

        edge_density = float(np.count_nonzero(_edge_map(gray))) / float(gray.size)
        contrast_std = float(np.std(gray))
        edge_score = min(edge_density / 0.03, 1.0)
        contrast_score = min(contrast_std / 64.0, 1.0)
        score = float(np.clip(0.55 * edge_score + 0.45 * contrast_score, 0.0, 1.0))
        label = "present" if score >= threshold else "absent"
        return AnalysisResult(
            analyzer_name=self.name,
            label=label,
            score=score,
            passed=(label == "present"),
            threshold=threshold,
            details={
                "model": "edge_contrast_presence",
                "edge_density": round(edge_density, 4),
                "contrast_std": round(contrast_std, 2),
            },
            timestamp=_utc_ts(),
        )


_ANALYZERS: dict[str, FrameDiffAnalyzer | NarrowClassifierHook] = {
    "frame_diff": FrameDiffAnalyzer(),
    "simple_presence": NarrowClassifierHook(),
    "narrow_classifier": NarrowClassifierHook(),
}


def analyze(frame: np.ndarray | None, analyzer: str | None, params: dict | None = None) -> AnalysisResult:
    """Run named analyzer; returns AnalysisResult with mock data for unknown/None analyzers."""
    params = params or {}
    name = analyzer or "none"
    impl = _ANALYZERS.get(name)
    if impl is not None:
        return impl.analyze(frame, params)
    # Unknown analyzer — return a valid AnalysisResult so checkpoints always persist
    return AnalysisResult(
        analyzer_name=name,
        label="not_configured",
        score=0.0,
        passed=False,
        threshold=float(params.get("threshold", 0.25)),
        details={"reason": "unknown_or_missing_analyzer"},
        timestamp=_utc_ts(),
    )
