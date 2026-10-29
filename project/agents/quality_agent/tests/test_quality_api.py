from fastapi.testclient import (
    TestClient,
)

from apps.api.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ok"

    assert (
        payload["component"]
        == "quality-testing-intelligence"
    )


def test_raw_overview_contract():
    response = client.get(
        "/api/quality/overview"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["requirements"] == 30
    assert payload["acceptance_criteria"] == 90

    assert (
        payload[
            "functional_requirements"
        ]
        == 20
    )

    assert (
        payload[
            "non_functional_requirements"
        ]
        == 10
    )


def test_requirements_endpoint():
    response = client.get(
        "/api/quality/requirements"
    )

    assert response.status_code == 200

    payload = response.json()

    assert isinstance(
        payload,
        list,
    )

    assert len(payload) == 30

    assert {
        "requirement_id",
        "title",
        "type",
        "risk",
        "ac_count",
        "rvu_count",
    }.issubset(
        payload[0].keys()
    )


def test_unknown_requirement_returns_404():
    response = client.get(
        (
            "/api/quality/"
            "requirements/"
            "REQ-NOT-FOUND"
        )
    )

    assert response.status_code == 404


def test_invalid_retrieval_method_returns_422():
    response = client.post(
        (
            "/api/quality/rvus/"
            "REQ-PET-001-RVU-01/"
            "retrieve"
        ),
        params={
            "method": "invalid",
            "top_k": 5,
        },
    )

    assert response.status_code == 422


def test_intelligence_overview_contract():
    response = client.get(
        (
            "/api/quality/"
            "intelligence/overview"
        )
    )

    assert response.status_code == 200

    payload = response.json()

    assert "overall_rvc" in payload
    assert "avg_rves" in payload
    assert "history" in payload


def test_intelligence_requirements_contract():
    response = client.get(
        (
            "/api/quality/"
            "intelligence/requirements"
        )
    )

    assert response.status_code == 200

    assert isinstance(
        response.json(),
        list,
    )


def test_revalidation_contract():
    response = client.get(
        "/api/quality/revalidation"
    )

    assert response.status_code == 200

    assert isinstance(
        response.json(),
        list,
    )


def test_reports_contract():
    response = client.get(
        (
            "/api/quality/"
            "intelligence/reports"
        )
    )

    assert response.status_code == 200

    payload = response.json()

    assert "requirements" in payload

    assert (
        "revalidation_summary"
        in payload
    )


def test_export_summary_contract():
    response = client.get(
        (
            "/api/quality/"
            "export/summary"
        )
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["component"]
        == "Quality & Testing Intelligence"
    )

    assert "analytics" in payload
    assert "revalidation" in payload