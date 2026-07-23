from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

from spidermapp.core import recommendations, stats, url_utils
from spidermapp.core.models import CrawlResult, Issue

# Sober, modern palette — matches the app's own theme (indigo primary,
# neutral grays) rather than a generic template look.
INK = RGBColor(0x11, 0x18, 0x27)
MUTED = RGBColor(0x6B, 0x72, 0x80)
SUBTLE = RGBColor(0x9C, 0xA3, 0xAF)
PRIMARY = RGBColor(0x4F, 0x46, 0xE5)
PRIMARY_DARK = RGBColor(0x37, 0x30, 0xA3)
PRIMARY_SOFT = RGBColor(0xEE, 0xF2, 0xFF)
BG_LIGHT = RGBColor(0xF9, 0xFA, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOOD = RGBColor(0x05, 0x96, 0x69)
WARNING = RGBColor(0xD9, 0x77, 0x06)
CRITICAL = RGBColor(0xDC, 0x26, 0x26)
BORDER = RGBColor(0xE5, 0xE7, 0xEB)

FONT = "Helvetica Neue"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def default_pptx_filename(seed_url: str) -> str:
    domain = url_utils.strip_www(url_utils.registrable_domain(seed_url)) or "sitio"
    return f"presentación_status_{domain}.pptx"


def _score_color(score: int) -> RGBColor:
    if score < 50:
        return CRITICAL
    if score < 80:
        return WARNING
    return GOOD


def _blank_slide(prs: Presentation, bg: RGBColor = WHITE):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    rect.fill.solid()
    rect.fill.fore_color.rgb = bg
    rect.line.fill.background()
    rect.shadow.inherit = False
    # Push the background rect behind everything added afterward.
    spTree = slide.shapes._spTree
    spTree.remove(rect._element)
    spTree.insert(2, rect._element)
    return slide


def _textbox(slide, left, top, width, height, text, size, color, bold=False, align=PP_ALIGN.LEFT, font=FONT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.name = font
    return box


def _bullets(slide, left, top, width, height, items, size, color, spacing=6, font=FONT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(spacing)
        run = p.add_run()
        run.text = f"•  {item}"
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.name = font
    return box


def _footer(slide, prs, seed_url: str, page_label: str) -> None:
    _textbox(
        slide, Inches(0.5), prs.slide_height - Inches(0.45), Inches(7), Inches(0.3),
        url_utils.strip_www(url_utils.registrable_domain(seed_url)), 9, SUBTLE,
    )
    _textbox(
        slide, prs.slide_width - Inches(3.5), prs.slide_height - Inches(0.45), Inches(3), Inches(0.3),
        page_label, 9, SUBTLE, align=PP_ALIGN.RIGHT,
    )


def _kpi_card(slide, left, top, width, height, value: str, label: str, value_color: RGBColor) -> None:
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.adjustments[0] = 0.08
    card.fill.solid()
    card.fill.fore_color.rgb = WHITE
    card.line.color.rgb = BORDER
    card.line.width = Pt(0.75)
    card.shadow.inherit = False

    _textbox(slide, left, top + Inches(0.18), width, Inches(0.7), value, 30, value_color, bold=True, align=PP_ALIGN.CENTER)
    _textbox(slide, left, top + height - Inches(0.55), width, Inches(0.4), label, 10.5, MUTED, align=PP_ALIGN.CENTER)


def generate_pptx_report(result: CrawlResult, path: str | Path, priority_urls: set[str] | None = None) -> Path:
    priority_urls = priority_urls or set()
    score = stats.health_score(result.pages, priority_urls)
    budget = stats.compute_crawl_budget(result.pages)
    breakdown = stats.category_breakdown(result.pages)
    opportunities = stats.find_opportunities(result.pages, limit=6)
    domain = url_utils.strip_www(url_utils.registrable_domain(result.seed_url)) or result.seed_url

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    _build_title_slide(prs, domain, result.seed_url, score)
    _build_summary_slide(prs, result, budget, score)
    _build_categories_slide(prs, result, breakdown)
    _build_opportunities_slide(prs, result, opportunities)
    _build_closing_slide(prs, result)

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return output_path


def _build_title_slide(prs: Presentation, domain: str, seed_url: str, score: int) -> None:
    slide = _blank_slide(prs, bg=INK)

    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), prs.slide_height)
    accent.fill.solid()
    accent.fill.fore_color.rgb = PRIMARY
    accent.line.fill.background()
    accent.shadow.inherit = False

    _textbox(slide, Inches(1), Inches(2.5), Inches(11), Inches(0.5), "AUDITORÍA SEO", 16, RGBColor(0xA5, 0xB4, 0xFC), bold=True)
    _textbox(slide, Inches(1), Inches(3.0), Inches(11), Inches(1.1), domain, 44, WHITE, bold=True)
    _textbox(slide, Inches(1), Inches(4.0), Inches(11), Inches(0.5), "Resumen ejecutivo de status del sitio", 18, RGBColor(0xC7, 0xCC, 0xD8))
    _textbox(
        slide, Inches(1), Inches(4.55), Inches(11), Inches(0.4),
        f"{seed_url}   ·   {datetime.now().strftime('%d/%m/%Y')}", 12, SUBTLE,
    )

    _textbox(slide, Inches(1), Inches(6.0), Inches(4), Inches(0.4), "PREPARADO CON SPIDERMAPP", 10, RGBColor(0x6B, 0x72, 0x80), bold=True)


def _build_summary_slide(prs: Presentation, result: CrawlResult, budget: stats.CrawlBudget, score: int) -> None:
    slide = _blank_slide(prs, bg=BG_LIGHT)
    _textbox(slide, Inches(0.6), Inches(0.45), Inches(8), Inches(0.6), "Resumen ejecutivo", 26, INK, bold=True)
    _textbox(slide, Inches(0.6), Inches(1.05), Inches(9), Inches(0.4), "Estado general del sitio a la fecha de este análisis.", 12, MUTED)

    # Health score hero
    ring = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.7), Inches(1.7), Inches(2.1), Inches(2.1))
    ring.fill.solid()
    ring.fill.fore_color.rgb = WHITE
    ring.line.color.rgb = _score_color(score)
    ring.line.width = Pt(4)
    ring.shadow.inherit = False
    tf = ring.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = str(score)
    run.font.size = Pt(40)
    run.font.bold = True
    run.font.color.rgb = _score_color(score)
    run.font.name = FONT

    _textbox(slide, Inches(0.55), Inches(3.85), Inches(2.4), Inches(0.4), "Puntaje de salud", 12, MUTED, align=PP_ALIGN.CENTER)

    # KPI cards
    cards = [
        (str(budget.total_pages), "URLs rastreadas", INK),
        (str(budget.ok_pages), "Páginas OK", GOOD),
        (str(budget.error_pages), "Con errores", CRITICAL),
        (str(budget.duplicate_pages), "Contenido duplicado", WARNING),
    ]
    card_w, card_h, gap = Inches(2.55), Inches(1.5), Inches(0.25)
    start_x = Inches(3.4)
    for i, (value, label, color) in enumerate(cards):
        x = start_x + i * (card_w + gap)
        _kpi_card(slide, x, Inches(1.7), card_w, card_h, value, label, color)

    cards2 = [
        (str(budget.blocked_by_robots), "Bloqueadas por robots.txt", MUTED),
        (str(budget.orphan_pages), "Páginas huérfanas", WARNING),
    ]
    for i, (value, label, color) in enumerate(cards2):
        x = start_x + i * (card_w + gap)
        _kpi_card(slide, x, Inches(3.4), card_w, card_h, value, label, color)

    note = (
        "El puntaje de salud combina la severidad y cantidad de hallazgos técnicos detectados; "
        "100 indica ausencia de problemas relevantes."
    )
    _textbox(slide, Inches(3.4), Inches(5.15), Inches(9.2), Inches(1.2), note, 11, MUTED)

    _footer(slide, prs, result.seed_url, "01  ·  Resumen ejecutivo")


def _build_categories_slide(prs: Presentation, result: CrawlResult, breakdown: list[stats.CategoryBreakdown]) -> None:
    slide = _blank_slide(prs, bg=WHITE)
    _textbox(slide, Inches(0.6), Inches(0.45), Inches(9), Inches(0.6), "Hallazgos por categoría", 26, INK, bold=True)
    _textbox(slide, Inches(0.6), Inches(1.05), Inches(10), Inches(0.4), "Distribución de issues técnicos detectados, por área de SEO.", 12, MUTED)

    top = Inches(1.75)
    row_h = Inches(0.55)
    max_total = max((b.total for b in breakdown), default=1) or 1
    bar_area_x = Inches(4.6)
    bar_area_w = Inches(7.2)

    if not breakdown:
        _textbox(slide, Inches(0.6), top, Inches(10), Inches(0.5), "Sin issues detectados en este análisis.", 13, GOOD, bold=True)
    else:
        for i, bucket in enumerate(breakdown[:9]):
            y = top + i * row_h
            label = bucket.category.value.replace("_", " ").title()
            _textbox(slide, Inches(0.6), y, Inches(3.8), Inches(0.4), label, 11.5, INK)

            track = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bar_area_x, y + Emu(60000), bar_area_w, Inches(0.28))
            track.adjustments[0] = 0.5
            track.fill.solid()
            track.fill.fore_color.rgb = BORDER
            track.line.fill.background()
            track.shadow.inherit = False

            frac = bucket.total / max_total
            fill_w = max(Emu(int(bar_area_w * frac)), Inches(0.05))
            color = CRITICAL if bucket.critical >= bucket.warning and bucket.critical >= bucket.info else (
                WARNING if bucket.warning >= bucket.info else PRIMARY
            )
            fill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bar_area_x, y + Emu(60000), fill_w, Inches(0.28))
            fill.adjustments[0] = 0.5
            fill.fill.solid()
            fill.fill.fore_color.rgb = color
            fill.line.fill.background()
            fill.shadow.inherit = False

            _textbox(slide, bar_area_x + bar_area_w + Inches(0.15), y, Inches(0.6), Inches(0.4), str(bucket.total), 11.5, MUTED)

    _footer(slide, prs, result.seed_url, "02  ·  Hallazgos por categoría")


def _build_opportunities_slide(prs: Presentation, result: CrawlResult, opportunities: list[stats.IssueOpportunity]) -> None:
    slide = _blank_slide(prs, bg=BG_LIGHT)
    _textbox(slide, Inches(0.6), Inches(0.45), Inches(10), Inches(0.6), "Principales oportunidades", 26, INK, bold=True)
    _textbox(slide, Inches(0.6), Inches(1.05), Inches(11), Inches(0.4), "Acciones priorizadas con mayor impacto potencial para el sitio.", 12, MUTED)

    if not opportunities:
        _textbox(slide, Inches(0.6), Inches(1.8), Inches(10), Inches(0.5), "Sin oportunidades relevantes detectadas — el sitio está en buena forma.", 13, GOOD, bold=True)
    else:
        top = Inches(1.75)
        card_h = Inches(0.82)
        gap = Inches(0.12)
        for i, opp in enumerate(opportunities[:6]):
            rec = recommendations.get_recommendation(Issue(opp.category, opp.severity, opp.code, ""))
            y = top + i * (card_h + gap)
            color = CRITICAL if opp.severity.value == "critical" else (WARNING if opp.severity.value == "warning" else PRIMARY)

            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), y, Inches(12.1), card_h)
            card.adjustments[0] = 0.12
            card.fill.solid()
            card.fill.fore_color.rgb = WHITE
            card.line.color.rgb = BORDER
            card.line.width = Pt(0.75)
            card.shadow.inherit = False

            bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), y, Inches(0.09), card_h)
            bar.fill.solid()
            bar.fill.fore_color.rgb = color
            bar.line.fill.background()
            bar.shadow.inherit = False

            pages_word = "página" if opp.affected_pages == 1 else "páginas"
            _textbox(slide, Inches(0.9), y + Inches(0.1), Inches(9.8), Inches(0.35), rec.title, 13, INK, bold=True)
            _textbox(
                slide, Inches(0.9), y + Inches(0.44), Inches(9.8), Inches(0.32),
                rec.fix_steps[0] if rec.fix_steps else rec.why, 10.5, MUTED,
            )
            _textbox(
                slide, Inches(10.9), y + Inches(0.24), Inches(1.7), Inches(0.4),
                f"{opp.affected_pages} {pages_word}", 11, color, bold=True, align=PP_ALIGN.RIGHT,
            )

    _footer(slide, prs, result.seed_url, "03  ·  Oportunidades")


def _build_closing_slide(prs: Presentation, result: CrawlResult) -> None:
    slide = _blank_slide(prs, bg=INK)
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), prs.slide_height)
    accent.fill.solid()
    accent.fill.fore_color.rgb = PRIMARY
    accent.line.fill.background()
    accent.shadow.inherit = False

    _textbox(slide, Inches(1), Inches(2.9), Inches(11), Inches(0.7), "Próximos pasos", 30, WHITE, bold=True)
    _bullets(
        slide, Inches(1), Inches(3.8), Inches(10.5), Inches(2.5),
        [
            "Priorizar las oportunidades marcadas como críticas.",
            "Reevaluar el sitio después de aplicar las correcciones para medir el impacto.",
            "Programar auditorías periódicas para detectar regresiones a tiempo.",
        ],
        14, RGBColor(0xC7, 0xCC, 0xD8),
        spacing=10,
    )
    _textbox(slide, Inches(1), Inches(6.6), Inches(6), Inches(0.4), "Generado con Spidermapp", 10, SUBTLE)
