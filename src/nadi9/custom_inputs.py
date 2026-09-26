from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


ROLE_LABELS = (
    "Auto-detect",
    "Approved examples",
    "Dictionary",
    "Episode transcript",
    "Grammar note",
    "Expert notes",
    "Interview transcript",
    "Viewer feedback",
    "Catalog metadata",
    "Ignore",
)
ROLE_FILES = {
    "Approved examples": "examples",
    "Dictionary": "dictionary",
    "Episode transcript": "episode",
    "Grammar note": "grammar",
    "Expert notes": "expert_notes",
    "Interview transcript": "interviews",
    "Viewer feedback": "viewer_feedback",
    "Catalog metadata": "catalog",
    "Ignore": "ignore",
}
SUPPORTED_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".srt", ".txt"}


def suggest_role(name: str, content: bytes) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    hint = f"{path.as_posix()} {path.stem}".lower()
    suffix = path.suffix.lower()
    if "catalog" in hint or path.name.lower() == "metadata.json":
        return "Catalog metadata"
    if any(word in hint for word in ("example", "approved")):
        return "Approved examples"
    if any(word in hint for word in ("dictionary", "lexicon", "glossary", "dict_")):
        return "Dictionary"
    if any(word in hint for word in ("episode", "subtitle", "caption")) or suffix == ".srt":
        return "Episode transcript"
    if "grammar" in hint or "rule" in hint:
        return "Grammar note"
    if any(word in hint for word in ("expert", "linguist")):
        return "Expert notes"
    if any(word in hint for word in ("feedback", "viewer", "comment")):
        return "Viewer feedback"
    if any(word in hint for word in ("interview", "transcript", "audio")):
        return "Interview transcript"

    text = content.decode("utf-8-sig", errors="ignore")
    if suffix == ".csv":
        try:
            headers = {header.strip().lower().replace("-", "_") for header in next(csv.reader(io.StringIO(text)), [])}
            if {"start", "start_time", "in"} & headers and {"end", "end_time", "out"} & headers and {"source", "source_text", "text", "dialogue"} & headers:
                return "Episode transcript"
            if {"source", "source_text", "english"} & headers and {"nadi9", "nadi_9", "translation", "translated"} & headers:
                return "Approved examples"
            if {"term", "lemma", "word"} & headers and {"meaning", "gloss", "definition"} & headers:
                return "Dictionary"
        except csv.Error:
            pass
    if suffix == ".json":
        try:
            payload = json.loads(text)
            rows = _rows(payload)
            keys = {str(key).lower() for row in rows[:3] for key in row}
            if {"start", "start_time", "in"} & keys and {"end", "end_time", "out"} & keys and {"source", "text", "source_text", "dialogue"} & keys:
                return "Episode transcript"
            if {"source", "source_text", "english"} & keys and {"nadi9", "nadi_9", "translation", "translated"} & keys:
                return "Approved examples"
            if {"old_claim", "new_claim"} <= keys:
                return "Expert notes"
        except (json.JSONDecodeError, ValueError):
            pass
    if suffix in {".md", ".txt", ".jsonl"}:
        return "Interview transcript"
    return "Auto-detect"


def normalize_custom_files(
    files: list[tuple[str, bytes]],
    data_dir: Path,
    role_overrides: dict[str, str] | None = None,
) -> tuple[Path, list[dict[str, Any]]]:
    """Map common custom source files to the normalized evidence layout."""
    data_dir = Path(data_dir)
    role_overrides = role_overrides or {}
    (data_dir / "interviews").mkdir(parents=True, exist_ok=True)
    (data_dir / "episode").mkdir(parents=True, exist_ok=True)
    (data_dir / "corrections").mkdir(parents=True, exist_ok=True)

    examples: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    dictionaries: dict[str, list[dict[str, Any]]] = {}
    note_files: dict[str, list[str]] = {
        "grammar": [],
        "expert_notes": [],
        "viewer_feedback": [],
    }
    report: list[dict[str, Any]] = []
    catalog: dict[str, Any] | None = None
    used_ids: set[str] = set()

    for name, content in files:
        name = str(name).replace("\\", "/")
        role = role_overrides.get(name, "Auto-detect")
        if role == "Auto-detect":
            role = suggest_role(name, content)
        source_type = ROLE_FILES.get(role)
        if source_type is None:
            report.append({"File": name, "Detected as": role, "Status": "Unsupported role"})
            continue
        if source_type == "ignore":
            report.append({"File": name, "Detected as": role, "Status": "Ignored by reviewer"})
            continue

        suffix = PurePosixPath(name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            report.append({"File": name, "Detected as": role, "Status": f"Unsupported file type: {suffix or 'none'}"})
            continue
        try:
            if source_type == "catalog":
                catalog = json.loads(content.decode("utf-8-sig"))
                report.append({"File": name, "Detected as": role, "Status": "Loaded metadata"})
            elif source_type == "examples":
                rows = _read_rows(name, content)
                added = 0
                for index, row in enumerate(rows, start=1):
                    source = _pick(row, "source", "source_text", "english", "original", "text")
                    translated = _pick(row, "nadi9", "nadi_9", "translation", "translated", "target")
                    if not source or not translated:
                        continue
                    row_id = str(_pick(row, "id", "example_id", "subtitle_id") or f"{_slug(name)}-{index}")
                    examples.append(
                        {
                            "id": _unique_id(row_id, used_ids, name),
                            "source": str(source),
                            "nadi9": str(translated),
                            "speaker": _pick(row, "speaker", "character"),
                            "scene": _pick(row, "scene", "context"),
                            "notes": str(_pick(row, "notes", "context", "status") or ""),
                        }
                    )
                    added += 1
                report.append({"File": name, "Detected as": role, "Status": f"Loaded {added} examples"})
            elif source_type == "dictionary":
                rows = _read_rows(name, content)
                source_id = f"dictionary_{_slug(PurePosixPath(name).stem)}"
                entries = dictionaries.setdefault(source_id, [])
                added = 0
                for index, row in enumerate(rows, start=1):
                    source, translated = _dictionary_pair(row)
                    if not source or not translated:
                        continue
                    entries.append(
                        {
                            "id": str(_pick(row, "id", "entry_id", "term_id") or f"{_slug(name)}-{index}"),
                            "source": str(source),
                            "nadi9": str(translated),
                            "notes": json.dumps(row, ensure_ascii=False, default=str),
                        }
                    )
                    added += 1
                report.append({"File": name, "Detected as": role, "Status": f"Loaded {added} dictionary entries"})
            elif source_type == "episode":
                parsed_segments = _read_episode(name, content)
                added = 0
                for index, segment in enumerate(parsed_segments, start=1):
                    sid = _unique_id(segment.get("subtitle_id") or f"{_slug(name)}-{index:03d}", used_ids, name)
                    segments.append({**segment, "subtitle_id": sid})
                    added += 1
                report.append({"File": name, "Detected as": role, "Status": f"Loaded {added} timed subtitle lines"})
            elif source_type in note_files:
                note_files[source_type].append(f"## {name}\n\n{content.decode('utf-8-sig')}")
                report.append({"File": name, "Detected as": role, "Status": "Loaded text evidence"})
            elif source_type == "interviews":
                text = _as_text(name, content)
                target_name = f"{_slug(PurePosixPath(name).stem)}.txt"
                (data_dir / "interviews" / target_name).write_text(text, encoding="utf-8")
                report.append({"File": name, "Detected as": role, "Status": "Loaded text evidence"})
        except (UnicodeDecodeError, json.JSONDecodeError, csv.Error, ValueError, KeyError) as exc:
            report.append({"File": name, "Detected as": role, "Status": f"Could not parse: {exc}"})

    (data_dir / "examples.json").write_text(
        json.dumps({"examples": examples}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for index, (source_id, entries) in enumerate(dictionaries.items(), start=1):
        filename = "dictionary_a.json" if index == 1 else "dictionary_b.json" if index == 2 else f"{source_id}.json"
        (data_dir / filename).write_text(
            json.dumps({"source_id": source_id, "entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    for role, blocks in note_files.items():
        if blocks:
            filename = {"grammar": "grammar.md", "expert_notes": "expert_notes.md", "viewer_feedback": "viewer_feedback.md"}[role]
            (data_dir / filename).write_text("\n\n".join(blocks), encoding="utf-8")
    (data_dir / "episode" / "transcript.json").write_text(
        json.dumps({"segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if catalog is not None:
        (data_dir / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    if not segments:
        detail = "; ".join(row["File"] + ": " + row["Status"] for row in report)
        raise ValueError("No timed episode lines were found. Include an SRT file or source text with start/end timecodes. " + detail)
    return data_dir, report


def _read_rows(name: str, content: bytes) -> list[dict[str, Any]]:
    suffix = PurePosixPath(name).suffix.lower()
    text = content.decode("utf-8-sig")
    if suffix == ".csv":
        return [dict(row) for row in csv.DictReader(io.StringIO(text))]
    if suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if suffix == ".json":
        return _rows(json.loads(text))
    raise ValueError("Expected CSV, JSON, or JSONL rows")


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("examples", "segments", "subtitles", "lines", "entries", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [dict(row) for row in value if isinstance(row, dict)]
        if any(key in payload for key in ("source", "source_text", "term", "start", "start_time")):
            return [payload]
    raise ValueError("Expected a list of records or an object containing a records list")


def _dictionary_pair(row: dict[str, Any]) -> tuple[Any, Any]:
    lowered = {str(key).lower().replace("-", "_"): value for key, value in row.items()}
    target = _pick(lowered, "nadi9", "nadi_9", "target", "target_word", "translation")
    source = _pick(lowered, "source", "source_word", "english", "gloss", "definition", "meaning")
    if target and source:
        return source, target
    term = _pick(lowered, "term", "lemma", "word")
    gloss = _pick(lowered, "meaning", "gloss", "definition")
    if term and gloss:
        return gloss, term
    return None, None


def _read_episode(name: str, content: bytes) -> list[dict[str, Any]]:
    suffix = PurePosixPath(name).suffix.lower()
    if suffix == ".srt":
        text = content.decode("utf-8-sig")
        pattern = re.compile(
            r"(?:^|\n\s*\n)\s*\d+\s*\n"
            r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
            r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})[^\n]*\n"
            r"(?P<text>.*?)(?=\n\s*\n|\Z)",
            re.DOTALL,
        )
        return [
            {
                "subtitle_id": f"S{index:03d}",
                "start_time": match.group("start").replace(".", ","),
                "end_time": match.group("end").replace(".", ","),
                "source_text": " ".join(line.strip() for line in match.group("text").splitlines() if line.strip()),
                "speaker": None,
                "scene": None,
            }
            for index, match in enumerate(pattern.finditer(text), start=1)
        ]
    rows = _read_rows(name, content)
    segments = []
    for row in rows:
        start = _pick(row, "start_time", "start", "in", "begin")
        end = _pick(row, "end_time", "end", "out", "finish")
        source = _pick(row, "source_text", "source", "text", "dialogue", "caption")
        if not start or not end or not source:
            continue
        segments.append(
            {
                "subtitle_id": str(_pick(row, "subtitle_id", "id", "line_id") or ""),
                "start_time": _normalize_time(start),
                "end_time": _normalize_time(end),
                "source_text": str(source),
                "speaker": _pick(row, "speaker", "character"),
                "scene": _pick(row, "scene", "location"),
            }
        )
    return segments


def _normalize_time(value: Any) -> str:
    if isinstance(value, (int, float)):
        total_milliseconds = round(float(value) * 1000)
        hours, remainder = divmod(total_milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    text = str(value).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return _normalize_time(float(text))
    return text.replace(".", ",") if re.fullmatch(r"\d\d:\d\d:\d\d\.\d{3}", text) else text


def _as_text(name: str, content: bytes) -> str:
    suffix = PurePosixPath(name).suffix.lower()
    if suffix == ".jsonl":
        return content.decode("utf-8-sig")
    if suffix == ".json":
        return json.dumps(json.loads(content.decode("utf-8-sig")), ensure_ascii=False, indent=2)
    return content.decode("utf-8-sig")


def _pick(row: dict[str, Any], *keys: str) -> Any:
    lowered = {str(key).lower().replace("-", "_").replace(" ", "_"): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower().replace("-", "_").replace(" ", "_"))
        if value is not None and str(value).strip():
            return value
    return None


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "source"


def _unique_id(value: str, used: set[str], filename: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_") or "row"
    if value not in used:
        used.add(value)
        return value
    candidate = f"{_slug(PurePosixPath(filename).stem)}_{value}"
    suffix = 2
    while candidate in used:
        candidate = f"{_slug(PurePosixPath(filename).stem)}_{value}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate
