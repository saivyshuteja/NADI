from __future__ import annotations

from nadi9.models import Decision, SubtitleDecision, ValidationIssue, ValidationResult
from nadi9.security.injection import detect_injection
from nadi9.verification.timing import timing_issues


def merge_verification(
    subtitle: dict,
    candidate: dict,
    llm_verify: dict,
    max_cps: float,
) -> ValidationResult:
    issues = [ValidationIssue(**i) if not isinstance(i, ValidationIssue) else i for i in llm_verify.get("issues", [])]
    issues.extend(
        timing_issues(
            subtitle["start_time"],
            subtitle["end_time"],
            candidate.get("nadi_9_text"),
            max_cps,
        )
    )
    nadi = candidate.get("nadi_9_text")
    if nadi and detect_injection(nadi):
        issues.append(ValidationIssue(code="injection", severity="high", message="candidate contains instruction-like text"))
    high = any(i.severity == "high" for i in issues)
    valid = bool(llm_verify.get("valid", True)) and not high
    return ValidationResult(
        subtitle_id=subtitle["subtitle_id"],
        valid=valid,
        independent=True,
        issues=issues,
        evidence_coverage=candidate.get("evidence", []),
    )


def decide(
    candidate: dict,
    validation: ValidationResult,
    release_threshold: float,
) -> SubtitleDecision:
    base_decision = Decision(candidate.get("decision", Decision.HUMAN_REVIEW.value))
    confidence = 0.9
    reasons = [candidate.get("reason", "")]
    if candidate.get("conflicts"):
        confidence -= 0.25
        reasons.append("conflicts present")
    if base_decision in {Decision.HUMAN_REVIEW, Decision.INSUFFICIENT_EVIDENCE}:
        confidence = min(confidence, 0.72 if base_decision == Decision.HUMAN_REVIEW else 0.35)
    if not validation.valid:
        confidence -= 0.3
        reasons.append("independent verifier rejected")
        base_decision = Decision.HUMAN_REVIEW if base_decision == Decision.RELEASE else base_decision
        if any(i.code in {"unsupported_token", "injection", "invented_gap"} for i in validation.issues):
            if candidate.get("nadi_9_text"):
                base_decision = Decision.HUMAN_REVIEW
    if validation.issues:
        confidence -= 0.05 * len(validation.issues)
    confidence = max(0.05, min(0.95, confidence))
    if base_decision == Decision.RELEASE and (confidence < release_threshold or candidate.get("conflicts")):
        base_decision = Decision.HUMAN_REVIEW
        reasons.append("below release threshold or unresolved conflict")
    review_q = candidate.get("review_question")
    if base_decision in {Decision.HUMAN_REVIEW, Decision.INSUFFICIENT_EVIDENCE} and not review_q:
        review_q = "Which evidence-backed form should be used for this line?"
    return SubtitleDecision(
        subtitle_id=candidate["subtitle_id"],
        source_text=candidate["source_text"],
        nadi_9_text=candidate.get("nadi_9_text"),
        confidence=round(confidence, 2),
        confidence_reason="; ".join(r for r in reasons if r),
        decision=base_decision,
        evidence=candidate.get("evidence", []),
        hypotheses=candidate.get("hypotheses", []),
        assumptions=candidate.get("assumptions", []),
        conflicts=candidate.get("conflicts", []),
        review_question=review_q,
        review_status="queued" if base_decision != Decision.RELEASE else "none",
        start_time=candidate.get("start_time"),
        end_time=candidate.get("end_time"),
        speaker=candidate.get("speaker"),
        scene=candidate.get("scene"),
        verification=validation,
    )
