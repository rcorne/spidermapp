from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

CONFIG_PATH = Path.home() / ".spidermapp" / "connectors.json"

# Every external service Spidermapp can talk to. `field` is the credential the
# user pastes in Conectores; services marked needs_oauth need more than a key
# and stay informational until that flow is built.
@dataclass(frozen=True)
class ConnectorSpec:
    key: str
    label: str
    field_label: str
    help_url: str
    needs_oauth: bool = False


CONNECTORS: list[ConnectorSpec] = [
    ConnectorSpec("pagespeed", "Google PageSpeed Insights", "API key", "https://developers.google.com/speed/docs/insights/v5/get-started"),
    ConnectorSpec("openai", "OpenAI (ChatGPT)", "API key", "https://platform.openai.com/api-keys"),
    ConnectorSpec("anthropic", "Anthropic (Claude)", "API key", "https://console.anthropic.com/settings/keys"),
    ConnectorSpec("gemini", "Google Gemini", "API key", "https://aistudio.google.com/apikey"),
    ConnectorSpec("deepseek", "DeepSeek", "API key", "https://platform.deepseek.com/api_keys"),
    ConnectorSpec("perplexity", "Perplexity", "API key", "https://www.perplexity.ai/settings/api"),
    ConnectorSpec("ahrefs", "Ahrefs", "API token", "https://ahrefs.com/api"),
    ConnectorSpec("moz", "Moz", "API token", "https://moz.com/products/api"),
    ConnectorSpec("majestic", "Majestic", "API key", "https://majestic.com/support/api"),
    ConnectorSpec("ga4", "Google Analytics 4", "Ruta al JSON de service account", "https://developers.google.com/analytics/devguides/reporting/data/v1", needs_oauth=True),
    ConnectorSpec("search_console", "Google Search Console", "Ruta al JSON de credenciales OAuth", "https://developers.google.com/webmaster-tools", needs_oauth=True),
]


def load_config() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: dict[str, str]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    os.chmod(CONFIG_PATH, 0o600)


def get_key(name: str) -> str:
    return load_config().get(name, "").strip()


def is_configured(name: str) -> bool:
    return bool(get_key(name))


class ConnectorNotConfigured(Exception):
    pass


def _require(name: str) -> str:
    key = get_key(name)
    if not key:
        raise ConnectorNotConfigured(
            f"El conector '{name}' no tiene clave configurada. Ve al menú Conectores → Configurar APIs."
        )
    return key


# ---------------------------------------------------------------------------
# PageSpeed Insights (real, key-only API)
# ---------------------------------------------------------------------------

PAGESPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def run_pagespeed(url: str, strategy: str = "mobile", timeout: float = 60.0) -> dict:
    """Live PageSpeed Insights run. Returns {score, lcp_ms, cls, fcp_ms, tbt_ms}."""
    key = _require("pagespeed")
    response = httpx.get(
        PAGESPEED_ENDPOINT,
        params={"url": url, "key": key, "strategy": strategy, "category": "PERFORMANCE"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    lighthouse = data.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})

    def metric(audit_id: str) -> float | None:
        value = audits.get(audit_id, {}).get("numericValue")
        return float(value) if value is not None else None

    score = lighthouse.get("categories", {}).get("performance", {}).get("score")
    return {
        "score": round(score * 100) if score is not None else None,
        "lcp_ms": metric("largest-contentful-paint"),
        "cls": metric("cumulative-layout-shift"),
        "fcp_ms": metric("first-contentful-paint"),
        "tbt_ms": metric("total-blocking-time"),
    }


# ---------------------------------------------------------------------------
# LLM chat endpoints (key-only REST APIs) — used by llm_visibility
# ---------------------------------------------------------------------------

LLM_PROVIDERS = ["openai", "anthropic", "gemini", "deepseek", "perplexity"]

# Perplexity's "sonar" models are inherently grounded in live web search — that's
# the product's whole premise, unlike the other providers' plain chat completion
# endpoints, which answer only from trained (parametric) knowledge unless the
# caller wires up separate tool-calling. Used to tag raw responses honestly for
# the with/without-search comparison in brand_visibility.py, rather than faking
# a toggle the other providers don't really support here.
WEB_SEARCH_PROVIDERS = {"perplexity"}

_LLM_TIMEOUT = 60.0


def supports_web_search(provider: str) -> bool:
    return provider in WEB_SEARCH_PROVIDERS


def ask_llm(provider: str, prompt: str, temperature: float = 0.7) -> str:
    """Send one user prompt to the given provider and return the text answer.

    Each call is a clean, stateless session: no conversation history and no
    system prompt, by design — every call here is independent of any other.
    """
    key = _require(provider)

    if provider == "openai":
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 700,
                "temperature": temperature,
            },
            timeout=_LLM_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    if provider == "anthropic":
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 700,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=_LLM_TIMEOUT,
        )
        response.raise_for_status()
        blocks = response.json().get("content", [])
        return " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    if provider == "gemini":
        response = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            params={"key": key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature},
            },
            timeout=_LLM_TIMEOUT,
        )
        response.raise_for_status()
        candidates = response.json().get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return " ".join(p.get("text", "") for p in parts)

    if provider == "deepseek":
        response = httpx.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 700,
                "temperature": temperature,
            },
            timeout=_LLM_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    if provider == "perplexity":
        response = httpx.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 700,
                "temperature": temperature,
            },
            timeout=_LLM_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    raise ValueError(f"Proveedor LLM desconocido: {provider}")
