from pathlib import Path

from nadi9.config.settings import Settings
from nadi9.evidence.lexicon import dictionary_conflicts
from nadi9.evidence.loader import load_evidence
from nadi9.graph.graph import run_pipeline


def _settings(tmp_path: Path) -> Settings:
    root = Path(__file__).resolve().parents[1]
    return Settings(
        mode="mock",
        data_dir=root / "data" / "raw",
        output_dir=tmp_path / "out",
        db_path=tmp_path / "nadi9.sqlite",
    )


def test_dictionary_conflict_is_visible_not_auto_resolved(tmp_path):
    records = load_evidence(Path(__file__).resolve().parents[1] / "data" / "raw")
    conflicts = dictionary_conflicts(records)
    brother = next(c for c in conflicts if c.term == "brother")
    assert "bira" in brother.claims
    assert "anbira" in brother.claims
    state = run_pipeline(_settings(tmp_path), apply_midrun_correction=False)
    kinship = next(d for d in state["subtitle_decisions"] if "brother" in d["source_text"].lower())
    assert kinship["decision"] in {"HUMAN_REVIEW", "RELEASE"}
    # conflict remains inspectable even if an example match is used
    assert any(c["term"] == "brother" for c in state["conflicts"])
    assert "dictionary:A:term-44 vs dictionary:B:term-19" in " ".join(
        " ".join(d.get("conflicts") or []) for d in state["subtitle_decisions"]
    ) or any("bira" in str(c["claims"]) and "anbira" in str(c["claims"]) for c in state["conflicts"])
