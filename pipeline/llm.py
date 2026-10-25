"""NVIDIA NIM chat client (OpenAI-compatible API at integrate.api.nvidia.com)."""

import json
import logging
import os
import re
import time

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://integrate.api.nvidia.com/v1"

# Tried in order; models your key lists come first, the rest are tried after.
# Set NVIDIA_MODEL in env to force a specific model.
PREFERRED_MODELS = [
    "deepseek-ai/deepseek-v4.1-flash",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "deepseek-ai/deepseek-v3.2",
    "deepseek-ai/deepseek-v3.1",
    "qwen/qwen3-235b-a22b",
    "moonshotai/kimi-k2-instruct",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-70b-instruct",
]

# Give up on a model if it sends nothing for this long, or takes longer than this in total.
SILENCE_TIMEOUT = 90
TOTAL_TIMEOUT = 600

_chosen_model: str | None = None


class _ModelError(Exception):
    pass


def _headers() -> dict:
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY is not set")
    return {"Authorization": f"Bearer {key}", "Accept": "application/json"}


def _candidate_models() -> list[str]:
    """Preferred models in order, the ones this key lists first."""
    if forced := os.environ.get("NVIDIA_MODEL"):
        return [forced]
    try:
        resp = httpx.get(f"{BASE_URL}/models", headers=_headers(), timeout=30)
        resp.raise_for_status()
        available = {m["id"] for m in resp.json().get("data", [])}
        listed = [m for m in PREFERRED_MODELS if m in available]
        return listed + [m for m in PREFERRED_MODELS if m not in available]
    except Exception as exc:
        log.warning("Could not list NVIDIA models (%s); trying preferred list", exc)
    return PREFERRED_MODELS


def _stream_reply(model: str, payload: dict) -> tuple[str, str]:
    """Stream one completion. Returns (content, reasoning). Raises _ModelError on HTTP errors."""
    content, reasoning = [], []
    deadline = time.monotonic() + TOTAL_TIMEOUT
    timeout = httpx.Timeout(SILENCE_TIMEOUT, connect=30)
    with httpx.stream("POST", f"{BASE_URL}/chat/completions", headers=_headers(),
                      json={**payload, "model": model, "stream": True}, timeout=timeout) as resp:
        if resp.status_code >= 400:
            resp.read()
            raise _ModelError(f"HTTP {resp.status_code} {resp.text[:300]}")
        for line in resp.iter_lines():
            if time.monotonic() > deadline:
                raise _ModelError(f"no complete answer within {TOTAL_TIMEOUT}s")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            for choice in json.loads(data).get("choices", []):
                delta = choice.get("delta") or {}
                content.append(delta.get("content") or "")
                reasoning.append(delta.get("reasoning_content") or "")
    return "".join(content), "".join(reasoning)


def chat(prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 4000) -> str:
    """Send one chat request. Falls back to the next model on errors."""
    global _chosen_model
    models = [_chosen_model] if _chosen_model else _candidate_models()

    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    # Reasoning models can spend the whole budget "thinking", so allow plenty
    # of tokens and ask them not to think (ignored by models without the option).
    no_thinking = {"chat_template_kwargs": {"thinking": False, "enable_thinking": False}}
    last_error = None
    for model in models:
        extra = dict(no_thinking)
        for attempt in range(4):
            payload = {"messages": messages, "temperature": temperature,
                       "max_tokens": max(max_tokens, 8000), **extra}
            try:
                text, reasoning = _stream_reply(model, payload)
            except _ModelError as exc:
                msg = str(exc)
                if msg.startswith("HTTP 429"):  # rate limited - wait and retry
                    last_error = f"{model}: rate limited (429)"
                    log.warning(last_error)
                    time.sleep(20 * (attempt + 1))
                    continue
                if msg.startswith("HTTP 400") and extra:  # rejects the no-thinking option
                    log.warning("%s rejected thinking option, retrying without it", model)
                    extra = {}
                    continue
                last_error = f"{model}: {msg}"
                log.warning(last_error)
                break
            except Exception as exc:  # timeouts, connection errors
                last_error = f"{model}: {type(exc).__name__}: {exc}"
                log.warning(last_error)
                break

            # Reasoning models may include their thinking - drop it.
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
            if not text and "{" in reasoning:
                text = reasoning  # answer ended up in the reasoning
            if text:
                if _chosen_model != model:
                    log.info("Using NVIDIA model: %s", model)
                _chosen_model = model
                return text
            last_error = f"{model}: empty reply"
            log.warning(last_error)
            break
        _chosen_model = None
    raise RuntimeError(f"All NVIDIA models failed. Last error: {last_error}")


def chat_json(prompt: str, system: str = "", **kwargs) -> dict:
    """Chat and parse a JSON object out of the reply. Asks once more if the reply is broken."""
    ask = prompt + "\n\nReply with ONLY a JSON object, no other text."
    for attempt in range(2):
        text = chat(ask, system, **kwargs)
        match = re.search(r"\{.*\}", text, flags=re.S)
        try:
            if not match:
                raise ValueError("no JSON object found")
            # strict=False allows raw line breaks inside strings (common in scripts).
            return json.loads(match.group(0), strict=False)
        except ValueError as exc:
            log.warning("Bad JSON from model (%s): %s", exc, text[:200])
    raise ValueError(f"Model did not return valid JSON: {text[:300]}")
