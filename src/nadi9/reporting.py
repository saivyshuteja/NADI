from __future__ import annotations

import json
from pathlib import Path

from nadi9.tools.subtitle import to_srt


def write_sample_run(state: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    decisions = state.get("subtitle_decisions", [])
    (output_dir / "subtitles.srt").write_text(to_srt(decisions), encoding="utf-8")
    with (output_dir / "subtitle_decisions.jsonl").open("w", encoding="utf-8") as fh:
        for row in decisions:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output_dir / "learned_rules.json").write_text(
        json.dumps(
            {
                "hypotheses": state.get("hypotheses", []),
                "tests": state.get("hypothesis_tests", []),
                "conflicts": state.get("conflicts", []),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (output_dir / "review_queue.json").write_text(
        json.dumps(state.get("review_queue", []), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "final_report.md").write_text(_report_md(state), encoding="utf-8")
    (output_dir / "run_state.json").write_text(
        json.dumps(
            {
                "run_id": state.get("run_id"),
                "plan": state.get("plan"),
                "model_calls": state.get("model_calls"),
                "tool_calls": state.get("tool_calls"),
                "release_recommendation": state.get("release_recommendation"),
                "corrections": state.get("corrections"),
                "affected_subtitles": state.get("affected_subtitles"),
                "errors": state.get("errors"),
                "notes": state.get("_notes"),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _report_md(state: dict) -> str:
    lines = [
        "# Nadi-9 Episode-01 release report",
        "",
        f"- Run: `{state.get('run_id')}`",
        f"- Recommendation: **{state.get('release_recommendation')}**",
        f"- Model calls: {state.get('model_calls')} / 25",
        f"- Tool calls: {state.get('tool_calls')} / 50",
        f"- Review items: {len(state.get('review_queue', []))}",
        "",
        "## Plan",
    ]
    for step in state.get("plan") or []:
        lines.append(f"- {step}")
    lines += ["", "## Subtitle decisions", ""]
    for d in state.get("subtitle_decisions", []):
        lines.append(
            f"- `{d['subtitle_id']}` {d.get('decision')} "
            f"(p={d.get('confidence')}): {d.get('source_text')} → {d.get('nadi_9_text')}"
        )
        lines.append(f"  - reason: {d.get('confidence_reason')}")
        if d.get("conflicts"):
            lines.append(f"  - conflicts: {d['conflicts']}")
        if d.get("review_question"):
            lines.append(f"  - review: {d['review_question']}")
    lines += ["", "## Corrections", ""]
    for c in state.get("corrections") or []:
        lines.append(f"- {c.get('correction_id')}: {c.get('new_claim')}")
        lines.append(f"  - affected subtitles: {c.get('affected_subtitles')}")
    lines += ["", "## Limitations", ""]
    lines.append("- Sample pack is synthetic demonstration data, not the hidden evaluator pack.")
    lines.append("- Mock mode uses deterministic evidence mapping rather than a hosted LLM.")
    return "\n".join(lines) + "\n"
