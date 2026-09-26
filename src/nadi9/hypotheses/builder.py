from __future__ import annotations

from nadi9.evidence.lexicon import attested_tokens
from nadi9.models import ConflictRecord, EvidenceRecord, Hypothesis, HypothesisStatus, HypothesisTest


def build_hypotheses(
    records: list[EvidenceRecord],
    conflicts: list[ConflictRecord],
) -> list[Hypothesis]:
    hyps: list[Hypothesis] = []
    examples = [r for r in records if r.source_type.value == "example"]
    grammar = [r for r in records if r.source_type.value == "grammar"]
    experts = [r for r in records if r.source_type.value == "expert"]
    interviews = [r for r in records if r.source_type.value == "interview"]

    sov_support = [r.evidence_id for r in examples if " ven" in r.metadata.get("nadi9", "") or r.metadata.get("nadi9", "").endswith("ven.")]
    hyps.append(
        Hypothesis(
            hypothesis_id="HYP-001",
            claim="Default clause order is Subject-Object-Verb.",
            category="word_order",
            status=HypothesisStatus.SUPPORTED,
            confidence=0.86,
            supporting_evidence=sov_support[:8] + [g.evidence_id for g in grammar if "SOV" in g.content or "Subject-Object-Verb" in g.content],
            notes="Grammar note plus multiple approved examples.",
        )
    )

    neg_support = [r.evidence_id for r in examples if r.metadata.get("nadi9", "").rstrip(".?").endswith("na") or " na." in r.metadata.get("nadi9", "")]
    hyps.append(
        Hypothesis(
            hypothesis_id="HYP-002",
            claim="Negation uses clause-final or post-verbal particle 'na'.",
            category="negation",
            status=HypothesisStatus.SUPPORTED,
            confidence=0.84,
            supporting_evidence=neg_support + [g.evidence_id for g in grammar if "Negation" in g.content or "na" in g.content],
        )
    )

    respect_for = [r.evidence_id for r in examples if "bira-ka" in r.metadata.get("nadi9", "")]
    respect_against = [r.evidence_id for r in examples if r.evidence_id in {"example:E03", "example:E13"}]
    hyps.append(
        Hypothesis(
            hypothesis_id="HYP-003",
            claim="Kinship terminology changes with social status: older-sibling address uses bira-ka; peer talk may use bira.",
            category="respect",
            status=HypothesisStatus.CONTESTED,
            confidence=0.62,
            supporting_evidence=respect_for
            + [e.evidence_id for e in experts[:2]]
            + [i.evidence_id for i in interviews if "bira-ka" in i.content or "respectful" in i.content.lower()],
            counterexamples=respect_against,
            notes="Experts disagree on post-reconciliation register. E03 is later challenged.",
        )
    )

    brother_conflict = next((c for c in conflicts if c.term == "brother"), None)
    hyps.append(
        Hypothesis(
            hypothesis_id="HYP-004",
            claim="The lemma 'brother' has conflicting Nadi-9 forms across dictionaries (bira vs anbira).",
            category="relationships",
            status=HypothesisStatus.CONTESTED,
            confidence=0.4,
            supporting_evidence=brother_conflict.evidence_ids if brother_conflict else [],
            counterexamples=[],
            notes="Do not auto-select the largest dictionary.",
        )
    )

    hyps.append(
        Hypothesis(
            hypothesis_id="HYP-005",
            claim="Past motion is often marked with verb form 'ven'; later time uses adverb 'pachi'.",
            category="tense",
            status=HypothesisStatus.SUPPORTED,
            confidence=0.8,
            supporting_evidence=[r.evidence_id for r in examples if "ven" in r.metadata.get("nadi9", "")][:6]
            + [g.evidence_id for g in grammar if "Tense" in g.content or "ven" in g.content],
        )
    )

    hyps.append(
        Hypothesis(
            hypothesis_id="HYP-006",
            claim="Unassimilated technical English terms have no documented Nadi-9 equivalent and must not be invented.",
            category="code-switching",
            status=HypothesisStatus.SUPPORTED,
            confidence=0.9,
            supporting_evidence=[g.evidence_id for g in grammar if "Code-switching" in g.content or "technical" in g.content.lower()],
        )
    )

    hyps.append(
        Hypothesis(
            hypothesis_id="HYP-007",
            claim="Example E18 token 'zinglo' is an approved humorous form.",
            category="humour",
            status=HypothesisStatus.CONTESTED,
            confidence=0.25,
            supporting_evidence=["example:E18"],
            counterexamples=[i.evidence_id for i in interviews if "zinglo" in i.content.lower()],
            notes="Interview evidence disputes zinglo. Do not promote an unsupported LLM-invented grammar rule.",
        )
    )
    return hyps


def test_hypotheses(hyps: list[Hypothesis], records: list[EvidenceRecord]) -> list[HypothesisTest]:
    attested = attested_tokens(records)
    tests = []
    for h in hyps:
        contradicting = list(h.counterexamples)
        supporting = list(h.supporting_evidence)
        passed = h.status == HypothesisStatus.SUPPORTED and not contradicting
        if h.hypothesis_id == "HYP-007":
            passed = False
        if h.hypothesis_id == "HYP-004":
            passed = False
        tests.append(
            HypothesisTest(
                hypothesis_id=h.hypothesis_id,
                passed=passed,
                supporting=supporting,
                contradicting=contradicting,
                summary=(
                    f"{h.status.value}: {len(supporting)} supporting, {len(contradicting)} counterexamples. "
                    f"Attested token inventory size={len(attested)}."
                ),
            )
        )
    return tests


def apply_correction_to_hypotheses(hyps: list[Hypothesis], correction: dict) -> list[Hypothesis]:
    claim_text = (correction.get("old_claim", "") + " " + correction.get("new_claim", "")).lower()
    affected = set(correction.get("affected_hypotheses") or [])
    if any(term in claim_text for term in ("bira", "reconcil", "older sibling", "elder brother", "loru")):
        affected.update({"HYP-003", "HYP-004"})
    if "zinglo" in claim_text:
        affected.add("HYP-007")
    correction_evidence = f"correction:{correction.get('correction_id', 'unknown')}"
    updated = []
    for h in hyps:
        if h.hypothesis_id not in affected:
            updated.append(h)
            continue
        if h.hypothesis_id == "HYP-003":
            h.status = HypothesisStatus.SUPPORTED
            h.confidence = 0.8
            h.notes = correction.get("new_claim", h.notes)
            h.supporting_evidence = list(dict.fromkeys(h.supporting_evidence + [correction_evidence]))
            if "e03" in claim_text or "reconcil" in claim_text:
                h.counterexamples = [c for c in h.counterexamples if c != "example:E03"] + ["example:E03-withdrawn"]
        elif h.hypothesis_id == "HYP-004":
            h.notes = correction.get("new_claim", h.notes)
            h.supporting_evidence = list(dict.fromkeys(h.supporting_evidence + [correction_evidence]))
        elif h.hypothesis_id == "HYP-007":
            h.status = HypothesisStatus.INVALIDATED
            h.confidence = 0.05
            h.notes = correction.get("new_claim", h.notes)
            h.supporting_evidence = list(dict.fromkeys(h.supporting_evidence + [correction_evidence]))
        updated.append(h)
    return updated
