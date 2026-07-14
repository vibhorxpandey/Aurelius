"""Phase 3 — cryptographic Proof-of-Rigor, IPFS pinning, and blockchain anchoring.

Core (``rigor``) is dependency-free and always available: content hash + signature + verify.
``ipfs`` (Pinata over httpx) and ``anchor`` (local log + optional lazy-`web3` on-chain) are
opt-in and degrade gracefully when unconfigured."""
from .rigor import build_proof, content_hash, save_proof, verify_proof

__all__ = ["build_proof", "content_hash", "verify_proof", "save_proof"]
