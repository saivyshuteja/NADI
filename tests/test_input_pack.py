from pathlib import Path

from nadi9.config.settings import Settings
from nadi9.evidence.lexicon import dictionary_conflicts
from nadi9.evidence.loader import load_evidence, load_episode_segments
from nadi9.graph.graph import replan_with_correction, run_pipeline
from nadi9.custom_inputs import normalize_custom_files
from nadi9.input_pack import prepare_input_pack


def test_candidate_pack_runs_and_replans_only_affected_lines(tmp_path):
    root = Path(__file__).resolve().parents[1]
    data_dir = prepare_input_pack(root / "nadi9_test_input_pack", tmp_path / "normalized")
    records = load_evidence(data_dir)

    assert sum(record.source_type.value == "example" for record in records) == 20
    assert sum(record.source_type.value == "interview" for record in records) == 5
    assert len(load_episode_segments(data_dir)) == 12
    assert any(
        conflict.term == "older sibling" and set(conflict.claims) == {"loru", "toren"}
        for conflict in dictionary_conflicts(records)
    )
    assert all(record.date is None for record in records)

    settings = Settings(
        mode="mock",
        data_dir=data_dir,
        output_dir=tmp_path / "out",
        db_path=tmp_path / "nadi9.sqlite",
    )
    initial = run_pipeline(settings, apply_midrun_correction=False)
    assert not initial["errors"]
    assert len(initial["subtitle_decisions"]) == 12
    assert initial["release_recommendation"] == "HOLD_FOR_HUMAN_REVIEW"

    by_id = {row["subtitle_id"]: row for row in initial["subtitle_decisions"]}
    assert by_id["S07"]["decision"] == "INSUFFICIENT_EVIDENCE"
    assert by_id["S11"]["decision"] == "HUMAN_REVIEW"
    assert by_id["S11"]["review_question"] == (
        "For Tena's family, should loru be used instead of toren for an older brother?"
    )
    assert {"dictionary:dictionary_A:A002", "dictionary:dictionary_B:B013"} <= set(by_id["S11"]["evidence"])

    replanned = replan_with_correction(
        settings,
        initial,
        {
            "correction_id": "C-UI-1",
            "old_claim": "toren is preferred for elders",
            "new_claim": "Tena's family prefers loru for an older brother",
        },
    )
    affected = set(replanned["affected_subtitles"])
    assert affected == {"S01", "S04", "S09", "S11"}
    assert "S08" not in affected
    after_by_id = {row["subtitle_id"]: row for row in replanned["subtitle_decisions"]}
    assert all(by_id[subtitle_id] == after_by_id[subtitle_id] for subtitle_id in by_id.keys() - affected)
    assert replanned["last_replan_model_calls"] == 2 * len(affected)
    assert not replanned["errors"]
    assert next(hyp for hyp in replanned["hypotheses"] if hyp["hypothesis_id"] == "HYP-007")["status"] == "CONTESTED"


def test_custom_mixed_files_run_without_bundle_layout(tmp_path):
    files = [
        ("samples.csv", b"id,source,translation\nX1,Good morning friend.,sava neli.\n"),
        ("vocabulary.csv", b"term,meaning\ntoren,elder\n"),
        ("episode.srt", b"1\n00:00:01,000 --> 00:00:03,000\nGood morning friend.\n"),
        ("rules.md", b"Word order is not yet established."),
    ]
    data_dir, import_report = normalize_custom_files(
        files,
        tmp_path / "custom-data",
        {"vocabulary.csv": "Dictionary", "rules.md": "Grammar note"},
    )
    settings = Settings(
        mode="mock",
        data_dir=data_dir,
        output_dir=tmp_path / "custom-out",
        db_path=tmp_path / "custom.sqlite",
    )

    state = run_pipeline(settings, apply_midrun_correction=False)

    assert len(state["subtitle_decisions"]) == 1
    assert state["subtitle_decisions"][0]["nadi_9_text"] == "sava neli."
    assert state["subtitle_decisions"][0]["decision"] == "RELEASE"
    assert not state["errors"]
    assert [item["Status"] for item in import_report] == [
        "Loaded 1 examples",
        "Loaded 1 dictionary entries",
        "Loaded 1 timed subtitle lines",
        "Loaded text evidence",
    ]
