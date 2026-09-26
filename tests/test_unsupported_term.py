from pathlib import Path

from nadi9.config.settings import Settings
from nadi9.graph.graph import run_pipeline
from nadi9.models import Decision


def test_unsupported_term_escalates(tmp_path):
    root = Path(__file__).resolve().parents[1]
    state = run_pipeline(
        Settings(
            mode="mock",
            data_dir=root / "data" / "raw",
            output_dir=tmp_path / "out",
            db_path=tmp_path / "nadi9.sqlite",
        ),
        apply_midrun_correction=False,
    )
    line = next(d for d in state["subtitle_decisions"] if "telescope" in d["source_text"].lower())
    assert line["decision"] in {Decision.HUMAN_REVIEW.value, Decision.INSUFFICIENT_EVIDENCE.value}
    assert line["nadi_9_text"] is None
    assert line["review_question"]
    assert "telescope" in (line.get("confidence_reason") or "").lower() or "unsupported" in (
        line.get("confidence_reason") or ""
    ).lower() or line["decision"] == Decision.INSUFFICIENT_EVIDENCE.value
