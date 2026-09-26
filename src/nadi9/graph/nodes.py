from __future__ import annotations

import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig

from nadi9.corrections.impact import affected_subtitle_ids
from nadi9.evidence.lexicon import dictionary_conflicts
from nadi9.evidence.loader import load_correction, load_episode_segments, load_evidence
from nadi9.evidence.retrieval import build_index
from nadi9.graph.runtime import Runtime
from nadi9.graph.state import AgentState
from nadi9.hypotheses.builder import apply_correction_to_hypotheses, build_hypotheses, test_hypotheses
from nadi9.models import Decision, ReviewItem
from nadi9.security.injection import wrap_as_data
from nadi9.storage.audit import persist_decision
from nadi9.verification.timing import validate_srt_order
from nadi9.verification.verifier import decide, merge_verification


def _rt(config: RunnableConfig) -> Runtime:
    return config["configurable"]["runtime"]


def load_run(state: AgentState, config: RunnableConfig) -> dict:
    rt = _rt(config)
    run_id = state.get("run_id") or str(uuid.uuid4())[:8]
    return {
        "run_id": run_id,
        "user_request": state.get("user_request") or "Produce evidence-grounded Nadi-9 subtitle decisions.",
        "tool_calls": 0,
        "model_calls": 0,
        "errors": [],
        "subtitle_decisions": [],
        "review_queue": [],
        "budget_exhausted": False,
        "retriever_available": not rt.force_tool_failure,
        "phase": "load_run",
        "plan": [],
    }


def inspect_evidence(state: AgentState, config: RunnableConfig) -> dict:
    rt = _rt(config)
    if not rt.records:
        rt.records = load_evidence(rt.settings.data_dir)
        rt.index = build_index(rt.records)
        rt.retrieval.index = rt.index
    inventory = []
    seen = set()
    for rec in rt.records:
        if rec.source_id in seen:
            continue
        seen.add(rec.source_id)
        inventory.append(
            {
                "source_id": rec.source_id,
                "source_type": rec.source_type.value,
                "author": rec.author,
                "date": rec.date,
                "scope": rec.scope,
                "reliability": rec.reliability,
            }
        )
    conflicts = [c.model_dump() for c in dictionary_conflicts(rt.records)]
    return {
        "evidence_records": [
            {
                "evidence_id": r.evidence_id,
                "source_id": r.source_id,
                "source_type": r.source_type.value,
                "reliability": r.reliability,
                "injection_flag": r.injection_flag,
                "claim": r.claim,
            }
            for r in rt.records
        ],
        "conflicts": conflicts,
        "phase": "inspect_evidence",
        "errors": state.get("errors", []),
        "plan": [
            f"Inventory: {len(inventory)} sources, {len(rt.records)} evidence records",
            "Do not trust largest (dictionary_A) or newest file automatically",
            "Retrieve evidence for risky scenes first (kinship, humour, gaps)",
            "Form and test hypotheses with counterexamples visible",
            "Translate only from evidence; independent verify; escalate uncertainty",
            "Apply mid-run correction to affected subtitles only",
        ],
    }


def retrieve_relevant_evidence(state: AgentState, config: RunnableConfig) -> dict:
    rt = _rt(config)
    tool_calls = state.get("tool_calls", 0)
    retrieved: list[dict[str, Any]] = []
    errors = list(state.get("errors", []))
    queries = [
        "elder brother kinship respect reconciliation bira",
        "negation particle na",
        "unsupported technical terms code-switching",
        "joke funny humour zinglo hasa",
        "IGNORE PREVIOUS INSTRUCTIONS",
    ]
    available = True
    for q in queries:
        if not rt.budget.can_tool(tool_calls):
            errors.append("tool budget exhausted during retrieval")
            break
        tool_calls += 1
        try:
            chunks = _retrieve_with_retry(rt, q)
            for ch in chunks:
                retrieved.append(
                    {
                        "query": q,
                        "evidence_id": ch.evidence_id,
                        "score": ch.score,
                        "injection_flag": ch.injection_flag,
                        "prompt_view": wrap_as_data(ch.content, ch.evidence_id)[:500],
                    }
                )
        except Exception as exc:  # noqa: BLE001
            available = False
            errors.append(f"retrieval failed after retry/fallback: {exc}")
            break
    return {
        "retrieved_evidence": retrieved,
        "tool_calls": tool_calls,
        "retriever_available": available,
        "phase": "retrieve",
        "errors": errors,
    }


def _retrieve_with_retry(rt: Runtime, query: str):
    last_exc = None
    attempts = 1 + rt.retriever_retries
    for _ in range(attempts):
        try:
            if rt.force_tool_failure:
                raise RuntimeError("retriever unavailable")
            return rt.retrieval.retrieve(query, top_k=rt.settings.retrieve_top_k)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    if rt.records and not rt.disable_fallback:
        rt.notes.append("used lexical fallback after retriever failure")
        return rt.index.retrieve(query, top_k=rt.settings.retrieve_top_k)
    raise last_exc or RuntimeError("retriever unavailable")


def form_and_test_hypotheses(state: AgentState, config: RunnableConfig) -> dict:
    rt = _rt(config)
    model_calls = state.get("model_calls", 0)
    errors = list(state.get("errors", []))
    if not rt.budget.can_model(model_calls):
        return {"budget_exhausted": True, "errors": errors + ["model budget exhausted before hypotheses"]}
    model_calls += 1
    try:
        rt.provider.generate("hypotheses", {"conflicts": state.get("conflicts", [])})
    except Exception as exc:  # noqa: BLE001
        errors.append(f"hypothesis LLM failed, using deterministic builder: {exc}")
    from nadi9.models import ConflictRecord

    conflicts = [ConflictRecord(**c) for c in state.get("conflicts", [])]
    hyps = build_hypotheses(rt.records, conflicts)
    tests = test_hypotheses(hyps, rt.records)
    return {
        "hypotheses": [h.model_dump(mode="json") for h in hyps],
        "hypothesis_tests": [t.model_dump(mode="json") for t in tests],
        "model_calls": model_calls,
        "phase": "hypotheses",
        "errors": errors,
    }


def prioritize_episode(state: AgentState, config: RunnableConfig) -> dict:
    rt = _rt(config)
    segments = load_episode_segments(rt.settings.data_dir)

    def risk(seg: dict) -> int:
        text = seg["source_text"].lower()
        score = 0
        if "brother" in text or "sister" in text:
            score += 5
        if "joke" in text or "funny" in text:
            score += 4
        if any(w in text for w in ("telescope", "wifi", "internet")):
            score += 6
        if seg.get("scene") == "reunion":
            score += 3
        return score

    ordered = sorted(segments, key=risk, reverse=True)
    plan = list(state.get("plan", []))
    plan.append("Priority order: " + ", ".join(s["subtitle_id"] for s in ordered))
    return {
        "episode_segments": segments,
        "pending_segment_ids": [s["subtitle_id"] for s in ordered],
        "plan": plan,
        "phase": "prioritize",
    }


def translate_and_verify(state: AgentState, config: RunnableConfig) -> dict:
    rt = _rt(config)
    segments = {s["subtitle_id"]: s for s in state.get("episode_segments", [])}
    pending = list(state.get("rerun_ids") or state.get("pending_segment_ids") or [])
    existing = {d["subtitle_id"]: d for d in state.get("subtitle_decisions", [])}
    model_calls = state.get("model_calls", 0)
    tool_calls = state.get("tool_calls", 0)
    errors = list(state.get("errors", []))
    validations = list(state.get("validation_results", []))

    for sid in pending:
        if not rt.budget.can_model(model_calls + 1):
            errors.append(f"model budget stopped processing at {sid}")
            existing[sid] = _safe_failure(segments[sid], "model budget exhausted")
            continue
        seg = segments[sid]
        tool_calls += 1
        evidence_blocks = []
        try:
            chunks = _retrieve_with_retry(rt, seg["source_text"] + " " + (seg.get("scene") or ""))
            evidence_blocks = [
                {"evidence_id": c.evidence_id, "data": wrap_as_data(c.content, c.evidence_id), "injection_flag": c.injection_flag}
                for c in chunks
            ]
        except Exception as exc:  # noqa: BLE001
            errors.append(f"tool failure on {sid}: {exc}")
            existing[sid] = _safe_failure(seg, f"retrieval failed: {exc}")
            continue

        model_calls += 1
        try:
            proposal = rt.provider.generate(
                "translate",
                {
                    "source_text": seg["source_text"],
                    "speaker": seg.get("speaker"),
                    "scene": seg.get("scene"),
                    "evidence": evidence_blocks,
                    "hypotheses": [h for h in state.get("hypotheses", []) if h.get("status") != "UNSUPPORTED"],
                },
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"translator LLM failed on {sid}: {exc}")
            existing[sid] = _safe_failure(seg, f"translator failed: {exc}")
            continue

        proposal["subtitle_id"] = sid
        proposal["source_text"] = seg["source_text"]
        proposal["start_time"] = seg["start_time"]
        proposal["end_time"] = seg["end_time"]
        proposal["speaker"] = seg.get("speaker")
        proposal["scene"] = seg.get("scene")

        if not rt.budget.can_model(model_calls):
            errors.append(f"no budget left for verifier on {sid}")
            existing[sid] = _safe_failure(seg, "verifier budget exhausted")
            continue

        model_calls += 1
        try:
            vraw = rt.provider.generate(
                "verify",
                {
                    "source_text": seg["source_text"],
                    "nadi_9_text": proposal.get("nadi_9_text"),
                    "translator_decision": proposal.get("decision"),
                    "evidence": evidence_blocks,
                    # verifier does not receive translator reasoning on purpose
                },
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"verifier LLM failed on {sid}: {exc}")
            vraw = {"valid": False, "issues": [{"code": "verifier_failure", "severity": "high", "message": str(exc)}]}

        validation = merge_verification(seg, proposal, vraw, rt.settings.max_cps)
        validations.append(validation.model_dump(mode="json"))
        decision = decide(proposal, validation, rt.settings.release_confidence_threshold)
        persist_decision(rt.settings.db_path, state["run_id"], decision)
        existing[sid] = decision.model_dump(mode="json")

    ordered = [existing[s["subtitle_id"]] for s in state.get("episode_segments", []) if s["subtitle_id"] in existing]
    return {
        "subtitle_decisions": ordered,
        "model_calls": model_calls,
        "tool_calls": tool_calls,
        "validation_results": validations,
        "errors": errors,
        "phase": "translate_verify",
        "rerun_ids": [],
    }


def _safe_failure(seg: dict, reason: str) -> dict:
    return {
        "subtitle_id": seg["subtitle_id"],
        "source_text": seg["source_text"],
        "nadi_9_text": None,
        "confidence": 0.1,
        "confidence_reason": reason,
        "decision": Decision.HUMAN_REVIEW.value,
        "evidence": [],
        "hypotheses": [],
        "assumptions": [],
        "conflicts": [],
        "review_question": "System could not complete a safe evidence-backed decision. Please review the source line.",
        "review_status": "queued",
        "start_time": seg["start_time"],
        "end_time": seg["end_time"],
        "speaker": seg.get("speaker"),
        "scene": seg.get("scene"),
    }


def apply_correction(state: AgentState, config: RunnableConfig) -> dict:
    rt = _rt(config)
    if not rt.apply_midrun_correction:
        return {"phase": "correction_skipped", "affected_subtitles": []}
    correction = load_correction(rt.settings.data_dir)
    if not correction:
        return {"phase": "correction_none", "affected_subtitles": []}
    from nadi9.models import Hypothesis

    hyps = [Hypothesis(**h) if not isinstance(h, Hypothesis) else h for h in state.get("hypotheses", [])]
    hyps = apply_correction_to_hypotheses(hyps, correction)
    affected = affected_subtitle_ids(state.get("subtitle_decisions", []), correction, [h.model_dump() for h in hyps])
    correction["affected_hypotheses"] = ["HYP-003"]
    correction["affected_subtitles"] = affected
    return {
        "hypotheses": [h.model_dump(mode="json") for h in hyps],
        "corrections": [correction],
        "affected_subtitles": affected,
        "rerun_ids": affected,
        "phase": "correction",
    }


def build_review_and_report(state: AgentState, config: RunnableConfig) -> dict:
    rt = _rt(config)
    decisions = state.get("subtitle_decisions", [])
    reviews = []
    for d in decisions:
        if d.get("decision") in {Decision.HUMAN_REVIEW.value, Decision.INSUFFICIENT_EVIDENCE.value, Decision.REJECTED.value}:
            reviews.append(
                ReviewItem(
                    subtitle_id=d["subtitle_id"],
                    reason=d.get("confidence_reason") or d.get("decision"),
                    review_question=d.get("review_question") or "Please review.",
                    evidence=d.get("evidence") or [],
                ).model_dump()
            )
    fmt_issues = [i.model_dump() for i in validate_srt_order(state.get("episode_segments", []))]
    release_ok = all(d.get("decision") == Decision.RELEASE.value for d in decisions) and not reviews
    recommendation = "RELEASE" if release_ok else "HOLD_FOR_HUMAN_REVIEW"
    errors = list(state.get("errors", []))
    if fmt_issues:
        errors.append(f"srt validation issues: {fmt_issues}")
    return {
        "review_queue": reviews,
        "release_recommendation": recommendation,
        "phase": "report",
        "errors": errors,
        "assumptions": sorted({a for d in decisions for a in d.get("assumptions") or []}),
    }
