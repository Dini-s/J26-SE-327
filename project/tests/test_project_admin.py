"""Project deletion scoping, synchronization guards and local-file boundaries."""
from contextlib import contextmanager
from types import SimpleNamespace
import json

import pytest

from apps.api import project_admin as admin, repo_connector as rc, repo_sync as sync, runner, sources, labeling


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, 'CLONE_ROOT', tmp_path / 'repos')
    monkeypatch.setattr(rc, '_guard_local', lambda: None)
    monkeypatch.setattr(runner, 'status', lambda: {'state': 'idle'})
    monkeypatch.setattr(sync, '_active', None)
    monkeypatch.setattr(sources, 'RUNS_DIR', tmp_path / 'runs')
    monkeypatch.setattr(labeling, 'LABELS_DIR', tmp_path / 'labels')
    folder = rc.CLONE_ROOT / 'aspire-target'
    folder.mkdir(parents=True)
    (folder / 'App.java').write_text('class App {}')
    sync.register('aspire/target', 'https://github.com/example/target', folder,
                  {'branch': 'main', 'head': 'a' * 40})
    monkeypatch.setattr(sources, 'neo4j_projects', lambda: [{'project': 'aspire/target'}, {'project': 'other'}])
    calls = []
    class Tx:
        def run(self, query, **params):
            calls.append((query, params))
            return SimpleNamespace(consume=lambda: SimpleNamespace(counters=SimpleNamespace(nodes_deleted=4, relationships_deleted=3)))
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute_write(self, fn, project): return fn(Tx(), project)
    class Driver:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def session(self): return Session()
    monkeypatch.setattr(sources, '_neo4j_driver', Driver)
    return tmp_path, folder, calls, monkeypatch


def test_delete_removes_only_selected_clone_history_and_connection(setup):
    root, folder, calls, _ = setup
    other_clone = rc.CLONE_ROOT / 'other'
    other_clone.mkdir()
    for name, project in [('target-run', 'aspire/target'), ('other-run', 'other')]:
        run = sources.RUNS_DIR / name
        run.mkdir(parents=True)
        (run / 'events.jsonl').write_text(json.dumps({'type': 'run_start', 'project': project})+'\n')
    original = root / 'original-project'
    original.mkdir()
    result = admin.delete_project('aspire/target', 'aspire/target')
    assert result['nodes'] == 4 and result['relationships'] == 3
    assert calls[0][1] == {'project': 'aspire/target'}
    assert not folder.exists() and other_clone.exists() and original.exists()
    assert not (sources.RUNS_DIR / 'target-run').exists()
    assert (sources.RUNS_DIR / 'other-run').exists()
    assert 'aspire/target' not in sync.load()


def test_delete_is_rejected_without_exact_confirmation(setup):
    _, folder, calls, _ = setup
    with pytest.raises(admin.ProjectError, match='Confirm'):
        admin.delete_project('aspire/target', 'other')
    assert folder.exists() and not calls


def test_active_analysis_blocks_deletion(setup):
    _, folder, calls, monkeypatch = setup
    monkeypatch.setattr(runner, 'status', lambda: {'state': 'running'})
    with pytest.raises(admin.ProjectError, match='analysis'):
        admin.delete_project('aspire/target', 'aspire/target')
    assert folder.exists() and not calls


def test_database_failure_restores_connection_and_keeps_clone(setup):
    _, folder, calls, monkeypatch = setup
    def fail(): raise RuntimeError('database unavailable')
    monkeypatch.setattr(sources, '_neo4j_driver', fail)
    with pytest.raises(RuntimeError):
        admin.delete_project('aspire/target', 'aspire/target')
    assert sync.load()['aspire/target']['enabled'] is True
    assert folder.exists() and not calls


def test_external_folder_is_never_deleted(setup):
    root, _, calls, _ = setup
    original = root / 'original-project'
    original.mkdir()
    records = sync.load()
    records['aspire/target']['folder'] = str(original)
    sync.save(records)
    with pytest.raises(admin.ProjectError, match='path'):
        admin.delete_project('aspire/target', 'aspire/target')
    assert original.exists() and not calls


def test_unknown_project_is_rejected(setup):
    with pytest.raises(admin.ProjectError, match='no longer exists'):
        admin.delete_project('unknown', 'unknown')
