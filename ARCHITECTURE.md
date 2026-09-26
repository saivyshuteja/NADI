# Architecture

## Planning

The graph writes an explicit plan during `inspect_evidence` and reorders episode lines by linguistic risk (kinship, humour, undocumented terms) before translation. A mid-run correction does not restart the episode: impact analysis collects subtitle IDs that depend on the changed claim and `translate_and_verify` runs only those IDs.

## Memory

LangGraph `AgentState` holds evidence inventory, hypotheses, tests, conflicts, decisions, review queue, budget counters, and correction traces. SQLite persists subtitle rows, evidence links, and immutable audit JSON for each decision.

## Verification

Translator and verifier are separate `LLMProvider.generate` purposes with different payloads. The verifier never receives `reason` / translator chain-of-thought. Deterministic checks cover SRT order, timestamps, and characters-per-second.

## Failure recovery

- LLM exception → deterministic mock-style abstention or `HUMAN_REVIEW`
- Retriever exception → retry, then lexical fallback, then safe failure with empty `nadi_9_text`
- Model/tool budget → stop new calls and escalate remaining lines
- Missing lemma → `INSUFFICIENT_EVIDENCE`, never a fluent invention

## Trust boundaries

```
external file → parser → EvidenceRecord (untrusted=True)
        → retriever → wrap_as_data(...)
        → LLM (data, not instructions)
        → Python validators
        → decision record
```

Source precedence is **not** “newest” or “largest”. Dictionary A is largest and least trusted (unknown vendor + poisoned entries). Dictionary B, examples, grammar, and interviews are compared; disagreements remain as `ConflictRecord`s.

## What was not forced in

- No multi-agent swarm
- No cloud vector DB in the take-home
- No React UI
- Reading speed and SRT checks are ordinary Python
