"""NVIDIA NIM chat client (OpenAI-compatible API at integrate.api.nvidia.com)."""

import json
import logging
import os
import re
import time

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://integrate.api.nvidia.com/v1"

# Tried in order; the first one available on your key is used.
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

_chosen_model: str | None = None


def _headers() -> dict:
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY is not set")
    return {"Authorization": f"Bearer {key}", "Accept": "application/json"}


def _candidate_models() -> list[str]:
    """Preferred models that this key can see, in preference order."""
    if forced := os.environ.get("NVIDIA_MODEL"):
        return [forced]
    try:
        resp = httpx.get(f"{BASE_URL}/models", headers=_headers(), timeout=30)
        resp.raise_for_status()
        available = {m["id"] for m in resp.json().get("data", [])}
        found = [m for m in PREFERRED_MODELS if m in available]
        if found:
            return found
        log.warning("None of the preferred models are listed; trying them anyway")
    except Exception as exc:
        log.warning("Could not list NVIDIA models (%s); trying preferred list", exc)
    return PREFERRED_MODELS


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
            try:
                resp = httpx.post(
                    f"{BASE_URL}/chat/completions",
                    headers=_headers(),
                    json={"model": model, "messages": messages, "temperature": temperature,
                          "max_tokens": max(max_tokens, 8000), **extra},
                    timeout=300,
                )
                if resp.status_code == 429:  # rate limited - wait and retry
                    last_error = f"{model}: rate limited (429)"
                    log.warning(last_error)
                    time.sleep(20 * (attempt + 1))
                    continue
                if resp.status_code == 400 and extra:  # model rejects the no-thinking option
                    log.warning("%s rejected thinking option, retrying without it", model)
                    extra = {}
                    continue
                if resp.status_code >= 400:
                    last_error = f"{model}: HTTP {resp.status_code} {resp.text[:300]}"
                    log.warning(last_error)
                    break
                choice = resp.json()["choices"][0]
                msg = choice.get("message") or {}
                text = msg.get("content") or ""
                # Reasoning models may include their thinking - drop it.
                text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
                if not text and "{" in (msg.get("reasoning_content") or ""):
                    text = msg["reasoning_content"]  # answer ended up in the reasoning
                if text:
                    if _chosen_model != model:
                        log.info("Using NVIDIA model: %s", model)
                    _chosen_model = model
                    return text
                last_error = f"{model}: empty reply (finish_reason={choice.get('finish_reason')})"
                log.warning(last_error)
                break
            except Exception as exc:
                last_error = f"{model}: {exc}"
                log.warning("Model %s failed (attempt %d): %s", model, attempt + 1, exc)
                break
        _chosen_model = None
    raise RuntimeError(f"All NVIDIA models failed. Last error: {last_error}")


def chat_json(prompt: str, system: str = "", **kwargs) -> dict:
    """Chat and parse a JSON object out of the reply."""
    text = chat(prompt + "\n\nReply with ONLY a JSON object, no other text.", system, **kwargs)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError(f"No JSON in model reply: {text[:300]}")
    return json.loads(match.group(0))
