from spidermapp.core import app_settings


def test_load_settings_missing_file_returns_defaults(tmp_path):
    settings = app_settings.load_settings(tmp_path / "settings.json")
    assert settings.default_max_pages == 500
    assert settings.default_max_depth == 10
    assert settings.default_concurrency == 8
    assert settings.default_render_js is False


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    original = app_settings.AppSettings(default_max_pages=1000, default_max_depth=5, default_concurrency=16, default_render_js=True)
    app_settings.save_settings(original, path)
    loaded = app_settings.load_settings(path)
    assert loaded == original


def test_load_settings_ignores_unknown_keys(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"default_max_pages": 42, "unknown_key": "ignored"}')
    settings = app_settings.load_settings(path)
    assert settings.default_max_pages == 42
    assert settings.default_max_depth == 10


def test_load_settings_corrupt_file_returns_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("not valid json {{{")
    settings = app_settings.load_settings(path)
    assert settings.default_max_pages == 500
