from __future__ import annotations

import json
from datetime import datetime, timezone

from nadi9.models import SubtitleDecision
from nadi9.storage.database import connect


def persist_decision(db_path, run_id: str, decision: SubtitleDecision) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO subtitles
            (subtitle_id, source_text, nadi_9_text, start_time, end_time, confidence, decision)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.subtitle_id,
                decision.source_text,
                decision.nadi_9_text,
                decision.start_time,
                decision.end_time,
                decision.confidence,
                decision.decision.value,
            ),
        )
        conn.execute("DELETE FROM subtitle_evidence WHERE subtitle_id = ?", (decision.subtitle_id,))
        for eid in decision.evidence:
            conn.execute(
                "INSERT INTO subtitle_evidence (subtitle_id, evidence_id) VALUES (?, ?)",
                (decision.subtitle_id, eid),
            )
        conn.execute(
            "INSERT INTO audit_events (run_id, subtitle_id, payload) VALUES (?, ?, ?)",
            (
                run_id,
                decision.subtitle_id,
                json.dumps(
                    {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "decision": decision.model_dump(mode="json"),
                    }
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()
