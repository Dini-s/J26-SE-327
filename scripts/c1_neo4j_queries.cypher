// READ-ONLY queries for Neo4j Query / Browser, to look at what Component 1 published.
// Proposal schema: docs/c1_neo4j_contract.md. Replace 'demo-project' with your C1_PROJECT_ID. Run one query at a time.

// 1. How many nodes of each label does C1 own?
MATCH (n {produced_by: 'c1'})
RETURN labels(n)[0] AS label, count(n) AS nodes, sum(CASE WHEN coalesce(n.active, true) THEN 1 ELSE 0 END) AS active
ORDER BY label;

// 2. Requirements by status (active only)
MATCH (r:Requirement {project_id: 'demo-project'})
WHERE r.active
RETURN r.status AS status, count(*) AS requirements
ORDER BY requirements DESC;

// 3. Approved requirements: what C2-C4 should build on
MATCH (r:Requirement {project_id: 'demo-project'})
WHERE r.status IN ['accepted', 'edited'] AND r.active
RETURN r.req_id AS req_id, r.kind AS kind, r.final_text AS final_text
ORDER BY req_id;

// 4. Requirements with their task draft and issues
MATCH (r:Requirement {project_id: 'demo-project'})
WHERE r.active
OPTIONAL MATCH (r)-[:HAS_DRAFT]->(d:TaskDraft)
OPTIONAL MATCH (r)-[:HAS_ISSUE]->(i:Issue)
WITH r, d, collect(i.type + '/' + i.raised_by) AS issues
RETURN r.req_id AS req_id, r.status AS status, d.user_story AS user_story, d.generated_by AS model, d.generated_on AS generated_on,
       d.endpoint_host AS endpoint_host, issues
ORDER BY req_id
LIMIT 50;

// 5. Sources of the project and how many requirements each holds
MATCH (:Project {project_id: 'demo-project'})-[:HAS_SOURCE]->(s:SourceDocument)
OPTIONAL MATCH (s)-[:CONTAINS]->(r:Requirement)
WHERE r.active
RETURN s.filename AS filename, s.source_type AS type, s.active AS active, count(r) AS requirements
ORDER BY filename;

// 6. Duplicate links
MATCH (a:Requirement {project_id: 'demo-project'})-[d:DUPLICATE_OF]->(b:Requirement)
WHERE d.active
RETURN a.req_id AS duplicate, b.req_id AS of, d.score AS score
ORDER BY score DESC
LIMIT 50;

// 7. Open issues of requirements that were not decided yet
MATCH (r:Requirement {project_id: 'demo-project', status: 'pending'})-[:HAS_ISSUE]->(i:Issue)
WHERE r.active AND i.active
RETURN i.type AS type, i.raised_by AS raised_by, count(*) AS issues
ORDER BY issues DESC;

// 8. The lossless record of one requirement (what C3 reads); payload_json is a string
MATCH (r:Requirement {project_id: 'demo-project'})
WHERE r.active
RETURN r.req_id AS req_id, r.payload_json AS payload_json
LIMIT 1;
