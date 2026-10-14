"""PetClinic seed: analysis of Java sources, the C1/C2-shaped rows, and the write guards. No Neo4j, no network."""

import subprocess

import pytest

from apps.seed import petclinic as pc


class FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, **params):
        self.calls.append((query, params))
        return [], None, None


@pytest.fixture
def repo(tmp_path):
    base = tmp_path / "src/main/java/org/springframework/samples/petclinic"
    (base / "model").mkdir(parents=True)
    (base / "owner").mkdir()
    (base / "model/Person.java").write_text("package org.springframework.samples.petclinic.model;\n/** doc */\npublic class Person { String name; }\n")
    (base / "owner/Owner.java").write_text(
        "package org.springframework.samples.petclinic.owner;\nimport org.springframework.samples.petclinic.model.Person;\n"
        "// comment\npublic class Owner extends Person {\n  int f(int a) { if (a > 1 && a < 5) { return 1; } return a > 0 ? 2 : 3; }\n}\n")
    (base / "owner/OwnerController.java").write_text(
        "package org.springframework.samples.petclinic.owner;\nclass OwnerController { Owner o; }\n")
    (base / "owner/package-info.java").write_text("package org.springframework.samples.petclinic.owner;\n")
    templates = tmp_path / "src/main/resources/templates/owners"
    templates.mkdir(parents=True)
    (templates / "find.html").write_text('<form th:if="${x}"><input/></form>\n')
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x.org", "-c", "commit.gpgsign=false", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    return tmp_path


def test_measure_java_ignores_comments_and_counts_decisions():
    loc, cc, mi = pc.measure_java("// c\n/* b\nlock */\nclass A {\n  void f(int a){ if (a>1 && a<5) {} }\n}\n")
    assert loc == 3 and cc == 3 and 0 <= mi <= 100


def test_scan_finds_java_and_templates_but_not_package_info(repo):
    files = pc.scan(repo)
    assert sorted(f.name for f in files) == ["Owner.java", "OwnerController.java", "Person.java", "find.html"]
    owner = next(f for f in files if f.name == "Owner.java")
    assert owner.package.endswith(".owner") and owner.classes == ["Owner"] and owner.complexity == 4 and owner.id == f"{pc.PROJECT}:{owner.path}"
    assert next(f for f in files if f.language == "html").package == "templates.owners"


def test_dependencies_by_import_and_same_package(repo):
    files = {f.name: f for f in pc.scan(repo)}
    pc.resolve_dependencies(list(files.values()))
    assert files["Owner.java"].depends_on == {files["Person.java"].id}                 # imported
    assert files["OwnerController.java"].depends_on == {files["Owner.java"].id}        # same package, mentioned
    assert files["Person.java"].depends_on == set()


def test_package_metrics_fan_in_out_and_instability(repo):
    files = pc.scan(repo)
    pc.resolve_dependencies(files)
    m = pc.package_metrics(files)
    owner, model = m[f"{pc.BASE_PACKAGE}.owner"], m[f"{pc.BASE_PACKAGE}.model"]
    assert (owner["fan_out"], owner["fan_in"], owner["instability"]) == (1, 0, 1.0)
    assert (model["fan_out"], model["fan_in"], model["instability"]) == (0, 1, 0.0)
    assert owner["total_coupling"] == 1 and owner["risk_level"] in ("Low", "Medium", "High")
    assert m["__edges__"]["edges"] == [(f"{pc.BASE_PACKAGE}.owner", f"{pc.BASE_PACKAGE}.model")]


def test_circular_dependencies():
    assert pc.circular_dependencies([("a", "b"), ("b", "c")]) == []
    assert pc.circular_dependencies([("a", "b"), ("b", "a"), ("b", "c")]) == [["a", "b"]]


def test_git_evolution_and_head(repo):
    evo = pc.git_evolution(repo)
    e = evo["src/main/java/org/springframework/samples/petclinic/owner/Owner.java"]
    assert e["commit_count"] == 1 and e["total_insertions"] == 6 and e["total_churn"] == 6 and len(pc.head_commit(repo)) == 40


def test_requirements_are_complete_and_unique():
    reqs = pc.build_requirements()
    ids = [r["id"] for r in reqs["items"]]
    assert len(ids) == len(set(ids)) >= 20 and all(i.startswith("PC-REQ-") for i in ids)
    for r in reqs["items"]:
        assert len(r["text"]) >= 40 and r["story"].startswith("As a ") and len(r["criteria"]) == 2 and r["task"]
        assert r["type"] in ("FR", "NFR") and r["status"] in ("approved", "pending")
    assert any(r["status"] == "pending" for r in reqs["items"])                          # features PetClinic does not have


def test_findings_are_rule_based():
    sec = pc.derive_findings("The system shall require a username and password.")
    assert sec[0]["type"] == "security" and "password" in sec[0]["cue_words"]
    vague = pc.derive_findings("The system shall be fast and user-friendly.")
    assert vague[-1]["label"] == "vague" and "fast" in vague[-1]["weak_words"]
    assert pc.derive_findings("The system shall store owners.")[-1]["label"] == "clear"


def test_rows_use_project_scoped_ids_and_both_labels(repo):
    analysis = pc.analyze(repo)
    c2 = pc.c2_rows(analysis)
    assert all(r["id"].startswith("spring-petclinic:") for r in c2["files"])
    assert all(r["props"]["project"] == "spring-petclinic" and r["props"]["kind"] == "code" and r["props"]["text"] for r in c2["files"])
    assert "c:CodeFile" in pc._C2_QUERIES[2][0] and "CodeEntity" in pc._C2_QUERIES[2][0]       # C4 reads CodeEntity
    c1 = pc.c1_rows(pc.build_requirements())
    assert all(r["props"]["project"] == "spring-petclinic" for r in c1["requirements"])


def test_write_graph_and_guards(repo, monkeypatch):
    driver = FakeDriver()
    counts = pc.write_graph(pc.analyze(repo), pc.build_requirements(), driver)
    assert counts["c2 files"] == 4 and counts["c1 requirements"] >= 20
    assert not any("DELETE" in q for q, _ in driver.calls)                                     # no reset requested
    driver = FakeDriver()
    pc.write_graph(pc.analyze(repo), pc.build_requirements(), driver, reset=True)
    resets = [q for q, _ in driver.calls if "DELETE" in q]
    assert len(resets) == 2 and all("$source" in q and "$project" in q for q in resets)
    monkeypatch.setenv("NEO4J_URI", "bolt://prod.example.com:7687")
    with pytest.raises(SystemExit):
        pc.write_graph(pc.analyze(repo), pc.build_requirements(), FakeDriver())


def test_cli_explains_a_missing_clone(tmp_path, capsys):
    assert pc.main(["--repo", str(tmp_path / "nope"), "--dry-run"]) == 1
    assert "git clone" in capsys.readouterr().err
