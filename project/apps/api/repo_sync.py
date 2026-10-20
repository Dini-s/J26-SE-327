"""Persist connected GitHub branches and poll them while the API is running."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from apps.api import repo_connector as rc, runner

INTERVAL = 60
_lock = threading.RLock()
_active = None
wake = threading.Event()


def now():
    return datetime.now(timezone.utc).isoformat()


def state_path():
    return rc.CLONE_ROOT / 'connections.json'


def load():
    path = state_path()
    return json.loads(path.read_text()) if path.exists() else {}


def save(records):
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(records, indent=2))
    temp.replace(path)


def register(key, url, folder, info, installation_id=None):
    with _lock:
        records = load()
        records[key] = dict(project=key, url=url, folder=str(folder), branch=info['branch'],
                            head=info['head'], enabled=True, state='watching', error=None,
                            checkedAt=None, syncedAt=now(), commits=[], installationId=installation_id,
                            mode='webhook' if installation_id else 'polling', pending=False)
        save(records)


def discover():
    """Recover connections imported before the watcher was installed; use only owned clones."""
    from apps.api import sources
    from apps.api.repo_import import slug
    with sources._neo4j_driver() as driver:
        rows, _, _ = driver.execute_query("MATCH (c:CodeEntity {source: 'repo-connector'}) RETURN DISTINCT c.project AS project")
    for row in rows:
        key = row['project']
        if not key or not key.startswith('aspire/'):
            continue
        with _lock:
            if key in load():
                continue
        folder = rc.CLONE_ROOT / slug(key.replace('/', '-'))
        if folder.is_symlink() or not (folder / '.git').is_dir():
            continue
        url = rc.run_git(['remote', 'get-url', 'origin'], cwd=folder).strip()
        _, url = rc.parse_github_url(url)
        info = {k: rc.run_git(args, cwd=folder).strip() for k, args in {
            'branch': ['rev-parse', '--abbrev-ref', 'HEAD'], 'head': ['rev-parse', 'HEAD']}.items()}
        register(key, url, folder, info)


def status(project):
    with _lock:
        record = load().get(project)
        if not record:
            return {'connected': False, 'interval': INTERVAL}
        return {'connected': True, 'interval': INTERVAL,
                **{k: v for k, v in record.items() if k != 'folder'}}


def sync_once(project=None):
    """Apply one repository update, then launch C4. Checkpoint only after C4 succeeds.

    On process failure or server restart the old checkpoint is retained, so the same diff is retried.
    The runner lock prevents a manual run racing graph updates or another launch.
    """
    global _active
    with _lock, runner.RUN_LOCK:
        records = load()
        if _active:
            key, head, proc = _active
            if proc.poll() is None:
                return
            record = records.get(key)
            if record:
                if proc.returncode == 0:
                    record.update(head=head, state='watching', error=None, syncedAt=now(),
                                  pending=record.get('queuedVersion', 0) > record.get('activeVersion', 0))
                else:
                    record.update(state='error', error='Drift check failed; it will retry. See the activity log.')
                save(records)
            _active = None
            return
        if runner.status()['state'] != 'idle':
            return
        for key, record in records.items():
            if not record.get('enabled') or (project and project != key):
                continue
            if record.get('mode') != 'webhook' and record.get('state') not in ('checking', 'syncing') and not project and record.get('checkedAt'):
                elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(record['checkedAt'])).total_seconds()
                if elapsed < INTERVAL:
                    continue
            if record.get('mode') == 'webhook' and not record.get('pending'):
                continue
            try:
                folder = Path(record['folder'])
                if folder.is_symlink() or folder.resolve().parent != rc.CLONE_ROOT.resolve():
                    raise rc.ConnectorError('Invalid repository folder.')
                _, url = rc.parse_github_url(record['url'])
                remote = rc.run_git(['remote', 'get-url', 'origin'], cwd=folder).strip()
                if rc.parse_github_url(remote)[1] != url:
                    raise rc.ConnectorError('The repository remote has changed. Reconnect the repository.')
                rc.parse_branch(record['branch'])
                auth = {}
                if record.get('installationId'):
                    from apps.api import github_app
                    auth['auth_token'] = github_app.installation_token(record['installationId'])
                batch = rc.fetch_new(folder, record['head'], record['branch'], **auth)
                record.update(checkedAt=now(), error=None, state='watching')
                if batch is None:
                    record['pending'] = False
                    save(records)
                    continue
                record['commits'] = batch.commits[-20:]
                record['changes'] = {'modified': batch.modified, 'added': batch.added, 'deleted': batch.deleted}
                # Save retry state before changing graph content.
                record['state'] = 'syncing'
                record['activeVersion'] = record.get('queuedVersion', 0)
                save(records)
                changes = rc.apply_batch(folder, key, batch)
                # Added paths can restore a previously deleted node with existing decayed links.
                changed = changes['modified'] + changes['deleted'] + changes['added']
                if changed or changes['added']:
                    runner.start({'kind': 'changed', 'project': key,
                                  'code_changed': changed, 'code_added': changes['added']})
                    _active = (key, batch.head, runner._state['proc'])
                    record['state'] = 'checking'
                else:
                    record.update(head=batch.head, syncedAt=now(), state='watching', pending=False)
                save(records)
                if _active:
                    return
            except Exception as exc:
                record.update(state='error', error=str(exc), checkedAt=now())
                save(records)
                logging.exception('Repository sync failed for %s', key)


def start():
    stop = threading.Event()

    def watch():
        recovered = False
        while not stop.is_set():
            try:
                if not recovered:
                    discover()
                    recovered = True
                from apps.api import github_app
                github_app.drain()
                sync_once()
            except Exception:
                logging.exception('Repository watcher failed; retrying')
            wake.wait(2)
            wake.clear()

    threading.Thread(target=watch, name='repository-watcher', daemon=True).start()
    return stop
