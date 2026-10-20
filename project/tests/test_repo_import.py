"""Adding a project from a GitHub URL or a local folder. No network, no real Neo4j: a fake driver records the writes."""

import subprocess
from pathlib import Path

import pytest

from apps.api import repo_connector as rc, repo_import as ri


class FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, **params):
        self.calls.append((query, params))
        return [{"n": len(params.get("rows") or [])}], None, None

    def close(self):
        pass


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(ri, "HOME", tmp_path.resolve())
    monkeypatch.setattr(ri, "taken_keys", lambda: set())
    monkeypatch.setattr(rc, "_guard_local", lambda: None)
    return tmp_path


def make_project(root: Path):
    (root / "src").mkdir(parents=True)
    (root / "src" / "App.java").write_text("class App { void login() { check(password); } }\n")
    (root / "src" / "util.py").write_text("def pay(card):\n    return charge(card)\n")
    (root / "README.md").write_text("# not code\n")
    return root


# ---------------------------------------------------------------- local folders
def test_a_folder_inside_home_is_imported_under_a_local_key(home):
    folder = make_project(home / "my-shop")
    driver = FakeDriver()
    result = ri.import_folder(str(folder), None, driver)
    assert result["key"] == "local/my-shop" and result["files"] == 2 and result["name"] == "my-shop"
    query, params = driver.calls[0]
    assert params["project"] == "local/my-shop"
    assert {r["id"] for r in params["rows"]} == {"local/my-shop:src/App.java", "local/my-shop:src/util.py"}


def test_a_folder_outside_home_is_refused(home, tmp_path_factory):
    outside = make_project(tmp_path_factory.mktemp("elsewhere") / "x")
    with pytest.raises(ri.ImportError_, match="inside your home folder"):
        ri.import_folder(str(outside), None, FakeDriver())


def test_a_symlink_that_points_outside_home_is_refused(home, tmp_path_factory):
    outside = make_project(tmp_path_factory.mktemp("elsewhere") / "x")
    link = home / "sneaky"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ri.ImportError_, match="inside your home folder"):
        ri.import_folder(str(link), None, FakeDriver())


@pytest.mark.parametrize("bad", ["", None, 5, "/definitely/not/here/xyz"])
def test_bad_folder_paths_are_refused_with_a_clear_message(home, bad):
    with pytest.raises(ri.ImportError_):
        ri.import_folder(bad, None, FakeDriver())


def test_a_file_is_not_a_folder(home):
    f = home / "note.txt"
    f.write_text("hi")
    with pytest.raises(ri.ImportError_, match="not a folder"):
        ri.import_folder(str(f), None, FakeDriver())


def test_a_folder_without_source_files_is_refused(home):
    empty = home / "docs-only"
    empty.mkdir()
    (empty / "readme.md").write_text("hi")
    with pytest.raises(ri.ImportError_, match="No source files"):
        ri.import_folder(str(empty), None, FakeDriver())


def test_a_second_import_with_the_same_name_gets_a_new_key(home, monkeypatch):
    folder = make_project(home / "shop")
    taken = {"local/shop"}
    monkeypatch.setattr(ri, "taken_keys", lambda: taken)
    result = ri.import_folder(str(folder), None, FakeDriver())
    assert result["key"] == "local/shop-2"


# ---------------------------------------------------------------- GitHub
def test_github_urls_are_validated_before_anything_runs(home, monkeypatch):
    called = []
    monkeypatch.setattr(rc, "clone", lambda *a, **k: called.append(a))
    for bad in ("git@github.com:octo/shop.git", "file:///etc", "https://evil.com/o/r", "", None):
        with pytest.raises(ri.ImportError_):
            ri.import_github(bad, None, None, FakeDriver())
    assert called == []


def test_github_import_clones_then_ingests(home, tmp_path, monkeypatch):
    origin = make_project(tmp_path / "origin")
    subprocess.run(["git", "init", "-q", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x.org", "-c", "commit.gpgsign=false", "-C", str(origin), "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x.org", "-c", "commit.gpgsign=false", "-C", str(origin), "commit", "-qm", "first"], check=True)
    monkeypatch.setattr(rc, "CLONE_ROOT", tmp_path / "clones")
    # the real clone is only allowed from github.com; the test points the same code at a local repository
    real_clone = rc.clone
    monkeypatch.setattr(rc, "clone", lambda url, dest, branch=None, allow_local=False: real_clone(str(origin), dest, branch, allow_local=True))
    driver = FakeDriver()
    result = ri.import_github("https://github.com/octo/shop", None, None, driver)
    assert result["key"] == "aspire/shop" and result["files"] == 2 and result["name"] == "Aspire/shop"
    assert driver.calls and driver.calls[0][1]["project"] == "aspire/shop"


def test_a_failed_clone_writes_nothing(home, tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "CLONE_ROOT", tmp_path / "clones")
    driver = FakeDriver()
    with pytest.raises(ri.ImportError_):
        ri.import_github("https://github.com/octo/does-not-exist-xyz", None, None, driver)
    assert driver.calls == []


def test_folder_chooser_lists_only_visible_directories_inside_home(home, tmp_path_factory):
    (home / 'Zoo').mkdir()
    (home / 'alpha').mkdir()
    (home / '.hidden').mkdir()
    (home / 'file.txt').write_text('not a folder')
    outside = tmp_path_factory.mktemp('outside-browser')
    (home / 'escape').symlink_to(outside, target_is_directory=True)
    result = ri.browse_folders()
    assert result['path'] == str(home)
    assert result['parent'] is None
    assert [item['name'] for item in result['folders']] == ['alpha', 'Zoo']
    child = ri.browse_folders(str(home / 'alpha'))
    assert child['parent'] == str(home)
    assert child['folders'] == []
    with pytest.raises(ri.ImportError_, match='inside your home folder'):
        ri.browse_folders(str(home / 'escape'))


def test_empty_source_is_imported_so_drift_sees_removed_implementation(tmp_path):
    (tmp_path / "App.java").write_text("")
    source = rc.read_source(tmp_path, "App.java")
    assert source is not None and source.text == ""
