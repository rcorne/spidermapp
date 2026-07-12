from spidermapp.core import html_analysis


SAMPLE_HTML = """
<html>
<head>
  <title>Ejemplo de título de página con largo razonable</title>
  <meta name="description" content="Esta es una meta description con una longitud razonable para pasar el check de tamaño mínimo y máximo.">
  <link rel="canonical" href="https://example.com/pagina">
  <meta name="robots" content="index, follow">
  <link rel="alternate" hreflang="es" href="https://example.com/es/pagina">
  <script type="application/ld+json">{"@type": "Article", "headline": "x"}</script>
</head>
<body>
  <h1>Título principal</h1>
  <h2>Subtítulo</h2>
  <p>Contenido de la página con varias palabras para el conteo de palabras visible en el cuerpo.</p>
  <a href="/otra-pagina">Otra página</a>
  <a href="https://external.com/x">Externo</a>
  <a href="javascript:void(0)">JS link</a>
  <a href="#anchor">Anchor</a>
</body>
</html>
"""


def test_analyze_html_extracts_title_and_meta():
    result = html_analysis.analyze_html(SAMPLE_HTML, "https://example.com/pagina")
    assert result.title == "Ejemplo de título de página con largo razonable"
    assert "longitud razonable" in result.meta_description
    assert result.canonical == "https://example.com/pagina"
    assert result.meta_robots == "index, follow"
    assert result.h1 == ["Título principal"]
    assert result.h2 == ["Subtítulo"]
    assert result.hreflang == [("es", "https://example.com/es/pagina")]
    assert result.json_ld_types == ["Article"]


def test_analyze_html_extracts_links_and_skips_js_mailto_anchor():
    result = html_analysis.analyze_html(SAMPLE_HTML, "https://example.com/pagina")
    targets = {l.target for l in result.outlinks}
    assert "https://example.com/otra-pagina" in targets
    assert "https://external.com/x" in targets
    assert not any(t.startswith("javascript:") for t in targets)
    assert not any(t.startswith("#") for t in targets)

    internal = {l.target: l.is_internal for l in result.outlinks}
    assert internal["https://example.com/otra-pagina"] is True
    assert internal["https://external.com/x"] is False


def test_check_title_missing_and_length():
    assert html_analysis.check_title("")[0].code == "title_missing"
    assert html_analysis.check_title("short")[0].code == "title_too_short"
    assert html_analysis.check_title("x" * 100)[0].code == "title_too_long"
    assert html_analysis.check_title("Un título de longitud razonable y correcta") == []


def test_check_meta_description_missing_and_length():
    assert html_analysis.check_meta_description("")[0].code == "meta_description_missing"
    assert html_analysis.check_meta_description("short")[0].code == "meta_description_too_short"


def test_check_h1_missing_and_multiple():
    assert html_analysis.check_h1([])[0].code == "h1_missing"
    assert html_analysis.check_h1(["A", "B"])[0].code == "h1_multiple"
    assert html_analysis.check_h1(["Solo uno"]) == []


def test_check_directives_flags_noindex():
    issues = html_analysis.check_directives("noindex, follow")
    assert any(i.code == "noindex" for i in issues)


def test_check_canonical_flags_pointing_elsewhere():
    issues = html_analysis.check_canonical(
        "https://example.com/otra", "https://example.com/pagina", "https://example.com/pagina"
    )
    assert issues[0].code == "canonical_points_elsewhere"


def test_check_canonical_self_referencing_has_no_issue():
    issues = html_analysis.check_canonical(
        "https://example.com/pagina", "https://example.com/pagina", "https://example.com/pagina"
    )
    assert issues == []


def test_check_thin_content():
    assert html_analysis.check_thin_content(10)[0].code == "thin_content"
    assert html_analysis.check_thin_content(500) == []
