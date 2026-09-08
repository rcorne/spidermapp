import json

import pytest

from spidermapp.core import data_reset


@pytest.fixture
def populated(tmp_path):
    """A ~/.spidermapp lookalike with something in every target."""
    (tmp_path / "history" / "ejemplo.com").mkdir(parents=True)
    (tmp_path / "history" / "ejemplo.com" / "2026-01-01.json").write_text('{"pages": []}')
    (tmp_path / "history" / "otro.com").mkdir(parents=True)
    (tmp_path / "history" / "otro.com" / "2026-01-02.json").write_text('{"pages": []}')

    (tmp_path / "checkpoints").mkdir()
    (tmp_path / "checkpoints" / "ejemplo.com.json").write_text("{}")

    (tmp_path / "brand_visibility").mkdir()
    (tmp_path / "brand_visibility" / "run.json").write_text("{}")

    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [{"id": "a"}]}))
    (tmp_path / "settings.json").write_text(json.dumps({"theme": "light"}))
    (tmp_path / "connectors.json").write_text(json.dumps({"key": "secret"}))
    (tmp_path / "auth_providers.json").write_text(json.dumps({"google": {}}))
    (tmp_path / "session.json").write_text("{}")
    (tmp_path / "pidge_session.json").write_text("{}")
    return tmp_path


def test_inventory_reports_what_exists(populated):
    by_key = {s.target.key: s for s in data_reset.inventory(populated)}

    assert by_key["history"].exists
    assert by_key["history"].item_count == 2  # two sites
    assert by_key["history"].size_bytes > 0
    assert by_key["tasks"].exists
    assert by_key["credentials"].exists
    assert by_key["credentials"].item_count == 4  # four credential files


def test_inventory_on_empty_dir_reports_nothing(tmp_path):
    for status in data_reset.inventory(tmp_path):
        assert not status.exists
        assert status.item_count == 0


def test_reset_removes_only_the_selected_targets(populated):
    data_reset.reset(["history", "tasks"], populated, backup=False)

    assert not (populated / "history").exists()
    assert not (populated / "tasks.json").exists()
    # Untouched:
    assert (populated / "checkpoints").exists()
    assert (populated / "settings.json").exists()
    assert (populated / "connectors.json").exists()


def test_credentials_target_removes_every_related_file(populated):
    data_reset.reset(["credentials"], populated, backup=False)

    assert not (populated / "connectors.json").exists()
    assert not (populated / "auth_providers.json").exists()
    assert not (populated / "session.json").exists()
    assert not (populated / "pidge_session.json").exists()
    # Data targets are a different concern and must survive.
    assert (populated / "history").exists()


def test_reset_reports_how_many_files_it_removed(populated):
    report = data_reset.reset(["history", "tasks"], populated, backup=False)
    assert report.removed["history"] == 2
    assert report.removed["tasks"] == 1
    assert report.total_files == 3


def test_reset_of_everything_leaves_the_base_dir_itself(populated):
    data_reset.reset([t.key for t in data_reset.TARGETS], populated, backup=False)
    assert populated.exists(), "the base folder must survive so the app can write again"
    assert list(populated.iterdir()) == []


def test_reset_on_missing_paths_is_a_noop(tmp_path):
    report = data_reset.reset(["history", "tasks"], tmp_path, backup=False)
    assert report.removed == {"history": 0, "tasks": 0}


def test_unknown_target_is_rejected(populated):
    with pytest.raises(data_reset.ResetError, match="desconocido"):
        data_reset.reset(["history", "no-existe"], populated, backup=False)
    assert (populated / "history").exists(), "nothing should be deleted when the request is invalid"


def test_a_target_escaping_the_base_dir_is_refused(tmp_path, monkeypatch):
    """The containment check is the guard that stops a malformed target from
    deleting something outside Pidge's own folder."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "importante.txt").write_text("no me borres")

    base = tmp_path / "base"
    base.mkdir()

    escaping = data_reset.ResetTarget(
        key="escaping",
        label="x",
        description="x",
        relative_paths=("../outside",),
    )
    monkeypatch.setitem(data_reset.TARGETS_BY_KEY, "escaping", escaping)

    with pytest.raises(data_reset.ResetError, match="fuera de"):
        data_reset.reset(["escaping"], base, backup=False)
    assert (outside / "importante.txt").exists()


def test_a_target_pointing_at_the_base_dir_is_refused(tmp_path, monkeypatch):
    base = tmp_path / "base"
    base.mkdir()
    (base / "algo.json").write_text("{}")

    whole_dir = data_reset.ResetTarget(key="whole", label="x", description="x", relative_paths=(".",))
    monkeypatch.setitem(data_reset.TARGETS_BY_KEY, "whole", whole_dir)

    with pytest.raises(data_reset.ResetError, match="carpeta base"):
        data_reset.reset(["whole"], base, backup=False)
    assert (base / "algo.json").exists()


def test_credentials_are_not_selected_by_default():
    """Losing API keys and OAuth client IDs means revisiting several developer
    consoles, so it must never ride along with a routine data reset."""
    by_key = {t.key: t for t in data_reset.TARGETS}
    assert not by_key["credentials"].default_selected
    assert not by_key["settings"].default_selected
    assert by_key["history"].default_selected
    assert by_key["tasks"].default_selected


@pytest.mark.parametrize(
    "size,expected",
    [(512, "512 B"), (2048, "2 KB"), (5 * 1024 * 1024, "5.0 MB")],
)
def test_format_size(size, expected):
    assert data_reset.format_size(size) == expected


# --- backups: the difference between "reset" and "lost forever" -------------


def test_backup_is_on_by_default_and_moves_data_aside(populated):
    """Crawl history records what a site looked like on a given day; no
    re-crawl brings back last month's snapshot. So the default must preserve
    it, not destroy it."""
    report = data_reset.reset(["history", "tasks"], populated)

    assert report.backup_path is not None
    assert not (populated / "history").exists()
    # ...but it still exists inside the backup.
    assert (report.backup_path / "history" / "ejemplo.com" / "2026-01-01.json").exists()
    assert (report.backup_path / "tasks.json").exists()


def test_backup_false_really_deletes(populated):
    report = data_reset.reset(["history"], populated, backup=False)
    assert report.backup_path is None
    assert not (populated / "history").exists()
    assert data_reset.list_backups(populated) == []


def test_a_backup_folder_is_never_itself_a_reset_target(populated, monkeypatch):
    """Otherwise a second reset would eat the safety net from the first."""
    data_reset.reset(["history"], populated)
    backup = data_reset.list_backups(populated)[0]

    eats_backup = data_reset.ResetTarget(
        key="eats", label="x", description="x", relative_paths=(backup.name,)
    )
    monkeypatch.setitem(data_reset.TARGETS_BY_KEY, "eats", eats_backup)

    with pytest.raises(data_reset.ResetError, match="respaldo"):
        data_reset.reset(["eats"], populated, backup=False)
    assert backup.exists()


def test_list_backups_returns_newest_first(populated):
    data_reset.reset(["history"], populated)
    data_reset.reset(["tasks"], populated)
    backups = data_reset.list_backups(populated)
    assert len(backups) >= 1
    assert backups == sorted(backups, reverse=True)


def test_inventory_ignores_backup_folders(populated):
    """A backup must not show up as something to delete."""
    data_reset.reset(["history"], populated)
    for status in data_reset.inventory(populated):
        for path in status.paths:
            assert not path.name.startswith(data_reset.BACKUP_PREFIX)
