from spidermapp.core import render_check
from spidermapp.core.models import RenderInfo


def test_texts_match_identical():
    assert render_check.texts_match("hola mundo", "hola mundo")


def test_texts_match_similar_enough():
    assert render_check.texts_match("hola mundo hoy", "hola mundo hoy!")


def test_texts_match_different():
    assert not render_check.texts_match("contenido para desktop " * 20, "otra cosa totalmente distinta")


def test_compare_raw_vs_rendered_detects_title_mismatch():
    rendered_html = "<html><head><title>Título distinto</title></head><body></body></html>"
    info = render_check.compare_raw_vs_rendered(
        raw_title="Título original",
        raw_description="",
        raw_h1=[],
        rendered_html=rendered_html,
        page_url="https://example.com/",
    )
    assert not info.raw_vs_rendered_title_match


def test_compare_raw_vs_rendered_match():
    rendered_html = "<html><head><title>Mismo título</title></head><body><h1>H1</h1></body></html>"
    info = render_check.compare_raw_vs_rendered(
        raw_title="Mismo título",
        raw_description="",
        raw_h1=["H1"],
        rendered_html=rendered_html,
        page_url="https://example.com/",
    )
    assert info.raw_vs_rendered_title_match
    assert info.raw_vs_rendered_h1_match


def test_check_rendering_reports_error():
    render = RenderInfo(error="timeout")
    assert render_check.check_rendering(render)[0].code == "render_failed"


def test_check_rendering_reports_mismatches():
    render = RenderInfo(
        raw_vs_rendered_title_match=False,
        raw_vs_rendered_desc_match=False,
        raw_vs_rendered_h1_match=False,
        mobile_desktop_match=False,
    )
    codes = {i.code for i in render_check.check_rendering(render)}
    assert codes == {
        "render_title_mismatch",
        "render_description_mismatch",
        "render_h1_mismatch",
        "mobile_desktop_mismatch",
    }


def test_check_rendering_no_issues_when_clean():
    assert render_check.check_rendering(RenderInfo()) == []


def test_check_rendering_none_returns_empty():
    assert render_check.check_rendering(None) == []
