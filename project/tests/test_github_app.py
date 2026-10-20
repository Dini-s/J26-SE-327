"""Signed push ingress, durable deduplication, branch filtering and GitHub App auth."""
import base64
import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

from apps.api import github_app as app, repo_sync as sync, repo_connector as rc, runner


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, 'CLONE_ROOT', tmp_path / 'repos')
    monkeypatch.setenv('GITHUB_WEBHOOK_SECRET', 'test-secret')
    sync.register('aspire/demo', 'https://github.com/example/demo', rc.CLONE_ROOT / 'aspire-demo',
                  {'branch': 'main', 'head': 'a' * 40}, installation_id=42)
    sync.wake.clear()
    return monkeypatch


def send(payload=None, delivery='delivery-1', event='push', secret='test-secret'):
    payload = payload or {'repository': {'full_name': 'example/demo'}, 'installation': {'id': 42}, 'ref': 'refs/heads/main'}
    raw = json.dumps(payload).encode()
    headers = {'X-GitHub-Event': event, 'X-GitHub-Delivery': delivery,
               'X-Hub-Signature-256': 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()}
    return app.receive(raw, headers)


def test_valid_push_is_durable_deduplicated_and_queues_matching_branch(setup):
    assert send()['accepted']
    assert sync.wake.is_set()
    assert send()['duplicate']
    # No graph fetch or AI work is performed inside the HTTP request.
    assert not sync.load()['aspire/demo']['pending']
    app.drain()
    record = sync.load()['aspire/demo']
    assert record['pending'] and record['queuedVersion'] == 1
    assert record['lastWebhookAt']
    assert record['lastDelivery'] == 'delivery-1'
    app.drain()
    assert sync.load()['aspire/demo']['queuedVersion'] == 1


@pytest.mark.parametrize('field,value', [('ref', 'refs/heads/develop'), ('ref', 'refs/tags/v1'),
                                         ('installation', {'id': 99}), ('repository', {'full_name': 'example/other'})])
def test_other_repositories_installations_and_branches_are_ignored(setup, field, value):
    payload = {'repository': {'full_name': 'example/demo'}, 'installation': {'id': 42}, 'ref': 'refs/heads/main'}
    payload[field] = value
    send(payload)
    app.drain()
    assert not sync.load()['aspire/demo']['pending']


def test_wrong_signature_cannot_queue_work(setup):
    with pytest.raises(app.GitHubError, match='signature'):
        send(secret='wrong')
    assert not sync.load()['aspire/demo']['pending']


def test_ping_and_unsubscribed_events_do_not_queue_scans(setup):
    assert send(event='ping')['event'] == 'ping'
    assert send(event='issues')['ignored']
    app.drain()
    assert not sync.load()['aspire/demo']['pending']


def test_webhook_mode_does_not_fetch_without_an_event(setup):
    setup.setattr(runner, 'status', lambda: {'state': 'idle'})
    setup.setattr(sync, '_active', None)
    setup.setattr(rc, 'fetch_new', lambda *a, **kw: pytest.fail('webhook mode must not poll remote'))
    sync.sync_once()


def test_push_during_active_analysis_stays_queued_after_completion(setup):
    with sync._lock:
        records = sync.load()
        records['aspire/demo'].update(activeVersion=1, queuedVersion=1, pending=True)
        sync.save(records)
    send()
    app.drain()
    proc = SimpleNamespace(returncode=0, poll=lambda: 0)
    setup.setattr(sync, '_active', ('aspire/demo', 'b' * 40, proc))
    sync.sync_once()
    record = sync.load()['aspire/demo']
    assert record['head'] == 'b' * 40 and record['pending']


def test_jwt_has_expected_claims_and_keeps_key_out_of_arguments(tmp_path, monkeypatch):
    key = tmp_path / 'key.pem'
    key.write_text('fake-key')
    monkeypatch.setenv('GITHUB_APP_PRIVATE_KEY_PATH', str(key))
    monkeypatch.setenv('GITHUB_APP_CLIENT_ID', 'client-id')
    captured = []
    def sign(command, **kwargs):
        captured.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=b'signature')
    monkeypatch.setattr(app.subprocess, 'run', sign)
    token = app.jwt()
    header, claims, signature = token.split('.')
    decode = lambda value: json.loads(base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)))
    assert decode(header)['alg'] == 'RS256'
    assert decode(claims)['iss'] == 'client-id'
    assert decode(claims)['exp'] - decode(claims)['iat'] == 600
    assert 'fake-key' not in str(captured)


def test_git_installation_token_uses_environment_not_command_or_remote(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout='ok', stderr='')
    monkeypatch.setattr(rc.subprocess, 'run', run)
    rc.run_git(['fetch', 'origin', 'main'], auth_token='secret-token')
    command, kwargs = calls[0]
    assert 'secret-token' not in str(command)
    assert kwargs['env']['GIT_CONFIG_KEY_0'] == 'http.https://github.com/.extraheader'
    assert kwargs['env']['GIT_CONFIG_VALUE_0'].startswith('AUTHORIZATION: basic ')


def test_receiver_accepts_signed_push_but_does_not_expose_dashboard_routes(setup):
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    setup.setenv('GITHUB_WEBHOOK_PORT', '0')
    server = app.start_receiver()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        raw = json.dumps({'repository': {'full_name': 'example/demo'}, 'installation': {'id': 42},
                          'ref': 'refs/heads/main'}).encode()
        signature = 'sha256=' + hmac.new(b'test-secret', raw, hashlib.sha256).hexdigest()
        request = Request(base + '/api/github/webhook', data=raw, headers={
            'X-Hub-Signature-256': signature, 'X-GitHub-Event': 'push', 'X-GitHub-Delivery': 'http-test'})
        with urlopen(request) as response:
            assert response.status == 202
            assert json.load(response)['accepted']
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base + '/api/import', data=b'{}'))
        assert error.value.code == 404
        request = Request(base + '/api/github/webhook', data=raw, headers={'X-Hub-Signature-256': 'bad'})
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
