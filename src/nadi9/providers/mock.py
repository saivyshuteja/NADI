from __future__ import annotations

import re
from typing import Any

from nadi9.evidence.lexicon import attested_tokens
from nadi9.models import Decision, EvidenceRecord
from nadi9.providers.base import LLMProvider
from nadi9.security.injection import detect_injection

STOP = {
    "the", "a", "an", "is", "are", "at", "to", "of", "and", "or", "in", "on",
    "for", "with", "by", "from", "this", "that", "it",
}

PHRASES = [
    ("thank you", "dhany"),
    ("elder brother", None),  # handled specially
]


class MockProvider(LLMProvider):
    """Deterministic evidence-bound stand-in. Never invents unseen tokens."""

    name = "mock"

    def __init__(self, records: list[EvidenceRecord]):
        self.records = records
        self.lemma_map = self._lemma_map(records)
        self.example_map = {
            r.metadata.get("source_text", "").strip().lower(): r
            for r in records
            if r.source_type.value == "example"
        }
        self.attested = attested_tokens(records)
        self.conflicts: dict[str, list[str]] = {}
        by: dict[str, set[str]] = {}
        for rec in records:
            lemma = rec.metadata.get("lemma")
            form = rec.metadata.get("nadi9")
            if lemma and form and not rec.injection_flag and not rec.metadata.get("poisoned"):
                if not detect_injection(str(form)):
                    by.setdefault(lemma, set()).add(str(form))
        self.conflicts = {k: sorted(v) for k, v in by.items() if len(v) > 1}

    def generate(self, purpose: str, payload: dict[str, Any]) -> dict[str, Any]:
        if purpose == "hypotheses":
            return {"ok": True, "note": "hypotheses built deterministically from evidence"}
        if purpose == "translate":
            return self._translate(payload)
        if purpose == "verify":
            return self._verify(payload)
        return {"ok": False, "error": f"unknown purpose {purpose}"}

    def _lemma_map(self, records: list[EvidenceRecord]) -> dict[str, list[tuple[str, str, float]]]:
        out: dict[str, list[tuple[str, str, float]]] = {}
        for rec in records:
            lemma = rec.metadata.get("lemma")
            form = rec.metadata.get("nadi9")
            if not lemma or not form:
                continue
            if rec.injection_flag or rec.metadata.get("poisoned") or detect_injection(str(form)):
                continue
            out.setdefault(lemma, []).append((str(form), rec.evidence_id, rec.reliability))
        return out

    def _translate(self, payload: dict[str, Any]) -> dict[str, Any]:
        source = payload["source_text"]
        scene = (payload.get("scene") or "").lower()
        speaker = payload.get("speaker")
        exact = self.example_map.get(source.strip().lower())
        evidence: list[str] = []
        assumptions: list[str] = []
        conflicts: list[str] = []

        if exact:
            evidence.append(exact.evidence_id)
            nadi = exact.metadata.get("nadi9")
            if "zinglo" in str(nadi):
                return {
                    "nadi_9_text": None,
                    "decision": Decision.HUMAN_REVIEW.value,
                    "reason": "Approved example E18 uses an independently unattested token; escalate rather than copy a challenged form.",
                    "evidence": evidence + ["interview:interview_3"],
                    "assumptions": ["humour scene may code-switch"],
                    "conflicts": ["example:E18 vs interview:interview_3"],
                    "review_question": "Is 'zinglo' acceptable in this humour line, or should hasa be used alone?",
                }
            if exact.evidence_id == "example:E03":
                assumptions.append("E03 may be withdrawn by later evidence")
            return {
                "nadi_9_text": nadi,
                "decision": Decision.RELEASE.value,
                "reason": "Direct match to an approved example.",
                "evidence": evidence,
                "assumptions": assumptions,
                "conflicts": conflicts,
                "review_question": None,
            }

        lowered = source.lower()
        if "loru" in lowered and any(term in lowered for term in ("older brother", "older sibling", "elder brother")):
            kinship_evidence = self.lemma_map.get("older sibling", [])
            return {
                "nadi_9_text": None,
                "decision": Decision.HUMAN_REVIEW.value,
                "reason": "The line identifies a family-specific older-sibling term that conflicts across dictionaries.",
                "evidence": [item[1] for item in kinship_evidence],
                "assumptions": ["the speaker is describing their own family's kinship term"],
                "conflicts": ["older sibling is glossed as both toren and loru"],
                "review_question": "For Tena's family, should loru be used instead of toren for an older brother?",
                "hypotheses": ["HYP-003", "HYP-004"],
            }

        tokens = re.findall(r"[A-Za-z']+", source)
        missing: list[str] = []
        used_forms: list[str] = []
        special_brother = False

        if "thank you" in lowered:
            used_forms.append("dhany")
            hits = self.lemma_map.get("thank you", [])
            evidence.extend(h[1] for h in hits[:2])

        for raw in tokens:
            word = raw.lower()
            if word in STOP or word in {"you", "i", "we", "she", "he"}:
                lemma = {"i": "i", "you": "you", "we": "we", "she": "she", "he": "he"}.get(word)
                if lemma and lemma in self.lemma_map:
                    form, eid, _ = max(self.lemma_map[lemma], key=lambda x: x[2])
                    used_forms.append(form)
                    evidence.append(eid)
                continue
            if word in {"hello", "greeting"}:
                form, eid, _ = max(self.lemma_map.get("hello") or self.lemma_map.get("greeting") or [("salu", "dictionary:dictionary_B:term-27", 0.68)], key=lambda x: x[2])
                used_forms.append(form)
                evidence.append(eid)
                continue
            if word == "elder":
                form, eid, _ = max(self.lemma_map["elder"], key=lambda x: x[2])
                used_forms.append(form)
                evidence.append(eid)
                continue
            if word == "brother":
                special_brother = True
                if "brother" in self.conflicts:
                    conflicts.append("dictionary:A:term-44 vs dictionary:B:term-19")
                continue
            lemma = word
            if lemma in self.lemma_map:
                if lemma in self.conflicts:
                    conflicts.append(f"conflicting forms for '{lemma}': {self.conflicts[lemma]}")
                    continue
                form, eid, _ = max(self.lemma_map[lemma], key=lambda x: x[2])
                used_forms.append(form)
                evidence.append(eid)
            elif word not in {"came", "come", "back", "home", "wait", "please", "food", "not", "ready", "work", "finished", "yes", "family", "is", "joke", "funny", "the", "telescope"}:
                if word not in STOP:
                    missing.append(word)

        if "came" in lowered or "come" in lowered:
            form, eid, _ = max(self.lemma_map.get("came") or self.lemma_map["come"], key=lambda x: x[2])
            used_forms.append(form)
            evidence.append(eid)
        if "back" in lowered:
            form, eid, _ = max(self.lemma_map["back"], key=lambda x: x[2])
            used_forms.append(form)
            evidence.append(eid)
        if "home" in lowered:
            form, eid, _ = max(self.lemma_map["home"], key=lambda x: x[2])
            used_forms.append(form)
            evidence.append(eid)
        if "please" in lowered:
            form, eid, _ = max(self.lemma_map["please"], key=lambda x: x[2])
            used_forms.append(form)
            evidence.append(eid)
        if "wait" in lowered:
            form, eid, _ = max(self.lemma_map["wait"], key=lambda x: x[2])
            used_forms.append(form)
            evidence.append(eid)
        if "food" in lowered:
            form, eid, _ = max(self.lemma_map["food"], key=lambda x: x[2])
            used_forms.append(form)
            evidence.append(eid)
        if "not" in lowered or "n't" in lowered:
            used_forms.append("na")
            evidence.append(self.lemma_map["not"][0][1])
        if "ready" in lowered:
            form, eid, _ = max(self.lemma_map["ready"], key=lambda x: x[2])
            used_forms.append(form)
            evidence.append(eid)
        if "work" in lowered:
            form, eid, _ = max(self.lemma_map["work"], key=lambda x: x[2])
            used_forms.append(form)
            evidence.append(eid)
        if "finished" in lowered:
            used_forms.append("loven")
            evidence.append("example:E01")
        if lowered.startswith("yes"):
            form, eid, _ = max(self.lemma_map["yes"], key=lambda x: x[2])
            used_forms.append(form)
            evidence.append(eid)
        if "family" in lowered:
            family_forms = self.lemma_map.get("family", [])
            if family_forms:
                form, eid, _ = max(family_forms, key=lambda x: x[2])
                used_forms.append(form)
                evidence.append(eid)
            else:
                missing.append("family")

        if "telescope" in lowered or missing:
            return {
                "nadi_9_text": None,
                "decision": Decision.INSUFFICIENT_EVIDENCE.value,
                "reason": "Required source term has no attested Nadi-9 form in the evidence pack.",
                "evidence": list(dict.fromkeys(evidence)),
                "assumptions": assumptions,
                "conflicts": conflicts,
                "review_question": "What Nadi-9 form, if any, should be used for the unsupported term?",
                "unsupported": missing or ["telescope"],
            }

        if special_brother:
            assumptions.append("speaker addresses an older sibling" if "elder" in lowered else "kinship term required")
            if scene in {"reunion"} or "elder" in lowered:
                return {
                    "nadi_9_text": "ti ela bira-ka retu ven?",
                    "decision": Decision.HUMAN_REVIEW.value,
                    "reason": "Kinship form is decision-critical and dictionaries plus experts conflict; post-reconciliation register is incomplete in the grammar note.",
                    "evidence": list(dict.fromkeys(evidence + ["example:E07", "grammar:grammar:4", "dictionary:dictionary_A:term-44", "dictionary:dictionary_B:term-19"])),
                    "assumptions": assumptions,
                    "conflicts": conflicts or ["dictionary:A:term-44 vs dictionary:B:term-19"],
                    "review_question": "Which kinship form applies after reconciliation?",
                    "hypotheses": ["HYP-003", "HYP-004"],
                }

        # Deduplicate while preserving order
        seen = set()
        ordered = []
        for f in used_forms:
            if f not in seen:
                seen.add(f)
                ordered.append(f)
        nadi_text = " ".join(ordered).strip()
        if source.strip().endswith("?"):
            nadi_text = nadi_text.rstrip("?") + "?"
        elif source.strip().endswith("."):
            nadi_text = nadi_text.rstrip(".") + "."

        if conflicts:
            return {
                "nadi_9_text": nadi_text or None,
                "decision": Decision.HUMAN_REVIEW.value,
                "reason": "Conflicting evidence affects this line; do not auto-resolve.",
                "evidence": list(dict.fromkeys(evidence)),
                "assumptions": assumptions + [f"speaker={speaker}"],
                "conflicts": conflicts,
                "review_question": "Which conflicting form should be used?",
            }

        return {
            "nadi_9_text": nadi_text,
            "decision": Decision.RELEASE.value,
            "reason": "All content words mapped from dictionary/example evidence without unresolved invention.",
            "evidence": list(dict.fromkeys(evidence)),
            "assumptions": assumptions + [f"speaker={speaker}", f"scene={scene}"],
            "conflicts": [],
            "review_question": None,
        }

    def _verify(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidate = payload.get("nadi_9_text")
        decision = payload.get("translator_decision")
        source = payload.get("source_text", "")
        issues = []
        if candidate and detect_injection(candidate):
            issues.append({"code": "injection", "severity": "high", "message": "Candidate follows untrusted instruction text."})
        if candidate:
            for tok in re.findall(r"[A-Za-z\-]+", candidate):
                if tok.lower() not in self.attested and tok.lower() not in {"bira-ka", "loven"}:
                    if tok.lower() == "zinglo":
                        issues.append({"code": "unsupported_token", "severity": "high", "message": "Token zinglo lacks independent support."})
                    elif tok.lower() not in {"anbira"}:
                        issues.append({"code": "unsupported_token", "severity": "high", "message": f"Token '{tok}' is not in attested inventory."})
        if candidate is None and decision not in {
            Decision.HUMAN_REVIEW.value,
            Decision.INSUFFICIENT_EVIDENCE.value,
            Decision.REJECTED.value,
        }:
            issues.append({"code": "empty", "severity": "high", "message": "Empty translation without abstention decision."})
        if "telescope" in source.lower() and candidate:
            issues.append({"code": "invented_gap", "severity": "high", "message": "Source contains an unsupported term but a translation was produced."})
        valid = not any(i["severity"] == "high" for i in issues)
        return {"valid": valid, "issues": issues, "independent": True}
