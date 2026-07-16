import httpx
import pytest

from spidermapp.core import ai_visibility
from spidermapp.core.models import PageResult

ROBOTS_BLOCKING_GPTBOT = """
User-agent: GPTBot
Disallow: /

User-agent: *
Disallow:
"""


def test_check_robots_ai_bots_parses_per_bot_rules():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ROBOTS_BLOCKING_GPTBOT, headers={"content-type": "text/plain"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    found, access = ai_visibility._check_robots_ai_bots(client, "https://example.com/")
    assert found
    gptbot = next(b for b in access if b.bot == "GPTBot")
    assert not gptbot.allowed
    claudebot = next(b for b in access if b.bot == "ClaudeBot")
    assert claudebot.allowed


def test_check_robots_ai_bots_missing_defaults_to_all_allowed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    found, access = ai_visibility._check_robots_ai_bots(client, "https://example.com/")
    assert not found
    assert all(b.allowed for b in access)
    assert len(access) == len(ai_visibility.AI_BOTS)


def test_check_llms_txt_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="# llms.txt")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    found, url = ai_visibility._check_llms_txt(client, "https://example.com/")
    assert found
    assert url.endswith("/llms.txt")


def test_check_llms_txt_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    found, _ = ai_visibility._check_llms_txt(client, "https://example.com/")
    assert not found


def test_readiness_score_perfect_signals():
    report = ai_visibility.AiVisibilityReport(
        domain="example.com",
        bot_access=[ai_visibility.BotAccess("GPTBot", "x", True), ai_visibility.BotAccess("ClaudeBot", "x", True)],
        llms_txt_found=True,
        structured_data_pages=10,
        structured_data_total=10,
        meta_description_pages=10,
        meta_description_total=10,
        wikipedia_found=True,
    )
    assert report.readiness_score == 100


def test_readiness_score_all_blocked_and_missing():
    report = ai_visibility.AiVisibilityReport(
        domain="example.com",
        bot_access=[ai_visibility.BotAccess("GPTBot", "x", False), ai_visibility.BotAccess("ClaudeBot", "x", False)],
        llms_txt_found=False,
        structured_data_pages=0,
        structured_data_total=10,
        meta_description_pages=0,
        meta_description_total=10,
        wikipedia_found=False,
    )
    assert report.readiness_score == 0


def _page(url, status=200, json_ld=None, meta_description=""):
    return PageResult(url=url, status_code=status, json_ld_types=json_ld or [], meta_description=meta_description)


def test_analyze_aggregates_structured_data_and_meta_description(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content="User-agent: *\nDisallow:\n")
        if request.url.path == "/llms.txt":
            return httpx.Response(404)
        return httpx.Response(404)

    real_client_cls = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr(ai_visibility.httpx, "Client", fake_client)
    monkeypatch.setattr(ai_visibility.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("no network in test")))

    pages = [
        _page("https://example.com/a", json_ld=["Product"], meta_description="desc"),
        _page("https://example.com/b", json_ld=[], meta_description=""),
        _page("https://example.com/broken", status=404),
    ]
    report = ai_visibility.analyze("https://example.com/", pages)

    assert report.structured_data_total == 2  # only 200s count
    assert report.structured_data_pages == 1
    assert report.structured_data_types == ["Product"]
    assert report.meta_description_total == 2
    assert report.meta_description_pages == 1
    assert not report.wikipedia_found


def test_check_wikipedia_found(monkeypatch):
    def fake_get(url, params=None, timeout=None, headers=None):
        return httpx.Response(
            200,
            json=["cruzverde", ["Cruz Verde"], [""], ["https://es.wikipedia.org/wiki/Cruz_Verde"]],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(ai_visibility.httpx, "get", fake_get)
    found, title, url = ai_visibility._check_wikipedia("cruzverde")
    assert found
    assert title == "Cruz Verde"
    assert url == "https://es.wikipedia.org/wiki/Cruz_Verde"


def test_check_wikipedia_not_found(monkeypatch):
    def fake_get(url, params=None, timeout=None, headers=None):
        return httpx.Response(200, json=["zzzznotarealbrandzzzz", [], [], []], request=httpx.Request("GET", url))

    monkeypatch.setattr(ai_visibility.httpx, "get", fake_get)
    found, title, url = ai_visibility._check_wikipedia("zzzznotarealbrandzzzz")
    assert not found
    assert title == ""
