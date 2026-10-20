"""Branch monitoring checkpoints, retries, serialization and actual Git file diffs."""
from types import SimpleNamespace
import subprocess

import pytest

from apps.api import repo_sync as sync, repo_connector as rc, runner


@pytest.fixture
def connected(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, 'CLONE_ROOT', tmp_path / 'clones')
    monkeypatch.setattr(sync, '_active', None)
    monkeypatch.setattr(runner, 'status', lambda: {'state': 'idle'})
    folder = rc.CLONE_ROOT / 'aspire-bmi'
    folder.mkdir(parents=True)
    sync.register('aspire/bmi', 'https://github.com/example/bmi', folder,
                  {'branch': 'main', 'head': 'a' * 40})
    monkeypatch.setattr(rc, 'run_git', lambda *a, **kw: 'https://github.com/example/bmi')
    return folder


def test_checkpoint_waits_for_success_and_survives_restart(connected, monkeypatch):
    batch = rc.CommitBatch('a' * 40, 'b' * 40, modified=['App.java'], deleted=['Old.java'], added=['New.java'])
    monkeypatch.setattr(rc, 'fetch_new', lambda *a: batch)
    applied = []
    monkeypatch.setattr(rc, 'apply_batch', lambda *a: applied.append(a) or {
        'modified': ['aspire/bmi:App.java'], 'deleted': ['aspire/bmi:Old.java'], 'added': ['aspire/bmi:New.java']})
    proc = SimpleNamespace(returncode=None)
    proc.poll = lambda: proc.returncode
    launched = []
    def start(params):
        launched.append(params)
        monkeypatch.setitem(runner._state, 'proc', proc)
    monkeypatch.setattr(runner, 'start', start)
    sync.sync_once()
    assert launched[0]['code_changed'] == ['aspire/bmi:App.java', 'aspire/bmi:Old.java', 'aspire/bmi:New.java']
    assert launched[0]['code_added'] == ['aspire/bmi:New.java']
    assert sync.load()['aspire/bmi']['head'] == 'a' * 40
    assert sync.status('aspire/bmi')['state'] == 'checking'
    sync.sync_once()
    assert len(applied) == 1
    # On a server restart a pending diff is replayed rather than silently lost.
    monkeypatch.setattr(sync, '_active', None)
    sync.sync_once()
    assert len(applied) == 2
    proc.returncode = 0
    sync.sync_once()
    assert sync.load()['aspire/bmi']['head'] == 'b' * 40
    assert sync.status('aspire/bmi')['state'] == 'watching'
    assert 'folder' not in sync.status('aspire/bmi')


def test_busy_pipeline_does_not_fetch_or_update_graph(connected, monkeypatch):
    monkeypatch.setattr(runner, 'status', lambda: {'state': 'running'})
    monkeypatch.setattr(rc, 'fetch_new', lambda *a: pytest.fail('must not fetch during analysis'))
    sync.sync_once()
    assert sync.load()['aspire/bmi']['head'] == 'a' * 40


def test_failed_fetch_preserves_checkpoint_and_reports_error(connected, monkeypatch):
    def fail(*a):
        raise rc.ConnectorError('Network unavailable')
    monkeypatch.setattr(rc, 'fetch_new', fail)
    sync.sync_once()
    record = sync.status('aspire/bmi')
    assert record['head'] == 'a' * 40
    assert record['state'] == 'error'
    assert record['error'] == 'Network unavailable'


def test_failed_drift_check_retries_original_diff(connected, monkeypatch):
    proc = SimpleNamespace(returncode=1, poll=lambda: 1)
    monkeypatch.setattr(sync, '_active', ('aspire/bmi', 'b' * 40, proc))
    sync.sync_once()
    assert sync.status('aspire/bmi')['head'] == 'a' * 40
    assert sync.status('aspire/bmi')['state'] == 'error'


def test_non_source_commit_advances_without_launching_ai(connected, monkeypatch):
    monkeypatch.setattr(rc, 'fetch_new', lambda *a: rc.CommitBatch('a' * 40, 'b' * 40))
    monkeypatch.setattr(rc, 'apply_batch', lambda *a: {'modified': [], 'added': [], 'deleted': []})
    monkeypatch.setattr(runner, 'start', lambda *a: pytest.fail('no AI for documentation-only commit'))
    sync.sync_once()
    assert sync.status('aspire/bmi')['head'] == 'b' * 40


def test_real_git_diff_updates_modified_added_and_deleted_files(tmp_path, monkeypatch):
    origin = tmp_path / 'origin'
    origin.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-c', 'user.name=test', '-c', 'user.email=t@example.com',
                                       '-c', 'commit.gpgsign=false', '-C', str(origin), *args], text=True).strip()
    git('init', '-q', '-b', 'main')
    (origin / 'App.java').write_text('class App { int x = 1; }')
    (origin / 'Old.java').write_text('class Old {}')
    git('add', '.')
    git('commit', '-qm', 'initial')
    clone = tmp_path / 'clone'
    info = rc.clone(str(origin), clone, allow_local=True)
    (origin / 'App.java').write_text('class App { int x = 2; }')
    (origin / 'Old.java').unlink()
    (origin / 'New.py').write_text('def added(): return True')
    git('add', '-A')
    git('commit', '-qm', 'change sources')
    batch = rc.fetch_new(clone, info['head'], 'main', allow_local=True)
    assert batch.modified == ['App.java']
    assert batch.deleted == ['Old.java']
    assert batch.added == ['New.py']
    assert batch.commits[0]['message'] == 'change sources'
    calls = []
    monkeypatch.setattr(rc, 'update_files', lambda key, files, driver: calls.append(('modified', files)))
    monkeypatch.setattr(rc, 'write_files', lambda key, files, driver: calls.append(('added', files)))
    monkeypatch.setattr(rc, 'mark_deleted', lambda key, paths, driver: calls.append(('deleted', paths)))
    changed = rc.apply_batch(clone, 'aspire/bmi', batch)
    assert calls[0][1][0].text == 'class App { int x = 2; }'
    assert changed['deleted'] == ['aspire/bmi:Old.java']
    assert rc.fetch_new(clone, batch.head, 'main', allow_local=True) is None


def test_real_commits_empty_then_revert_recover_link_and_close_decay(tmp_path, monkeypatch):
    from agents.traceability_agent.decay import DecayDetector
    from agents.traceability_agent.utils import content_hash
    from shared.schemas.traceability import Artifact, TraceabilityLink
    from shared.uskg.memory import InMemoryUSKG
    from unittest.mock import MagicMock
    origin = tmp_path / 'origin'
    origin.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-c', 'user.name=test', '-c', 'user.email=t@example.com',
                                       '-c', 'commit.gpgsign=false', '-C', str(origin), *args], text=True).strip()
    git('init', '-q', '-b', 'main')
    original = 'class Calculator { double bmi(double w, double h) { return w / (h*h); } }'
    (origin / 'Calculator.java').write_text(original)
    git('add', '.')
    git('commit', '-qm', 'initial')
    clone = tmp_path / 'clone'
    head = rc.clone(str(origin), clone, allow_local=True)['head']
    req = Artifact(id='R1', type='requirement', text='Calculate BMI using weight divided by height squared.')
    code = Artifact(id='p:Calculator.java', type='code', text=original)
    link = TraceabilityLink(source_id=req.id, target_id=code.id, link_type='requirement_to_code',
                            confidence=0.9, justification='BMI formula', text_hash=content_hash(req, code))
    store = InMemoryUSKG([req, code], [link])
    def update(key, files, driver):
        for file in files:
            store.artifacts[f'{key}:{file.path}'] = code.model_copy(update={'text': file.text})
    monkeypatch.setattr(rc, 'update_files', update)
    llm = MagicMock()
    detector = DecayDetector(store, llm)
    for text, message, broken in [('', 'remove implementation', True), (original, 'revert implementation', False)]:
        (origin / 'Calculator.java').write_text(text)
        git('add', '.')
        git('commit', '-qm', message)
        batch = rc.fetch_new(clone, head, 'main', allow_local=True)
        changes = rc.apply_batch(clone, 'p', batch)
        assert changes['modified'] == [code.id]
        result, = detector.run(only_targets=set(changes['modified']))
        assert result.decayed is broken
        head = batch.head
    llm.verify_link.assert_not_called()
    assert store.get_traces()[0].status == 'verified'
    assert len(store.decay_flags) == 1 and store.decay_flags[0]['resolved']
