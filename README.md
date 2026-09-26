<<<<<<< HEAD
# Nadi-9 Agentic Subtitle Platform

Evidence-grounded agent that learns a **fictional** dialect from incomplete, conflicting material and produces subtitle *decisions* (including abstention), not fluent guesses.

## 1. Problem statement

Nadi-9 is not available online. The only valid knowledge is the supplied evidence pack. The hiring brief scores **reasoning under uncertainty**, not translation polish.

## 2. Objective

Inspect evidence → form/test hypotheses → propose subtitles → **independently** verify → escalate uncertainty → replan on corrections.

## 3. Architecture

CLI / optional FastAPI → LangGraph workflow → evidence RAG (lexical + metadata) → hypothesis engine → translator LLM (or mock) → independent verifier + deterministic SRT/CPS checks → SQLite audit trail.

See [ARCHITECTURE.md](ARCHITECTURE.md).

## 4. Evidence model

Each chunk is an `EvidenceRecord` with `source_id`, type, author, date, scope, reliability, and an injection flag. Retrieved text is wrapped as **untrusted data**.

This repository ships a **synthetic demonstration pack** under `data/raw/`. It is **not** the hidden evaluator pack. Replace `data/raw` with the official assignment materials when you have them. Do not treat sample lemmas as real Nadi-9.

## 5. RAG pipeline

Loaders → catalog metadata → chunking (entries/paragraphs) → in-memory inverted index with reliability-weighted overlap. Dictionary lookup is exact-lemma, not “trust the largest file”.

Chroma / sentence-transformers were intentionally **not** required: local lexical retrieval keeps mock/replay offline, private, and reproducible at assignment scale.

## 6. Hypothesis engine

Deterministic builder emits rules (SOV, negation `na`, status-shaped kinship, dictionary conflict, no invented technical terms). Counterexamples stay on the hypothesis. A mid-run linguist correction updates only linked hypotheses.

## 7. LangGraph workflow

`load_run → inspect_evidence → retrieve → form_and_test_hypotheses → prioritize_episode → translate_and_verify → apply_correction → (targeted re-verify) → report`

## 8. Verification

The verifier prompt/payload does **not** include translator reasoning. Python validates timestamps and reading speed. Unsupported tokens fail closed.

## 9. Uncertainty handling

Confidence is reduced by conflicts, verifier issues, and missing lemmas. `HUMAN_REVIEW` / `INSUFFICIENT_EVIDENCE` beat invention. Every review item has a focused question.

## 10. Correction / replanning

Correction C-R17 invalidates the casual elder-brother example path, traces `HYP-003` / kinship lines, and reruns **only** those subtitle IDs.

## 11. Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## 12. Configuration

Copy `.env.example` to `.env`. Mock mode needs no API key.

## 13. Mock mode

```bash
python -m nadi9 --mode mock
```

Evaluators can run the full pipeline without your personal key. Live mode (`--mode live`) requires `OPENAI_API_KEY` and must not use a retention/training endpoint for the real evidence pack.

## 14. Running

```bash
python -m nadi9 --mode mock
python -m nadi9 --serve
```

API: `POST /runs`, `GET /runs/{id}/decisions`, `GET /runs/{id}/reviews`, `GET /runs/{id}/report`, `POST /corrections`, `GET /health`.

## 15. Streamlit reviewer

```bash
streamlit run src/nadi9/streamlit_app.py
```

The reviewer defaults to `nadi9_test_input_pack/`, but also accepts individual files, a whole uploaded folder, a ZIP, or a local directory. Common CSV/JSON/JSONL examples and dictionaries, timecoded CSV/JSON/SRT episodes, and Markdown/text notes are normalized automatically. A per-file role selector handles ambiguous names or schemas, and the evidence view reports files it could not parse. Episode input must include start/end timestamps (or numeric-second offsets); unsupported audio/PDF formats are reported, not silently treated as transcripts. The synthetic sample pack has no source dates or catalog trust scores, so the interface marks missing metadata and distinguishes its neutral loader default from its qualitative reliability notes. Reviewer rubric scores are evaluator-entered rather than agent-generated.

## 16. Tests

```bash
pytest -q
```

Covers dictionary conflict, unsupported term, correction impact, tool failure, and prompt-injection isolation.

## 17. Sample run

Generated under `sample_run/`: `subtitles.srt`, `subtitle_decisions.jsonl`, `learned_rules.json`, `review_queue.json`, `final_report.md`.

## 18. Evaluation mapping

| Rubric | Where to look |
| --- | --- |
| Evidence-based reasoning | `learned_rules.json`, decision `evidence` fields |
| Planning / replanning | `run_state.json` plan + `affected_subtitles` |
| Translation quality | abstention on `telescope`; no invented tokens |
| Verification | independent verify payload in `graph/nodes.py` |
| Uncertainty | `review_queue.json` |
| Engineering | tests, mock mode, budget counters |

## 19. Security

Retrieved documents cannot become system instructions. Poisoned dictionary A `peace` entry is flagged. Secrets stay in `.env`. SQL uses parameters.

## 20. Limitations

See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## 21. Future improvements

Swap the lexical index for pgvector/Qdrant, add real ASR, and add dialect_id routing.
=======
# NADI
>>>>>>> e1ae80b1cd1b2de77c130b72973f9a2dc7cc734e
