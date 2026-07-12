from spidermapp.core import duplicates


def test_find_duplicate_content_groups_shared_hashes():
    pairs = [("/a", "hash1"), ("/b", "hash1"), ("/c", "hash2")]
    groups = duplicates.find_duplicate_content(pairs)
    assert groups == {"hash1": ["/a", "/b"]}


def test_find_duplicate_content_ignores_empty_keys():
    pairs = [("/a", ""), ("/b", "")]
    assert duplicates.find_duplicate_content(pairs) == {}


def test_find_duplicate_titles():
    pairs = [("/a", "Título X"), ("/b", "Título X"), ("/c", "Título Y")]
    assert duplicates.find_duplicate_titles(pairs) == {"Título X": ["/a", "/b"]}


def test_issues_for_url_reports_all_three_kinds():
    content_groups = {"h1": ["/a", "/b"]}
    title_groups = {"t1": ["/a", "/c"]}
    meta_groups = {"m1": ["/a", "/d"]}
    issues = duplicates.issues_for_url("/a", content_groups, title_groups, meta_groups)
    codes = {i.code for i in issues}
    assert codes == {"duplicate_content", "duplicate_title", "duplicate_meta_description"}


def test_issues_for_url_no_duplicates():
    assert duplicates.issues_for_url("/z", {}, {}, {}) == []
