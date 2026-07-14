"""Proof-of-Rigor — content hash, signing/verify, tamper detection, IPFS/anchor degradation."""
from __future__ import annotations

import pytest

from aurelius.orchestration.state import new_state
from aurelius.proof import anchor, build_proof, ipfs, rigor, verify_proof


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    monkeypatch.setenv("AURELIUS_OUTPUT_DIR", str(tmp_path))
    # default: no HMAC secret, no Pinata, no chain
    for var in ("AURELIUS_PROOF_HMAC_SECRET", "PINATA_JWT", "AURELIUS_PINATA_JWT",
                "AURELIUS_CHAIN_RPC", "AURELIUS_CHAIN_PRIVATE_KEY"):
        monkeypatch.delenv(var, raising=False)


def _state():
    st = new_state("Effect of X on Y")
    st["hypothesis"] = "X increases Y"
    st["evidence_ledger"] = [{"claim": "paper A", "verdict": "verified"}]
    st["verification_report"] = {"verification_score": 1.0, "counts": {"total": 1, "verified": 1}}
    return st


def test_build_and_verify_valid():
    bundle = build_proof(_state())
    assert len(bundle["content_hash"]) == 64  # sha256 hex
    v = verify_proof(bundle)
    assert v["valid"] and v["hash_ok"] and v["sig_ok"]


def test_tamper_is_detected():
    bundle = build_proof(_state())
    bundle["payload"]["hypothesis"] = "TAMPERED"
    v = verify_proof(bundle)
    assert v["valid"] is False and v["hash_ok"] is False


def test_hmac_signature_path(monkeypatch):
    monkeypatch.setenv("AURELIUS_PROOF_HMAC_SECRET", "s3cret")
    bundle = build_proof(_state())
    assert bundle["sig_algo"] == "hmac-sha256"
    assert verify_proof(bundle)["valid"] is True
    # wrong secret fails verification
    monkeypatch.setenv("AURELIUS_PROOF_HMAC_SECRET", "different")
    assert verify_proof(bundle)["valid"] is False


def test_deterministic_hash():
    st = _state()  # one state: content hash is a pure function of the (same) payload
    a = build_proof(st)["content_hash"]
    b = build_proof(st)["content_hash"]
    assert a == b


def test_ipfs_skips_without_key():
    r = ipfs.pin_json({"session_id": "x"})
    assert r["pinned"] is False and "PINATA_JWT" in r["note"]


def test_anchor_writes_local_and_skips_chain(tmp_path):
    r = anchor.anchor_hash("deadbeef" * 8, session_id="sess1")
    assert r["backend"] == "local" and r["anchored"] is True
    assert r["chain"]["anchored"] is False
    # local anchor log exists and contains the hash
    log = tmp_path / "anchors" / "anchor_log.jsonl"
    assert log.exists() and "deadbeef" in log.read_text(encoding="utf-8")


def test_save_proof_writes_bundle(tmp_path):
    path = rigor.save_proof(build_proof(_state()), "sessABC")
    assert path.endswith("proof_sessABC.json")
    import os
    assert os.path.exists(path)
