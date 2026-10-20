"""Import legacy reviews only when their timestamp and current text prove their version."""
from datetime import datetime, timezone

from apps.api import labeling
from agents.traceability_agent.utils import content_hash


def migrate_reviews(graph):
    imported = 0
    for project in graph.list_projects():
        key = project.get('project')
        if not key:
            continue
        saved = labeling.load_labels(key)
        if not saved:
            continue
        reqs = {a.id: a for a in graph.get_artifacts('requirement', project=key)}
        codes = {a.id: a for kind in ('code', 'test', 'design') for a in graph.get_artifacts(kind, project=key)}
        for link in graph.get_traces(project=key):
            review = saved.get(f'{link.source_id}||{link.target_id}', {})
            if link.review_label or link.status == 'decayed' or review.get('label') not in labeling.VALID:
                continue
            try:
                reviewed = datetime.fromisoformat(review['at']).astimezone(timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            if not link.last_checked_at or reviewed < link.last_checked_at:
                continue
            req, code = reqs.get(link.source_id), codes.get(link.target_id)
            if req is None or code is None or content_hash(req, code) != link.text_hash:
                continue
            graph.review_link(key, link.source_id, link.target_id, review['label'], link.text_hash)
            imported += 1
    return imported
