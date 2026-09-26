from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path


PACK_FILES = {
    "examples": Path("01_approved_examples/approved_examples.json"),
    "dictionary_a": Path("04_dictionary_A/dictionary_A.csv"),
    "dictionary_b": Path("05_dictionary_B/dictionary_B.csv"),
    "grammar": Path("03_grammar/grammar_note.md"),
    "expert_notes": Path("07_expert_notes/expert_notes.md"),
    "viewer_feedback": Path("06_viewer_feedback/viewer_feedback.md"),
    "episode": Path("08_episode_package/episode_01.json"),
}


def is_input_pack(path: Path) -> bool:
    path = Path(path)
    return all((path / relative).is_file() for relative in PACK_FILES.values())


def prepare_input_pack(source_dir: Path, data_dir: Path) -> Path:
    """Convert the supplied candidate pack into the agent's normalized input layout."""
    source_dir = Path(source_dir)
    data_dir = Path(data_dir)
    if not is_input_pack(source_dir):
        raise ValueError(f"Not a complete Nadi-9 test input pack: {source_dir}")

    (data_dir / "interviews").mkdir(parents=True, exist_ok=True)
    (data_dir / "corrections").mkdir(parents=True, exist_ok=True)

    examples = json.loads((source_dir / PACK_FILES["examples"]).read_text(encoding="utf-8"))
    normalized_examples = [
        {
            "id": row["id"],
            "source": row["source"],
            "nadi9": row["nadi9"],
            "speaker": row.get("speaker"),
            "scene": row.get("scene"),
            "notes": row.get("context", ""),
        }
        for row in examples
    ]
    (data_dir / "examples.json").write_text(
        json.dumps({"examples": normalized_examples}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    for label, filename in (("dictionary_a", "dictionary_a.json"), ("dictionary_b", "dictionary_b.json")):
        source_file = source_dir / PACK_FILES[label]
        with source_file.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        entries = []
        for row in rows:
            senses = [sense.strip() for sense in re.split(r"\s*[;/]\s*", row["meaning"]) if sense.strip()]
            senses = [re.sub(r"^in some families,\s*", "", sense, flags=re.IGNORECASE) for sense in senses]
            entries.extend(
                {
                    "id": row["entry_id"],
                    "source": sense,
                    "nadi9": row["term"],
                    "notes": (
                        f"gloss={row['meaning']}; category={row.get('category', '')}; "
                        f"source={row.get('source', '')}"
                    ),
                }
                for sense in senses
            )
        source_id = "dictionary_A" if label == "dictionary_a" else "dictionary_B"
        (data_dir / filename).write_text(
            json.dumps({"source_id": source_id, "entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    shutil.copyfile(source_dir / PACK_FILES["grammar"], data_dir / "grammar.md")
    shutil.copyfile(source_dir / PACK_FILES["expert_notes"], data_dir / "expert_notes.md")
    shutil.copyfile(source_dir / PACK_FILES["viewer_feedback"], data_dir / "viewer_feedback.md")

    interview_dir = source_dir / "02_audio_interviews"
    for transcript in sorted(interview_dir.glob("*_transcript.txt")):
        target = data_dir / "interviews" / f"{transcript.name.removesuffix('_transcript.txt')}.txt"
        shutil.copyfile(transcript, target)

    episode = json.loads((source_dir / PACK_FILES["episode"]).read_text(encoding="utf-8"))
    segments = [
        {
            "subtitle_id": row["subtitle_id"],
            "start_time": row["start"],
            "end_time": row["end"],
            "source_text": row["source"],
            "speaker": row.get("speaker"),
            "scene": row.get("scene"),
        }
        for row in episode
    ]
    (data_dir / "episode").mkdir(parents=True, exist_ok=True)
    (data_dir / "episode" / "transcript.json").write_text(
        json.dumps({"segments": segments}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    sources = [
        ("examples", "approved examples"),
        ("dictionary_A", "glossary; publisher not independently identified"),
        ("dictionary_B", "glossary; publisher not independently identified"),
        ("grammar", "grammar note"),
        ("expert_notes", "expert commentary; individual views retained in text"),
        ("viewer_feedback", "viewer feedback; anecdotal, not linguistic authority"),
        ("interviews", "five supplied transcript files; WAV fixtures not transcribed by this pipeline"),
        ("episode", "episode source lines and timecodes"),
    ]
    catalog = {
        "sources": [
            {
                "source_id": source_id,
                "author": None,
                "date": None,
                "scope": scope,
                "reliability": 0.5,
            }
            for source_id, scope in sources
        ]
    }
    (data_dir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data_dir