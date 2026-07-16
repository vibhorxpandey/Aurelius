"""Phase 4 — LaTeX template variants and the preprint submission packager."""
from __future__ import annotations

import json
import zipfile

import pytest

from aurelius.tools.latex import TEMPLATES, latex_outline
from aurelius.tools.preprint import build_submission_package


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    monkeypatch.setenv("AURELIUS_OUTPUT_DIR", str(tmp_path))


def test_all_templates_render_with_title():
    for name in TEMPLATES:
        out = latex_outline("Fiber & Glucose", template=name)
        assert out["template"] == name
        assert "Fiber & Glucose" in out["latex"]
        assert r"\begin{document}" in out["latex"]


def test_unknown_template_falls_back_to_article():
    out = latex_outline("t", template="nature-super-premium")
    assert out["template"] == "article"


def test_package_contents_and_zip(tmp_path):
    ledger = [
        {"type": "citation", "verdict": "verified",
         "sources": [{"title": "Real Paper", "doi": "10.1/x", "year": 2020,
                      "authors": ["Ada Lovelace"], "venue": "J. Test"}]},
        {"type": "citation", "verdict": "unverified", "sources": []},  # excluded
        {"type": "claim", "verdict": "verified", "sources": [{"title": "web"}]},  # excluded
    ]
    pkg = build_submission_package(
        topic="T", session_id="s1", paper_draft="# Draft", latex="",
        evidence_ledger=ledger, proof={"content_hash": "abc", "sig_algo": "ed25519"},
        server="arxiv",
    )
    assert pkg["ok"] and pkg["server"] == "arxiv"

    bib = (tmp_path / "preprints" / "s1" / "references.bib").read_text(encoding="utf-8")
    assert "Real Paper" in bib and bib.count("@article") == 1  # only verified citations

    meta = json.loads((tmp_path / "preprints" / "s1" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["proof_content_hash"] == "abc" and meta["verified_references"] == 1

    checklist = (tmp_path / "preprints" / "s1" / "SUBMISSION_CHECKLIST.md").read_text(encoding="utf-8")
    assert "manual by design" in checklist and "ENDORSEMENT" in checklist

    with zipfile.ZipFile(pkg["zip"]) as zf:
        assert set(zf.namelist()) == set(pkg["files"])


def test_unknown_server_falls_back_to_arxiv():
    pkg = build_submission_package("T", "s2", paper_draft="d", server="vixra")
    assert pkg["server"] == "arxiv"


def test_medrxiv_checklist_mentions_ethics(tmp_path):
    build_submission_package("T", "s3", paper_draft="d", server="medrxiv")
    text = (tmp_path / "preprints" / "s3" / "SUBMISSION_CHECKLIST.md").read_text(encoding="utf-8")
    assert "ethics" in text.lower()
