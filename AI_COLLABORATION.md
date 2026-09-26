# AI collaboration log

Tools used: Cursor Grok 4.6 in-repo agent.

## How the assistant was directed

- The 5-page candidate brief was treated as the spec: uncertainty, verification, and replanning outrank a pretty translator.
- Implementation followed the agreed sequence: models → evidence → retrieval → hypotheses → translate/verify → LangGraph → correction → CLI/tests/docs.
- The official hidden evidence pack is **not** in the PDF; the assistant was instructed not to present sample lemmas as real Nadi-9.

## What was accepted

- LangGraph as the workflow spine, with a small number of responsibilities (evidence, hypothesis, translate, verify).
- Mock provider so evaluators run without an API key.
- Independent verifier payload (no translator rationale).
- Conflict records that do not auto-pick Dictionary A.
- Targeted correction impact instead of full reprocessing.
- Injection wrapping for retrieved text.

## What was checked by running

- `pytest` for conflict, unsupported term, correction, tool failure, injection.
- `python -m nadi9 --mode mock` to emit `sample_run/`.

## What was rejected or simplified

- **Chroma + sentence-transformers as a hard dependency.** Offline lexical retrieval is enough for this corpus, preserves privacy, and keeps mock mode reproducible. The index interface can be swapped later.
- **Ten autonomous LLM agents.** Extra agents would burn the 25-call budget and add correlated failures.
- **Inventing a “complete” Nadi-9 grammar** to make every line RELEASE. Abstention is the scored behavior.
- **Streamlit as priority-1.** The brief prefers a working decision pipeline.
- **Blindly copying approved example E18 (`zinglo`).** Interviews contest it; the mock translator escalates.
- **Using live web search as Nadi-9 evidence.** Forbidden by the brief.

## Remaining human responsibility

Replace `data/raw` with the real pack, re-check every decision against those files, and do not submit mock vocabulary as if it were evaluator ground truth.
