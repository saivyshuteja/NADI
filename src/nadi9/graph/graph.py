from __future__ import annotations

import copy

from langgraph.graph import END, START, StateGraph

from nadi9.budget import BudgetManager
from nadi9.config.settings import Settings
from nadi9.evidence.loader import load_evidence
from nadi9.evidence.retrieval import build_index
from nadi9.graph.nodes import (
    apply_correction,
    build_review_and_report,
    form_and_test_hypotheses,
    inspect_evidence,
    load_run,
    prioritize_episode,
    retrieve_relevant_evidence,
    translate_and_verify,
)
from nadi9.graph.routing import after_correction, after_translate
from nadi9.graph.runtime import Runtime
from nadi9.graph.state import AgentState
from nadi9.providers import get_provider
from nadi9.tools.retrieval import RetrievalTool
from nadi9.corrections.impact import affected_subtitle_ids
from nadi9.graph.nodes import build_review_and_report, translate_and_verify
from nadi9.hypotheses.builder import apply_correction_to_hypotheses
from nadi9.models import Hypothesis


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_run", load_run)
    g.add_node("inspect_evidence", inspect_evidence)
    g.add_node("retrieve_relevant_evidence", retrieve_relevant_evidence)
    g.add_node("form_and_test_hypotheses", form_and_test_hypotheses)
    g.add_node("prioritize_episode", prioritize_episode)
    g.add_node("translate_and_verify", translate_and_verify)
    g.add_node("apply_correction", apply_correction)
    g.add_node("build_review_and_report", build_review_and_report)

    g.add_edge(START, "load_run")
    g.add_edge("load_run", "inspect_evidence")
    g.add_edge("inspect_evidence", "retrieve_relevant_evidence")
    g.add_edge("retrieve_relevant_evidence", "form_and_test_hypotheses")
    g.add_edge("form_and_test_hypotheses", "prioritize_episode")
    g.add_edge("prioritize_episode", "translate_and_verify")
    g.add_conditional_edges(
        "translate_and_verify",
        after_translate,
        {
            "apply_correction": "apply_correction",
            "build_review_and_report": "build_review_and_report",
        },
    )
    g.add_conditional_edges(
        "apply_correction",
        after_correction,
        {
            "translate_and_verify": "translate_and_verify",
            "build_review_and_report": "build_review_and_report",
        },
    )
    g.add_edge("build_review_and_report", END)
    return g.compile()


def make_runtime(
    settings: Settings,
    force_tool_failure: bool = False,
    apply_midrun_correction: bool = True,
    disable_fallback: bool = False,
) -> Runtime:
    records = load_evidence(settings.data_dir)
    index = build_index(records)
    provider = get_provider(settings.mode, records, settings.llm_model)
    retrieval = RetrievalTool(index, fail=force_tool_failure)
    return Runtime(
        settings=settings,
        records=records,
        index=index,
        provider=provider,
        retrieval=retrieval,
        budget=BudgetManager(settings),
        force_tool_failure=force_tool_failure,
        disable_fallback=disable_fallback,
        apply_midrun_correction=apply_midrun_correction,
    )


def run_pipeline(
    settings: Settings | None = None,
    force_tool_failure: bool = False,
    apply_midrun_correction: bool = True,
    disable_fallback: bool = False,
) -> AgentState:
    from nadi9.config.settings import get_settings

    settings = settings or get_settings()
    runtime = make_runtime(
        settings,
        force_tool_failure=force_tool_failure,
        apply_midrun_correction=apply_midrun_correction,
        disable_fallback=disable_fallback,
    )
    graph = build_graph()
    result = graph.invoke(
        {"user_request": "Learn Nadi-9 from evidence and decide episode subtitles."},
        config={"configurable": {"runtime": runtime}},
    )
    result["_notes"] = runtime.notes
    return result


def replan_with_correction(settings: Settings, previous_state: dict, correction: dict) -> dict:
    """Apply a new claim and rerun only subtitle decisions linked to it."""
    runtime = make_runtime(settings, apply_midrun_correction=False)
    state = copy.deepcopy(previous_state)
    correction = {
        "correction_id": correction.get("correction_id") or "C-UI",
        "source_id": correction.get("source_id") or "reviewer",
        "old_claim": correction.get("old_claim", ""),
        "new_claim": correction.get("new_claim", ""),
        "notes": correction.get("notes", ""),
    }
    hypotheses = [Hypothesis(**item) for item in state.get("hypotheses", [])]
    hypotheses = apply_correction_to_hypotheses(hypotheses, correction)
    serialized_hypotheses = [hypothesis.model_dump(mode="json") for hypothesis in hypotheses]
    affected = affected_subtitle_ids(
        state.get("subtitle_decisions", []), correction, serialized_hypotheses
    )
    correction["affected_hypotheses"] = [
        item["hypothesis_id"]
        for item in serialized_hypotheses
        if f"correction:{correction['correction_id']}" in item.get("supporting_evidence", [])
    ]
    correction["affected_subtitles"] = affected
    previous_model_calls = state.get("model_calls", 0)
    previous_tool_calls = state.get("tool_calls", 0)
    state.update(
        {
            "hypotheses": serialized_hypotheses,
            "corrections": state.get("corrections", []) + [correction],
            "affected_subtitles": affected,
            "rerun_ids": affected,
            "pending_segment_ids": [],
            "model_calls": 0,
            "tool_calls": 0,
        }
    )
    config = {"configurable": {"runtime": runtime}}
    state.update(translate_and_verify(state, config))
    state["last_replan_model_calls"] = state.get("model_calls", 0)
    state["last_replan_tool_calls"] = state.get("tool_calls", 0)
    state["model_calls"] += previous_model_calls
    state["tool_calls"] += previous_tool_calls
    state.update(build_review_and_report(state, config))
    state["_notes"] = runtime.notes
    return state
