"""The CSV inspector routes (``/api/v1/csv/*``) read the scraped CSV through
``csv_inspector_service``; a missing CSV or row is a 404 with the same detail."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.services.csv_inspector_service as svc
from src.api.v1.endpoints import csv_inspector


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(csv_inspector.router, prefix="/api/v1/csv")
    return TestClient(app)


@pytest.fixture
def csv_file(tmp_path, monkeypatch):
    path = tmp_path / "enhanced.csv"
    path.write_text(
        "Peptide_Name,Full_Name,Method,URL,overview_what_is,graph_data_json\n"
        'BPC-157,Body Protection Compound,Injectable,https://x/bpc-157,heals,"{""a"": 1}"\n'
        "BPC-157,Body Protection Compound,Oral,https://x/bpc-157,,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "MASTER_CSV", path)
    monkeypatch.setitem(svc._CACHE, "mtime", None)
    return path


def test_missing_csv_is_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "MASTER_CSV", tmp_path / "absent.csv")
    res = client.get("/api/v1/csv/columns")
    assert res.status_code == 404
    assert res.json()["detail"].startswith("Master CSV not found at ")


def test_peptides_columns_and_one_row(client, csv_file):
    peptides = client.get("/api/v1/csv/peptides").json()
    assert [(p["name"], p["method"], p["slug"]) for p in peptides] == [
        ("BPC-157", "Injectable", "bpc-157"),
        ("BPC-157", "Oral", "bpc-157"),
    ]
    columns = client.get("/api/v1/csv/columns").json()
    assert columns["total"] == 6 and columns["row_count"] == 2
    assert columns["groups"]["identity"] == ["Peptide_Name", "Full_Name", "Method", "URL"]
    row = client.get("/api/v1/csv/peptide", params={"name": "bpc-157", "method": "Injectable"}).json()
    assert row["groups"]["graph"] == {"graph_data_json": {"a": 1}}
    assert row["groups"]["overview"] == {"overview_what_is": "heals"}


def test_unknown_peptide_is_404(client, csv_file):
    res = client.get("/api/v1/csv/peptide", params={"name": "nope", "method": "Oral"})
    assert res.status_code == 404
    assert res.json()["detail"] == "No CSV row found for name='nope', method='Oral'"
