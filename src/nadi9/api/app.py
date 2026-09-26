from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from nadi9.config.settings import get_settings
from nadi9.graph.graph import run_pipeline
from nadi9.reporting import write_sample_run

app = FastAPI(title="Nadi-9 subtitle decision API")
RUNS: dict[str, dict] = {}


class RunRequest(BaseModel):
    mode: str = "mock"
    apply_correction: bool = True


class CorrectionIn(BaseModel):
    correction_id: str
    source_id: str
    old_claim: str
    new_claim: str


@app.get("/health")
def health():
    return {"ok": True, "mode": get_settings().mode}


@app.post("/runs")
def start_run(req: RunRequest):
    settings = get_settings()
    state = run_pipeline(settings, apply_midrun_correction=req.apply_correction)
    write_sample_run(state, settings.output_dir)
    RUNS[state["run_id"]] = state
    return {
        "run_id": state["run_id"],
        "release_recommendation": state.get("release_recommendation"),
        "model_calls": state.get("model_calls"),
        "tool_calls": state.get("tool_calls"),
    }


@app.get("/runs/{run_id}")
def run_status(run_id: str):
    return _get(run_id)


@app.get("/runs/{run_id}/decisions")
def decisions(run_id: str):
    return _get(run_id).get("subtitle_decisions", [])


@app.get("/runs/{run_id}/reviews")
def reviews(run_id: str):
    return _get(run_id).get("review_queue", [])


@app.get("/runs/{run_id}/report")
def report(run_id: str):
    state = _get(run_id)
    return {
        "release_recommendation": state.get("release_recommendation"),
        "plan": state.get("plan"),
        "corrections": state.get("corrections"),
        "errors": state.get("errors"),
    }


@app.post("/corrections")
def corrections(body: CorrectionIn):
    return {
        "accepted": True,
        "note": "Submit correction files under data/raw/corrections and re-run the pipeline for targeted revalidation.",
        "correction": body.model_dump(),
    }


def _get(run_id: str) -> dict:
    if run_id not in RUNS:
        raise HTTPException(404, "run not found; POST /runs first")
    return RUNS[run_id]
