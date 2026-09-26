from __future__ import annotations

import re
from dataclasses import dataclass, field

from nadi9.models import EvidenceRecord
from nadi9.security.injection import wrap_as_data

TOKEN = re.compile(r"[a-z0-9\-]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


@dataclass
class RetrievedChunk:
    evidence_id: str
    content: str
    source_id: str
    source_type: str
    reliability: float
    score: float
    metadata: dict
    injection_flag: bool = False

    def prompt_block(self) -> str:
        return wrap_as_data(self.content, self.evidence_id)


@dataclass
class EvidenceIndex:
    records: list[EvidenceRecord]
    inverted: dict[str, set[str]] = field(default_factory=dict)
    by_id: dict[str, EvidenceRecord] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.by_id = {r.evidence_id: r for r in self.records}
        inv: dict[str, set[str]] = {}
        for rec in self.records:
            for tok in tokenize(rec.content):
                inv.setdefault(tok, set()).add(rec.evidence_id)
        self.inverted = inv

    def retrieve(self, query: str, top_k: int = 8, source_types: list[str] | None = None) -> list[RetrievedChunk]:
        q = tokenize(query)
        scores: dict[str, float] = {}
        for tok in q:
            for eid in self.inverted.get(tok, ()):
                rec = self.by_id[eid]
                if source_types and rec.source_type.value not in source_types:
                    continue
                scores[eid] = scores.get(eid, 0.0) + 1.0 + rec.reliability
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        out = []
        for eid, score in ranked:
            rec = self.by_id[eid]
            out.append(
                RetrievedChunk(
                    evidence_id=rec.evidence_id,
                    content=rec.content,
                    source_id=rec.source_id,
                    source_type=rec.source_type.value,
                    reliability=rec.reliability,
                    score=score,
                    metadata=rec.metadata,
                    injection_flag=rec.injection_flag,
                )
            )
        return out

    def lookup_lemma(self, lemma: str) -> list[EvidenceRecord]:
        lemma = lemma.lower()
        hits = []
        for rec in self.records:
            if rec.metadata.get("lemma") == lemma:
                hits.append(rec)
        return hits


def build_index(records: list[EvidenceRecord]) -> EvidenceIndex:
    return EvidenceIndex(records=records)
