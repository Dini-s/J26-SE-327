"""The PetClinic answer key must match the requirements and the real file names."""

import pytest

from apps.seed import petclinic as pc, petclinic_gold as gold


def test_gold_covers_exactly_the_seeded_requirements():
    ids = {f"PC-REQ-{r[0]}" for r in pc.data.REQUIREMENTS}
    assert set(gold.GOLD) == ids
    assert sum(1 for v in gold.GOLD.values() if not v) == 4      # payment, e-mail reminder, login, database setup
    assert all(len(v) == len(set(v)) for v in gold.GOLD.values())


def test_every_gold_path_is_a_real_petclinic_file():
    if not (pc.DEFAULT_REPO / "src" / "main").is_dir():
        pytest.skip("spring-petclinic is not cloned (data/seed/spring-petclinic)")
    known = {f.id for f in pc.scan(pc.DEFAULT_REPO)}
    missing = [i for ids in gold.gold_pairs().values() for i in ids if i not in known]
    assert not missing, missing


def test_embedder_reads_the_optional_model_settings(tmp_path):
    from shared.embeddings.embedder import read_settings

    assert read_settings(tmp_path) == {}
    (tmp_path / "c4_embedder.json").write_text('{"max_seq_length": 256}')
    assert read_settings(tmp_path) == {"max_seq_length": 256}
    (tmp_path / "c4_embedder.json").write_text("not json")
    assert read_settings(tmp_path) == {}
