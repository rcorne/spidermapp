from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class IssueCategory(str, Enum):
    RESPONSE_CODES = "response_codes"
    TITLES = "titles"
    META = "meta"
    CANONICALS = "canonicals"
    DIRECTIVES = "directives"
    LINKS = "links"
    SITEMAP_ROBOTS = "sitemap_robots"
    SECURITY = "security"
    REDIRECTS = "redirects"
    DUPLICATES = "duplicates"
    URL_CONVENTIONS = "url_conventions"
    RENDERING = "rendering"
    TECH = "tech"


@dataclass(frozen=True)
class Issue:
    category: IssueCategory
    severity: IssueSeverity
    code: str
    message: str


@dataclass
class LinkEdge:
    source: str
    target: str
    anchor_text: str = ""
    is_internal: bool = True
    rel: str = ""


@dataclass
class CrawlConfig:
    seed_url: str
    max_pages: int = 500
    max_depth: int = 10
    concurrency: int = 8
    respect_robots: bool = True
    render_js: bool = False
    user_agent: str = "PidgeotBot/0.1 (+https://example.invalid/bot)"
    request_timeout: float = 15.0
    priority_urls: list[str] = field(default_factory=list)
    include_subdomains: bool = False
    exclude_patterns: list[str] = field(default_factory=list)
    max_url_length: int = 0  # 0 = sin límite
    limit_to_start_folder: bool = False
    follow_nofollow: bool = True
    max_query_params: int = 0  # 0 = sin límite
    max_links_per_page: int = 0  # 0 = sin límite
    max_retries: int = 2


@dataclass
class TlsInfo:
    valid: bool = False
    issuer: str = ""
    expires_at: str = ""
    days_until_expiry: int | None = None
    error: str = ""


@dataclass
class RenderInfo:
    rendered_html: str = ""
    raw_vs_rendered_title_match: bool = True
    raw_vs_rendered_desc_match: bool = True
    raw_vs_rendered_h1_match: bool = True
    mobile_desktop_match: bool = True
    lcp_ms: float | None = None
    cls: float | None = None
    fcp_ms: float | None = None
    error: str = ""


@dataclass
class PageResult:
    url: str
    status_code: int | None = None
    final_url: str = ""
    redirect_chain: list[tuple[str, int]] = field(default_factory=list)
    content_type: str = ""
    depth: int = 0
    fetch_time_ms: float = 0.0
    fetched_at: float = field(default_factory=time.time)

    title: str = ""
    meta_description: str = ""
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    canonical: str = ""
    meta_robots: str = ""
    x_robots_tag: str = ""
    hreflang: list[tuple[str, str]] = field(default_factory=list)
    json_ld_types: list[str] = field(default_factory=list)
    word_count: int = 0

    outlinks: list[LinkEdge] = field(default_factory=list)
    inlinks: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    content_hash: str = ""
    is_soft_404: bool = False
    is_orphan: bool = False
    in_sitemap: bool = False
    meta_keywords: str = ""
    images_without_alt: int = 0
    empty_anchors: int = 0
    keywords: list[str] = field(default_factory=list)

    tls: TlsInfo | None = None
    tech: list[str] = field(default_factory=list)
    render: RenderInfo | None = None

    raw_html: str = ""
    error: str = ""

    issues: list[Issue] = field(default_factory=list)

    @property
    def is_indexable(self) -> bool:
        if self.status_code != 200:
            return False
        robots = (self.meta_robots + " " + self.x_robots_tag).lower()
        if "noindex" in robots:
            return False
        if self.canonical and self.canonical != self.final_url and self.canonical != self.url:
            return False
        return True

    def add_issue(self, category: IssueCategory, severity: IssueSeverity, code: str, message: str) -> None:
        self.issues.append(Issue(category=category, severity=severity, code=code, message=message))


@dataclass
class CrawlResult:
    seed_url: str
    pages: list[PageResult] = field(default_factory=list)
    site_issues: list[Issue] = field(default_factory=list)
    sitemap_urls: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    stopped_early: bool = False
    duplicate_content_groups: dict[str, list[str]] = field(default_factory=dict)
    duplicate_title_groups: dict[str, list[str]] = field(default_factory=dict)
    duplicate_meta_groups: dict[str, list[str]] = field(default_factory=dict)
