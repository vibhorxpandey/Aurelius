"""Optional IPFS pinning for Proof-of-Rigor bundles (Phase 3), via the Pinata pinning API.

Uses httpx (already a dependency) — no IPFS node required. When no ``PINATA_JWT`` is
configured, this is a graceful no-op: the proof stays local and the bundle records
``pinned: false``. Never raises into the pipeline.
"""
from __future__ import annotations

from typing import Any, Dict

import httpx

from ..config import get_pinata_jwt

_PINATA_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"


def pin_json(bundle: Dict[str, Any], *, timeout: float = 30.0) -> Dict[str, Any]:
    """Pin a JSON bundle to IPFS via Pinata. Returns {"pinned", "cid", "url", "note"}."""
    jwt = get_pinata_jwt()
    if not jwt:
        return {"pinned": False, "cid": None, "url": None,
                "note": "IPFS pinning skipped (no PINATA_JWT configured); proof stored locally."}
    try:
        headers = {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}
        body = {"pinataContent": bundle,
                "pinataMetadata": {"name": f"aurelius-proof-{bundle.get('session_id','')}"}}
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(_PINATA_URL, headers=headers, json=body)
        if resp.status_code != 200:
            return {"pinned": False, "cid": None, "url": None,
                    "note": f"Pinata HTTP {resp.status_code}: {resp.text[:200]}"}
        cid = resp.json().get("IpfsHash")
        return {"pinned": True, "cid": cid, "url": f"https://gateway.pinata.cloud/ipfs/{cid}",
                "note": "Pinned to IPFS via Pinata."}
    except (httpx.HTTPError, ValueError, KeyError) as e:
        return {"pinned": False, "cid": None, "url": None, "note": f"IPFS pinning failed: {e}"}
