"""
Atomic file write helpers for state/config outputs.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: str | Path, content: str, encoding: str = "utf-8") -> None:
    """Write text atomically via temp file + rename."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def atomic_write_json(path: str | Path, payload: Any, ensure_ascii: bool = False) -> None:
    """Serialize JSON and write atomically."""
    text = json.dumps(payload, ensure_ascii=ensure_ascii, indent=2)
    atomic_write_text(path, text)
