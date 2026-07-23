from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from spidermapp.core import recommendations, stats, url_utils
from spidermapp.core.models import CrawlResult, Issue, PageResult

PRIMARY_RGB = (79, 70, 229)
CRITICAL_RGB = (220, 38, 38)
WARNING_RGB = (217, 119, 6)
GOOD_RGB = (5, 150, 105)
MUTED_RGB = (100, 100, 110)
INK_RGB = (20, 20, 30)

# Detailed appendices are capped so a 10,000-page crawl doesn't produce an
# unusable multi-thousand-page PDF; the count is always stated in full even
# when the listing itself is truncated.
MAX_ERROR_ROWS = 300
MAX_URL_ROWS = 500


def default_pdf_filename(seed_url: str) -> str:
    domain = url_utils.strip_www(url_utils.registrable_domain(seed_url)) or "sitio"
    return f"reporte_{domain}.pdf"


def _score_color(score: int) -> tuple[int, int, int]:
    if score < 50:
        return CRITICAL_RGB
    if score < 80:
        return WARNING_RGB
    return GOOD_RGB


def _page_error_label(page: PageResult) -> str:
    if page.error:
        return page.error
    if page.status_code is None:
        return "Sin respuesta"
    return f"HTTP {page.status_code}"


def generate_pdf_report(result: CrawlResult, path: str | Path, priority_urls: set[str] | None = None) -> Path:
    priority_urls = priority_urls or set()
    score = stats.health_score(result.pages, priority_urls)
    budget = stats.compute_crawl_budget(result.pages)
    breakdown = stats.category_breakdown(result.pages)
    opportunities = stats.find_opportunities(result.pages, limit=20)
    error_pages = [
        p for p in result.pages
        if not any(i.code == "blocked_by_robots" for i in p.issues) and (p.status_code is None or p.status_code >= 400)
    ]
    error_pages.sort(key=lambda p: (p.status_code is None, p.status_code or 0))

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.core_fonts_encoding = "cp1252"
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    def _s(text) -> str:
        return str(text).encode("cp1252", errors="replace").decode("cp1252")

    def _h1(text: str) -> None:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*INK_RGB)
        pdf.cell(0, 9, _s(text), new_x="LMARGIN", new_y="NEXT")

    def _body(text: str, color=MUTED_RGB, size=9.5) -> None:
        pdf.set_font("Helvetica", "", size)
        pdf.set_text_color(*color)
        pdf.multi_cell(0, 5.5, _s(text), new_x="LMARGIN", new_y="NEXT")

    def _rule() -> None:
        pdf.set_draw_color(225, 227, 232)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)

    # ---------------------------------------------------------------- portada
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*PRIMARY_RGB)
    pdf.cell(0, 12, "Spidermapp", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*MUTED_RGB)
    pdf.cell(0, 7, "Reporte de auditoria SEO", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(result.seed_url), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, datetime.now().strftime("%d/%m/%Y %H:%M"), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(*_score_color(score))
    pdf.cell(0, 16, f"{score}/100", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED_RGB)
    pdf.cell(0, 6, "Puntaje de salud del sitio", new_x="LMARGIN", new_y="NEXT")

    # ------------------------------------------------------- resumen ejecutivo
    pdf.ln(8)
    _h1("Resumen ejecutivo")
    stat_rows = [
        ("URLs totales rastreadas", str(budget.total_pages), "Total de URLs visitadas durante este rastreo."),
        ("Paginas OK", str(budget.ok_pages), "Codigo 200 y sin errores criticos."),
        ("Paginas con error", str(budget.error_pages), "Codigo 4xx/5xx o sin respuesta del servidor."),
        ("Bloqueadas por robots.txt", str(budget.blocked_by_robots), "El propio sitio le impide el paso a los motores de busqueda."),
        ("Contenido duplicado", str(budget.duplicate_pages), "Contenido practicamente identico al de otra pagina."),
        ("Paginas huerfanas", str(budget.orphan_pages), "Sin ningun enlace interno hacia ellas; solo aparecen en el sitemap."),
    ]
    pdf.set_font("Helvetica", "B", 10)
    for label, value, definition in stat_rows:
        pdf.set_text_color(*INK_RGB)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(58, 6, _s(f"{label}:"), new_x="RIGHT", new_y="TOP")
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*PRIMARY_RGB)
        pdf.cell(14, 6, _s(value))
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*MUTED_RGB)
        pdf.multi_cell(0, 6, _s(definition), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    _rule()

    # --------------------------------------------------- issues por categoria
    _h1("Issues por categoria")
    col_widths = (80, 27, 30, 20, 20)
    headers = ("Categoria", "Critico", "Advertencia", "Info", "Total")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(240, 240, 245)
    pdf.set_text_color(*INK_RGB)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln(7)

    pdf.set_font("Helvetica", "", 9)
    for bucket in breakdown:
        label = bucket.category.value.replace("_", " ").title()
        pdf.cell(col_widths[0], 6.5, _s(label), border=1)
        pdf.cell(col_widths[1], 6.5, str(bucket.critical), border=1, align="C")
        pdf.cell(col_widths[2], 6.5, str(bucket.warning), border=1, align="C")
        pdf.cell(col_widths[3], 6.5, str(bucket.info), border=1, align="C")
        pdf.cell(col_widths[4], 6.5, str(bucket.total), border=1, align="C")
        pdf.ln(6.5)
    if not breakdown:
        pdf.cell(0, 6.5, "Sin issues detectados.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    _rule()

    # --------------------------------------- oportunidades y posibles soluciones
    _h1("Oportunidades de optimizacion y posibles soluciones")
    _body("Cada hallazgo agrupa todas las paginas afectadas: aplicar la solucion una vez las corrige todas.", size=9)
    if opportunities:
        for opp in opportunities:
            rec = recommendations.get_recommendation(Issue(opp.category, opp.severity, opp.code, ""))
            color = CRITICAL_RGB if opp.severity.value == "critical" else (WARNING_RGB if opp.severity.value == "warning" else MUTED_RGB)
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(*INK_RGB)
            pages_word = "pagina" if opp.affected_pages == 1 else "paginas"
            pdf.multi_cell(0, 6, _s(f"{rec.title}  —  {opp.affected_pages} {pages_word}"), new_x="LMARGIN", new_y="NEXT")
            if rec.why:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*MUTED_RGB)
                pdf.multi_cell(0, 5, _s(f"Por que importa: {rec.why}"), new_x="LMARGIN", new_y="NEXT")
            if rec.fix_steps:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*color)
                for step in rec.fix_steps:
                    pdf.multi_cell(0, 5, _s(f"  -  {step}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
    else:
        _body("Sin oportunidades de optimizacion detectadas. El sitio esta en buena forma.", color=GOOD_RGB)
    pdf.ln(2)
    _rule()

    # ------------------------------------------------------------- errores
    _h1(f"Paginas con error ({len(error_pages)} en total)")
    if error_pages:
        _body(
            "Codigos de respuesta 4xx/5xx o solicitudes que no obtuvieron respuesta."
            + (f" Se listan las primeras {MAX_ERROR_ROWS}." if len(error_pages) > MAX_ERROR_ROWS else ""),
            size=9,
        )
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(240, 240, 245)
        pdf.set_text_color(*INK_RGB)
        pdf.cell(28, 7, "Estado", border=1, fill=True, align="C")
        pdf.cell(0, 7, "URL", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8.5)
        for page in error_pages[:MAX_ERROR_ROWS]:
            pdf.set_text_color(*CRITICAL_RGB)
            pdf.cell(28, 6, _s(_page_error_label(page)[:14]), border=1, align="C")
            pdf.set_text_color(*INK_RGB)
            x, y = pdf.get_x(), pdf.get_y()
            pdf.multi_cell(0, 6, _s(page.url), border=1, new_x="LMARGIN", new_y="NEXT")
        if len(error_pages) > MAX_ERROR_ROWS:
            _body(f"... y {len(error_pages) - MAX_ERROR_ROWS} paginas con error adicionales.", size=8.5)
    else:
        _body("Sin paginas con errores de respuesta. ✓", color=GOOD_RGB)
    pdf.ln(2)
    _rule()

    # ------------------------------------------------------ apendice: URLs
    _h1(f"Apendice: todas las URLs rastreadas ({len(result.pages)} en total)")
    if len(result.pages) > MAX_URL_ROWS:
        _body(f"Se listan las primeras {MAX_URL_ROWS} de {len(result.pages)} URLs rastreadas.", size=9)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(240, 240, 245)
    pdf.set_text_color(*INK_RGB)
    pdf.cell(16, 7, "Estado", border=1, fill=True, align="C")
    pdf.cell(0, 7, "URL", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    for page in result.pages[:MAX_URL_ROWS]:
        status_text = str(page.status_code) if page.status_code is not None else "—"
        color = GOOD_RGB if (page.status_code and page.status_code < 400) else CRITICAL_RGB
        pdf.set_text_color(*color)
        pdf.cell(16, 5.5, _s(status_text), border=1, align="C")
        pdf.set_text_color(*MUTED_RGB)
        pdf.multi_cell(0, 5.5, _s(page.url), border=1, new_x="LMARGIN", new_y="NEXT")
    if len(result.pages) > MAX_URL_ROWS:
        _body(f"... y {len(result.pages) - MAX_URL_ROWS} URLs adicionales (ver exportacion CSV/XLSX para el listado completo).", size=8.5)

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path
