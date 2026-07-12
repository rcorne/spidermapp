"""Google Search Console integration — not implemented yet (v2).

This module is a placeholder for the checks that can't be done by crawling
the site directly and instead require Google's own data:

  - Cobertura de índice (Index Coverage report)
  - Confirmación de que el sitemap fue enviado y procesado en GSC
  - Fuentes de tráfico / impresiones y clics por URL

Setup needed before this can be built out:
  1. Create a project in Google Cloud Console.
  2. Enable the "Google Search Console API".
  3. Create OAuth 2.0 credentials (Desktop app type) and download the
     client secret JSON.
  4. Verify site ownership for the property in Search Console under the
     same Google account used for the OAuth consent.

Once those credentials exist, this module should:
  - Run an installed-app OAuth flow (e.g. via google-auth-oauthlib) and
    cache the refresh token locally.
  - Wrap the `searchconsole` REST API (sites, sitemaps, urlInspection,
    searchanalytics.query) with functions mirroring the style of
    spidermapp.core.robots / sitemap: a pure parser for API responses and
    a thin async fetch layer, so results can feed into PageResult /
    CrawlResult the same way the rest of the crawler does.
"""

from __future__ import annotations


class GscNotConfigured(Exception):
    """Raised by any GSC call until OAuth credentials are wired up."""


def is_configured() -> bool:
    return False


def get_index_coverage(site_url: str):
    raise GscNotConfigured(
        "La integración con Google Search Console todavía no está configurada. "
        "Ver spidermapp/gsc/client.py para los pasos de setup (proyecto en Google "
        "Cloud, credenciales OAuth, verificación de propiedad)."
    )


def get_sitemap_status(site_url: str):
    raise GscNotConfigured(
        "La integración con Google Search Console todavía no está configurada."
    )


def get_traffic_sources(site_url: str):
    raise GscNotConfigured(
        "La integración con Google Search Console todavía no está configurada."
    )
