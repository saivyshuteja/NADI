from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  source_type TEXT,
  title TEXT,
  author TEXT,
  date TEXT,
  scope TEXT,
  reliability REAL,
  version TEXT
);
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  source_id TEXT,
  content TEXT,
  claim TEXT,
  metadata TEXT
);
CREATE TABLE IF NOT EXISTS hypotheses (
  hypothesis_id TEXT PRIMARY KEY,
  claim TEXT,
  status TEXT,
  confidence REAL,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS hypothesis_evidence (
  hypothesis_id TEXT,
  evidence_id TEXT,
  relationship TEXT
);
CREATE TABLE IF NOT EXISTS subtitles (
  subtitle_id TEXT PRIMARY KEY,
  source_text TEXT,
  nadi_9_text TEXT,
  start_time TEXT,
  end_time TEXT,
  confidence REAL,
  decision TEXT
);
CREATE TABLE IF NOT EXISTS subtitle_evidence (
  subtitle_id TEXT,
  evidence_id TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
  review_id TEXT PRIMARY KEY,
  subtitle_id TEXT,
  reason TEXT,
  review_question TEXT,
  status TEXT
);
CREATE TABLE IF NOT EXISTS corrections (
  correction_id TEXT PRIMARY KEY,
  source_id TEXT,
  old_claim TEXT,
  new_claim TEXT,
  affected_items TEXT
);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT,
  subtitle_id TEXT,
  payload TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
