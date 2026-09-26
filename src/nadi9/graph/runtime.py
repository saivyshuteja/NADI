from __future__ import annotations

from dataclasses import dataclass, field

from nadi9.budget import BudgetManager
from nadi9.config.settings import Settings
from nadi9.evidence.retrieval import EvidenceIndex
from nadi9.models import EvidenceRecord
from nadi9.providers.base import LLMProvider
from nadi9.tools.retrieval import RetrievalTool


@dataclass
class Runtime:
    settings: Settings
    records: list[EvidenceRecord]
    index: EvidenceIndex
    provider: LLMProvider
    retrieval: RetrievalTool
    budget: BudgetManager
    retriever_retries: int = 1
    force_tool_failure: bool = False
    disable_fallback: bool = False
    apply_midrun_correction: bool = True
    notes: list[str] = field(default_factory=list)
