from __future__ import annotations


def to_srt(decisions: list[dict]) -> str:
    blocks = []
    for i, d in enumerate(decisions, start=1):
        text = d.get("nadi_9_text") or "[INSUFFICIENT EVIDENCE]"
        if d.get("decision") in {"HUMAN_REVIEW", "INSUFFICIENT_EVIDENCE"} and d.get("nadi_9_text"):
            text = f"{d['nadi_9_text']} [REVIEW]"
        blocks.append(
            f"{i}\n{d['start_time']} --> {d['end_time']}\n{text}\n"
        )
    return "\n".join(blocks)
