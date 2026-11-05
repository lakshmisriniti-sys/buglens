import pytest

import ai
import main
from auth import COOKIE_NAME
from schemas import StructureResult

BUG = {"title": "Login fails", "priority": "high", "steps": ["Open app"], "labels": ["authentication"]}


def fake_ticket(**changes):
    values = dict(
        title="A ticket", priority="low", environment="", steps=[], expected="",
        actual="", labels=["ui"], source="ai",
    )
    return StructureResult(**{**values, **changes})


# ---------- Access control ----------
@pytest.mark.parametrize("method, path", [
    ("get", "/api/bugs"),
    ("post", "/api/bugs"),
    ("get", "/api/bugs/1"),
    ("patch", "/api/bugs/1"),
    ("delete", "/api/bugs/1"),
    ("post", "/api/ai/structure"),
])
def test_team_routes_reject_visitors(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_wrong_password_is_rejected(client):
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401


def test_forged_cookie_is_rejected(client):
    client.cookies.set(COOKIE_NAME, "9999999999.notarealsignature")
    assert client.get("/api/bugs").status_code == 401


def test_non_ascii_cookie_is_rejected_not_a_server_error(client):
    response = client.get("/api/bugs", headers={"Cookie": f"{COOKIE_NAME}=9999999999.caf\xe9".encode("latin-1")})
    assert response.status_code == 401


def test_logout_ends_the_session(team_client):
    team_client.post("/api/logout")
    assert team_client.get("/api/bugs").status_code == 401


# ---------- Bug CRUD ----------
def test_create_read_update_delete(team_client):
    created = team_client.post("/api/bugs", json=BUG)
    assert created.status_code == 201
    bug_id = created.json()["id"]
    assert created.json()["steps"] == ["Open app"]

    updated = team_client.patch(f"/api/bugs/{bug_id}", json={"status": "resolved"})
    assert updated.json()["status"] == "resolved"
    assert updated.json()["title"] == "Login fails"

    assert team_client.delete(f"/api/bugs/{bug_id}").status_code == 204
    assert team_client.get(f"/api/bugs/{bug_id}").status_code == 404


def test_invalid_priority_is_rejected(team_client):
    assert team_client.post("/api/bugs", json={**BUG, "priority": "urgent"}).status_code == 422


def test_search_cannot_inject_sql(team_client):
    team_client.post("/api/bugs", json=BUG)
    results = team_client.get("/api/bugs", params={"q": "' OR 1=1; DROP TABLE bugs; --"})
    assert results.status_code == 200
    assert results.json() == []
    assert len(team_client.get("/api/bugs").json()) == 1


def test_filters_narrow_the_list(team_client):
    team_client.post("/api/bugs", json=BUG)
    team_client.post("/api/bugs", json={**BUG, "title": "Typo", "priority": "low"})
    results = team_client.get("/api/bugs", params={"priority": "low"}).json()
    assert [bug["title"] for bug in results] == ["Typo"]


# ---------- Public reports ----------
def test_public_report_is_saved_and_tagged(team_client):
    response = team_client.post("/api/reports", json={"description": "i was charged twice at checkout"})
    assert response.status_code == 201
    bug = team_client.get(f"/api/bugs/{response.json()['id']}").json()
    assert bug["priority"] == "critical"
    assert "user-report" in bug["labels"]
    assert bug["raw_report"] == "i was charged twice at checkout"


def test_whitespace_report_is_rejected(client):
    assert client.post("/api/reports", json={"description": "        "}).status_code == 422


def test_report_is_kept_when_ai_fails(team_client, monkeypatch):
    def fail(_):
        raise ai.AIError("AI is down")

    monkeypatch.setattr(main, "structure_report", fail)
    response = team_client.post("/api/reports", json={"description": "the page is broken"})
    assert response.status_code == 201
    bug = team_client.get(f"/api/bugs/{response.json()['id']}").json()
    assert "needs-triage" in bug["labels"]


@pytest.mark.parametrize("title", ["x" * 300, ""])
def test_report_is_kept_when_ai_returns_an_unusable_title(team_client, monkeypatch, title):
    monkeypatch.setattr(main, "structure_report", lambda _: fake_ticket(title=title))
    response = team_client.post("/api/reports", json={"description": "the page is broken"})
    assert response.status_code == 201
    bug = team_client.get(f"/api/bugs/{response.json()['id']}").json()
    assert 1 <= len(bug["title"]) <= 200


def test_ai_failure_returns_503_to_the_team(team_client, monkeypatch):
    def fail(_):
        raise ai.AIError("AI is down")

    monkeypatch.setattr(main, "structure_report", fail)
    response = team_client.post("/api/ai/structure", json={"raw_report": "broken"})
    assert response.status_code == 503


def test_demo_mode_is_used_without_an_api_key():
    assert ai.structure_report("the login is broken on chrome").source == "demo"
