"""Minimal multi-provider LLM client over plain REST (no vendor SDKs required).

Supports OpenAI (and OpenAI-compatible), Anthropic, and Google Gemini. Provider is
auto-detected from the model name unless given explicitly.
"""
from __future__ import annotations

from typing import Optional

import httpx

from ..config import get_llm_key


class LLMError(RuntimeError):
    pass


def detect_provider(model: str) -> str:
    m = model.lower()
    if m.startswith(("gpt", "o1", "o3", "o4", "chatgpt")):
        return "openai"
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gemini"):
        return "google"
    # Fallback: assume OpenAI-compatible endpoint.
    return "openai"


def complete(
    system: str,
    user: str,
    model: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: float = 120.0,
) -> str:
    """Return the model's text completion for a (system, user) prompt pair."""
    provider = (provider or detect_provider(model)).lower()
    key = api_key or get_llm_key(provider)
    if not key:
        raise LLMError(
            f"No API key found for provider '{provider}'. Set the appropriate environment "
            "variable (OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY) or pass api_key."
        )

    if provider == "openai":
        return _openai(system, user, model, key, temperature, max_tokens, timeout)
    if provider == "anthropic":
        return _anthropic(system, user, model, key, temperature, max_tokens, timeout)
    if provider == "google":
        return _google(system, user, model, key, temperature, max_tokens, timeout)
    raise LLMError(f"Unsupported provider: {provider}")


def _openai(system, user, model, key, temperature, max_tokens, timeout) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    # Newer OpenAI models reject custom temperature / use max_completion_tokens.
    if not model.lower().startswith(("gpt-5", "o1", "o3", "o4")):
        body["temperature"] = temperature
        body["max_tokens"] = max_tokens
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            raise LLMError(f"OpenAI HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
    return data["choices"][0]["message"]["content"]


def _anthropic(system, user, model, key, temperature, max_tokens, timeout) -> str:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            raise LLMError(f"Anthropic HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    return "".join(parts)


def _google(system, user, model, key, temperature, max_tokens, timeout) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, params={"key": key}, json=body)
        if resp.status_code != 200:
            raise LLMError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise LLMError(f"Unexpected Gemini response: {str(data)[:300]}")
