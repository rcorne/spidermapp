from spidermapp.core import soft_404


def test_detect_soft_404_true_for_thin_not_found_page():
    assert soft_404.detect_soft_404(
        status_code=200,
        title="Página no encontrada",
        visible_text_sample="Lo sentimos, no se encontró la página que buscas.",
        word_count=10,
    )


def test_detect_soft_404_false_for_normal_200_page():
    assert not soft_404.detect_soft_404(
        status_code=200,
        title="Nuestros productos",
        visible_text_sample="Aquí encontrarás el catálogo completo de productos disponibles.",
        word_count=500,
    )


def test_detect_soft_404_false_for_real_404_status():
    assert not soft_404.detect_soft_404(
        status_code=404,
        title="Página no encontrada",
        visible_text_sample="no se encontró",
        word_count=10,
    )


def test_check_soft_404_produces_issue():
    assert soft_404.check_soft_404(True)[0].code == "soft_404"
    assert soft_404.check_soft_404(False) == []
