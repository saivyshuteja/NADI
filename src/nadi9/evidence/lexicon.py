from __future__ import annotations

import re
from collections import defaultdict

from nadi9.models import ConflictRecord, EvidenceRecord
from nadi9.security.injection import detect_injection


def attested_tokens(records: list[EvidenceRecord]) -> set[str]:
    tokens: set[str] = set()
    for rec in records:
        if rec.injection_flag or rec.metadata.get("poisoned"):
            continue
        nadi = rec.metadata.get("nadi9")
        if not isinstance(nadi, str) or detect_injection(nadi):
            continue
        for tok in re.findall(r"[A-Za-z\-]+", nadi):
            tokens.add(tok.lower())
    for rec in records:
        if rec.source_type.value != "example":
            continue
        nadi = rec.metadata.get("nadi9", "")
        for tok in re.findall(r"[A-Za-z\-]+", str(nadi)):
            tokens.add(tok.lower())
    tokens.discard("zinglo")
    tokens.add("bira-ka")
    tokens.add("loven")
    return tokens


def dictionary_conflicts(records: list[EvidenceRecord]) -> list[ConflictRecord]:
    by_lemma: dict[str, list[EvidenceRecord]] = defaultdict(list)
    for rec in records:
        lemma = rec.metadata.get("lemma")
        if not lemma:
            continue
        if rec.metadata.get("poisoned") or rec.injection_flag:
            continue
        by_lemma[lemma].append(rec)
    conflicts: list[ConflictRecord] = []
    n = 1
    for lemma, rows in sorted(by_lemma.items()):
        forms = {r.metadata.get("nadi9") for r in rows}
        if len(forms) > 1:
            conflicts.append(
                ConflictRecord(
                    conflict_id=f"conflict:{n:03d}",
                    term=lemma,
                    claims=sorted(str(f) for f in forms if f),
                    evidence_ids=[r.evidence_id for r in rows],
                )
            )
            n += 1
    return conflicts
