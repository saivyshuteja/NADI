from __future__ import annotations

import io
import json
import tempfile
import uuid
import zipfile
from pathlib import Path

import streamlit as st

from nadi9.config.settings import ROOT, Settings
from nadi9.custom_inputs import ROLE_LABELS, SUPPORTED_SUFFIXES, normalize_custom_files, suggest_role
from nadi9.evidence.loader import load_evidence
from nadi9.graph.graph import replan_with_correction, run_pipeline
from nadi9.input_pack import is_input_pack, prepare_input_pack
from nadi9.reporting import write_sample_run
from nadi9.tools.subtitle import to_srt


WEIGHTS = {
    "Evidence-based reasoning": 20,
    "Planning and replanning": 15,
    "Translation decision quality": 15,
    "Verification": 15,
    "Uncertainty and escalation": 15,
    "Engineering quality": 10,
    "Use of AI tools": 10,
}
RUBRIC_NOTES = {
    "Evidence-based reasoning": "Evidence links, unresolved dictionary conflicts, and missing provenance.",
    "Planning and replanning": "Risk-prioritized plan and subtitle IDs selectively reverified after corrections.",
    "Translation decision quality": "Evidence-backed choices, unsupported terms, and conservative abstentions.",
    "Verification": "Independent verifier results, timing checks, and unresolved issues.",
    "Uncertainty and escalation": "Review count, confidence, and specificity of review questions.",
    "Engineering quality": "Reproducible mock run, audit exports, and focused automated tests.",
    "Use of AI tools": "Provider mode, call counts, verifier use, and the limits of recorded AI review.",
}
RELIABILITY_BASIS = {
    "examples": "Moderate: approved paired examples with context; finite, synthetic sample.",
    "dictionary_A": "Low to moderate: vendor-labeled; publisher is unnamed and kinship conflicts exist.",
    "dictionary_B": "Moderate: community-labeled; contributors are unnamed and meanings conflict.",
    "grammar": "Moderate: explicit patterns and caveats, but no author or date is supplied.",
    "expert_notes": "Moderate: three named expert positions; disagreement is explicit.",
    "viewer_feedback": "Low: anecdotal preference, not primary linguistic evidence.",
    "interviews": "Moderate: contextual testimony in transcripts; WAV files are not transcribed here.",
    "episode": "High for supplied source wording and timecodes; not evidence for Nadi-9 forms.",
}


st.set_page_config(page_title="Nadi-9 | Evidence desk", page_icon="N9", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
    :root { --ink:#1d2d29; --muted:#62716b; --line:#dce4df; --paper:#f5f7f4; --green:#176b52; --coral:#b64e3f; --gold:#9a6b13; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
    .stApp { background:linear-gradient(145deg,#f5f7f4 0%,#eef3f1 56%,#f8f5ee 100%); }
    .block-container { max-width:1440px; padding-top:2rem; padding-bottom:3rem; }
    h1,h2,h3 { color:var(--ink); letter-spacing:0; }
    h1 { font-weight:700; }
    [data-testid="stMetric"] { background:rgba(255,255,255,.8); border:1px solid var(--line); padding:14px 16px; border-radius:6px; }
    [data-testid="stMetricLabel"] { color:var(--muted); }
    [data-testid="stSidebar"] { background:#e9efeb; border-right:1px solid var(--line); }
    [data-testid="stTabs"] button { font-weight:600; }
    div[data-testid="stExpander"] { border-color:var(--line); border-radius:5px; background:rgba(255,255,255,.62); }
    code, .mono { font-family:'IBM Plex Mono',monospace; }
    .eyebrow { font:500 12px 'IBM Plex Mono',monospace; text-transform:uppercase; color:var(--green); }
    .status { color:var(--green); font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _extract_zip(uploaded_file) -> tuple[Path, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix="nadi9-input-"))
    root = temp_root.resolve()
    with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue())) as archive:
        for item in archive.infolist():
            target = (root / Path(item.filename)).resolve()
            if target != root and root not in target.parents:
                raise ValueError("The ZIP contains a path outside its input directory.")
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item))
    return root, temp_root


def _normalized_data_dir(path: Path) -> bool:
    return (path / "episode" / "transcript.json").is_file()


def _find_pack_root(root: Path) -> Path | None:
    if is_input_pack(root):
        return root
    for examples_file in root.rglob("approved_examples.json"):
        candidate = examples_file.parent.parent
        if is_input_pack(candidate):
            return candidate
    return None


def _collect_directory_files(root: Path) -> list[tuple[str, bytes]]:
    skipped_dirs = {".git", ".venv", "myvenv", "__pycache__", ".pytest_cache", "node_modules"}
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in skipped_dirs for part in path.parts):
            continue
        content = path.read_bytes() if path.suffix.lower() in SUPPORTED_SUFFIXES else b""
        files.append((path.relative_to(root).as_posix(), content))
    return files


def _resolve_data_dir(folder: str, uploaded_file, uploaded_files, role_overrides):
    import_report = []
    temp_root = None
    if uploaded_file is not None:
        source_dir, temp_root = _extract_zip(uploaded_file)
        pack_root = _find_pack_root(source_dir)
        if pack_root is not None:
            normalized_dir = temp_root / "normalized"
            return prepare_input_pack(pack_root, normalized_dir), True, temp_root, import_report
        if _normalized_data_dir(source_dir):
            return source_dir, False, temp_root, import_report
        files = _collect_directory_files(source_dir)
        data_dir, import_report = normalize_custom_files(files, temp_root / "normalized")
        return data_dir, False, temp_root, import_report
    if uploaded_files:
        temp_root = Path(tempfile.mkdtemp(prefix="nadi9-input-"))
        files = [(item.name, item.getvalue()) for item in uploaded_files]
        data_dir, import_report = normalize_custom_files(files, temp_root / "normalized", role_overrides)
        return data_dir, False, temp_root, import_report
    else:
        source_dir = Path(folder).expanduser().resolve()
    if not source_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {source_dir}")
    pack_root = _find_pack_root(source_dir)
    if pack_root is not None:
        normalized_dir = Path(tempfile.mkdtemp(prefix="nadi9-normalized-")) / "normalized"
        return prepare_input_pack(pack_root, normalized_dir), True, normalized_dir.parent, import_report
    if _normalized_data_dir(source_dir):
        return source_dir, False, None, import_report
    temp_root = Path(tempfile.mkdtemp(prefix="nadi9-input-"))
    files = _collect_directory_files(source_dir)
    data_dir, import_report = normalize_custom_files(files, temp_root / "normalized", role_overrides)
    return data_dir, False, temp_root, import_report


def _run_agent(folder: str, uploaded_file, uploaded_files, role_overrides, mode: str) -> None:
    data_dir, is_pack, temp_root, import_report = _resolve_data_dir(
        folder, uploaded_file, uploaded_files, role_overrides
    )
    run_id = uuid.uuid4().hex[:8]
    output_dir = ROOT / "data" / "processed" / "streamlit_runs" / run_id
    settings = Settings(
        mode=mode,
        data_dir=data_dir,
        output_dir=output_dir,
        db_path=output_dir / "nadi9.sqlite",
    )
    state = run_pipeline(settings)
    write_sample_run(state, output_dir)
    st.session_state["agent_state"] = state
    st.session_state["agent_settings"] = settings
    st.session_state["input_is_pack"] = is_pack
    st.session_state["input_temp_root"] = str(temp_root) if temp_root else None
    st.session_state["input_import_report"] = import_report


def _show_source_inventory(settings: Settings, is_pack: bool) -> None:
    records = load_evidence(settings.data_dir)
    sources = {}
    for record in records:
        sources.setdefault(
            record.source_id,
            {
                "Source": record.source_id,
                "Type": record.source_type.value,
                "Author": record.author or "Not supplied",
                "Date": record.date or "Not supplied",
                "Scope": record.scope or "Not supplied",
                "Reliability": record.reliability,
                "Reliability basis": RELIABILITY_BASIS.get(record.source_id, "Unassessed source type."),
            },
        )
    st.dataframe(list(sources.values()), hide_index=True, use_container_width=True)
    if is_pack:
        st.info(
            "This is a synthetic test pack. It supplies no catalog dates, named source authors, or reliability ratings; "
            "0.50 is the loader's neutral default, not an assessed trust score. Interview WAV files are present, "
            "but this run uses the supplied transcript text only."
        )
        st.caption("The expected-check notes and poisoned-evidence fixture are test material, not ingested linguistic evidence.")


def _evidence_list(items: list[str]) -> str:
    return ", ".join(items) if items else "None recorded"


with st.sidebar:
    st.markdown("<div class='eyebrow'>Nadi-9 / Local agent</div>", unsafe_allow_html=True)
    st.title("Evidence desk")
    default_pack = ROOT / "nadi9_test_input_pack"
    folder = st.text_input("Input folder", value=str(default_pack))
    individual_files = st.file_uploader("Upload individual source files", accept_multiple_files=True)
    folder_files = st.file_uploader("Or upload a whole folder", accept_multiple_files="directory")
    uploaded_files = [*(individual_files or []), *(folder_files or [])]
    uploaded_zip = st.file_uploader("Or upload a ZIP folder", type=["zip"])
    role_overrides = {}
    if uploaded_files:
        with st.expander("Review detected file roles", expanded=True):
            for index, item in enumerate(uploaded_files):
                suggested = suggest_role(item.name, item.getvalue())
                default_index = ROLE_LABELS.index(suggested) if suggested in ROLE_LABELS else 0
                selected = st.selectbox(
                    item.name,
                    ROLE_LABELS,
                    index=default_index,
                    key=f"input_role_{index}_{item.name}",
                )
                if selected != "Auto-detect":
                    role_overrides[item.name] = selected
    mode = st.selectbox("Provider", ["mock", "live"], index=0)
    run_clicked = st.button("Run all seven stages", type="primary", use_container_width=True)
    st.caption("Custom inputs are role-detected and shown for review. Timed episode lines are required; mock mode runs offline.")

if run_clicked:
    try:
        with st.spinner("Inspecting evidence, testing hypotheses, translating, and verifying..."):
            _run_agent(folder, uploaded_zip, uploaded_files, role_overrides, mode)
        st.success("Agent run complete.")
    except Exception as exc:
        st.error(f"Run failed: {exc}")

state = st.session_state.get("agent_state")
settings = st.session_state.get("agent_settings")
if not state or not settings:
    st.markdown("<div class='eyebrow'>Evidence-grounded subtitle decisions</div>", unsafe_allow_html=True)
    st.title("A reviewable language pipeline")
    st.write("Load the supplied test pack or a compatible evidence folder to inspect the agent's decisions, checks, and escalation trail.")
    st.stop()

is_pack = st.session_state.get("input_is_pack", False)
decisions = state.get("subtitle_decisions", [])
reviews = state.get("review_queue", [])
validations = state.get("validation_results", [])
valid_count = sum(bool(row.get("valid")) for row in validations)
evidence_linked = sum(bool(row.get("evidence")) for row in decisions)

st.markdown(f"<div class='eyebrow'>Run {state.get('run_id', '')} / {state.get('phase', 'report')}</div>", unsafe_allow_html=True)
st.title("Episode review")
st.caption("Every translation decision remains connected to evidence, assumptions, uncertainty, and independent checks.")
summary_cols = st.columns(4)
summary_cols[0].metric("Release recommendation", state.get("release_recommendation", "Pending"))
summary_cols[1].metric("Subtitle decisions", len(decisions))
summary_cols[2].metric("Human review", len(reviews))
summary_cols[3].metric("Verified", f"{valid_count}/{len(validations)}")

if is_pack:
    st.warning("Synthetic candidate test data. It is not authoritative Nadi-9 linguistic evidence.")

stage_tabs = st.tabs([
    "1 · Evidence",
    "2 · Hypotheses",
    "3 · Tests",
    "4 · Translation",
    "5 · Verification",
    "6 · Escalation",
    "7 · Replanning",
    "Rubric",
])

with stage_tabs[0]:
    st.subheader("Inspect the evidence")
    st.write("Source dates, named authors, scope, and reliability are shown as supplied. Missing metadata is left explicit.")
    import_report = st.session_state.get("input_import_report", [])
    if import_report:
        st.markdown("#### Input file report")
        st.dataframe(import_report, hide_index=True, use_container_width=True)
        skipped = [
            row for row in import_report
            if row["Status"].startswith(("Unsupported", "Could not parse", "Ignored"))
        ]
        if skipped:
            st.warning(f"{len(skipped)} file(s) were not used as evidence. Review their roles or formats before release.")
    _show_source_inventory(settings, is_pack)
    source_count = len({record.source_id for record in load_evidence(settings.data_dir)})
    st.caption(f"{source_count} sources indexed; {len(state.get('evidence_records', []))} evidence records.")

with stage_tabs[1]:
    st.subheader("Language hypotheses")
    hypotheses = state.get("hypotheses", [])
    st.dataframe(
        [
            {
                "ID": item.get("hypothesis_id"),
                "Category": item.get("category"),
                "Status": item.get("status"),
                "Confidence": item.get("confidence"),
                "Claim": item.get("claim"),
            }
            for item in hypotheses
        ],
        hide_index=True,
        use_container_width=True,
    )
    for item in hypotheses:
        with st.expander(f"{item.get('hypothesis_id')} · {item.get('claim')}"):
            st.write(item.get("notes", ""))
            st.write("Supporting: " + _evidence_list(item.get("supporting_evidence", [])))
            st.write("Counterexamples: " + _evidence_list(item.get("counterexamples", [])))

with stage_tabs[2]:
    st.subheader("Test rules against examples")
    tests = state.get("hypothesis_tests", [])
    test_rows = []
    for test in tests:
        test_rows.append(
            {
                "Hypothesis": test.get("hypothesis_id"),
                "Test": "Passed" if test.get("passed") else "Contested / not passed",
                "Supporting examples": len(test.get("supporting", [])),
                "Counterexamples": len(test.get("contradicting", [])),
                "Summary": test.get("summary"),
            }
        )
    st.dataframe(test_rows, hide_index=True, use_container_width=True)
    conflicts = state.get("conflicts", [])
    st.markdown("#### Dictionary disagreements")
    if conflicts:
        st.dataframe(conflicts, hide_index=True, use_container_width=True)
    else:
        st.write("No dictionary conflicts recorded.")

with stage_tabs[3]:
    st.subheader("Timed subtitle proposals")
    st.download_button("Download SRT", to_srt(decisions), file_name="subtitles.srt", mime="text/plain")
    st.dataframe(
        [
            {
                "ID": item.get("subtitle_id"),
                "Time": f"{item.get('start_time')} → {item.get('end_time')}",
                "Speaker": item.get("speaker") or "—",
                "Source": item.get("source_text"),
                "Nadi-9 proposal": item.get("nadi_9_text") or "[No supported proposal]",
                "Decision": item.get("decision"),
                "Confidence": item.get("confidence"),
            }
            for item in decisions
        ],
        hide_index=True,
        use_container_width=True,
    )
    selected_id = st.selectbox("Inspect subtitle record", [item.get("subtitle_id") for item in decisions])
    selected = next(item for item in decisions if item.get("subtitle_id") == selected_id)
    with st.expander("Complete decision record", expanded=True):
        st.json(selected)

with stage_tabs[4]:
    st.subheader("Independent verification")
    st.caption("Verifier output is separate from translator reasoning. Python checks subtitle timing and reading speed.")
    st.metric("Lines linked to evidence", f"{evidence_linked}/{len(decisions)}")
    validation_rows = []
    for item in validations:
        validation_rows.append(
            {
                "ID": item.get("subtitle_id"),
                "Valid": item.get("valid"),
                "Independent": item.get("independent"),
                "Evidence coverage": _evidence_list(item.get("evidence_coverage", [])),
                "Issues": "; ".join(issue.get("message", "") for issue in item.get("issues", [])) or "None",
            }
        )
    if validation_rows:
        st.dataframe(validation_rows, hide_index=True, use_container_width=True)
    else:
        st.warning("No verifier results were returned.")
    if state.get("errors"):
        st.markdown("#### Runtime and validation notes")
        for error in state["errors"]:
            st.write(f"- {error}")

with stage_tabs[5]:
    st.subheader("Expert review queue")
    if not reviews:
        st.success("No lines require human review.")
    for item in reviews:
        with st.container(border=True):
            st.markdown(f"**{item.get('subtitle_id')}** · {item.get('status', 'queued')}")
            st.write(item.get("reason"))
            st.markdown(f"**Review question:** {item.get('review_question')}")
            st.caption("Evidence: " + _evidence_list(item.get("evidence", [])))
    st.download_button(
        "Download review queue",
        json.dumps(reviews, ensure_ascii=False, indent=2),
        file_name="review_queue.json",
        mime="application/json",
    )

with stage_tabs[6]:
    st.subheader("Replan from a correction")
    st.write("Add a new evidence-backed claim. The agent traces affected hypotheses, then reruns only linked subtitle decisions.")
    with st.form("correction_form"):
        correction_id = st.text_input("Correction ID", value="C-UI")
        old_claim = st.text_input("Claim being revised")
        new_claim = st.text_area("New evidence-backed claim", height=110)
        correction_notes = st.text_input("Source or reviewer notes")
        apply_correction = st.form_submit_button("Apply correction and reverify", type="primary")
    if apply_correction:
        if not new_claim.strip():
            st.error("Enter the new claim before replanning.")
        else:
            correction = {
                "correction_id": correction_id.strip() or "C-UI",
                "source_id": "reviewer",
                "old_claim": old_claim,
                "new_claim": new_claim,
                "notes": correction_notes,
            }
            with st.spinner("Tracing impact and re-verifying affected subtitle lines..."):
                updated = replan_with_correction(settings, state, correction)
                write_sample_run(updated, settings.output_dir)
            st.session_state["agent_state"] = updated
            if updated.get("affected_subtitles"):
                st.success("Reverified only: " + ", ".join(updated["affected_subtitles"]))
                st.rerun()
            else:
                st.warning("No existing subtitle or hypothesis was linked to this correction; no subtitle was rerun.")
    if state.get("corrections"):
        st.markdown("#### Correction history")
        for correction in state["corrections"]:
            st.write(
                f"{correction.get('correction_id')}: {correction.get('new_claim')} "
                f"| affected: {_evidence_list(correction.get('affected_subtitles', []))}"
            )

with stage_tabs[7]:
    st.subheader("Weighted evaluation")
    st.caption("Scores are entered by the evaluator, not generated by the agent. Leave 0 for not yet scored.")
    scores = {}
    for criterion, weight in WEIGHTS.items():
        left, right = st.columns([3, 2])
        with left:
            st.markdown(f"**{criterion}** · {weight}%")
            st.caption(RUBRIC_NOTES[criterion])
        with right:
            scores[criterion] = st.select_slider(
                f"{criterion} score (0 = unscored)",
                options=[0, 1, 2, 3, 4, 5],
                value=0,
                key=f"score_{criterion}",
            )
    scored_weight = sum(weight for criterion, weight in WEIGHTS.items() if scores[criterion] > 0)
    weighted_score = sum(WEIGHTS[criterion] * scores[criterion] / 5 for criterion in WEIGHTS)
    st.metric("Weighted score", f"{weighted_score:.1f}/100", help=f"Scored rubric weight: {scored_weight}%")
    st.markdown("#### Run evidence")
    st.write(
        f"Provider: {settings.mode} · Model calls: {state.get('model_calls', 0)} · "
        f"Tool calls: {state.get('tool_calls', 0)} · Reviews: {len(reviews)} · "
        f"Independent checks passed: {valid_count}/{len(validations)}"
    )
    st.caption(
        "AI-tool-use scoring is only partially auditable: the run records provider mode, decisions, and verifier outcomes, "
        "but does not retain a separate before/after log for every model proposal."
    )

st.divider()
export_cols = st.columns(3)
with export_cols[0]:
    st.download_button(
        "Decisions JSONL",
        "\n".join(json.dumps(row, ensure_ascii=False) for row in decisions) + "\n",
        file_name="subtitle_decisions.jsonl",
        mime="application/x-ndjson",
    )
with export_cols[1]:
    rules_payload = {
        "hypotheses": state.get("hypotheses", []),
        "tests": state.get("hypothesis_tests", []),
        "conflicts": state.get("conflicts", []),
    }
    st.download_button(
        "Rules and tests JSON",
        json.dumps(rules_payload, ensure_ascii=False, indent=2),
        file_name="learned_rules.json",
        mime="application/json",
    )
with export_cols[2]:
    report_path = settings.output_dir / "final_report.md"
    report_content = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    st.download_button("Run report Markdown", report_content, file_name="final_report.md", mime="text/markdown")
