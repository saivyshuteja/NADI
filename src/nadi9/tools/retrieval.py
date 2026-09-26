from __future__ import annotations

from nadi9.evidence.retrieval import EvidenceIndex


class RetrievalTool:
    def __init__(self, index: EvidenceIndex | None, fail: bool = False):
        self.index = index
        self.fail = fail
        self.failures = 0

    def retrieve(self, query: str, top_k: int = 8):
        if self.fail:
            self.failures += 1
            raise RuntimeError("retriever unavailable")
        if self.index is None:
            raise RuntimeError("retriever unavailable")
        return self.index.retrieve(query, top_k=top_k)
