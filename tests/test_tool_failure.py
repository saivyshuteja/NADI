from pathlib import Path

from nadi9.config.settings import Settings
from nadi9.graph.graph import run_pipeline
from nadi9.models import Decision
from nadi9.tools.retrieval import RetrievalTool


def test_tool_failure_retries_then_fails_safe(tmp_path):
    tool = RetrievalTool(index=None, fail=True)
    raised = 0
    try:
        tool.retrieve("brother")
    except RuntimeError:
        raised += 1
    try:
        tool.retrieve("brother")
    except RuntimeError:
        raised += 1
    assert raised == 2

    root = Path(__file__).resolve().parents[1]
    state = run_pipeline(
        Settings(
            mode="mock",
            data_dir=root / "data" / "raw",
            output_dir=tmp_path / "out",
            db_path=tmp_path / "nadi9.sqlite",
        ),
        force_tool_failure=True,
        disable_fallback=True,
        apply_midrun_correction=False,
    )
    assert state["subtitle_decisions"]
    for row in state["subtitle_decisions"]:
        assert row["nadi_9_text"] is None
        assert row["decision"] == Decision.HUMAN_REVIEW.value
        assert "invent" not in (row.get("nadi_9_text") or "").lower()
