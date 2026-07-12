from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urljoin

from spidermapp.core.models import Issue, IssueCategory, IssueSeverity


@dataclass
class RobotsInfo:
    robots_url: str
    found: bool
    content: str = ""
    sitemap_urls: list[str] = field(default_factory=list)
    parser: urllib.robotparser.RobotFileParser | None = None
    fetch_error: str = ""


def robots_url_for(base_url: str) -> str:
    return urljoin(base_url, "/robots.txt")


def parse_robots_txt(content: str, robots_url: str, found: bool = True) -> RobotsInfo:
    """Pure parser: takes robots.txt text already fetched by the caller."""
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(content.splitlines())

    sitemap_urls: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            sitemap_urls.append(stripped.split(":", 1)[1].strip())

    return RobotsInfo(
        robots_url=robots_url,
        found=found,
        content=content,
        sitemap_urls=sitemap_urls,
        parser=parser,
    )


def missing_robots(robots_url: str, error: str = "") -> RobotsInfo:
    return RobotsInfo(robots_url=robots_url, found=False, fetch_error=error)


def is_allowed(robots: RobotsInfo, url: str, user_agent: str) -> bool:
    if not robots.found or robots.parser is None:
        return True
    return robots.parser.can_fetch(user_agent, url)


def crawl_delay(robots: RobotsInfo, user_agent: str) -> float | None:
    if not robots.found or robots.parser is None:
        return None
    delay = robots.parser.crawl_delay(user_agent)
    return float(delay) if delay is not None else None


def validate_robots(robots: RobotsInfo, seed_url: str) -> list[Issue]:
    issues: list[Issue] = []

    if not robots.found:
        issues.append(
            Issue(
                IssueCategory.SITEMAP_ROBOTS,
                IssueSeverity.INFO,
                "robots_missing",
                "No se encontró robots.txt (se asume que todo está permitido).",
            )
        )
        return issues

    if robots.parser is not None and not robots.parser.can_fetch("*", seed_url):
        issues.append(
            Issue(
                IssueCategory.SITEMAP_ROBOTS,
                IssueSeverity.CRITICAL,
                "robots_blocks_everything",
                "robots.txt bloquea el rastreo de la URL semilla para todos los user-agents.",
            )
        )

    if not robots.sitemap_urls:
        issues.append(
            Issue(
                IssueCategory.SITEMAP_ROBOTS,
                IssueSeverity.WARNING,
                "robots_no_sitemap_directive",
                "robots.txt no declara ninguna directiva Sitemap:.",
            )
        )

    return issues
