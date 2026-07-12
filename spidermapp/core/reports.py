from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from spidermapp.core import recommendations
from spidermapp.core.models import CrawlResult, IssueCategory, IssueSeverity

AREA_TITLES: dict[IssueCategory, str] = {
    IssueCategory.RESPONSE_CODES: "Códigos de respuesta (404, soft-404, 5xx)",
    IssueCategory.TITLES: "Titles",
    IssueCategory.META: "Meta descriptions, encabezados y contenido",
    IssueCategory.CANONICALS: "Canonicals",
    IssueCategory.DIRECTIVES: "Directivas de indexación (noindex/nofollow)",
    IssueCategory.LINKS: "Enlaces internos",
    IssueCategory.SITEMAP_ROBOTS: "Sitemap.xml y robots.txt",
    IssueCategory.SECURITY: "Seguridad (HTTPS / www)",
    IssueCategory.REDIRECTS: "Redirects",
    IssueCategory.DUPLICATES: "Contenido duplicado",
    IssueCategory.URL_CONVENTIONS: "Convenciones de URL",
    IssueCategory.RENDERING: "Renderizado JS / Mobile vs Desktop",
    IssueCategory.TECH: "CMS y tecnologías",
}

_SEVERITY_LABEL = {IssueSeverity.CRITICAL: "Crítico", IssueSeverity.WARNING: "Advertencia", IssueSeverity.INFO: "Info"}
_SEVERITY_RGB = {
    IssueSeverity.CRITICAL: (220, 38, 38),
    IssueSeverity.WARNING: (217, 119, 6),
    IssueSeverity.INFO: (37, 99, 235),
}
MAX_URLS_PER_ISSUE = 40


def _s(text: str) -> str:
    """fpdf's built-in Helvetica only speaks cp1252; degrade anything else."""
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _area_pdf(result: CrawlResult, category: IssueCategory, path: Path) -> bool:
    """Write one per-area report. Returns False (and writes nothing) if the
    area has no findings."""
    pages_with = [(p, [i for i in p.issues if i.category == category]) for p in result.pages]
    pages_with = [(p, found) for p, found in pages_with if found]
    site_issues = [i for i in result.site_issues if i.category == category]
    if not pages_with and not site_issues:
        return False

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.core_fonts_encoding = "cp1252"
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 10, "Spidermapp — Informe por área", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(20, 20, 30)
    pdf.cell(0, 9, _s(AREA_TITLES.get(category, category.value)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 110)
    pdf.cell(0, 6, _s(f"{result.seed_url} — {datetime.now().strftime('%d/%m/%Y %H:%M')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Páginas afectadas: {len(pages_with)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if site_issues:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(20, 20, 30)
        pdf.cell(0, 8, "Hallazgos a nivel de sitio", new_x="LMARGIN", new_y="NEXT")
        for issue in site_issues:
            rec = recommendations.get_recommendation(issue)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*_SEVERITY_RGB[issue.severity])
            pdf.multi_cell(0, 6, _s(f"[{_SEVERITY_LABEL[issue.severity]}] {rec.title}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(100, 100, 110)
            if rec.why:
                pdf.multi_cell(0, 5, _s(rec.why), new_x="LMARGIN", new_y="NEXT")
            for step in rec.fix_steps:
                pdf.multi_cell(0, 5, _s(f"  - {step}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    # Group affected URLs by issue code so each problem reads as one block
    by_code: dict[str, list] = {}
    for page, found in pages_with:
        for issue in found:
            by_code.setdefault(issue.code, []).append((page, issue))

    for code, entries in sorted(by_code.items(), key=lambda kv: -len(kv[1])):
        sample_issue = entries[0][1]
        rec = recommendations.get_recommendation(sample_issue)
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*_SEVERITY_RGB[sample_issue.severity])
        pdf.multi_cell(0, 7, _s(f"[{_SEVERITY_LABEL[sample_issue.severity]}] {rec.title} — {len(entries)} URL(s)"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 110)
        if rec.why:
            pdf.multi_cell(0, 5, _s(rec.why), new_x="LMARGIN", new_y="NEXT")
        for step in rec.fix_steps:
            pdf.multi_cell(0, 5, _s(f"  - {step}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(60, 60, 70)
        for page, _issue in entries[:MAX_URLS_PER_ISSUE]:
            pdf.multi_cell(0, 4.5, _s(f"    {page.url}"), new_x="LMARGIN", new_y="NEXT")
        if len(entries) > MAX_URLS_PER_ISSUE:
            pdf.multi_cell(0, 4.5, _s(f"    ... y {len(entries) - MAX_URLS_PER_ISSUE} URL(s) más (ver export CSV/XLSX)."), new_x="LMARGIN", new_y="NEXT")

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    return True


def generate_area_reports(result: CrawlResult, output_dir: str | Path) -> list[Path]:
    """One PDF per SEO area that has findings. Returns the written paths."""
    output_dir = Path(output_dir)
    written: list[Path] = []
    for category in IssueCategory:
        filename = f"informe_{category.value}.pdf"
        path = output_dir / filename
        if _area_pdf(result, category, path):
            written.append(path)
    return written
