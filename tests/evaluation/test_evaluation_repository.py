"""webscrape-2: the evaluation package holds no SQL; its reads live in ``app/repositories/``."""

import re
from pathlib import Path

from app.evaluation.db_actual_fetcher import DbActualFetcher
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.graph import GraphRepository

EVALUATION_DIR = Path(__file__).resolve().parents[2] / "app" / "evaluation"


class _Cursor:
    """Records every statement and answers from a canned table keyed by a SQL fragment."""

    def __init__(self, conn):
        self._conn = conn
        self.description = [("x",)]
        self._rows: list = []

    def execute(self, sql, params=()):
        self._conn.executed.append((sql, params))
        self._rows = next((rows for frag, rows in self._conn.answers if frag in sql), [])

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _Conn:
    def __init__(self, answers):
        self.answers = answers
        self.executed: list[tuple[str, tuple]] = []

    def cursor(self):
        return _Cursor(self)


def test_evaluation_package_runs_no_sql():
    offenders = [
        path.name
        for path in EVALUATION_DIR.glob("*.py")
        if re.search(r"\.cursor\(|\.execute\(|\bSELECT\b", path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_repository_returns_dict_rows_and_none_for_unknown_slug():
    conn = _Conn([("FROM peptides WHERE slug", [{"id": 7, "slug": "bpc-157"}])])
    repo = EvaluationRepository(conn)
    assert repo.get_peptide_by_slug("bpc-157") == {"id": 7, "slug": "bpc-157"}
    assert EvaluationRepository(_Conn([])).get_peptide_by_slug("nope") is None
    assert conn.executed[0][1] == ("bpc-157",)


def test_repository_maps_tuple_rows_with_column_names():
    class TupleCursor(_Cursor):
        def __init__(self, conn):
            super().__init__(conn)
            self.description = [("cnt",)]

    conn = _Conn([("COUNT(*)", [(3,)])])
    conn.cursor = lambda: TupleCursor(conn)
    assert EvaluationRepository(conn).count_references(7) == 3


def test_fetch_assembles_the_shape_the_engine_compares():
    conn = _Conn(
        [
            ("FROM peptides WHERE slug", [{"id": 7, "slug": "bpc-157"}]),
            ("FROM benefits b", [{"name": "Healing"}]),
            ("FROM side_effects se", [{"name": "Nausea"}]),
            ("FROM dosages d", [{"amount": 250, "unit": "mcg"}]),
            ("FROM schedules s", [{"name": "Daily"}]),
            ("FROM administration_methods am", [{"name": "Injectable"}]),
            ("FROM peptide_interactions", [{"secondary_peptide_name": "TB-500"}]),
            ("FROM peptide_research_indications", [{"indication_title": "Tendon"}]),
            ("FROM peptide_protocols WHERE", [{"id": 1, "name": "P1"}]),
            ("FROM peptide_references", [{"cnt": 4}]),
        ]
    )
    fetcher = DbActualFetcher.__new__(DbActualFetcher)
    fetcher._repo = EvaluationRepository(conn)
    actual = fetcher.fetch("bpc-157")
    assert actual == {
        "peptide": {"id": 7, "slug": "bpc-157"},
        "benefits": ["Healing"],
        "side_effects": ["Nausea"],
        "dosages": [{"amount": 250, "unit": "mcg"}],
        "schedules": ["Daily"],
        "administration_methods": ["Injectable"],
        "interactions": [{"secondary_peptide_name": "TB-500"}],
        "indications": [{"indication_title": "Tendon"}],
        "protocols": [{"id": 1, "name": "P1"}],
        "references_count": 4,
    }
    assert all(params == (7,) for _, params in conn.executed[1:])


def test_fetch_is_none_when_the_peptide_is_missing():
    fetcher = DbActualFetcher.__new__(DbActualFetcher)
    fetcher._repo = EvaluationRepository(_Conn([]))
    assert fetcher.fetch("nope") is None


def test_graph_rows_for_peptide_reads_peptide_graph_by_peptide_id():
    rows = [{"time_range": "24h", "path_data": "M0", "points": [], "markers": []}]
    conn = _Conn([("FROM peptide_graph WHERE peptide_id", rows)])
    assert GraphRepository(conn).graph_rows_for_peptide(7) == rows
    assert conn.executed[0][1] == (7,)
    assert GraphRepository(_Conn([])).graph_rows_for_peptide(7) == []
