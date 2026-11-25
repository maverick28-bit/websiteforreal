"""Parse X-Simulate-Failure header into a failure map."""
from __future__ import annotations

from typing import Dict, Optional


def parse_failure_header(header_value: Optional[str]) -> Dict[str, int]:
    """
    Parse "key_1=429,key_2=500" or "*=503" into {key_id: status_code}.
    Returns empty dict if header is None or malformed.
    """
    if not header_value:
        return {}
    failures: Dict[str, int] = {}
    for part in header_value.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, code_str = part.partition("=")
        key = key.strip()
        try:
            code = int(code_str.strip())
            if code in (429, 500, 502, 503):
                failures[key] = code
        except ValueError:
            pass
    return failures


def should_simulate_failure(key_id: str, failures: Dict[str, int]) -> Optional[int]:
    """
    Return the simulated status code for a given key_id, or None if no failure.
    Wildcard '*' applies to all keys.
    """
    if "*" in failures:
        return failures["*"]
    return failures.get(key_id)
