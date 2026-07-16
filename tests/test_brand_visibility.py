import json
import time

import pytest

from spidermapp.core import brand_visibility as bv


def _config(**overrides):
    defaults = dict(
        target=bv.Brand(name="MarcaX", domain="marcax.com", aliases=["Marca X"]),
        competitors=[bv.Brand(name="Rival Uno", domain="rivaluno.com"), bv.Brand(name="Rival Dos", domain="rivaldos.com")],
        category="farmacias online",
        market="Colombia",
        providers=["openai"],
    )
    defaults.update(overrides)
    return bv.BrandVisibilityConfig(**defaults)


def test_detect_mentions_orders_by_first_appearance():
    config = _config()
    text = "Te recomiendo Rival Dos primero, y también MarcaX es una buena opción."
    mentions = bv.detect_mentions(text, config.all_brands())
    assert [m.brand for m in mentions] == ["Rival Dos", "MarcaX"]
    assert mentions[0].position == 1
    assert mentions[1].position == 2


def test_detect_mentions_matches_alias_and_domain():
    config = _config()
    text = "Puedes visitar marcax.com o buscar Marca X en internet."
    mentions = bv.detect_mentions(text, config.all_brands())
    assert len(mentions) == 1
    assert mentions[0].brand == "MarcaX"
    assert mentions[0].is_domain_citation


def test_detect_mentions_respects_word_boundaries():
    config = _config(competitors=[bv.Brand(name="Uno", domain="")])
    text = "El número uno de la lista no es una marca."
    mentions = bv.detect_mentions(text, config.all_brands())
    # "Uno" appears as a standalone word here, so this *is* a real match —
    # the boundary check exists to prevent partial-word false positives like
    # "unofrecuente" matching "Uno", not to filter homonyms.
    assert any(m.brand == "Uno" for m in mentions)


def test_detect_mentions_no_false_positive_on_substring():
    config = _config(competitors=[bv.Brand(name="Cruz", domain="")])
    text = "La cruzada continúa sin cruzverde en la lista."
    mentions = bv.detect_mentions(text, config.all_brands())
    assert not any(m.brand == "Cruz" for m in mentions)


def _analysis(provider, intent, mentions, framing=None, web_search=False, error=""):
    response = bv.RawResponse(
        provider=provider, query="q", intent=intent, repetition=0, web_search=web_search, temperature=0.7, text="x", error=error
    )
    return bv.ResponseAnalysis(response=response, mentions=mentions, framing=framing or {})


def test_compute_brand_stats_mention_rate_and_share_of_voice():
    config = _config()
    analyses = [
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 1), bv.Mention("Rival Uno", 2)]),
        _analysis("openai", "comparativa", [bv.Mention("Rival Uno", 1)]),
        _analysis("openai", "comparativa", []),
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 1)]),
    ]
    stats = {s.brand: s for s in bv.compute_brand_stats(analyses, config)}

    assert stats["MarcaX"].mention_rate == pytest.approx(0.5)
    assert stats["Rival Uno"].mention_rate == pytest.approx(0.5)
    assert stats["Rival Dos"].mention_rate == 0.0
    # 4 total brand mentions across all responses; MarcaX and Rival Uno each account for 2.
    assert stats["MarcaX"].share_of_voice == pytest.approx(0.5)
    assert stats["Rival Uno"].share_of_voice == pytest.approx(0.5)


def test_compute_brand_stats_avg_position_only_over_mentioning_responses():
    config = _config(competitors=[bv.Brand(name="Rival Uno", domain="")])
    analyses = [
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 3)]),
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 1)]),
        _analysis("openai", "comparativa", []),  # no mention: excluded from avg position
    ]
    stats = {s.brand: s for s in bv.compute_brand_stats(analyses, config)}
    assert stats["MarcaX"].avg_position == pytest.approx(2.0)
    assert stats["Rival Uno"].avg_position is None


def test_compute_brand_stats_domain_citation_rate_only_from_web_search_series():
    config = _config(competitors=[])
    analyses = [
        _analysis("perplexity", "comparativa", [bv.Mention("MarcaX", 1, is_domain_citation=True)], web_search=True),
        _analysis("perplexity", "comparativa", [bv.Mention("MarcaX", 1, is_domain_citation=False)], web_search=True),
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 1, is_domain_citation=True)], web_search=False),
    ]
    stats = {s.brand: s for s in bv.compute_brand_stats(analyses, config)}
    # Only the 2 web_search=True responses count toward the denominator.
    assert stats["MarcaX"].domain_citation_rate == pytest.approx(0.5)


def test_compute_brand_stats_no_web_search_responses_gives_none():
    config = _config(competitors=[])
    analyses = [_analysis("openai", "comparativa", [bv.Mention("MarcaX", 1)], web_search=False)]
    stats = {s.brand: s for s in bv.compute_brand_stats(analyses, config)}
    assert stats["MarcaX"].domain_citation_rate is None


def test_compute_brand_stats_framing_distribution():
    config = _config(competitors=[])
    analyses = [
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 1)], framing={"MarcaX": "positivo"}),
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 1)], framing={"MarcaX": "positivo"}),
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 1)], framing={"MarcaX": "negativo"}),
    ]
    stats = {s.brand: s for s in bv.compute_brand_stats(analyses, config)}
    dist = stats["MarcaX"].framing_distribution
    assert dist["positivo"] == pytest.approx(2 / 3)
    assert dist["negativo"] == pytest.approx(1 / 3)
    assert dist["neutro"] == 0.0


def test_extract_json_strips_markdown_fence():
    text = '```json\n{"a": [1, 2]}\n```'
    assert bv._extract_json(text) == {"a": [1, 2]}


def test_generate_query_battery_parses_all_intents(monkeypatch):
    payload = {intent: [f"{intent} paráfrasis {i}" for i in range(2)] for intent in bv.INTENT_TYPES}

    def fake_ask_llm(provider, prompt, temperature=0.7):
        return json.dumps(payload)

    monkeypatch.setattr(bv.connectors, "ask_llm", fake_ask_llm)
    templates = bv.generate_query_battery("farmacias online", "Colombia", "openai", n=2)
    assert len(templates) == len(bv.INTENT_TYPES) * 2
    assert {t.intent for t in templates} == set(bv.INTENT_TYPES)


def test_generate_query_battery_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr(bv.connectors, "ask_llm", lambda *a, **k: "not json at all")
    with pytest.raises(ValueError):
        bv.generate_query_battery("x", "y", "openai")


def test_classify_framing_extracts_known_label(monkeypatch):
    monkeypatch.setattr(bv.connectors, "ask_llm", lambda *a, **k: "positivo")
    assert bv.classify_framing("openai", "MarcaX", "texto") == "positivo"


def test_classify_framing_falls_back_to_neutro_on_error(monkeypatch):
    def raise_err(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(bv.connectors, "ask_llm", raise_err)
    assert bv.classify_framing("openai", "MarcaX", "texto") == "neutro"


def test_classify_framing_falls_back_to_neutro_on_unrecognized_answer(monkeypatch):
    monkeypatch.setattr(bv.connectors, "ask_llm", lambda *a, **k: "no lo sé")
    assert bv.classify_framing("openai", "MarcaX", "texto") == "neutro"


def test_run_battery_retries_then_succeeds(monkeypatch):
    config = _config(repetitions=1)
    queries = [bv.QueryTemplate(intent="comparativa", text="q")]
    calls = {"n": 0}

    def flaky_ask_llm(provider, prompt, temperature=0.7):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("rate limited")
        return "respuesta ok"

    monkeypatch.setattr(bv.connectors, "ask_llm", flaky_ask_llm)
    monkeypatch.setattr(bv.time, "sleep", lambda *_: None)
    responses = bv.run_battery(config, queries, request_delay=0)
    assert len(responses) == 1
    assert responses[0].text == "respuesta ok"
    assert not responses[0].error


def test_run_battery_records_error_after_exhausting_retries(monkeypatch):
    config = _config(repetitions=1)
    queries = [bv.QueryTemplate(intent="comparativa", text="q")]

    def always_fails(provider, prompt, temperature=0.7):
        raise RuntimeError("still down")

    monkeypatch.setattr(bv.connectors, "ask_llm", always_fails)
    monkeypatch.setattr(bv.time, "sleep", lambda *_: None)
    responses = bv.run_battery(config, queries, request_delay=0)
    assert len(responses) == 1
    assert responses[0].error == "still down"
    assert responses[0].text == ""


def test_run_battery_tags_perplexity_as_web_search(monkeypatch):
    config = _config(providers=["openai", "perplexity"], repetitions=1)
    queries = [bv.QueryTemplate(intent="comparativa", text="q")]
    monkeypatch.setattr(bv.connectors, "ask_llm", lambda *a, **k: "ok")
    responses = bv.run_battery(config, queries, request_delay=0)
    by_provider = {r.provider: r for r in responses}
    assert by_provider["openai"].web_search is False
    assert by_provider["perplexity"].web_search is True


def test_analyze_response_skips_mentions_and_framing_on_error():
    response = bv.RawResponse(
        provider="openai", query="q", intent="comparativa", repetition=0, web_search=False, temperature=0.7, error="boom"
    )
    analysis = bv.analyze_response(_config(), response)
    assert analysis.mentions == []
    assert analysis.framing == {}


def test_save_and_load_run_roundtrip(tmp_path):
    config = _config()
    analyses = [
        bv.ResponseAnalysis(
            response=bv.RawResponse(
                provider="openai", query="q1", intent="comparativa", repetition=0, web_search=False, temperature=0.7, text="respuesta"
            ),
            mentions=[bv.Mention("MarcaX", 1, is_domain_citation=True)],
            framing={"MarcaX": "positivo"},
        )
    ]
    report = bv.BrandVisibilityReport(config=config, created_at=time.time(), analyses=analyses)
    path = bv.save_run(report, storage_dir=tmp_path)
    assert path.exists()

    loaded = bv.load_run(path)
    assert loaded.config.target.name == "MarcaX"
    assert loaded.config.competitors[0].name == "Rival Uno"
    assert len(loaded.analyses) == 1
    assert loaded.analyses[0].response.text == "respuesta"
    assert loaded.analyses[0].mentions[0].brand == "MarcaX"
    assert loaded.analyses[0].framing == {"MarcaX": "positivo"}


def test_list_runs_orders_by_filename_timestamp(tmp_path):
    config = _config()
    for ts in (100.0, 300.0, 200.0):
        report = bv.BrandVisibilityReport(config=config, created_at=ts, analyses=[])
        bv.save_run(report, storage_dir=tmp_path)
    runs = bv.list_runs("MarcaX", storage_dir=tmp_path)
    assert [p.stem for p in runs] == ["100000", "200000", "300000"]


def test_list_runs_empty_when_no_directory(tmp_path):
    assert bv.list_runs("Nadie", storage_dir=tmp_path) == []


def test_export_csv_writes_header_and_rows(tmp_path):
    config = _config(competitors=[])
    analyses = [
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 1)], framing={"MarcaX": "positivo"}),
    ]
    report = bv.BrandVisibilityReport(config=config, created_at=time.time(), analyses=analyses)
    path = tmp_path / "out.csv"
    bv.export_csv(report, path)
    content = path.read_text(encoding="utf-8")
    assert "modelo" in content.splitlines()[0]
    assert "MarcaX" in content


def test_export_html_report_is_self_contained(tmp_path):
    config = _config()
    analyses = [
        _analysis("openai", "comparativa", [bv.Mention("MarcaX", 1), bv.Mention("Rival Uno", 2)], framing={"MarcaX": "positivo"}),
        _analysis("perplexity", "informacional", [bv.Mention("Rival Dos", 1, is_domain_citation=True)], web_search=True),
    ]
    report = bv.BrandVisibilityReport(config=config, created_at=time.time(), analyses=analyses)
    path = tmp_path / "report.html"
    bv.export_html_report(report, path)
    html = path.read_text(encoding="utf-8")
    assert "<html" in html
    assert "MarcaX" in html
    assert "Rival Dos" in html
    assert "<script" not in html
