from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional, Union
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from spidermapp.core import duplicates, html_analysis, issues as issues_mod, render_check, robots, security, sitemap, tech_detect, url_utils
from spidermapp.core.models import (
    CrawlConfig,
    CrawlResult,
    Issue,
    IssueCategory,
    IssueSeverity,
    LinkEdge,
    PageResult,
)
from spidermapp.core.soft_404 import detect_soft_404

OnPage = Callable[[PageResult], Union[Awaitable[None], None]]
OnProgress = Callable[[int, int], Union[Awaitable[None], None]]
StopFlag = Callable[[], bool]

MAX_REDIRECT_HOPS = 10
SITEMAP_INDEX_MAX_CHILDREN = 20


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


async def _maybe_await(fn, *args):
    if fn is None:
        return
    result = fn(*args)
    if asyncio.iscoroutine(result):
        await result


async def _fetch_with_redirect_chain(
    client: httpx.AsyncClient, url: str, max_hops: int = MAX_REDIRECT_HOPS
) -> tuple[Optional[httpx.Response], list[tuple[str, int]], str]:
    chain: list[tuple[str, int]] = []
    current = url
    for _ in range(max_hops):
        try:
            response = await client.get(current, follow_redirects=False)
        except httpx.RequestError as exc:
            return None, chain, str(exc)

        if response.status_code in (301, 302, 303, 307, 308) and "location" in response.headers:
            chain.append((current, response.status_code))
            current = url_utils.normalize_url(response.headers["location"], base=current)
            continue
        return response, chain, ""

    return None, chain, "too_many_redirects"


class Crawler:
    def __init__(self, config: CrawlConfig):
        self.config = config
        self.priority_urls = set(config.priority_urls)
        self.visited: set[str] = set()
        self.inlinks: dict[str, set[str]] = {}
        self.pages: list[PageResult] = []
        self._browser = None
        self._playwright = None

    async def run(
        self,
        on_page: OnPage | None = None,
        on_progress: OnProgress | None = None,
        stop_flag: StopFlag | None = None,
    ) -> CrawlResult:
        result = CrawlResult(seed_url=self.config.seed_url)
        semaphore = asyncio.Semaphore(self.config.concurrency)
        headers = {"User-Agent": self.config.user_agent}

        async with httpx.AsyncClient(
            headers=headers, timeout=self.config.request_timeout, follow_redirects=False
        ) as client:
            robots_info = await self._fetch_robots(client)
            result.site_issues.extend(robots.validate_robots(robots_info, self.config.seed_url))

            sitemap_urls = await self._collect_sitemap_urls(client, robots_info)
            result.sitemap_urls = sitemap_urls

            if self.config.render_js:
                await self._start_browser()

            try:
                frontier: list[tuple[str, int]] = [(url_utils.normalize_url(self.config.seed_url), 0)]
                self.visited.add(frontier[0][0])

                while frontier:
                    if stop_flag and stop_flag():
                        result.stopped_early = True
                        break
                    if len(self.pages) >= self.config.max_pages:
                        result.stopped_early = True
                        break

                    budget = self.config.max_pages - len(self.pages)
                    batch = frontier[:budget]
                    frontier = frontier[budget:]

                    tasks = [
                        self._process_url(client, robots_info, semaphore, url, depth)
                        for url, depth in batch
                        if depth <= self.config.max_depth
                    ]
                    if not tasks:
                        continue

                    processed = await asyncio.gather(*tasks)

                    next_level: list[tuple[str, int]] = []
                    for page, discovered in processed:
                        self.pages.append(page)
                        await _maybe_await(on_page, page)
                        await _maybe_await(on_progress, len(self.pages), self.config.max_pages)

                        for link_url, depth in discovered:
                            self.inlinks.setdefault(link_url, set()).add(page.final_url or page.url)
                            if link_url in self.visited:
                                continue
                            self.visited.add(link_url)
                            next_level.append((link_url, depth))

                    frontier = next_level + frontier

                await self._crawl_orphans(client, robots_info, semaphore, sitemap_urls, on_page, on_progress)
            finally:
                if self._browser is not None:
                    await self._stop_browser()

            for page in self.pages:
                page.inlinks = sorted(self.inlinks.get(page.final_url or page.url, set()))

            await self._run_site_wide_checks(client, result)

        result.pages = self.pages
        result.finished_at = time.time()
        return result

    async def _fetch_robots(self, client: httpx.AsyncClient) -> robots.RobotsInfo:
        robots_url = robots.robots_url_for(self.config.seed_url)
        try:
            response = await client.get(robots_url)
            if response.status_code == 200:
                return robots.parse_robots_txt(response.text, robots_url)
            return robots.missing_robots(robots_url, error=f"status {response.status_code}")
        except httpx.RequestError as exc:
            return robots.missing_robots(robots_url, error=str(exc))

    async def _collect_sitemap_urls(self, client: httpx.AsyncClient, robots_info: robots.RobotsInfo) -> list[str]:
        candidate_sitemaps = list(robots_info.sitemap_urls) or [
            url_utils.normalize_url("/sitemap.xml", base=self.config.seed_url)
        ]
        collected: list[str] = []
        to_visit = list(candidate_sitemaps)
        visited_sitemaps: set[str] = set()

        while to_visit and len(visited_sitemaps) < SITEMAP_INDEX_MAX_CHILDREN:
            sitemap_url = to_visit.pop(0)
            if sitemap_url in visited_sitemaps:
                continue
            visited_sitemaps.add(sitemap_url)
            try:
                response = await client.get(sitemap_url)
            except httpx.RequestError:
                continue
            if response.status_code != 200:
                continue
            parsed = sitemap.parse_sitemap_xml(response.text, sitemap_url)
            if parsed.is_index:
                to_visit.extend(parsed.child_sitemaps)
            else:
                collected.extend(parsed.urls)

        return collected

    async def _crawl_orphans(
        self,
        client: httpx.AsyncClient,
        robots_info: robots.RobotsInfo,
        semaphore: asyncio.Semaphore,
        sitemap_urls: list[str],
        on_page: OnPage | None,
        on_progress: OnProgress | None,
    ) -> None:
        """Fetch sitemap URLs that were never reached by following internal
        links. These are orphan pages: real, indexable-looking URLs with zero
        internal inlinks, invisible in a plain crawl but real crawl-budget/
        indexation risks."""
        remaining_budget = self.config.max_pages - len(self.pages)
        if remaining_budget <= 0:
            return

        candidates: list[str] = []
        for raw_url in sitemap_urls:
            normalized = url_utils.normalize_url(raw_url)
            if normalized in self.visited:
                continue
            if not url_utils.is_same_site(normalized, self.config.seed_url, include_subdomains=self.config.include_subdomains):
                continue
            self.visited.add(normalized)
            candidates.append(normalized)
            if len(candidates) >= remaining_budget:
                break

        if not candidates:
            return

        tasks = [self._process_url(client, robots_info, semaphore, url, depth=0) for url in candidates]
        processed = await asyncio.gather(*tasks)
        for page, _discovered in processed:
            page.is_orphan = True
            page.add_issue(
                IssueCategory.LINKS,
                IssueSeverity.WARNING,
                "orphan_page",
                "Página encontrada en el sitemap pero sin ningún enlace interno hacia ella.",
            )
            self.pages.append(page)
            await _maybe_await(on_page, page)
            await _maybe_await(on_progress, len(self.pages), self.config.max_pages)

    async def _start_browser(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch()

    async def _stop_browser(self) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None

    async def _process_url(
        self,
        client: httpx.AsyncClient,
        robots_info: robots.RobotsInfo,
        semaphore: asyncio.Semaphore,
        url: str,
        depth: int,
    ) -> tuple[PageResult, list[tuple[str, int]]]:
        async with semaphore:
            if self.config.respect_robots and not robots.is_allowed(robots_info, url, self.config.user_agent):
                page = PageResult(url=url, depth=depth, error="Bloqueado por robots.txt")
                page.add_issue(
                    IssueCategory.SITEMAP_ROBOTS,
                    IssueSeverity.INFO,
                    "blocked_by_robots",
                    "Esta URL fue descubierta pero no se rastreó por estar bloqueada en robots.txt.",
                )
                return page, []

            start = time.monotonic()
            response, chain, error = await _fetch_with_redirect_chain(client, url)
            fetch_time_ms = (time.monotonic() - start) * 1000

            page = PageResult(url=url, depth=depth, fetch_time_ms=fetch_time_ms, redirect_chain=chain)

            if response is None:
                page.error = error
                page.issues = issues_mod.collect_page_issues(page, self.priority_urls)
                return page, []

            page.status_code = response.status_code
            page.final_url = str(response.url)
            page.headers = dict(response.headers)
            page.content_type = response.headers.get("content-type", "")
            page.x_robots_tag = response.headers.get("x-robots-tag", "")

            discovered: list[tuple[str, int]] = []

            if "text/html" in page.content_type and response.status_code == 200:
                html = response.text
                page.raw_html = html
                analysis = html_analysis.analyze_html(html, page.final_url)
                page.title = analysis.title
                page.meta_description = analysis.meta_description
                page.h1 = analysis.h1
                page.h2 = analysis.h2
                page.canonical = analysis.canonical
                page.meta_robots = analysis.meta_robots
                page.hreflang = analysis.hreflang
                page.json_ld_types = analysis.json_ld_types
                page.word_count = analysis.word_count
                page.content_hash = analysis.content_hash
                page.outlinks = analysis.outlinks
                page.tech = tech_detect.detect_tech(html, page.headers)

                visible_text = _visible_text(html)
                page.is_soft_404 = detect_soft_404(page.status_code, page.title, visible_text, page.word_count)

                outlinks_for_discovery = list(analysis.outlinks)

                if self.config.render_js and self._browser is not None:
                    rendered_outlinks = await self._run_render_checks(page)
                    seen_targets = {link.target for link in outlinks_for_discovery}
                    for link in rendered_outlinks:
                        if link.target not in seen_targets:
                            outlinks_for_discovery.append(link)
                            seen_targets.add(link.target)
                    page.outlinks = outlinks_for_discovery

                for link in outlinks_for_discovery:
                    if not link.is_internal:
                        continue
                    if not self.config.include_subdomains and not url_utils.is_same_site(
                        page.final_url, link.target, include_subdomains=False
                    ):
                        continue
                    discovered.append((link.target, depth + 1))

            page.issues = issues_mod.collect_page_issues(page, self.priority_urls)
            return page, discovered

    async def _run_render_checks(self, page: PageResult) -> list[LinkEdge]:
        """Render the page with a real browser, compare it against the raw
        HTML, and return the links found in the rendered DOM so JS-only
        sites (SPAs with no <a href> in the raw HTML) can still be crawled."""
        desktop = await render_check.render_with_browser(self._browser, page.final_url, render_check.DESKTOP_VIEWPORT)
        mobile = await render_check.render_with_browser(
            self._browser,
            page.final_url,
            render_check.MOBILE_VIEWPORT,
            user_agent=render_check.MOBILE_USER_AGENT,
        )

        if desktop.error:
            page.render = render_check.RenderInfo(error=desktop.error)
            return []

        rendered_analysis = html_analysis.analyze_html(desktop.html, page.final_url)
        render_info = render_check.compare_raw_vs_rendered(
            page.title,
            page.meta_description,
            page.h1,
            desktop.html,
            page.final_url,
            rendered_analysis=rendered_analysis,
        )
        render_info.lcp_ms = desktop.lcp_ms
        render_info.cls = desktop.cls
        render_info.fcp_ms = desktop.fcp_ms

        if not mobile.error:
            desktop_text = _visible_text(desktop.html)
            mobile_text = _visible_text(mobile.html)
            render_info.mobile_desktop_match = render_check.compare_mobile_desktop(desktop_text, mobile_text)

        page.render = render_info
        return rendered_analysis.outlinks

    async def _run_site_wide_checks(self, client: httpx.AsyncClient, result: CrawlResult) -> None:
        crawled_urls = [p.final_url or p.url for p in self.pages if p.status_code is not None]
        result.site_issues.extend(url_utils.check_site_wide_url_consistency(crawled_urls))

        status_by_url = {(p.final_url or p.url): p.status_code for p in self.pages if p.status_code is not None}
        result.site_issues.extend(
            sitemap.validate_sitemap_urls(
                result.sitemap_urls,
                self.config.seed_url,
                status_by_url=status_by_url,
                crawled_urls=set(crawled_urls),
            )
        )

        content_pairs = [(p.url, p.content_hash) for p in self.pages if p.status_code == 200]
        title_pairs = [(p.url, p.title) for p in self.pages if p.status_code == 200]
        meta_pairs = [(p.url, p.meta_description) for p in self.pages if p.status_code == 200]
        dup_content = duplicates.find_duplicate_content(content_pairs)
        dup_titles = duplicates.find_duplicate_titles(title_pairs)
        dup_meta = duplicates.find_duplicate_meta_descriptions(meta_pairs)
        for page in self.pages:
            page.issues.extend(duplicates.issues_for_url(page.url, dup_content, dup_titles, dup_meta))
        result.duplicate_content_groups = dup_content
        result.duplicate_title_groups = dup_titles
        result.duplicate_meta_groups = dup_meta

        await self._check_https_and_tls(client, result)

    async def _check_https_and_tls(self, client: httpx.AsyncClient, result: CrawlResult) -> None:
        parsed = urlparse(self.config.seed_url)
        host = parsed.netloc or parsed.path

        http_url = url_utils.swap_scheme(self.config.seed_url, "http")
        response, chain, error = await _fetch_with_redirect_chain(client, http_url)
        if response is not None:
            final_url = str(response.url)
            result.site_issues.extend(security.check_http_to_https_redirect(chain, final_url))
        elif error:
            result.site_issues.append(
                Issue(
                    IssueCategory.SECURITY,
                    IssueSeverity.WARNING,
                    "http_check_failed",
                    f"No se pudo verificar el redirect HTTP→HTTPS: {error}",
                )
            )

        loop = asyncio.get_running_loop()
        tls_info = await loop.run_in_executor(None, security.get_tls_info, url_utils.strip_www(host))
        result.site_issues.extend(security.check_tls_validity(tls_info))


async def crawl(
    config: CrawlConfig,
    on_page: OnPage | None = None,
    on_progress: OnProgress | None = None,
    stop_flag: StopFlag | None = None,
) -> CrawlResult:
    crawler = Crawler(config)
    return await crawler.run(on_page=on_page, on_progress=on_progress, stop_flag=stop_flag)
