from __future__ import annotations

import json
import re
from pathlib import Path

from nadi9.models import EvidenceRecord, SourceType
from nadi9.security.injection import detect_injection


def _catalog_map(data_dir: Path) -> dict:
    catalog_path = data_dir / "catalog.json"
    if not catalog_path.exists():
        return {}
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {row["source_id"]: row for row in payload.get("sources", [])}


def _meta(catalog: dict, source_id: str) -> dict:
    return catalog.get(source_id, {})


def load_evidence(data_dir: Path) -> list[EvidenceRecord]:
    data_dir = Path(data_dir)
    catalog = _catalog_map(data_dir)
    records: list[EvidenceRecord] = []
    records.extend(_load_examples(data_dir, catalog))
    dictionary_files = sorted(data_dir.glob("dictionary_*.json"))
    for path in dictionary_files:
        records.extend(_load_dictionary(path, catalog))
    records.extend(_load_markdown(data_dir / "grammar.md", "grammar", SourceType.GRAMMAR, catalog))
    records.extend(_load_markdown(data_dir / "expert_notes.md", "expert_notes", SourceType.EXPERT, catalog))
    records.extend(_load_markdown(data_dir / "viewer_feedback.md", "viewer_feedback", SourceType.FEEDBACK, catalog))
    records.extend(_load_interviews(data_dir / "interviews", catalog))
    records.extend(_load_episode(data_dir / "episode" / "transcript.json", catalog))
    return records


def load_episode_segments(data_dir: Path) -> list[dict]:
    path = Path(data_dir) / "episode" / "transcript.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["segments"]


def load_correction(data_dir: Path) -> dict | None:
    path = Path(data_dir) / "corrections" / "linguist_r17.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _base(catalog: dict, source_id: str, source_type: SourceType) -> dict:
    meta = _meta(catalog, source_id)
    return {
        "source_id": source_id,
        "source_type": source_type,
        "author": meta.get("author"),
        "date": meta.get("date"),
        "scope": meta.get("scope"),
        "reliability": float(meta.get("reliability", 0.5)),
        "version": str(meta.get("version", "1")),
    }


def _load_examples(data_dir: Path, catalog: dict) -> list[EvidenceRecord]:
    path = data_dir / "examples.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for item in payload["examples"]:
        content = f"source: {item['source']}\nnadi-9: {item['nadi9']}\nspeaker: {item.get('speaker')}\nscene: {item.get('scene')}\nnotes: {item.get('notes', '')}"
        rows.append(
            EvidenceRecord(
                evidence_id=f"example:{item['id']}",
                content=content,
                claim=f"{item['source']} => {item['nadi9']}",
                speaker=item.get("speaker"),
                scene=item.get("scene"),
                metadata={"source_text": item["source"], "nadi9": item["nadi9"], "notes": item.get("notes", "")},
                injection_flag=detect_injection(content),
                **_base(catalog, "examples", SourceType.EXAMPLE),
            )
        )
    return rows


def _load_dictionary(path: Path, catalog: dict) -> list[EvidenceRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_id = payload["source_id"]
    rows = []
    for entry in payload["entries"]:
        content = f"{entry['source']} => {entry['nadi9']}. {entry.get('notes', '')}"
        poisoned = bool(entry.get("poisoned")) or detect_injection(str(entry["nadi9"]))
        rows.append(
            EvidenceRecord(
                evidence_id=f"dictionary:{source_id}:{entry['id']}",
                content=content,
                claim=content,
                metadata={
                    "lemma": entry["source"].lower(),
                    "nadi9": entry["nadi9"],
                    "poisoned": poisoned,
                },
                injection_flag=poisoned,
                **_base(catalog, source_id, SourceType.DICTIONARY),
            )
        )
    return rows


def _load_markdown(path: Path, source_id: str, source_type: SourceType, catalog: dict) -> list[EvidenceRecord]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    rows = []
    for i, chunk in enumerate(chunks, start=1):
        rows.append(
            EvidenceRecord(
                evidence_id=f"{source_type.value}:{source_id}:{i}",
                content=chunk,
                claim=chunk.split("\n", 1)[0][:200],
                injection_flag=detect_injection(chunk),
                **_base(catalog, source_id, source_type),
            )
        )
    return rows


def _load_interviews(folder: Path, catalog: dict) -> list[EvidenceRecord]:
    if not folder.exists():
        return []
    rows = []
    for path in sorted(folder.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        rows.append(
            EvidenceRecord(
                evidence_id=f"interview:{path.stem}",
                content=text,
                claim=text.split("\n", 1)[0][:200],
                speaker=path.stem,
                injection_flag=detect_injection(text),
                **_base(catalog, "interviews", SourceType.INTERVIEW),
            )
        )
    return rows


def _load_episode(path: Path, catalog: dict) -> list[EvidenceRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for seg in payload["segments"]:
        content = f"{seg['subtitle_id']} [{seg['start_time']} --> {seg['end_time']}] {seg['speaker']}: {seg['source_text']}"
        rows.append(
            EvidenceRecord(
                evidence_id=f"episode:{seg['subtitle_id']}",
                content=content,
                claim=seg["source_text"],
                speaker=seg.get("speaker"),
                scene=seg.get("scene"),
                timecode=f"{seg['start_time']}-->{seg['end_time']}",
                metadata=seg,
                **_base(catalog, "episode", SourceType.EPISODE),
            )
        )
    return rows
