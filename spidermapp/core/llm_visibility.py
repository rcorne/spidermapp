from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from spidermapp.core import connectors
from spidermapp.core.url_utils import registrable_domain, strip_www

# How visible is this domain when someone asks an LLM the questions its
# pages are optimized for? For each configured provider we ask a handful of
# natural queries built from the site's own keywords and check whether the
# brand/domain shows up in the answer — the LLM-era equivalent of ranking.

MAX_QUERIES = 4

PROVIDER_LABELS = {
    "openai": "ChatGPT (OpenAI)",
    "anthropic": "Claude (Anthropic)",
    "gemini": "Gemini (Google)",
    "deepseek": "DeepSeek",
    "perplexity": "Perplexity",
}


@dataclass
class LlmQueryResult:
    provider: str
    query: str
    mentioned: bool
    answer_excerpt: str = ""
    error: str = ""


@dataclass
class LlmVisibilityReport:
    domain: str
    results: list[LlmQueryResult] = field(default_factory=list)
    providers_checked: list[str] = field(default_factory=list)
    providers_unconfigured: list[str] = field(default_factory=list)

    @property
    def mention_rate_by_provider(self) -> dict[str, float]:
        rates: dict[str, float] = {}
        for provider in self.providers_checked:
            provider_results = [r for r in self.results if r.provider == provider and not r.error]
            if provider_results:
                rates[provider] = sum(1 for r in provider_results if r.mentioned) / len(provider_results)
        return rates


def _brand_terms(seed_url: str) -> list[str]:
    """Ordered shortest-first so [0] is the bare brand name (e.g. 'cruzverde')."""
    domain = registrable_domain(seed_url)
    bare = strip_www(domain)
    brand = bare.split(".")[0]
    seen: list[str] = []
    for term in (brand.lower(), bare.lower(), domain.lower()):
        if len(term) >= 3 and term not in seen:
            seen.append(term)
    return seen


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def domain_mentioned(answer: str, seed_url: str) -> bool:
    haystack = _normalize(answer)
    for term in _brand_terms(seed_url):
        if re.search(rf"(?<![a-z0-9]){re.escape(_normalize(term))}(?![a-z0-9])", haystack):
            return True
    return False


def build_queries(site_keywords: list[str], seed_url: str, max_queries: int = MAX_QUERIES) -> list[str]:
    """Natural questions a user would ask an assistant, derived from the
    site's top on-page keywords. The domain itself is never included in the
    prompt — that would trivially bias the answer. Every query embeds a real
    topic term; there is no context-free fallback, since a question like
    "recommend something in this category" means nothing to the LLM if it
    was never told what the category is."""
    brand_terms = [_normalize(t) for t in _brand_terms(seed_url)]

    def strip_brand(term: str) -> str:
        words = [w for w in term.split() if _normalize(w) not in brand_terms]
        return " ".join(words).strip()

    queries: list[str] = []
    for kw in site_keywords:
        cleaned = strip_brand(kw)
        if not cleaned or len(cleaned) < 3:
            continue  # keyword was only the brand name itself; nothing left to ask about
        queries.append(f"¿Cuáles son los mejores sitios web o marcas para «{cleaned}»? Nombra varios.")
        if len(queries) >= max_queries:
            break
    return queries


def top_site_keywords(pages, limit: int = 6) -> list[str]:
    """Most repeated per-page keywords across the crawl (crude site topic
    model). Thin crawls (few pages, or every page's on-page keyword signal
    empty) fall back to the homepage's own title/H1/meta description, so
    there is always a concrete topic to ask an LLM about instead of a
    context-free question."""
    from collections import Counter

    from spidermapp.core import keywords as keywords_mod

    counts: Counter = Counter()
    for page in pages:
        for kw in page.keywords:
            counts[kw] += 1
    top = [kw for kw, _ in counts.most_common(limit)]
    if top or not pages:
        return top

    homepage = next((p for p in pages if getattr(p, "depth", None) == 0), pages[0])
    return keywords_mod.extract_keywords(homepage.title, homepage.h1, homepage.meta_description, "", top_n=limit)


def run_visibility_check(seed_url: str, site_keywords: list[str]) -> LlmVisibilityReport:
    """Query every configured LLM provider. Network I/O — run off the UI thread."""
    report = LlmVisibilityReport(domain=registrable_domain(seed_url))
    queries = build_queries(site_keywords, seed_url)

    for provider in connectors.LLM_PROVIDERS:
        if not connectors.is_configured(provider):
            report.providers_unconfigured.append(provider)
            continue
        report.providers_checked.append(provider)
        for query in queries:
            try:
                answer = connectors.ask_llm(provider, query)
            except Exception as exc:  # noqa: BLE001 - surfaced per-row in the UI
                report.results.append(LlmQueryResult(provider=provider, query=query, mentioned=False, error=str(exc)))
                continue
            report.results.append(
                LlmQueryResult(
                    provider=provider,
                    query=query,
                    mentioned=domain_mentioned(answer, seed_url),
                    answer_excerpt=answer[:300],
                )
            )
    return report
