from __future__ import annotations

from pathlib import Path

import pandas as pd

from spidermapp.core.models import PageResult


def pages_to_dataframe(pages: list[PageResult]) -> pd.DataFrame:
    rows = []
    for p in pages:
        rows.append(
            {
                "URL": p.url,
                "Status Code": p.status_code,
                "Indexable": p.is_indexable,
                "Title": p.title,
                "Title Length": len(p.title),
                "Meta Description": p.meta_description,
                "Meta Description Length": len(p.meta_description),
                "H1": " | ".join(p.h1),
                "Canonical": p.canonical,
                "Meta Robots": p.meta_robots,
                "Word Count": p.word_count,
                "Depth": p.depth,
                "Redirect Chain Length": len(p.redirect_chain),
                "Final URL": p.final_url,
                "Tech": ", ".join(p.tech),
                "Soft 404": p.is_soft_404,
                "Fetch Time (ms)": round(p.fetch_time_ms, 1),
                "Issue Count": len(p.issues),
                "Issues": "; ".join(f"[{i.severity.value}] {i.code}" for i in p.issues),
            }
        )
    return pd.DataFrame(rows)


def export_csv(pages: list[PageResult], path: str | Path) -> None:
    pages_to_dataframe(pages).to_csv(path, index=False)


def export_xlsx(pages: list[PageResult], path: str | Path) -> None:
    df = pages_to_dataframe(pages)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Crawl")

        issue_rows = []
        for p in pages:
            for issue in p.issues:
                issue_rows.append(
                    {
                        "URL": p.url,
                        "Category": issue.category.value,
                        "Severity": issue.severity.value,
                        "Code": issue.code,
                        "Message": issue.message,
                    }
                )
        pd.DataFrame(issue_rows).to_excel(writer, index=False, sheet_name="Issues")
