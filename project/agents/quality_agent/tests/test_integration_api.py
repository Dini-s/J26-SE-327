from fastapi.testclient import (
    TestClient,
)

from apps.api.main import (
    app,
)


client = TestClient(
    app
)


def test_c1_contract_endpoint():
    response = client.post(
        (
            "/api/quality/"
            "integration/"
            "c1/validate"
        ),

        json={
            "requirementId":
                "REQ-001",

            "title":
                "Example",

            "text":
                "Example requirement",

            "type":
                "FUNCTIONAL",

            "subtype":
                "SEARCH",

            "risk":
                "MEDIUM",

            "source":
                "C1",

            "acceptanceCriteria":
                [
                    {
                        "acId":
                            "AC-001",

                        "text":
                            "Example AC",
                    }
                ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()[
            "valid"
        ]
        is True
    )


def test_invalid_c1_contract_returns_422():
    response = client.post(
        (
            "/api/quality/"
            "integration/"
            "c1/validate"
        ),

        json={
            "title":
                "Missing ID"
        },
    )

    assert (
        response.status_code
        == 422
    )


def test_ownership_endpoint():
    response = client.get(
        (
            "/api/quality/"
            "integration/"
            "ownership"
        )
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        "C3_OWNED"
        in response.json()
    )