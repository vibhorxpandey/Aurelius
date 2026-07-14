"""Cryptographic Proof-of-Rigor: a tamper-evident, verifiable attestation of a research run.

Phase 3 core (dependency-free by default):
  1. Canonicalize the load-bearing state (topic, hypothesis, evidence ledger, verification &
     methodology reports, sandbox result, and the audit trail) into deterministic JSON.
  2. SHA-256 it → a **content hash** that doubles as a content-addressed id (like an IPFS CID
     is hash-derived): any later edit to the record changes the hash, so tampering is evident.
  3. **Sign** it. Signature backend, in order of preference:
       - HMAC-SHA256 if ``AURELIUS_PROOF_HMAC_SECRET`` is set (symmetric, stdlib only), or
       - ed25519 if the `cryptography` package is installed (asymmetric; public key embedded), or
       - none (hash-only — still tamper-evident, just not authenticated).

``verify_proof`` recomputes the hash and re-checks the signature, so a bundle can be
independently validated later. IPFS pinning and on-chain anchoring live in sibling modules
and are attached by the ProofOfRigorAgent.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import get_output_dir, get_proof_hmac_secret
from ..orchestration.state import ResearchState, now_iso

PROOF_VERSION = "1.0"

try:  # optional asymmetric signing
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization

    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover - environment without cryptography
    _HAVE_CRYPTO = False


def canonical_payload(state: ResearchState) -> Dict[str, Any]:
    """The stable subset of state that the proof attests to (order-independent)."""
    vr = state.get("verification_report", {}) or {}
    mr = state.get("methodology_report", {}) or {}
    sb = state.get("sandbox_result", {}) or {}
    # Deep-copy the mutable collections: the proof must snapshot state at build time, immune
    # to any later mutation (e.g. the ProofOfRigorAgent's own audit-log append after signing).
    return {
        "topic": state.get("topic", ""),
        "hypothesis": state.get("hypothesis", ""),
        "evidence_ledger": copy.deepcopy(state.get("evidence_ledger", [])),
        "verification": {"score": vr.get("verification_score"), "counts": copy.deepcopy(vr.get("counts"))},
        "methodology": {"risk": mr.get("risk"), "risk_score": mr.get("risk_score"),
                        "findings": [f.get("signal") for f in mr.get("findings", [])]},
        "sandbox": {"ran": sb.get("ran"), "ok": sb.get("ok"), "exit_code": sb.get("exit_code")},
        "audit_trail": copy.deepcopy(state.get("audit_trail", [])),
        "session_id": state.get("session_id", ""),
    }


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(payload: Dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonicalized payload."""
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _sign(digest_hex: str) -> Dict[str, Any]:
    """Sign the content hash with the best available backend."""
    secret = get_proof_hmac_secret()
    if secret:
        sig = hmac.new(secret.encode("utf-8"), digest_hex.encode("utf-8"), hashlib.sha256).hexdigest()
        return {"algo": "hmac-sha256", "signature": sig, "public_key": None}

    if _HAVE_CRYPTO:
        key = _load_or_create_ed25519_key()
        sig = key.sign(bytes.fromhex(digest_hex)).hex()
        pub = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        ).hex()
        return {"algo": "ed25519", "signature": sig, "public_key": pub}

    return {"algo": "none", "signature": None, "public_key": None}


def build_proof(state: ResearchState) -> Dict[str, Any]:
    """Build a signed, tamper-evident proof bundle for the run (no I/O beyond key access)."""
    payload = canonical_payload(state)
    digest = content_hash(payload)
    signed = _sign(digest)
    return {
        "proof_version": PROOF_VERSION,
        "created_at": now_iso(),
        "session_id": state.get("session_id", ""),
        "content_hash": digest,
        "hash_algo": "sha256",
        "sig_algo": signed["algo"],
        "signature": signed["signature"],
        "public_key": signed["public_key"],
        "payload": payload,
        "ipfs": {"pinned": False},
        "anchor": {"anchored": False},
    }


def verify_proof(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute the hash and re-check the signature. Returns {"valid", "hash_ok", "sig_ok", "reason"}."""
    recomputed = content_hash(bundle.get("payload", {}))
    hash_ok = recomputed == bundle.get("content_hash")
    sig_ok, reason = _verify_sig(bundle) if hash_ok else (False, "content hash mismatch (tampered)")
    return {"valid": hash_ok and sig_ok, "hash_ok": hash_ok, "sig_ok": sig_ok,
            "reason": reason if not (hash_ok and sig_ok) else "ok"}


def _verify_sig(bundle: Dict[str, Any]) -> tuple[bool, str]:
    algo = bundle.get("sig_algo")
    sig = bundle.get("signature")
    digest = bundle.get("content_hash", "")
    if algo == "none" or sig is None:
        return True, "hash-only (unsigned)"
    if algo == "hmac-sha256":
        secret = get_proof_hmac_secret()
        if not secret:
            return False, "HMAC secret not available to verify"
        expected = hmac.new(secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
        return (hmac.compare_digest(expected, sig), "ok" if hmac.compare_digest(expected, sig) else "bad HMAC")
    if algo == "ed25519":
        if not _HAVE_CRYPTO:
            return False, "cryptography not installed to verify ed25519"
        try:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(bundle["public_key"]))
            pub.verify(bytes.fromhex(sig), bytes.fromhex(digest))
            return True, "ok"
        except Exception:
            return False, "bad ed25519 signature"
    return False, f"unknown signature algo: {algo}"


def _key_path() -> Path:
    return get_output_dir() / "keys" / "proof_ed25519.pem"


def _load_or_create_ed25519_key() -> "Ed25519PrivateKey":
    """Persist one ed25519 key per user so proofs share a stable public identity."""
    path = _key_path()
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    return key


def save_proof(bundle: Dict[str, Any], session_id: Optional[str] = None) -> str:
    """Write the proof bundle to the output dir and return its path."""
    sid = session_id or bundle.get("session_id") or "session"
    path = get_output_dir() / "proofs" / f"proof_{sid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
    return str(path)
