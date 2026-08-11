"""Worker test bootstrap with the complete API SQLModel registry."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_API_SRC = _REPO_ROOT / "apps" / "api"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from app import models as _models  # noqa: E402, F401
