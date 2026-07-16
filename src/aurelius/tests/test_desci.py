"""Phase 5 — patent-freedom screening and the retraction watcher (all offline)."""
from __future__ import annotations

import json

import pytest

from aurelius.tools import patents, retractions


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    monkeypatch.setenv("AURELIUS_OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)
    monkeypatch.delenv("AURELIUS_PATENTSVIEW_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("AURELIUS_TAVILY_API_KEY", raising=False)


# --- patents ---------------------------------------------------------------------
def test_no_sources_gives_insufficient_data():
    r = patents.patent_freedom_report("gene editing delivery vector")
    assert r["verdict"] == "insufficient_data"
    assert "legal advice" in r["disclaimer"].lower() or "NOT legal" in r["disclaimer"]


def test_web_fallback_flags_overlap(monkeypatch):
    monkeypatch.setattr(patents.search, "web_search", lambda *a, **k: {
        "ok": True, "results": [{"title": "US Patent 1", "url": "u", "snippet": "s"}]})
    r = patents.patent_freedom_report("thing")
    assert r["verdict"] == "potential_overlap" and r["backend"] == "web"


def test_patentsview_backend_parses(monkeypatch):
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "k")

    class FakeResp:
        status_code = 200
        def json(self):
            return {"patents": [{"patent_id": "9999999", "patent_title": "A device",
                                 "patent_date": "2020-01-01",
                                 "assignees": [{"assignee_organization": "ACME"}]}]}

    class FakeClient:
        def __init__(self, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **k): return FakeResp()

    monkeypatch.setattr(patents.httpx, "Client", FakeClient)
    r = patents.patent_freedom_report("a device")
    assert r["backend"] == "patentsview" and r["verdict"] == "potential_overlap"
    assert r["hits"][0]["assignees"] == ["ACME"]


def test_empty_query():
    assert patents.patent_freedom_report("", "")["verdict"] == "insufficient_data"


# --- retraction watch --------------------------------------------------------------
def _fake_verify(status):
    def fake(citation, max_results=5):
        return {"verdict": status, "is_retracted": status == "retracted",
                "notes": f"now {status}"}
    return fake


def test_recheck_flags_newly_retracted(monkeypatch):
    monkeypatch.setattr(retractions, "verify_citation", _fake_verify("retracted"))
    r = retractions.retraction_watch(["Wakefield 1998 MMR"])
    assert r["retracted"] == 1 and len(r["alerts"]) == 1


def test_recheck_clean(monkeypatch):
    monkeypatch.setattr(retractions, "verify_citation", _fake_verify("verified"))
    r = retractions.retraction_watch(["Okun 1962"])
    assert r["alerts"] == [] and "still verify" in r["note"]


def test_scan_saved_proofs(monkeypatch, tmp_path):
    proof_dir = tmp_path / "proofs"
    proof_dir.mkdir(parents=True)
    (proof_dir / "proof_s1.json").write_text(json.dumps({
        "payload": {"evidence_ledger": [
            {"type": "citation", "claim": "Paper A (2020)"},
            {"type": "claim", "claim": "GDP grew"},  # not a citation - skipped
        ]}}), encoding="utf-8")
    monkeypatch.setattr(retractions, "verify_citation", _fake_verify("verified"))
    r = retractions.retraction_watch()
    assert r["checked"] == 1 and r["sessions_scanned"] == 1


def test_scan_with_no_proofs():
    r = retractions.retraction_watch()
    assert r["checked"] == 0 and "nothing to watch" in r["note"].lower()
