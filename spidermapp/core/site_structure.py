from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from spidermapp.core.models import PageResult
from spidermapp.core.url_utils import registrable_domain


@dataclass
class StructureNode:
    """One node of the site tree: a host (domain/subdomain) or a path segment."""

    label: str
    url: str = ""
    page: PageResult | None = None
    children: dict[str, "StructureNode"] = field(default_factory=dict)

    def child(self, label: str) -> "StructureNode":
        if label not in self.children:
            self.children[label] = StructureNode(label=label)
        return self.children[label]

    @property
    def descendant_count(self) -> int:
        return len(self.children) + sum(c.descendant_count for c in self.children.values())


def build_site_tree(pages: list[PageResult], seed_url: str) -> StructureNode:
    """Domain → subdomains → path-segment hierarchy.

    Hosts come both from crawled pages and from internal outlink targets, so
    subdomains that were linked but not crawled still show up in the tree.
    """
    root_domain = registrable_domain(seed_url) or urlparse(seed_url).netloc
    root = StructureNode(label=root_domain)

    def host_node(host: str) -> StructureNode:
        return root.child(host)

    def add_url(url: str, page: PageResult | None) -> None:
        parsed = urlparse(url)
        if not parsed.netloc:
            return
        if registrable_domain(url) != root_domain:
            return
        node = host_node(parsed.netloc.lower())
        segments = [seg for seg in parsed.path.split("/") if seg]
        for seg in segments:
            node = node.child(seg)
        if not node.url:
            node.url = url
        if page is not None:
            node.page = page

    for page in pages:
        add_url(page.final_url or page.url, page)
        for link in page.outlinks:
            if link.is_internal:
                add_url(link.target, None)

    return root
