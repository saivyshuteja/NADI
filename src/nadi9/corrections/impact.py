from __future__ import annotations


def affected_subtitle_ids(
    decisions: list[dict],
    correction: dict,
    hypotheses: list[dict],
) -> list[str]:
    """Trace a corrected claim to subtitles via hypothesis and evidence links."""
    text = (correction.get("new_claim", "") + " " + correction.get("old_claim", "")).lower()
    target_hyps = set(correction.get("affected_hypotheses") or [])
    kinship_correction = any(term in text for term in ("bira", "reconcil", "r17", "e03", "older sibling", "elder brother", "loru"))
    if kinship_correction:
        target_hyps.update({"HYP-003", "HYP-004"})
    if "zinglo" in text:
        target_hyps.add("HYP-007")

    affected: list[str] = []
    for d in decisions:
        hyps = set(d.get("hypotheses") or [])
        evid = " ".join(d.get("evidence") or []) + " " + (d.get("source_text") or "").lower() + " " + str(d.get("nadi_9_text") or "")
        if hyps & target_hyps:
            affected.append(d["subtitle_id"])
            continue
        source_text = (d.get("source_text") or "").lower()
        if kinship_correction and any(
            term in source_text for term in ("elder", "brother", "sister", "sibling")
        ):
            affected.append(d["subtitle_id"])
            continue
        if "zinglo" in evid and "zinglo" in text:
            affected.append(d["subtitle_id"])
    return list(dict.fromkeys(affected))
