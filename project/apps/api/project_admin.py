"""Explicit project deletion for the local dashboard, separate from C4's write ownership."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from apps.api import repo_connector as rc, repo_sync, runner, sources, labeling


class ProjectError(ValueError):
    pass


DELETE_GRAPH = """
MATCH (n) WHERE coalesce(n.project, n.repo, n.dataset) = $project
WITH collect(n) AS owned
OPTIONAL MATCH (r)-[:HAS_DECAY]->(d:DecayFlag)
WHERE r IN owned AND coalesce(d.project, d.repo, d.dataset) IS NULL
  AND NOT EXISTS { MATCH (other)-[:HAS_DECAY]->(d) WHERE NOT other IN owned }
WITH owned, collect(DISTINCT d) AS flags
WITH owned + flags AS targets
UNWIND targets AS n
WITH DISTINCT n
DETACH DELETE n
"""


def delete_graph(tx, project):
    summary = tx.run(DELETE_GRAPH, project=project).consume()
    return {'nodes': summary.counters.nodes_deleted, 'relationships': summary.counters.relationships_deleted}


def cleanup_history(project):
    removed = 0
    if not sources.RUNS_DIR.is_dir():
        return removed
    for folder in sources.RUNS_DIR.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            continue
        events = folder / 'events.jsonl'
        if events.is_symlink() or not events.is_file():
            continue
        # Only remove a run explicitly attributed to this project.
        with events.open() as stream:
            start = next((event for line in stream if (event := json.loads(line)).get('type') == 'run_start'), None)
        if start and start.get('project') == project:
            shutil.rmtree(folder)
            removed += 1
    return removed


def delete_project(project, confirmation):
    if not isinstance(project, str) or not project or len(project) > 200:
        raise ProjectError('Choose a project to delete.')
    if confirmation != project:
        raise ProjectError('Confirm the exact project you want to delete.')
    rc._guard_local()
    # Same lock order as repository synchronization. Never delete under an active pipeline.
    with repo_sync._lock, runner.RUN_LOCK:
        if runner.status()['state'] != 'idle':
            raise ProjectError('An analysis is running. Wait for it to finish before deleting a project.')
        records = repo_sync.load()
        record = records.get(project)
        if project not in {row['project'] for row in sources.neo4j_projects()} and not record:
            raise ProjectError('This project no longer exists.')
        # Do not report a successful deletion if the download path is unsafe to remove.
        folder = Path(record['folder']) if record and record.get('folder') else None
        if folder and (folder.is_symlink() or folder.resolve().parent != rc.CLONE_ROOT.resolve()):
            raise ProjectError('Project download path is invalid; deletion was cancelled.')
        if folder and any(key != project and value.get('folder') == str(folder) for key, value in records.items()):
            raise ProjectError('Another project shares this download folder; deletion was cancelled.')
        # Disable first so a checkpoint write failure cannot recreate deleted graph nodes.
        if record:
            records[project] = {**record, 'enabled': False, 'pending': False}
            repo_sync.save(records)
        try:
            with sources._neo4j_driver() as driver:
                with driver.session() as session:
                    counts = session.execute_write(delete_graph, project)
        except Exception:
            if record:
                records[project] = record
                repo_sync.save(records)
            raise
        records.pop(project, None)
        repo_sync.save(records)
        warnings = []
        runs = 0
        try:
            if folder and folder.exists():
                shutil.rmtree(folder)
            runs = cleanup_history(project)
            label_path = labeling._path(project, labeling.LABELS_DIR)
            # Label filenames are normalized: preserve files that could belong to another project.
            remaining = {row['project'] for row in sources.neo4j_projects()}
            if not any(labeling._path(key, labeling.LABELS_DIR) == label_path for key in remaining):
                if label_path.is_file() and not label_path.is_symlink():
                    label_path.unlink()
        except (OSError, ValueError) as exc:
            warnings.append(f'Graph deleted, but some local history or downloads could not be removed: {type(exc).__name__}')
        if repo_sync._active and repo_sync._active[0] == project:
            repo_sync._active = None
        return {'project': project, 'deleted': True, **counts, 'runs': runs, 'warnings': warnings}
