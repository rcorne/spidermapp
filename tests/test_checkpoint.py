import json
import time

from spidermapp.core import checkpoint


def _sample(seed="https://ejemplo.com/", **kwargs):
    defaults = dict(
        visited=["https://ejemplo.com/", "https://ejemplo.com/a"],
        frontier=[("https://ejemplo.com/b", 1), ("https://ejemplo.com/c", 2)],
        pages_done=2,
        sitemap_total=40,
    )
    defaults.update(kwargs)
    return checkpoint.CrawlCheckpoint(seed_url=seed, **defaults)


def test_save_and_load_roundtrip(tmp_path):
    original = _sample()
    checkpoint.save(original, checkpoint_dir=tmp_path)
    loaded = checkpoint.load("https://ejemplo.com/", checkpoint_dir=tmp_path)

    assert loaded is not None
    assert loaded.seed_url == original.seed_url
    assert loaded.visited == original.visited
    assert loaded.frontier == original.frontier  # tuples survive the JSON list roundtrip
    assert loaded.pages_done == 2
    assert loaded.sitemap_total == 40


def test_load_missing_returns_none(tmp_path):
    assert checkpoint.load("https://nada.com/", checkpoint_dir=tmp_path) is None


def test_corrupt_checkpoint_returns_none_instead_of_raising(tmp_path):
    path = checkpoint.checkpoint_path("https://ejemplo.com/", tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json at all")
    assert checkpoint.load("https://ejemplo.com/", checkpoint_dir=tmp_path) is None


def test_checkpoint_missing_keys_returns_none(tmp_path):
    path = checkpoint.checkpoint_path("https://ejemplo.com/", tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"visited": []}))  # no seed_url
    assert checkpoint.load("https://ejemplo.com/", checkpoint_dir=tmp_path) is None


def test_same_domain_shares_one_checkpoint_regardless_of_path(tmp_path):
    a = checkpoint.checkpoint_path("https://ejemplo.com/blog/", tmp_path)
    b = checkpoint.checkpoint_path("https://www.ejemplo.com/otra", tmp_path)
    assert a == b


def test_resumable_requires_pending_work(tmp_path):
    assert _sample().is_resumable
    assert not _sample(frontier=[]).is_resumable


def test_old_checkpoint_is_stale_and_not_resumable():
    old = _sample(saved_at=time.time() - checkpoint.MAX_AGE_SECONDS - 60)
    assert old.is_stale
    assert not old.is_resumable


def test_clear_removes_the_file(tmp_path):
    checkpoint.save(_sample(), checkpoint_dir=tmp_path)
    checkpoint.clear("https://ejemplo.com/", checkpoint_dir=tmp_path)
    assert checkpoint.load("https://ejemplo.com/", checkpoint_dir=tmp_path) is None


def test_clear_on_missing_file_is_a_noop(tmp_path):
    checkpoint.clear("https://nunca.com/", checkpoint_dir=tmp_path)  # must not raise


def test_find_resumable_lists_only_unfinished_recent_crawls(tmp_path):
    checkpoint.save(_sample("https://uno.com/"), checkpoint_dir=tmp_path)
    checkpoint.save(_sample("https://dos.com/", frontier=[]), checkpoint_dir=tmp_path)  # finished
    checkpoint.save(
        _sample("https://tres.com/", saved_at=time.time() - checkpoint.MAX_AGE_SECONDS - 60),
        checkpoint_dir=tmp_path,
    )  # stale

    seeds = {c.seed_url for c in checkpoint.find_resumable(checkpoint_dir=tmp_path)}
    assert seeds == {"https://uno.com/"}


def test_find_resumable_on_missing_dir_returns_empty(tmp_path):
    assert checkpoint.find_resumable(checkpoint_dir=tmp_path / "nope") == []


def test_save_leaves_no_temp_file_behind(tmp_path):
    checkpoint.save(_sample(), checkpoint_dir=tmp_path)
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_overwrites_previous_checkpoint_for_same_site(tmp_path):
    checkpoint.save(_sample(pages_done=2), checkpoint_dir=tmp_path)
    checkpoint.save(_sample(pages_done=99), checkpoint_dir=tmp_path)
    loaded = checkpoint.load("https://ejemplo.com/", checkpoint_dir=tmp_path)
    assert loaded.pages_done == 99
    assert len(list(tmp_path.glob("*.json"))) == 1
