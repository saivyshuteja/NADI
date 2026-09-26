from nadi9.graph.state import AgentState


def after_translate(state: AgentState) -> str:
    if state.get("corrections"):
        return "build_review_and_report"
    return "apply_correction"


def after_correction(state: AgentState) -> str:
    if state.get("rerun_ids"):
        return "translate_and_verify"
    return "build_review_and_report"
