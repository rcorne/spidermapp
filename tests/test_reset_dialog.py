"""The reset dialog is the one destructive surface in the app, so its
selection defaults get tests even though the other widgets don't."""

import json

import pytest
from PySide6.QtWidgets import QApplication

from spidermapp.gui.reset_dialog import CONFIRM_WORD, ResetDataDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def populated(tmp_path):
    (tmp_path / "history" / "ejemplo.com").mkdir(parents=True)
    (tmp_path / "history" / "ejemplo.com" / "a.json").write_text("{}")
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": []}))
    (tmp_path / "connectors.json").write_text(json.dumps({"api_key": "secret"}))
    (tmp_path / "auth_providers.json").write_text("{}")
    (tmp_path / "settings.json").write_text("{}")
    return tmp_path


def test_credentials_and_settings_are_never_preselected(qt_app, populated):
    """Wiping API keys and OAuth client IDs means revisiting several developer
    consoles — it must only ever happen because someone ticked it on purpose."""
    dialog = ResetDataDialog(base_dir=populated)
    selected = dialog.selected_keys()
    assert "credentials" not in selected
    assert "settings" not in selected
    assert "history" in selected
    assert "tasks" in selected


def test_targets_with_nothing_stored_are_disabled(qt_app, populated):
    dialog = ResetDataDialog(base_dir=populated)
    # Nothing was written for these in the fixture.
    assert not dialog._checkboxes["checkpoints"].isEnabled()
    assert not dialog._checkboxes["brand_visibility"].isEnabled()
    assert dialog._checkboxes["history"].isEnabled()


def test_empty_targets_are_never_returned_as_selected(qt_app, tmp_path):
    dialog = ResetDataDialog(base_dir=tmp_path)
    assert dialog.selected_keys() == []


def test_confirm_button_is_disabled_when_nothing_is_selected(qt_app, tmp_path):
    dialog = ResetDataDialog(base_dir=tmp_path)
    dialog.confirm_input.setText(CONFIRM_WORD)
    assert not dialog._confirm_button.isEnabled()


def test_confirm_button_stays_disabled_until_the_word_is_typed(qt_app, populated):
    """Regression: with things pre-checked and no typing required, a single
    stray Enter was enough to wipe everything."""
    dialog = ResetDataDialog(base_dir=populated)
    assert dialog.selected_keys(), "targets should be pre-selected"
    assert not dialog._confirm_button.isEnabled()

    dialog.confirm_input.setText("borra")
    assert not dialog._confirm_button.isEnabled()

    dialog.confirm_input.setText(CONFIRM_WORD)
    assert dialog._confirm_button.isEnabled()

    for box in dialog._checkboxes.values():
        box.setChecked(False)
    assert not dialog._confirm_button.isEnabled()


def test_confirm_word_is_case_insensitive(qt_app, populated):
    dialog = ResetDataDialog(base_dir=populated)
    dialog.confirm_input.setText(CONFIRM_WORD.lower())
    assert dialog._confirm_button.isEnabled()


def test_enter_key_never_reaches_the_destructive_button(qt_app, populated):
    """Qt wires an AcceptRole button to Enter by default; on a destructive
    dialog that turned a keypress into data loss."""
    dialog = ResetDataDialog(base_dir=populated)
    assert not dialog._confirm_button.autoDefault()
    assert not dialog._confirm_button.isDefault()


def test_backup_is_on_by_default(qt_app, populated):
    assert ResetDataDialog(base_dir=populated).wants_backup()


def test_amount_label_names_sites_for_history(qt_app, populated):
    dialog = ResetDataDialog(base_dir=populated)
    status = next(s for s in dialog._statuses if s.target.key == "history")
    assert "1 sitio" in dialog._describe_amount(status)


def test_amount_label_flags_empty_targets(qt_app, tmp_path):
    dialog = ResetDataDialog(base_dir=tmp_path)
    status = next(s for s in dialog._statuses if s.target.key == "history")
    assert "Vacío" in dialog._describe_amount(status)
