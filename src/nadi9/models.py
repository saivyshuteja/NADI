from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Decision(str, Enum):
    RELEASE = "RELEASE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED = "REJECTED"


class HypothesisStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    UNSUPPORTED = "UNSUPPORTED"
    INVALIDATED = "INVALIDATED"


class SourceType(str, Enum):
    EXAMPLE = "example"
    DICTIONARY = "dictionary"
    GRAMMAR = "grammar"
    INTERVIEW = "interview"
    EXPERT = "expert"
    FEEDBACK = "feedback"
    EPISODE = "episode"
    CORRECTION = "correction"


class EvidenceRecord(BaseModel):
    evidence_id: str
    source_id: str
    source_type: SourceType
    content: str
    claim: str | None = None
    author: str | None = None
    date: str | None = None
    scope: str | None = None
    reliability: float = 0.5
    version: str = "1"
    speaker: str | None = None
    scene: str | None = None
    timecode: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    untrusted: bool = True
    injection_flag: bool = False


class Hypothesis(BaseModel):
    hypothesis_id: str
    claim: str
    category: str
    status: HypothesisStatus
    confidence: float
    supporting_evidence: list[str] = Field(default_factory=list)
    counterexamples: list[str] = Field(default_factory=list)
    notes: str = ""


class HypothesisTest(BaseModel):
    hypothesis_id: str
    passed: bool
    supporting: list[str] = Field(default_factory=list)
    contradicting: list[str] = Field(default_factory=list)
    summary: str = ""


class SubtitleSegment(BaseModel):
    subtitle_id: str
    source_text: str
    speaker: str | None = None
    scene: str | None = None
    start_time: str
    end_time: str
    notes: str | None = None


class ValidationIssue(BaseModel):
    code: str
    severity: str
    message: str


class ValidationResult(BaseModel):
    subtitle_id: str
    valid: bool
    independent: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)
    evidence_coverage: list[str] = Field(default_factory=list)


class SubtitleDecision(BaseModel):
    subtitle_id: str
    source_text: str
    nadi_9_text: str | None = None
    confidence: float
    confidence_reason: str
    decision: Decision
    evidence: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    review_question: str | None = None
    review_status: str = "none"
    start_time: str | None = None
    end_time: str | None = None
    speaker: str | None = None
    scene: str | None = None
    verification: ValidationResult | None = None


class ReviewItem(BaseModel):
    subtitle_id: str
    reason: str
    review_question: str
    status: str = "queued"
    evidence: list[str] = Field(default_factory=list)


class Correction(BaseModel):
    correction_id: str
    source_id: str
    old_claim: str
    new_claim: str
    affected_hypotheses: list[str] = Field(default_factory=list)
    affected_subtitles: list[str] = Field(default_factory=list)
    notes: str = ""


class ConflictRecord(BaseModel):
    conflict_id: str
    term: str
    claims: list[str]
    evidence_ids: list[str]


class RunReport(BaseModel):
    run_id: str
    release_recommendation: str
    model_calls: int
    tool_calls: int
    subtitle_count: int
    review_count: int
    notes: list[str] = Field(default_factory=list)
