from pathlib import Path

from nadi9.config.settings import Settings
from nadi9.corrections.impact import affected_subtitle_ids
from nadi9.graph.graph import run_pipeline


def test_correction_reruns_only_affected(tmp_path):
    root = Path(__file__).resolve().parents[1]
    settings = Settings(
        mode="mock",
        data_dir=root / "data" / "raw",
        output_dir=tmp_path / "out",
        db_path=tmp_path / "nadi9.sqlite",
    )
    state = run_pipeline(settings, apply_midrun_correction=True)
    assert state.get("corrections")
    affected = state.get("affected_subtitles") or []
    assert affected, "correction must identify impacted subtitle IDs"
    all_ids = [d["subtitle_id"] for d in state["subtitle_decisions"]]
    assert set(affected) <= set(all_ids)
    assert len(affected) < len(all_ids)

    hypothetical = affected_subtitle_ids(
        state["subtitle_decisions"],
        state["corrections"][0],
        state["hypotheses"],
    )
    assert set(hypothetical) == set(affected)
    hyp003 = next(h for h in state["hypotheses"] if h["hypothesis_id"] == "HYP-003")
    assert "correction:C-R17" in hyp003["supporting_evidence"] or "R17" in hyp003["notes"]
