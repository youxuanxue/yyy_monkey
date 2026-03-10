"""
Security helpers for untrusted external identifiers.
"""

from __future__ import annotations

def sanitize_identifier(value: str | None, field_name: str = "identifier") -> str | None:
    """
    Validate identifier used in file-path composition.

    Rules:
    - allow only ASCII letters/digits/_/-
    - length 1..64
    - reject path traversal and separators (`..`, `/`, `\\`)
    """
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    if ".." in normalized or "/" in normalized or "\\" in normalized:
        raise ValueError(f"{field_name} contains forbidden path characters")

    if len(normalized) > 64:
        raise ValueError(f"{field_name} is too long (max 64 chars)")

    if normalized in {".", ".."}:
        raise ValueError(
            f"{field_name} must be a normal name (not dot-path markers)"
        )

    return normalized
