from fastapi.testclient import TestClient

from backend import app as backend_app_module


client = TestClient(backend_app_module.app)


def test_query_endpoint_returns_answer_and_citations(monkeypatch):
    def fake_answer_question(question):
        return {
            "answer": "Infosys revenue rose over the last year.",
            "citations": [
                {
                    "filename": "infosys_annual_report.md",
                    "filepath": "data/infosys_annual_report.md",
                    "score": 0.91,
                }
            ],
            "context": "Sample context",
            "timings": {"total": 1.2},
        }

    monkeypatch.setattr(backend_app_module, "answer_question", fake_answer_question)

    response = client.post(
        "/api/query",
        json={"question": "What are Infosys earnings and revenue trends?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Infosys revenue rose over the last year."
    assert payload["citations"][0]["filename"] == "infosys_annual_report.md"
    assert isinstance(payload["citations"], list)
