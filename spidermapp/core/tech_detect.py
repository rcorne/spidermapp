from __future__ import annotations

import re

# Each rule: (technology name, compiled pattern) tested against a lowercase
# haystack built from HTML, response headers, and cookie names.
_RULES: list[tuple[str, re.Pattern]] = [
    ("WordPress", re.compile(r"wp-content|wp-includes|/wp-json/", re.I)),
    ("WooCommerce", re.compile(r"woocommerce", re.I)),
    ("Shopify", re.compile(r"cdn\.shopify\.com|shopify\.com/s/|x-shopid", re.I)),
    ("Wix", re.compile(r"static\.wixstatic\.com|wix\.com", re.I)),
    ("Squarespace", re.compile(r"squarespace\.com|static1\.squarespace\.com", re.I)),
    ("Webflow", re.compile(r"webflow\.com|assets\.website-files\.com", re.I)),
    ("Drupal", re.compile(r"sites/default/files|/drupal\.js|x-generator: drupal", re.I)),
    ("Joomla", re.compile(r"/media/jui/|joomla", re.I)),
    ("Magento", re.compile(r"mage/cookies|magento", re.I)),
    ("PrestaShop", re.compile(r"prestashop", re.I)),
    ("Next.js", re.compile(r"__next_data__|/_next/static", re.I)),
    ("Nuxt.js", re.compile(r"__nuxt__|/_nuxt/", re.I)),
    ("React", re.compile(r"data-reactroot|react-dom", re.I)),
    ("Vue.js", re.compile(r"data-v-app|__vue__", re.I)),
    ("Angular", re.compile(r"ng-version", re.I)),
    ("Google Tag Manager", re.compile(r"googletagmanager\.com/gtm\.js", re.I)),
    ("Google Analytics", re.compile(r"google-analytics\.com|gtag\('config'", re.I)),
    ("Cloudflare", re.compile(r"cf-ray|cloudflare", re.I)),
    ("Nginx", re.compile(r"server: nginx", re.I)),
    ("Apache", re.compile(r"server: apache", re.I)),
]

_GENERATOR_RE = re.compile(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', re.I)


def detect_tech(html: str, headers: dict[str, str]) -> list[str]:
    header_blob = " ".join(f"{k}: {v}" for k, v in headers.items())
    haystack = f"{html} {header_blob}"

    found: list[str] = []
    for name, pattern in _RULES:
        if pattern.search(haystack):
            found.append(name)

    generator_match = _GENERATOR_RE.search(html)
    if generator_match:
        generator = generator_match.group(1).strip()
        if generator and generator not in found:
            found.append(generator)

    return found
