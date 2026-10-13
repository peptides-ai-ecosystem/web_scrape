"""Tests for the ``fill_empty_only`` sync mode (AAD-9a).

After a curator approves a new peptide, the peptide-microservice asks this
service to sync it from pep-pedia with ``fill_empty_only: true``: only empty
columns of the existing peptide row may be filled, and a child-row kind
(benefits, protocols, references, PK graph, ...) may be added only when the
peptide has none of that kind. Offline: the DB layer is replaced by fakes.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api.v1.endpoints.sync as sync_endpoints
import src.mappers.db_import_orchestrator as core_module
import src.mappers.graph_import_orchestrator as graph_module
from src.infrastructure.db.repositories.peptide import (
    CHILD_KIND_SQL,
    PeptideRepository,
    is_empty_value,
)
from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.mappers.graph_import_orchestrator import GraphImportOrchestrator


# ---------------------------------------------------------------------------
# Repository: fill_empty_columns / is_empty_value
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "   ", "[]", "{}", [], {}])
def test_empty_values(value):
    assert is_empty_value(value)


@pytest.mark.parametrize("value", ["8 hrs", 0, False, ["x"], {"a": 1}, "[1]"])
def test_non_empty_values(value):
    assert not is_empty_value(value)


class _RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))


def _repo_with_row(row):
    repo = PeptideRepository(connection=None)
    cur = _RecordingCursor()

    @contextmanager
    def get_cursor():
        yield cur

    repo.get_by_id = lambda _id: row
    repo.get_cursor = get_cursor
    repo._commit = lambda: None
    return repo, cur


def test_fill_empty_columns_never_overwrites_curated_values():
    row = {
        "id": 223, "name": "KLOW", "slug": "klow",
        "overview": "Curator text", "half_life": None, "cycle_length": "",
        "stop_signs": [], "storage": "Fridge",
    }
    repo, cur = _repo_with_row(row)

    filled = repo.fill_empty_columns(223, {
        "name": "Klow (blend)", "slug": "klow-blend",       # identity: never written
        "overview": "Scraped text", "storage": "Freezer",   # curated: kept
        "half_life": "8 hrs", "cycle_length": "4 weeks",    # empty: filled
        "stop_signs": '["rash"]',                           # empty JSON: filled
        "not_a_column": "x",                                # unknown: ignored
        "safety": "",                                       # empty value: ignored
    })

    assert sorted(filled) == ["cycle_length", "half_life", "stop_signs"]
    assert len(cur.calls) == 1
    sql, params = cur.calls[0]
    assert sql.startswith("UPDATE peptides SET ")
    for col in ("overview", "storage", "name", "slug", "not_a_column"):
        assert f"{col} =" not in sql
    assert params[-1] == 223
    assert "INSERT" not in sql


def test_fill_empty_columns_does_nothing_when_row_is_complete():
    repo, cur = _repo_with_row({"id": 1, "overview": "x"})
    assert repo.fill_empty_columns(1, {"overview": "y"}) == []
    assert cur.calls == []


def test_fill_empty_columns_missing_row_never_inserts():
    repo, cur = _repo_with_row(None)
    assert repo.fill_empty_columns(1, {"overview": "y"}) == []
    assert cur.calls == []


def test_child_kinds_cover_every_relation_kind_and_graph():
    assert set(CHILD_KIND_SQL) == {
        "benefits", "side_effects", "interactions", "indications",
        "references", "protocols", "graph",
    }


# ---------------------------------------------------------------------------
# Core orchestrator
# ---------------------------------------------------------------------------

def _payload(slug="klow"):
    return {
        "group_a": {
            "administration_methods": [], "benefits": [], "side_effects": [],
            "dosages": [], "schedules": [], "studies": [], "application_places": [],
        },
        "group_b": {"peptide": {"name": "KLOW", "slug": slug, "half_life": "8 hrs"}},
        "relations": {
            "benefits": [{"benefit_name": "Healing"}],
            "side_effects": [{"side_effect_name": "Nausea"}],
            "interactions": [],
            "indications": [{"indication_title": "Wounds"}],
            "references": [],
        },
        "protocols": [{
            "administration_method_name": "Injectable",
            "reconstitution_steps": [], "quality_indicators": [],
            "application_places": [], "dosages": [{"amount": "250mcg"}],
        }],
    }


def _fake_db(kinds_present, existing_row):
    db = MagicMock()
    db.get_all_peptide_identifiers.return_value = {"klow"}
    db.get_all_administration_methods.return_value = [{"id": 6, "name": "Injectable"}]
    db.get_peptide_by_identifier.return_value = existing_row
    db.get_child_kinds_present.return_value = {k: k in kinds_present for k in CHILD_KIND_SQL}
    db.fill_empty_peptide_columns.return_value = ["half_life"]
    db.upsert_peptide_fill_nulls.return_value = 999
    db.get_lookup_id.return_value = 1
    db.upsert_protocol.return_value = 77
    return db


def _run_core(monkeypatch, db, payload, **kwargs):
    monkeypatch.setattr(core_module, "DbManager", lambda _url: db)
    orch = DbImportOrchestrator()
    monkeypatch.setattr(orch, "map_row", lambda _row: payload)
    return orch.sync_to_db(
        "postgres://fake", [{"Peptide_Name": "KLOW", "Method": "Injectable"}],
        activity_type="manual", **kwargs,
    )


def test_core_fill_empty_only_fills_and_adds_only_missing_kinds(monkeypatch):
    db = _fake_db(
        kinds_present={"benefits", "side_effects"},
        existing_row={"id": 223, "slug": "klow", "activity_type": "manual"},
    )
    # The mapper's slug differs from the matched row: must still not insert.
    result = _run_core(monkeypatch, db, _payload(slug="klow-blend"), fill_empty_only=True)

    assert result["synced_count"] == 1
    db.upsert_peptide_fill_nulls.assert_not_called()
    db.fill_empty_peptide_columns.assert_called_once()
    assert db.fill_empty_peptide_columns.call_args.args[0] == 223

    # Curator-approved benefits/side effects exist -> not linked again.
    linked_tables = [c.args[0] for c in db.link_relation.call_args_list]
    assert "peptide_benefits" not in linked_tables
    assert "peptide_side_effects" not in linked_tables
    # Kinds the peptide had none of are added.
    db.upsert_indication.assert_called_once_with(223, {"indication_title": "Wounds"})
    db.upsert_protocol.assert_called_once()
    db.upsert_protocol_dosage.assert_called_once_with(77, {"amount": "250mcg"})
    # activity_type already set -> left alone.
    db.update_peptide_activity_type.assert_not_called()


def test_core_fill_empty_only_keeps_existing_protocols(monkeypatch):
    db = _fake_db(
        kinds_present={"protocols", "indications"},
        existing_row={"id": 223, "slug": "klow", "activity_type": None},
    )
    _run_core(monkeypatch, db, _payload(), fill_empty_only=True)

    db.upsert_protocol.assert_not_called()
    db.upsert_protocol_dosage.assert_not_called()
    db.upsert_indication.assert_not_called()
    linked_tables = [c.args[0] for c in db.link_relation.call_args_list]
    assert "peptide_benefits" in linked_tables
    db.update_peptide_activity_type.assert_called_once_with(223, "manual")


def test_core_fill_empty_only_skips_when_row_cannot_be_resolved(monkeypatch):
    db = _fake_db(kinds_present=set(), existing_row=None)
    result = _run_core(monkeypatch, db, _payload(), fill_empty_only=True)

    assert result["synced_count"] == 0
    assert result["skipped_count"] == 1
    db.upsert_peptide_fill_nulls.assert_not_called()
    db.fill_empty_peptide_columns.assert_not_called()


def test_core_default_mode_is_unchanged(monkeypatch):
    db = _fake_db(kinds_present=set(CHILD_KIND_SQL), existing_row={"id": 223})
    _run_core(monkeypatch, db, _payload())

    db.get_child_kinds_present.assert_not_called()
    db.fill_empty_peptide_columns.assert_not_called()
    db.upsert_peptide_fill_nulls.assert_called_once()
    db.upsert_protocol.assert_called_once()
    linked_tables = [c.args[0] for c in db.link_relation.call_args_list]
    assert "peptide_benefits" in linked_tables
    db.update_peptide_activity_type.assert_called_once_with(999, "manual")


# ---------------------------------------------------------------------------
# Graph orchestrator
# ---------------------------------------------------------------------------

def _run_graph(monkeypatch, has_graph, **kwargs):
    db = MagicMock()
    db.get_all_peptide_identifiers.return_value = {"klow"}
    db.get_peptide_by_slug.return_value = {"id": 223, "slug": "klow"}
    db.get_child_kinds_present.return_value = {"graph": has_graph}
    db.get_lookup_id.return_value = 6
    monkeypatch.setattr(graph_module, "DbManager", lambda _url: db)
    orch = GraphImportOrchestrator()
    monkeypatch.setattr(orch.graph_mapper, "map", lambda _row: [{"method": "Injectable", "time_range": "24h"}])
    result = orch.sync_graph_data("postgres://fake", [{"Peptide_Name": "KLOW"}], **kwargs)
    return db, result


def test_graph_fill_empty_only_never_overwrites_existing_curves(monkeypatch):
    db, result = _run_graph(monkeypatch, has_graph=True, fill_empty_only=True)
    db.upsert_graph_data.assert_not_called()
    assert result["skipped_count"] == 1


def test_graph_fill_empty_only_writes_when_peptide_has_no_curves(monkeypatch):
    db, result = _run_graph(monkeypatch, has_graph=False, fill_empty_only=True)
    db.upsert_graph_data.assert_called_once()
    assert result["synced_count"] == 1


def test_graph_default_mode_still_upserts(monkeypatch):
    db, _ = _run_graph(monkeypatch, has_graph=True)
    db.upsert_graph_data.assert_called_once()


# ---------------------------------------------------------------------------
# Endpoints pass the flag through
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    app = FastAPI()
    app.include_router(sync_endpoints.router, prefix="/api/v1/sync")
    return TestClient(app)


@pytest.mark.parametrize("path,task", [("/core", "run_core_sync_task"), ("/graph", "run_graph_sync_task")])
@pytest.mark.parametrize("body,expected", [
    ({"urls": ["https://pep-pedia.org/peptides/klow"], "fill_empty_only": True}, True),
    ({"urls": ["https://pep-pedia.org/peptides/klow"]}, False),
])
def test_endpoint_passes_flag(client, monkeypatch, path, task, body, expected):
    calls = []
    monkeypatch.setattr(sync_endpoints, task, lambda *a, **kw: calls.append(kw))
    res = client.post(f"/api/v1/sync{path}", json=body)
    assert res.status_code == 202
    assert calls == [{"fill_empty_only": expected}]
