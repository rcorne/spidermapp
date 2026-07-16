from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from spidermapp.core import connectors
from spidermapp.core.llm_visibility import PROVIDER_LABELS

# Analizador de visibilidad de marca/dominio en LLMs.
#
# Principio de diseño central: el LLM se trata como caja negra. Medimos sus
# respuestas de forma repetida y estadística (tasa de mención, posición,
# share of voice, framing). Nunca le pedimos al modelo que explique por qué
# mencionó (o no) una marca — esas explicaciones introspectivas son
# racionalizaciones no confiables, no datos. La única llamada secundaria al
# LLM (classify_framing) le pide clasificar el tono de un texto ya generado,
# no que juzgue su propio proceso de generación.

STORAGE_DIR = Path.home() / ".spidermapp" / "brand_visibility"

INTENT_TYPES = [
    "recomendacion_abierta",
    "recomendacion_caso_de_uso",
    "comparativa",
    "transaccional",
    "informacional",
]

INTENT_LABELS = {
    "recomendacion_abierta": "Recomendación abierta",
    "recomendacion_caso_de_uso": "Recomendación con caso de uso",
    "comparativa": "Comparativa",
    "transaccional": "Transaccional",
    "informacional": "Informacional",
}

FRAMINGS = ["positivo", "neutro", "negativo", "con_reservas"]

FRAMING_LABELS = {
    "positivo": "Positivo",
    "neutro": "Neutro",
    "negativo": "Negativo",
    "con_reservas": "Con reservas",
}

DEFAULT_TEMPERATURE = 0.7
DEFAULT_REPETITIONS = 10
PARAPHRASES_PER_INTENT = 4


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Brand:
    name: str
    domain: str = ""
    aliases: list[str] = field(default_factory=list)

    def all_terms(self) -> list[str]:
        terms = [self.name, *self.aliases]
        if self.domain:
            terms.append(self.domain)
        return [t for t in terms if t.strip()]


@dataclass
class BrandVisibilityConfig:
    target: Brand
    competitors: list[Brand]
    category: str
    market: str
    providers: list[str]
    repetitions: int = DEFAULT_REPETITIONS
    temperature: float = DEFAULT_TEMPERATURE
    paraphrase_provider: str = ""

    def all_brands(self) -> list[Brand]:
        return [self.target, *self.competitors]


@dataclass
class QueryTemplate:
    intent: str
    text: str


@dataclass
class RawResponse:
    provider: str
    query: str
    intent: str
    repetition: int
    web_search: bool
    temperature: float
    text: str = ""
    error: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class Mention:
    brand: str
    position: int  # 1-based rank of first mention within the response
    is_domain_citation: bool = False


@dataclass
class ResponseAnalysis:
    response: RawResponse
    mentions: list[Mention] = field(default_factory=list)
    framing: dict[str, str] = field(default_factory=dict)  # brand name -> framing


@dataclass
class BrandStats:
    brand: str
    is_target: bool
    responses: int = 0
    mention_rate: float = 0.0
    avg_position: float | None = None
    share_of_voice: float = 0.0
    domain_citation_rate: float | None = None
    framing_distribution: dict[str, float] = field(default_factory=dict)


@dataclass
class BrandVisibilityReport:
    config: BrandVisibilityConfig
    created_at: float
    analyses: list[ResponseAnalysis] = field(default_factory=list)

    @property
    def errors(self) -> list[RawResponse]:
        return [a.response for a in self.analyses if a.response.error]

    @property
    def providers_used(self) -> list[str]:
        seen: list[str] = []
        for a in self.analyses:
            if a.response.provider not in seen:
                seen.append(a.response.provider)
        return seen


# ---------------------------------------------------------------------------
# Mechanical mention detection (no LLM involved — regex over raw text)
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def detect_mentions(text: str, brands: list[Brand]) -> list[Mention]:
    """Order of first appearance = position. Purely mechanical string
    matching — this is the measurement step, never an LLM judgment call."""
    normalized = _normalize(text)
    hits: list[tuple[int, str, bool]] = []
    for brand in brands:
        best_offset: int | None = None
        for term in brand.all_terms():
            term_norm = _normalize(term)
            if not term_norm:
                continue
            match = re.search(rf"(?<![a-z0-9]){re.escape(term_norm)}(?![a-z0-9])", normalized)
            if match and (best_offset is None or match.start() < best_offset):
                best_offset = match.start()
        if best_offset is not None:
            is_domain = bool(brand.domain) and _normalize(brand.domain) in normalized
            hits.append((best_offset, brand.name, is_domain))
    hits.sort(key=lambda h: h[0])
    return [Mention(brand=name, position=i + 1, is_domain_citation=is_domain) for i, (_, name, is_domain) in enumerate(hits)]


# ---------------------------------------------------------------------------
# Framing classification — a secondary, independent LLM call with a fixed
# rubric. This classifies the tone of already-generated text; it never asks
# the model to explain or justify what it wrote.
# ---------------------------------------------------------------------------

FRAMING_RUBRIC = """Vas a clasificar el tono con el que un texto menciona una marca específica. \
Responde ÚNICAMENTE con una palabra de esta lista, sin explicación ni puntuación: \
positivo, neutro, negativo, con_reservas.

Definiciones:
- positivo: la marca se presenta como buena opción, recomendada o destacada favorablemente.
- neutro: se menciona la marca sin juicio de valor claro (ej. solo nombrarla en una lista).
- negativo: se menciona la marca de forma desfavorable o como opción a evitar.
- con_reservas: se menciona positivamente pero con advertencias, condiciones o matices relevantes.

Marca a evaluar: "{brand}"

Texto:
\"\"\"{text}\"\"\"

Responde solo con una palabra: positivo, neutro, negativo o con_reservas."""


def classify_framing(provider: str, brand: str, text: str) -> str:
    prompt = FRAMING_RUBRIC.format(brand=brand, text=text[:2000])
    try:
        answer = connectors.ask_llm(provider, prompt, temperature=0.0)
    except Exception:
        return "neutro"
    normalized = _normalize(answer.strip())
    for framing in FRAMINGS:
        if framing in normalized:
            return framing
    return "neutro"


def analyze_response(config: BrandVisibilityConfig, response: RawResponse, classify: bool = True) -> ResponseAnalysis:
    analysis = ResponseAnalysis(response=response)
    if response.error or not response.text:
        return analysis
    analysis.mentions = detect_mentions(response.text, config.all_brands())
    if classify:
        for mention in analysis.mentions:
            analysis.framing[mention.brand] = classify_framing(response.provider, mention.brand, response.text)
    return analysis


# ---------------------------------------------------------------------------
# Query battery generation — one LLM call asks for paraphrased user-language
# queries across the 5 fixed intent types. This is generation, not
# measurement, so it is not subject to the black-box principle.
# ---------------------------------------------------------------------------

BATTERY_PROMPT = """Genera variaciones de preguntas que una persona real escribiría en un buscador \
o asistente de IA, sobre la categoría "{category}" en el mercado "{market}".

Necesito {n} paráfrasis distintas para cada uno de estos 5 tipos de intención, con lenguaje \
natural y variado (evita repetir la misma estructura de frase):

1. recomendacion_abierta: pregunta abierta pidiendo las mejores opciones de la categoría.
2. recomendacion_caso_de_uso: pregunta pidiendo una recomendación para una situación o necesidad \
específica dentro de la categoría.
3. comparativa: pregunta pidiendo comparar las principales opciones.
4. transaccional: pregunta con intención de compra o contratación inmediata.
5. informacional: pregunta sobre qué considerar al elegir dentro de esta categoría.

Responde ÚNICAMENTE con JSON válido, sin texto adicional ni bloques de código, con esta forma \
exacta:
{{"recomendacion_abierta": ["...", "..."], "recomendacion_caso_de_uso": ["...", "..."], \
"comparativa": ["...", "..."], "transaccional": ["...", "..."], "informacional": ["...", "..."]}}"""


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?|```$", "", cleaned, flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


def generate_query_battery(
    category: str, market: str, provider: str, n: int = PARAPHRASES_PER_INTENT
) -> list[QueryTemplate]:
    prompt = BATTERY_PROMPT.format(category=category, market=market, n=n)
    answer = connectors.ask_llm(provider, prompt, temperature=0.9)
    try:
        data = _extract_json(answer)
    except (json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f"No se pudo interpretar la batería de consultas generada: {exc}") from exc

    templates: list[QueryTemplate] = []
    for intent in INTENT_TYPES:
        for text in data.get(intent, [])[:n]:
            text = str(text).strip()
            if text:
                templates.append(QueryTemplate(intent=intent, text=text))
    if not templates:
        raise ValueError("La batería de consultas generada llegó vacía.")
    return templates


# ---------------------------------------------------------------------------
# Execution — clean-session calls, fixed temperature, rate-limit backoff,
# raw responses handed to the caller (persisted) before any parsing.
# ---------------------------------------------------------------------------


def _call_with_retry(
    provider: str,
    query: QueryTemplate,
    repetition: int,
    web_search: bool,
    temperature: float,
    max_retries: int = 3,
    base_delay: float = 1.5,
) -> RawResponse:
    delay = base_delay
    last_error = ""
    for attempt in range(max_retries):
        try:
            text = connectors.ask_llm(provider, query.text, temperature=temperature)
            return RawResponse(
                provider=provider,
                query=query.text,
                intent=query.intent,
                repetition=repetition,
                web_search=web_search,
                temperature=temperature,
                text=text,
            )
        except Exception as exc:  # noqa: BLE001 - retried, then recorded on the raw response
            last_error = str(exc)
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
    return RawResponse(
        provider=provider,
        query=query.text,
        intent=query.intent,
        repetition=repetition,
        web_search=web_search,
        temperature=temperature,
        error=last_error,
    )


def run_battery(
    config: BrandVisibilityConfig,
    queries: list[QueryTemplate],
    on_response=None,
    request_delay: float = 0.3,
) -> list[RawResponse]:
    """Executes every query N times per configured model. Each call is a
    fresh, stateless session (connectors.ask_llm holds no history and sends
    no system prompt), so there is nothing to reset between repetitions."""
    responses: list[RawResponse] = []
    for provider in config.providers:
        web_search = connectors.supports_web_search(provider)
        for query in queries:
            for rep in range(config.repetitions):
                raw = _call_with_retry(provider, query, rep, web_search, config.temperature)
                responses.append(raw)
                if on_response:
                    on_response(raw)
                if request_delay:
                    time.sleep(request_delay)
    return responses


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def compute_brand_stats(analyses: list[ResponseAnalysis], config: BrandVisibilityConfig) -> list[BrandStats]:
    total = len(analyses)
    if total == 0:
        return []

    total_mentions_all_brands = sum(len(a.mentions) for a in analyses)
    web_search_analyses = [a for a in analyses if a.response.web_search]

    stats: list[BrandStats] = []
    for brand in config.all_brands():
        mention_analyses = [a for a in analyses if any(m.brand == brand.name for m in a.mentions)]
        positions = [next(m.position for m in a.mentions if m.brand == brand.name) for a in mention_analyses]
        brand_mention_count = sum(1 for a in analyses for m in a.mentions if m.brand == brand.name)

        domain_citation_rate = None
        if web_search_analyses:
            citations = sum(
                1
                for a in web_search_analyses
                if any(m.brand == brand.name and m.is_domain_citation for m in a.mentions)
            )
            domain_citation_rate = citations / len(web_search_analyses)

        framings = [a.framing.get(brand.name) for a in mention_analyses if a.framing.get(brand.name)]
        distribution = {f: (framings.count(f) / len(framings) if framings else 0.0) for f in FRAMINGS}

        stats.append(
            BrandStats(
                brand=brand.name,
                is_target=(brand.name == config.target.name),
                responses=total,
                mention_rate=len(mention_analyses) / total,
                avg_position=(sum(positions) / len(positions)) if positions else None,
                share_of_voice=(brand_mention_count / total_mentions_all_brands) if total_mentions_all_brands else 0.0,
                domain_citation_rate=domain_citation_rate,
                framing_distribution=distribution,
            )
        )
    return stats


def group_by(analyses: list[ResponseAnalysis], key) -> dict:
    groups: dict = {}
    for a in analyses:
        groups.setdefault(key(a), []).append(a)
    return groups


def stats_by_provider(analyses: list[ResponseAnalysis], config: BrandVisibilityConfig) -> dict[str, list[BrandStats]]:
    groups = group_by(analyses, lambda a: a.response.provider)
    return {provider: compute_brand_stats(items, config) for provider, items in groups.items()}


def stats_by_intent(analyses: list[ResponseAnalysis], config: BrandVisibilityConfig) -> dict[str, list[BrandStats]]:
    groups = group_by(analyses, lambda a: a.response.intent)
    return {intent: compute_brand_stats(items, config) for intent, items in groups.items()}


# ---------------------------------------------------------------------------
# Persistence — one JSON file per run, under a per-brand directory, following
# the same convention as core/history.py. Raw responses are stored verbatim
# alongside the derived analysis so parsing can be redone without re-querying
# the models. Filenames are millisecond timestamps, enabling longitudinal
# comparison by listing a brand's directory in order.
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "marca"


def _config_to_dict(config: BrandVisibilityConfig) -> dict:
    return {
        "target": {"name": config.target.name, "domain": config.target.domain, "aliases": config.target.aliases},
        "competitors": [{"name": b.name, "domain": b.domain, "aliases": b.aliases} for b in config.competitors],
        "category": config.category,
        "market": config.market,
        "providers": config.providers,
        "repetitions": config.repetitions,
        "temperature": config.temperature,
        "paraphrase_provider": config.paraphrase_provider,
    }


def _config_from_dict(data: dict) -> BrandVisibilityConfig:
    target = Brand(**data["target"])
    competitors = [Brand(**c) for c in data.get("competitors", [])]
    return BrandVisibilityConfig(
        target=target,
        competitors=competitors,
        category=data.get("category", ""),
        market=data.get("market", ""),
        providers=data.get("providers", []),
        repetitions=data.get("repetitions", DEFAULT_REPETITIONS),
        temperature=data.get("temperature", DEFAULT_TEMPERATURE),
        paraphrase_provider=data.get("paraphrase_provider", ""),
    )


def _analysis_to_dict(a: ResponseAnalysis) -> dict:
    r = a.response
    return {
        "response": {
            "provider": r.provider,
            "query": r.query,
            "intent": r.intent,
            "repetition": r.repetition,
            "web_search": r.web_search,
            "temperature": r.temperature,
            "text": r.text,
            "error": r.error,
            "timestamp": r.timestamp,
        },
        "mentions": [{"brand": m.brand, "position": m.position, "is_domain_citation": m.is_domain_citation} for m in a.mentions],
        "framing": a.framing,
    }


def _analysis_from_dict(data: dict) -> ResponseAnalysis:
    r = data["response"]
    response = RawResponse(
        provider=r["provider"],
        query=r["query"],
        intent=r["intent"],
        repetition=r["repetition"],
        web_search=r["web_search"],
        temperature=r["temperature"],
        text=r.get("text", ""),
        error=r.get("error", ""),
        timestamp=r.get("timestamp", 0.0),
    )
    mentions = [Mention(brand=m["brand"], position=m["position"], is_domain_citation=m["is_domain_citation"]) for m in data.get("mentions", [])]
    return ResponseAnalysis(response=response, mentions=mentions, framing=data.get("framing", {}))


def save_run(report: BrandVisibilityReport, storage_dir: Path = STORAGE_DIR) -> Path:
    brand_dir = storage_dir / _slug(report.config.target.name)
    brand_dir.mkdir(parents=True, exist_ok=True)
    path = brand_dir / f"{int(report.created_at * 1000)}.json"
    payload = {
        "created_at": report.created_at,
        "config": _config_to_dict(report.config),
        "analyses": [_analysis_to_dict(a) for a in report.analyses],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return path


def list_runs(target_brand_name: str, storage_dir: Path = STORAGE_DIR) -> list[Path]:
    brand_dir = storage_dir / _slug(target_brand_name)
    if not brand_dir.exists():
        return []
    return sorted(brand_dir.glob("*.json"))


def load_run(path: Path) -> BrandVisibilityReport:
    data = json.loads(path.read_text())
    config = _config_from_dict(data["config"])
    analyses = [_analysis_from_dict(a) for a in data.get("analyses", [])]
    return BrandVisibilityReport(config=config, created_at=data["created_at"], analyses=analyses)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_csv(report: BrandVisibilityReport, path: Path) -> None:
    import csv

    by_provider_intent = group_by(report.analyses, lambda a: (a.response.provider, a.response.intent))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "modelo",
                "tipo_intent",
                "marca",
                "es_objetivo",
                "respuestas",
                "tasa_mencion",
                "posicion_promedio",
                "share_of_voice",
                "tasa_cita_dominio",
                *[f"framing_{f}" for f in FRAMINGS],
            ]
        )
        for (provider, intent), items in sorted(by_provider_intent.items()):
            for s in compute_brand_stats(items, report.config):
                writer.writerow(
                    [
                        PROVIDER_LABELS.get(provider, provider),
                        INTENT_LABELS.get(intent, intent),
                        s.brand,
                        "sí" if s.is_target else "no",
                        s.responses,
                        f"{s.mention_rate:.3f}",
                        f"{s.avg_position:.2f}" if s.avg_position is not None else "",
                        f"{s.share_of_voice:.3f}",
                        f"{s.domain_citation_rate:.3f}" if s.domain_citation_rate is not None else "",
                        *[f"{s.framing_distribution.get(f, 0.0):.3f}" for f in FRAMINGS],
                    ]
                )


_HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Visibilidad de marca en LLMs — {target}</title>
<style>
body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 32px; color: #1F2937; background: #F9FAFB; }}
h1 {{ font-size: 22px; margin-bottom: 4px; }}
h2 {{ font-size: 16px; margin-top: 32px; color: #374151; }}
.meta {{ color: #6B7280; font-size: 13px; margin-bottom: 24px; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.06); }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #E5E7EB; font-size: 13px; }}
th {{ background: #F3F4F6; font-weight: 600; }}
tr.target td {{ font-weight: 700; background: #F5F3FF; }}
.bar-track {{ background: #E5E7EB; border-radius: 4px; height: 10px; width: 160px; overflow: hidden; }}
.bar-fill {{ background: #7C3AED; height: 100%; }}
.bar-fill.competitor {{ background: #9CA3AF; }}
.bar-row {{ display: flex; align-items: center; gap: 8px; }}
</style>
</head>
<body>
<h1>Visibilidad de marca en LLMs — {target}</h1>
<p class="meta">Categoría: {category} · Mercado: {market} · Corrida: {created_at} · Respuestas analizadas: {n_responses}</p>

<h2>Comparativa general: marca vs. competidores</h2>
{overall_table}

<h2>Por modelo</h2>
{by_provider_tables}

<h2>Por tipo de intención</h2>
{by_intent_tables}

<p class="meta">Generado por Spidermapp. Metodología: caja negra — muestreo repetido y estadístico de respuestas de LLMs, sin preguntar al modelo por qué mencionó una marca.</p>
</body>
</html>"""


def _stats_table_html(stats: list[BrandStats]) -> str:
    max_rate = max((s.mention_rate for s in stats), default=0.0) or 1.0
    rows = []
    for s in sorted(stats, key=lambda s: s.mention_rate, reverse=True):
        bar_class = "" if s.is_target else "competitor"
        width_pct = round((s.mention_rate / max_rate) * 100)
        pos_txt = f"{s.avg_position:.2f}" if s.avg_position is not None else "—"
        citation_txt = f"{s.domain_citation_rate * 100:.1f}%" if s.domain_citation_rate is not None else "—"
        framing_txt = ", ".join(
            f"{FRAMING_LABELS[f]} {s.framing_distribution.get(f, 0.0) * 100:.0f}%" for f in FRAMINGS if s.framing_distribution.get(f)
        ) or "—"
        row_class = "target" if s.is_target else ""
        rows.append(
            f'<tr class="{row_class}"><td>{s.brand}</td>'
            f'<td><div class="bar-row"><div class="bar-track"><div class="bar-fill {bar_class}" style="width:{width_pct}%"></div></div>{s.mention_rate * 100:.1f}%</div></td>'
            f"<td>{pos_txt}</td>"
            f"<td>{s.share_of_voice * 100:.1f}%</td>"
            f"<td>{citation_txt}</td>"
            f"<td>{framing_txt}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Marca</th><th>Tasa de mención</th><th>Posición promedio</th>"
        "<th>Share of voice</th><th>Cita de dominio (con búsqueda web)</th><th>Framing</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def export_html_report(report: BrandVisibilityReport, path: Path) -> None:
    from datetime import datetime

    overall = compute_brand_stats(report.analyses, report.config)
    by_provider = stats_by_provider(report.analyses, report.config)
    by_intent = stats_by_intent(report.analyses, report.config)

    by_provider_html = "".join(
        f"<h3>{PROVIDER_LABELS.get(p, p)}</h3>{_stats_table_html(s)}"
        for p, s in sorted(by_provider.items())
    )
    by_intent_html = "".join(
        f"<h3>{INTENT_LABELS.get(i, i)}</h3>{_stats_table_html(s)}"
        for i, s in sorted(by_intent.items())
    )

    html = _HTML_TEMPLATE.format(
        target=report.config.target.name,
        category=report.config.category,
        market=report.config.market,
        created_at=datetime.fromtimestamp(report.created_at).strftime("%d/%m/%Y %H:%M"),
        n_responses=len(report.analyses),
        overall_table=_stats_table_html(overall),
        by_provider_tables=by_provider_html,
        by_intent_tables=by_intent_html,
    )
    path.write_text(html, encoding="utf-8")
