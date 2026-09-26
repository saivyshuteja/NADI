from __future__ import annotations

import re
from datetime import datetime

from nadi9.models import ValidationIssue


def parse_ts(value: str) -> datetime:
    return datetime.strptime(value.replace(",", "."), "%H:%M:%S.%f")


def duration_seconds(start: str, end: str) -> float:
    return (parse_ts(end) - parse_ts(start)).total_seconds()


def chars_per_second(text: str | None, start: str, end: str) -> float:
    if not text:
        return 0.0
    dur = duration_seconds(start, end)
    if dur <= 0:
        return 999.0
    return len(text) / dur


def timing_issues(start: str, end: str, text: str | None, max_cps: float) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        if parse_ts(end) <= parse_ts(start):
            issues.append(ValidationIssue(code="timing", severity="high", message="end_time must be after start_time"))
    except ValueError:
        issues.append(ValidationIssue(code="timing", severity="high", message="invalid timecode"))
        return issues
    cps = chars_per_second(text, start, end)
    if text and cps > max_cps:
        issues.append(
            ValidationIssue(
                code="reading_speed",
                severity="medium",
                message=f"reading speed {cps:.1f} CPS exceeds {max_cps}",
            )
        )
    return issues


def validate_srt_order(segments: list[dict]) -> list[ValidationIssue]:
    issues = []
    prev_end = None
    seen = set()
    for seg in segments:
        sid = seg["subtitle_id"]
        if sid in seen:
            issues.append(ValidationIssue(code="duplicate_id", severity="high", message=sid))
        seen.add(sid)
        if prev_end and parse_ts(seg["start_time"]) < prev_end:
            issues.append(ValidationIssue(code="overlap", severity="medium", message=sid))
        prev_end = parse_ts(seg["end_time"])
    return issues
