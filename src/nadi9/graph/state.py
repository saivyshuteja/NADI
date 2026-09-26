from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    user_request: str
    evidence_records: list[dict[str, Any]]
    retrieved_evidence: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    hypothesis_tests: list[dict[str, Any]]
    episode_segments: list[dict[str, Any]]
    current_segment_id: str | None
    pending_segment_ids: list[str]
    subtitle_decisions: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    assumptions: list[str]
    corrections: list[dict[str, Any]]
    affected_subtitles: list[str]
    tool_calls: int
    model_calls: int
    validation_results: list[dict[str, Any]]
    review_queue: list[dict[str, Any]]
    release_recommendation: str
    errors: list[str]
    plan: list[str]
    budget_exhausted: bool
    retriever_available: bool
    phase: str
    rerun_ids: list[str]
