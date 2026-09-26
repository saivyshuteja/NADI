# Known limitations

Intentionally incomplete relative to a production dialect platform:

1. **Synthetic evidence pack.** `data/raw` exists so the repo is runnable. It is not the hidden assignment pack. Reliability numbers in `catalog.json` are sample-pack metadata, not discoveries about real Nadi-9.
2. **Mock translator is rule-based.** Live LLM structured output is stubbed behind `OpenAIProvider` and is untested here without a key (privacy + evaluator mock requirement).
3. **No real ASR.** Interviews are text stand-ins; `transcribe_audio` reads `.txt` sidecars.
4. **Lexical retrieval only.** No learned embeddings, hybrid BM25+dense, or Chroma persistence.
5. **Single episode, single dialect.** `dialect_id` routing is not implemented.
6. **FastAPI is in-memory.** Runs vanish when the process exits; CLI writes `sample_run/` and SQLite.
7. **No reviewer UI.** JSONL + report + optional API only.
8. **Hypothesis builder is deterministic.** It will not discover unexpected rules in a brand-new pack without code or live-LLM hypothesis extraction being wired through and validated.
9. **Budget is counted at node granularity.** A hostile live model that loops tool calls inside one generate() is not sandboxed beyond provider choice.
10. **Exact-match examples can look “too confident.”** Verification and conflict inventory still keep dictionary disagreements visible at run level.

These cuts match the brief: 10–12 hours, working decision pipeline over polish.
