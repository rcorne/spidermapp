from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass, field

import httpx

from spidermapp.core.models import PageResult
from spidermapp.core.url_utils import normalize_url, registrable_domain, strip_www

# How ready is this site to be found, understood, and cited by AI systems —
# using only public, keyless signals. No API key required: this is what
# GPTBot/ClaudeBot/etc. themselves would see, plus what's already public
# knowledge about the brand.

AI_BOTS: list[tuple[str, str]] = [
    ("GPTBot", "OpenAI (entrenamiento de ChatGPT)"),
    ("ChatGPT-User", "OpenAI (navegación en vivo de ChatGPT)"),
    ("OAI-SearchBot", "OpenAI (búsqueda)"),
    ("ClaudeBot", "Anthropic (Claude)"),
    ("anthropic-ai", "Anthropic (Claude, legado)"),
    ("Google-Extended", "Google (Gemini / AI Overviews)"),
    ("PerplexityBot", "Perplexity"),
    ("CCBot", "Common Crawl (fuente de entrenamiento de muchos LLMs)"),
    ("Applebot-Extended", "Apple Intelligence"),
    ("Bytespider", "ByteDance / TikTok"),
    ("Amazonbot", "Amazon"),
]

_WIKIPEDIA_LANGS = ("es", "en")
_HTTP_TIMEOUT = 10.0


@dataclass
class BotAccess:
    bot: str
    description: str
    allowed: bool


@dataclass
class AiVisibilityReport:
    domain: str
    robots_found: bool = False
    bot_access: list[BotAccess] = field(default_factory=list)
    llms_txt_found: bool = False
    llms_txt_url: str = ""
    structured_data_pages: int = 0
    structured_data_total: int = 0
    structured_data_types: list[str] = field(default_factory=list)
    meta_description_pages: int = 0
    meta_description_total: int = 0
    wikipedia_found: bool = False
    wikipedia_title: str = ""
    wikipedia_url: str = ""
    error: str = ""

    @property
    def blocked_bots(self) -> list[BotAccess]:
        return [b for b in self.bot_access if not b.allowed]

    @property
    def structured_data_ratio(self) -> float:
        return self.structured_data_pages / self.structured_data_total if self.structured_data_total else 0.0

    @property
    def meta_description_ratio(self) -> float:
        return self.meta_description_pages / self.meta_description_total if self.meta_description_total else 0.0

    @property
    def readiness_score(self) -> int:
        """0-100 composite of every public signal below. Not a guarantee an
        LLM will cite the site — just whether the door is open for it to."""
        total_bots = len(self.bot_access) or 1
        points = 40 * (1 - len(self.blocked_bots) / total_bots)
        points += 20 if self.llms_txt_found else 0
        points += 20 * self.structured_data_ratio
        points += 10 * self.meta_description_ratio
        points += 10 if self.wikipedia_found else 0
        return round(min(100, points))


def _check_robots_ai_bots(client: httpx.Client, seed_url: str) -> tuple[bool, list[BotAccess]]:
    robots_url = normalize_url("/robots.txt", base=seed_url)
    try:
        response = client.get(robots_url, timeout=_HTTP_TIMEOUT)
    except httpx.RequestError:
        return False, [BotAccess(bot, desc, True) for bot, desc in AI_BOTS]
    if response.status_code != 200:
        return False, [BotAccess(bot, desc, True) for bot, desc in AI_BOTS]

    parser = urllib.robotparser.RobotFileParser()
    parser.parse(response.text.splitlines())
    access = [BotAccess(bot, desc, parser.can_fetch(bot, seed_url)) for bot, desc in AI_BOTS]
    return True, access


def _check_llms_txt(client: httpx.Client, seed_url: str) -> tuple[bool, str]:
    url = normalize_url("/llms.txt", base=seed_url)
    try:
        response = client.get(url, timeout=_HTTP_TIMEOUT)
        return response.status_code == 200, url
    except httpx.RequestError:
        return False, url


def _check_wikipedia(brand: str) -> tuple[bool, str, str]:
    if not brand:
        return False, "", ""
    for lang in _WIKIPEDIA_LANGS:
        try:
            response = httpx.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={"action": "opensearch", "search": brand, "limit": 1, "namespace": 0, "format": "json"},
                timeout=_HTTP_TIMEOUT,
                headers={"User-Agent": "PidgeBot/0.1 (+SEO audit tool; public data only)"},
            )
            response.raise_for_status()
            data = response.json()
            titles, urls = data[1], data[3]
            if titles and urls:
                return True, titles[0], urls[0]
        except (httpx.RequestError, IndexError, ValueError, KeyError):
            continue
    return False, "", ""


def analyze(seed_url: str, pages: list[PageResult]) -> AiVisibilityReport:
    """Blocking network I/O — run this off the UI thread."""
    domain = registrable_domain(seed_url)
    brand = strip_www(domain).split(".")[0]
    report = AiVisibilityReport(domain=domain)

    try:
        with httpx.Client(follow_redirects=True) as client:
            report.robots_found, report.bot_access = _check_robots_ai_bots(client, seed_url)
            report.llms_txt_found, report.llms_txt_url = _check_llms_txt(client, seed_url)
    except Exception as exc:  # noqa: BLE001 - surfaced in the report, not fatal
        report.error = str(exc)

    crawled = [p for p in pages if p.status_code == 200]
    report.structured_data_total = len(crawled)
    report.structured_data_pages = sum(1 for p in crawled if p.json_ld_types)
    types: set[str] = set()
    for page in crawled:
        types.update(page.json_ld_types)
    report.structured_data_types = sorted(types)

    report.meta_description_total = len(crawled)
    report.meta_description_pages = sum(1 for p in crawled if p.meta_description)

    report.wikipedia_found, report.wikipedia_title, report.wikipedia_url = _check_wikipedia(brand)

    return report
