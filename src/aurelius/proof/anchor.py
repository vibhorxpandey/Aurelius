"""Optional blockchain anchoring for the Proof-of-Rigor content hash (Phase 3).

Two backends:
  * **local** (always on): append the content hash + timestamp to a local anchor log
    (`<output_dir>/anchors/anchor_log.jsonl`). This gives an ordered, append-only local
    record with zero cost or dependencies.
  * **chain** (opt-in): embed the hash in the data field of a 0-value self-transaction on an
    EVM chain (a classic "OP_RETURN-style" anchor — no smart contract needed). Requires the
    ``[chain]`` extra (``web3`` + ``eth-account``) and env config
    (``AURELIUS_CHAIN_RPC`` + ``AURELIUS_CHAIN_PRIVATE_KEY``, optional ``AURELIUS_CHAIN_ID``),
    plus a funded wallet for gas.

`web3` is imported lazily so it is never a hard dependency, and every failure path degrades
to the local anchor with an honest note rather than raising into the pipeline.

NOTE: the on-chain path sends a real, gas-costing transaction — it is left unexercised in
Aurelius's own tests (no wallet/gas in CI) and should be validated by the operator on a
testnet (e.g. Polygon Amoy) before mainnet use.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from ..config import get_chain_config, get_output_dir
from ..orchestration.state import now_iso


def _local_anchor(content_hash: str, session_id: str) -> Dict[str, Any]:
    path = get_output_dir() / "anchors" / "anchor_log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": now_iso(), "session_id": session_id, "content_hash": content_hash}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return {"backend": "local", "anchored": True, "log": str(path),
            "note": "Recorded in append-only local anchor log."}


def anchor_hash(content_hash: str, session_id: str = "") -> Dict[str, Any]:
    """Anchor a content hash. Always writes the local anchor; additionally anchors on-chain
    when configured. Returns a dict describing what happened (never raises)."""
    result = _local_anchor(content_hash, session_id)
    cfg = get_chain_config()
    if not (cfg["rpc"] and cfg["private_key"]):
        result["chain"] = {"anchored": False,
                           "note": "On-chain anchoring skipped (set AURELIUS_CHAIN_RPC + "
                                   "AURELIUS_CHAIN_PRIVATE_KEY and install the [chain] extra)."}
        return result
    result["chain"] = _chain_anchor(content_hash, cfg)
    result["anchored"] = result["anchored"] or result["chain"].get("anchored", False)
    return result


def _chain_anchor(content_hash: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Send a 0-value self-transaction embedding the hash in calldata. Lazy web3 import."""
    try:
        from web3 import Web3
        from eth_account import Account
    except Exception:
        return {"anchored": False,
                "note": "web3/eth-account not installed — run `pip install aurelius-mcp[chain]`."}
    try:
        w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
        acct = Account.from_key(cfg["private_key"])
        tx = {
            "from": acct.address,
            "to": acct.address,  # self-send; the payload is what matters
            "value": 0,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "data": "0x" + content_hash,
            "chainId": cfg["chain_id"] or w3.eth.chain_id,
        }
        gas = w3.eth.estimate_gas(tx)
        tx["gas"] = gas
        tx["maxFeePerGas"] = w3.eth.gas_price * 2
        tx["maxPriorityFeePerGas"] = w3.eth.max_priority_fee
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        return {"anchored": True, "backend": "evm", "tx_hash": tx_hash.hex(),
                "chain_id": tx["chainId"], "note": "Anchored on-chain (self-tx with hash in calldata)."}
    except Exception as e:  # RPC down, insufficient funds, bad key, etc.
        return {"anchored": False, "note": f"On-chain anchoring failed: {type(e).__name__}: {e}"}
