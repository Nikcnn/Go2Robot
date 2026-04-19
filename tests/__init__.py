from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def make_test_dir(name: str) -> Path:
    path = ROOT / "runs" / "_test_artifacts" / f"{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path
