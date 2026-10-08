"""Preserve API payloads while providing PostgreSQL-compatible projections."""

import json
import math


class _ProjectionUnavailable(ValueError):
    """The source value cannot be represented losslessly in PostgreSQL JSONB."""


def _safe_text(value, flags):
    output = []
    for char in value:
        codepoint = ord(char)
        if codepoint == 0:
            output.append("\uFFFD")
            flags.add("U+0000_REPLACED_IN_JSONB")
        elif 0xD800 <= codepoint <= 0xDFFF:
            output.append("\uFFFD")
            flags.add("UNPAIRED_SURROGATE_REPLACED_IN_JSONB")
        else:
            output.append(char)
    return "".join(output)


def _project(value, flags):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        flags.add("NON_FINITE_NUMBER_REPLACED_WITH_NULL")
        return None
    if isinstance(value, str):
        return _safe_text(value, flags)
    if isinstance(value, (list, tuple)):
        return [_project(item, flags) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                flags.add("NON_STRING_JSON_KEY")
                raise _ProjectionUnavailable
            safe_key = _safe_text(key, flags)
            if safe_key in result:
                flags.add("NORMALIZED_JSON_KEY_COLLISION")
                raise _ProjectionUnavailable
            result[safe_key] = _project(item, flags)
        return result
    flags.add("UNSUPPORTED_JSON_VALUE_TYPE")
    raise _ProjectionUnavailable


def postgres_value(value):
    """Return a safe projection and sorted flags without altering source data."""
    flags = set()
    try:
        projection = _project(value, flags)
    except _ProjectionUnavailable:
        projection = {} if isinstance(value, dict) else None
        flags.add("JSONB_PROJECTION_UNAVAILABLE")
    return projection, sorted(flags)


def normalize_payload(value):
    """Normalize one API job object; preserve the original separately."""
    if not isinstance(value, dict):
        raise ValueError("Every source job payload must be a JSON object")
    return postgres_value(value)


def payload_quality_flags(value):
    return normalize_payload(value)[1]


def source_json(value):
    """Serialize parsed source values deterministically for PostgreSQL TEXT."""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"),
                      sort_keys=True, allow_nan=True)


def jsonb_projection(value):
    """Return only the PostgreSQL-safe projection of a source value."""
    return postgres_value(value)[0]
