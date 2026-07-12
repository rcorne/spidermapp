import re
from pathlib import Path

from spidermapp.core import recommendations
from spidermapp.core.models import Issue, IssueCategory, IssueSeverity

CORE_DIR = Path(__file__).parent.parent / "spidermapp" / "core"

# Every issue `code=` used across the crawler's check modules must have a
# recommendation entry, so the detail panel never falls back to a raw code.
_CODE_ASSIGNMENT_RE = re.compile(r'"code"\s*:\s*"([a-z0-9_]+)"|code="([a-z0-9_]+)"|"([a-z0-9_]+)",\s*\n?\s*"')


def _issue_codes_used_in_core() -> set[str]:
    codes = set()
    pattern = re.compile(r"IssueCategory\.[A-Z_]+,\s*\n?\s*IssueSeverity\.[A-Z_]+,\s*\n?\s*\"([a-z0-9_]+)\"")
    for py_file in CORE_DIR.glob("*.py"):
        if py_file.name in ("recommendations.py",):
            continue
        text = py_file.read_text()
        codes.update(pattern.findall(text))
    return codes


def test_every_issue_code_used_in_core_has_a_recommendation():
    used_codes = _issue_codes_used_in_core()
    assert used_codes, "sanity check: the scanner should find at least some issue codes"
    missing = used_codes - recommendations._RECOMMENDATIONS.keys()
    assert not missing, f"Missing recommendations for: {sorted(missing)}"


def test_get_recommendation_returns_known_entry():
    issue = Issue(IssueCategory.TITLES, IssueSeverity.CRITICAL, "title_missing", "Falta la etiqueta <title>.")
    rec = recommendations.get_recommendation(issue)
    assert rec.title == "Falta la etiqueta <title>"
    assert rec.fix_steps


def test_get_recommendation_falls_back_for_unknown_code():
    issue = Issue(IssueCategory.TITLES, IssueSeverity.INFO, "totally_unknown_code", "Mensaje crudo.")
    rec = recommendations.get_recommendation(issue)
    assert rec.title == "Mensaje crudo."
    assert rec.fix_steps
