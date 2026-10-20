"""Single-user local dashboard GitHub App authentication and durable push inbox."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apps.api import repo_connector as rc


class GitHubError(ValueError):
    pass


def jwt():
    key = os.getenv('GITHUB_APP_PRIVATE_KEY_PATH', '')
    issuer = os.getenv('GITHUB_APP_CLIENT_ID') or os.getenv('GITHUB_APP_ID')
    if not key or not issuer or not Path(key).is_file():
        raise GitHubError('Configure the GitHub App ID and private key path on the server.')
    def b64(data):
        return base64.urlsafe_b64encode(data).rstrip(b'=')
    stamp = int(time.time())
    message = b'.'.join(b64(json.dumps(part, separators=(',', ':')).encode()) for part in (
        {'alg': 'RS256', 'typ': 'JWT'}, {'iat': stamp - 60, 'exp': stamp + 540, 'iss': issuer}))
    signed = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', key], input=message, capture_output=True)
    if signed.returncode:
        raise GitHubError('The configured GitHub App private key could not sign a request.')
    return (message + b'.' + b64(signed.stdout)).decode()


def api(path, token=None, body=None):
    if not path.startswith('/') or path.startswith('//'):
        raise GitHubError('Invalid GitHub API path.')
    request = Request('https://api.github.com' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + (token or jwt()), 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2026-03-10', 'User-Agent': 'Aspire-C4', 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        raise GitHubError(f'GitHub returned {exc.code}. Check App installation and repository permissions.') from None
    except (URLError, TimeoutError):
        raise GitHubError('Cannot reach GitHub. Check your connection.') from None


def installation_token(installation_id):
    if not str(installation_id).isdigit():
        raise GitHubError('Invalid GitHub installation ID.')
    return api(f'/app/installations/{int(installation_id)}/access_tokens', body={})['token']


def repository_access(url):
    owner_repo, _ = rc.parse_github_url(url)
    info = api('/repos/' + owner_repo + '/installation')
    return int(info['id'])


def configuration():
    configured = bool(os.getenv('GITHUB_APP_ID') and os.getenv('GITHUB_APP_PRIVATE_KEY_PATH'))
    if not configured:
        return {'configured': False}
    info = api('/app')
    return {'configured': True, 'name': info['name'], 'installUrl': info['html_url'] + '/installations/new',
            'webhookConfigured': bool(os.getenv('GITHUB_WEBHOOK_SECRET'))}


def repositories():
    found = []
    page = 1
    while True:
        installations = api(f'/app/installations?per_page=100&page={page}')
        for installation in installations:
            if installation.get('suspended_at'):
                continue
            token = installation_token(installation['id'])
            repo_page = 1
            while True:
                result = api(f'/installation/repositories?per_page=100&page={repo_page}', token=token)
                rows = result['repositories']
                found.extend({'name': r['full_name'], 'url': r['html_url'], 'defaultBranch': r['default_branch'],
                              'installationId': installation['id'], 'private': r['private']} for r in rows)
                if len(rows) < 100:
                    break
                repo_page += 1
        if len(installations) < 100:
            break
        page += 1
    return {'repositories': sorted(found, key=lambda r: r['name'].lower())}


@contextmanager
def inbox():
    rc.CLONE_ROOT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(rc.CLONE_ROOT / 'webhooks.sqlite', timeout=5)
    db.execute('CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, payload TEXT NOT NULL, processed INTEGER NOT NULL DEFAULT 0)')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def receive(raw, headers):
    secret = os.getenv('GITHUB_WEBHOOK_SECRET')
    if not secret:
        raise GitHubError('Webhook receiver is not configured.')
    expected = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, headers.get('X-Hub-Signature-256', '')):
        raise GitHubError('Invalid webhook signature.')
    event = headers.get('X-GitHub-Event', '')
    if event == 'ping':
        return {'accepted': True, 'event': 'ping'}
    if event != 'push':
        return {'accepted': False, 'ignored': True}
    try:
        data = json.loads(raw)
        delivery = headers.get('X-GitHub-Delivery', '')
        repo = data['repository']['full_name']
        installation = int(data['installation']['id'])
        ref = data['ref']
        if not re.fullmatch(r'[A-Za-z0-9-]{1,100}', delivery) or not isinstance(ref, str):
            raise ValueError()
        rc.parse_github_url('https://github.com/' + repo)
        payload = {'repository': repo, 'installation': installation, 'ref': ref,
                   'deleted': bool(data.get('deleted')),
                   'receivedAt': datetime.now(timezone.utc).isoformat()}
    except (ValueError, KeyError, TypeError, rc.ConnectorError):
        raise GitHubError('Invalid push payload.') from None
    with inbox() as db:
        cursor = db.execute('INSERT OR IGNORE INTO deliveries (id, payload) VALUES (?, ?)',
                            (delivery, json.dumps(payload)))
        duplicate = cursor.rowcount == 0
    from apps.api import repo_sync
    repo_sync.wake.set()
    return {'accepted': True, 'duplicate': duplicate}


def drain():
    """Move durable events into project queues; unrelated repos and branches are ignored."""
    from apps.api import repo_sync
    with inbox() as db:
        rows = db.execute('SELECT id, payload FROM deliveries WHERE processed = 0 ORDER BY rowid LIMIT 100').fetchall()
    for delivery, payload in rows:
        event = json.loads(payload)
        with repo_sync._lock:
            records = repo_sync.load()
            for record in records.values():
                if (record.get('installationId') == event['installation']
                    and record['url'].removeprefix('https://github.com/').lower() == event['repository'].lower()
                    and event['ref'] == 'refs/heads/' + record['branch']):
                    record['lastDelivery'] = delivery
                    record['lastWebhookAt'] = event.get('receivedAt') or repo_sync.now()
                    if event['deleted']:
                        record.update(state='error', error='Connected branch was deleted. Reconnect to another branch.')
                    else:
                        record.update(pending=True, queuedVersion=record.get('queuedVersion', 0) + 1)
            repo_sync.save(records)
        with inbox() as db:
            db.execute('UPDATE deliveries SET processed = 1 WHERE id = ?', (delivery,))


def connect(project):
    from apps.api import repo_sync
    with repo_sync._lock:
        record = repo_sync.load().get(project)
        if not record:
            raise GitHubError('Select a connected GitHub project first.')
        url = record['url']
    installation = repository_access(url)
    with repo_sync._lock:
        records = repo_sync.load()
        record = records[project]
        record.update(installationId=installation, mode='webhook', pending=True,
                      queuedVersion=record.get('queuedVersion', 0) + 1)
        repo_sync.save(records)
    repo_sync.wake.set()
    return {'connected': True, 'mode': 'webhook'}


def start_receiver():
    """Expose only signed webhooks on a dedicated port suitable for a public tunnel."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    class WebhookHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != '/api/github/webhook':
                self.send_error(404)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 25 * 1024 * 1024:
                    self.send_error(413)
                    return
                response = receive(self.rfile.read(size), self.headers)
                body = json.dumps(response).encode()
                self.send_response(202)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (GitHubError, ValueError) as exc:
                self.send_error(400, str(exc))

    server = ThreadingHTTPServer(('127.0.0.1', int(os.getenv('GITHUB_WEBHOOK_PORT', '8001'))), WebhookHandler)
    threading.Thread(target=server.serve_forever, name='github-webhooks', daemon=True).start()
    return server
