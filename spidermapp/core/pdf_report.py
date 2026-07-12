from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from spidermapp.core import stats
from spidermapp.core.models import CrawlResult

PRIMARY_RGB = (79, 70, 229)
CRITICAL_RGB = (220, 38, 38)
WARNING_RGB = (217, 119, 6)
GOOD_RGB = (5, 150, 105)
MUTED_RGB = (100, 100, 110)
INK_RGB = (20, 20, 30)


def _score_color(score: int) -> tuple[int, int, int]:
    if score < 50:
        return CRITICAL_RGB
    if score < 80:
        return WARNING_RGB
    return GOOD_RGB


def generate_pdf_report(result: CrawlResult, path: str | Path, priority_urls: set[str] | None = None) -> Path:
    priority_urls = priority_urls or set()
    score = stats.health_score(result.pages, priority_urls)
    budget = stats.compute_crawl_budget(result.pages)
    breakdown = stats.category_breakdown(result.pages)
    offenders = stats.top_offenders(result.pages, limit=10)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*PRIMARY_RGB)
    pdf.cell(0, 12, "Spidermapp", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*MUTED_RGB)
    pdf.cell(0, 7, "Reporte de auditoría SEO", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, result.seed_url, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, datetime.now().strftime("%d/%m/%Y %H:%M"), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(*_score_color(score))
    pdf.cell(0, 16, f"{score}/100", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED_RGB)
    pdf.cell(0, 6, "Puntaje de salud del sitio", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK_RGB)
    pdf.cell(0, 8, "Presupuesto de crawl", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED_RGB)
    for line in (
        f"Páginas rastreadas: {budget.total_pages}",
        f"OK: {budget.ok_pages}    Errores: {budget.error_pages}    Bloqueadas por robots.txt: {budget.blocked_by_robots}",
        f"Contenido duplicado: {budget.duplicate_pages}    Páginas huérfanas: {budget.orphan_pages}",
    ):
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK_RGB)
    pdf.cell(0, 8, "Issues por categoría", new_x="LMARGIN", new_y="NEXT")

    col_widths = (80, 27, 30, 20, 20)
    headers = ("Categoría", "Crítico", "Advertencia", "Info", "Total")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(240, 240, 245)
    pdf.set_text_color(*INK_RGB)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln(7)

    pdf.set_font("Helvetica", "", 9)
    for bucket in breakdown:
        label = bucket.category.value.replace("_", " ").title()
        pdf.cell(col_widths[0], 6.5, label, border=1)
        pdf.cell(col_widths[1], 6.5, str(bucket.critical), border=1, align="C")
        pdf.cell(col_widths[2], 6.5, str(bucket.warning), border=1, align="C")
        pdf.cell(col_widths[3], 6.5, str(bucket.info), border=1, align="C")
        pdf.cell(col_widths[4], 6.5, str(bucket.total), border=1, align="C")
        pdf.ln(6.5)
    if not breakdown:
        pdf.cell(0, 6.5, "Sin issues detectados.", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK_RGB)
    pdf.cell(0, 8, "Top ofensores", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED_RGB)
    if offenders:
        for page in offenders:
            pdf.multi_cell(0, 6, f"[{len(page.issues)} issues]  {page.url}", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 6, "Sin páginas con issues.", new_x="LMARGIN", new_y="NEXT")

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path
