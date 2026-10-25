"""AID-4: the pep-pedia mapping fills what it can and says what it left out.

Offline: rows are plain dicts shaped like the scraper's CSV; the DB layer is a fake.
"""

from unittest.mock import MagicMock

import pytest

import app.services.sync.db_import_orchestrator as core_module
from app.repositories.peptide import CHILD_KIND_SQL
from app.services.sync.db_import_orchestrator import DbImportOrchestrator
from app.services.sync.group_b.peptide_mapper import PeptideMapper
from app.services.sync.method_resolution import resolve_method

DB_METHODS = {"Injectable", "Nasal Spray", "Topical Cream", "Capsule"}

# ── method resolution ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Injectable", "Injectable"),
        ("Nasal, Injectable", "Nasal Spray"),
        ("Intranasal", "Nasal Spray"),
        ("Oral", "Capsule"),
        ("Topical", "Topical Cream"),
        ("Subcutaneous", "Injectable"),
        ("Nasal spray", "Nasal Spray"),
        ("Sublingual drops, Oral", "Capsule"),  # the first part is unknown, a later one maps
    ],
)
def test_method_keywords_resolve(raw, expected):
    assert resolve_method(raw, DB_METHODS).method == expected


def test_unmapped_and_missing_methods_say_why_instead_of_raising():
    unknown = resolve_method("Sublingual drops", DB_METHODS)
    assert unknown.method is None and "no mapping" in unknown.reason
    empty = resolve_method("", DB_METHODS)
    assert empty.method is None and "no Method" in empty.reason
    missing = resolve_method("Oral", {"Injectable"})
    assert missing.method is None and "'Capsule' not in DB" in missing.reason


# ── peptide mapper: the columns that were dropped ───────────────────────────

ROW = {
    "Peptide_Name": "BPC-157",
    "Full_Name": "Body Protection Compound 157",
    "Method": "Injectable",
    "research_level": "Well Researched",
    "half-life": "4 hrs ()",
    "quick_guide_onset": "1-2 weeks",
    "Break Period": "2 weeks off",
    "materials_needed": "Syringes, bacteriostatic water",
    "side_effects_and_safety_safety_guidelines_1": "Use sterile technique",
    "side_effects_and_safety_safety_guidelines_2": "Rotate sites",
    "quality_checks_1": "Clear solution",
    "quality_checks_2": "Third-party HPLC",
    "cycle": "4 weeks",
    "storage": "2-8 C",
}


def test_mapper_fills_the_columns_it_used_to_drop():
    out = PeptideMapper().map(ROW)
    assert out["half_life_value"] == 4.0 and out["half_life_unit"] == "hours"
    assert out["effect_onset"] == "1-2 weeks"
    assert out["break_period"] == "2 weeks off"
    assert out["required_materials"] == "Syringes, bacteriostatic water"
    assert out["safety_guidelines"] == "Use sterile technique\nRotate sites"
    assert out["quality_checks"] == "Clear solution\nThird-party HPLC"
    # what it already mapped is unchanged
    assert out["cycle_duration"] == "4 weeks" and out["storage_temperature"] == "2-8 C"


def test_research_level_is_no_longer_dropped_but_is_not_written_to_the_enum_column():
    mapper = PeptideMapper()
    assert mapper.extras(ROW) == {"research_stage": "Well Researched"}
    # peptides.research_level is the development-phase enum (preclinical..approved): pep-pedia's
    # maturity label must never be written into it.
    assert "research_level" not in mapper.map(ROW) and "research_stage" not in mapper.map(ROW)


@pytest.mark.parametrize(
    "text,value,unit",
    [("30 min", 30.0, "minutes"), ("~1.7 days", 1.7, "days"), ("4-6 hours", 4.0, "hours"), ("8 hrs ()", 8.0, "hours")],
)
def test_half_life_text_is_parsed(text, value, unit):
    out = PeptideMapper().map({"Peptide_Name": "X", "half_life": text})
    assert (out["half_life_value"], out["half_life_unit"]) == (value, unit)


def test_a_row_without_the_new_fields_maps_to_empty_values_not_errors():
    out = PeptideMapper().map({"Peptide_Name": "X"})
    assert out["half_life_value"] is None and out["half_life_unit"] == ""
    for col in ("effect_onset", "break_period", "required_materials", "safety_guidelines", "quality_checks"):
        assert out[col] == ""
    assert PeptideMapper().map({"Peptide_Name": "X", "half_life": "unknown"})["half_life_value"] is None
    assert PeptideMapper().extras({"Peptide_Name": "X"}) == {"research_stage": None}


# ── orchestrator: an unmapped Method no longer skips the whole peptide ───────


def _fake_db(methods=("Injectable",)):
    db = MagicMock()
    db.get_all_peptide_identifiers.return_value = {"klow"}
    db.get_all_administration_methods.return_value = [{"id": i, "name": m} for i, m in enumerate(methods, 1)]
    db.get_peptide_by_slug.return_value = None
    db.get_peptide_by_identifier.return_value = {"id": 223, "slug": "klow", "activity_type": None}
    db.get_child_kinds_present.return_value = {k: False for k in CHILD_KIND_SQL}
    db.fill_empty_peptide_columns.return_value = ["effect_onset"]
    db.upsert_peptide_fill_nulls.return_value = 223
    db.get_lookup_id.return_value = 1
    db.upsert_protocol.return_value = 77
    return db


def _run(monkeypatch, db, method, **kwargs):
    monkeypatch.setattr(core_module, "DbManager", lambda _url: db)
    row = {
        "Peptide_Name": "KLOW",
        "Method": method,
        "research_level": "Limited Research",
        "quick_guide_onset": "1 week",
        "overview_key_benefits": "Tissue repair.",
        "research_protocols_goal_1": "Starter",
        "research_protocols_dose_1": "250 mcg",
        "research_protocols_frequency_1": "daily",
        "what_to_expect_1": "Week 1: calmer",
    }
    return DbImportOrchestrator().sync_to_db("postgres://fake", [row], activity_type="manual", **kwargs)


def test_unmapped_method_still_writes_columns_and_method_free_children(monkeypatch):
    db = _fake_db()
    result = _run(monkeypatch, db, "Sublingual drops")

    assert result["synced_count"] == 1 and result["skipped_count"] == 0
    written = db.upsert_peptide_fill_nulls.call_args.args[0]
    assert written["effect_onset"] == "1 week"
    linked = [c.args[0] for c in db.link_relation.call_args_list]
    assert "peptide_benefits" in linked
    # a protocol needs an administration method: not written, and the job result says why
    db.upsert_protocol.assert_not_called()
    partial = result["partial_peptides"]
    assert partial == [
        {
            "name": "KLOW",
            "slug": "klow",
            "reason": "admin method 'Sublingual drops' has no mapping",
            "not_written": ["protocols"],
        }
    ]
    assert result["synced_peptides"][0]["method"] is None
    assert result["synced_peptides"][0]["research_stage"] == "Limited Research"


def test_empty_method_and_method_missing_from_the_db_behave_the_same(monkeypatch):
    for method, methods in (("", ("Injectable",)), ("Oral", ("Injectable",))):
        db = _fake_db(methods)
        result = _run(monkeypatch, db, method)
        assert result["synced_count"] == 1 and result["skipped_count"] == 0, method
        db.upsert_protocol.assert_not_called()
        assert result["partial_peptides"][0]["not_written"] == ["protocols"], method


def test_mapped_method_is_unchanged(monkeypatch):
    db = _fake_db()
    result = _run(monkeypatch, db, "Injectable")
    db.upsert_protocol.assert_called_once()
    assert result["partial_peptides"] == []
    assert result["synced_peptides"][0]["method"] == "Injectable"


def test_fill_empty_only_with_unmapped_method_fills_empty_columns_only(monkeypatch):
    db = _fake_db()
    result = _run(monkeypatch, db, "Sublingual drops", fill_empty_only=True)
    assert result["synced_count"] == 1
    db.upsert_peptide_fill_nulls.assert_not_called()
    db.fill_empty_peptide_columns.assert_called_once()
    db.upsert_protocol.assert_not_called()


def test_a_peptide_with_no_db_match_is_still_skipped(monkeypatch):
    db = _fake_db()
    db.get_all_peptide_identifiers.return_value = {"other"}
    result = _run(monkeypatch, db, "Injectable")
    assert result["synced_count"] == 0 and result["skipped_count"] == 1
    db.upsert_peptide_fill_nulls.assert_not_called()


@pytest.mark.parametrize("raw", ["Topical spray", "Oral spray", "Transdermal spray"])
def test_a_bare_spray_is_not_a_nasal_spray(raw):
    assert resolve_method(raw, DB_METHODS).method != "Nasal Spray"


def test_long_onset_and_break_are_cut_to_the_varchar_100_columns():
    long_text = "Most users notice improved sleep in the first week, full effects build over 8 to 12 weeks. " * 2
    assert len(long_text) > 150
    row = {**ROW, "quick_guide_onset": long_text, "Break Period": long_text}
    row |= {"cycle": long_text, "storage": long_text}
    out = PeptideMapper().map(row)
    for column in ("effect_onset", "break_period", "cycle_duration", "storage_temperature"):
        assert len(out[column]) == 100
        assert long_text.startswith(out[column])
