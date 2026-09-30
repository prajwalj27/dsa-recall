from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.models import Problem
from app.engines.reviews import schedule_new_solves
from app.sync.engine import set_state
from app.timeutil import utc_naive, utc_now
from tests.factories import add_problem, add_solve, add_submission


@pytest.fixture
def seeded(client: TestClient, session_factory) -> dict[str, int]:
    """Two due history problems, one pending solve, one attempted-only problem."""
    now = utc_now()
    with session_factory() as s, s.begin():
        add_problem(s, "hard-one", "Hard")
        add_problem(s, "easy-one", "Easy")
        add_problem(s, "fresh", "Medium")
        add_problem(s, "stuck", "Hard")
        add_solve(s, "hard-one", now - timedelta(days=400), source="history")
        add_solve(s, "easy-one", now - timedelta(days=400), source="history")
        pending = add_solve(s, "fresh", now - timedelta(hours=1), wrong=1)
        add_submission(s, "stuck", now - timedelta(days=2), "Time Limit Exceeded")
        stuck = s.get(Problem, "stuck")
        stuck.question_status = "ATTEMPTED"
        stuck.last_submitted_at = utc_naive(now - timedelta(days=2))
        stuck.frontend_id = "4"
        s.get(Problem, "hard-one").frontend_id = "410"
        set_state(s, "backfill_done", True)
        schedule_new_solves(s, now)
        return {"pending": pending.id}


def test_today(client: TestClient, seeded) -> None:
    today = client.get("/api/today").json()

    assert [p["solve_id"] for p in today["pending"]] == [seeded["pending"]]
    assert today["pending"][0]["default"] == "hard"
    due = today["due"]
    assert [i["slug"] for i in due["items"]] == ["hard-one", "easy-one"]
    assert (due["total_due"], due["shown"], due["done_today"], due["target"]) == (2, 2, 0, 8)
    assert due["items"][0]["due"].endswith("Z")
    assert due["items"][0]["last_review"].endswith("Z")
    assert due["items"][0]["frontend_id"] == "410"
    assert today["pending"][0]["frontend_id"] is None
    [stuck] = today["attempted"]
    assert (stuck["slug"], stuck["last_status"], stuck["frontend_id"]) == (
        "stuck",
        "Time Limit Exceeded",
        "4",
    )
    assert today["target"]["mode"] == "steady"
    assert today["study_mode"] == {"enabled": False, "until": None, "active": False}
    assert today["backfill_done"] is True


def test_shown_is_limited_by_target_minus_done(client: TestClient, seeded) -> None:
    client.put("/api/settings/target", json={"mode": "custom", "daily_target": 2})
    client.post("/api/problems/easy-one/review", json={"choice": "good"})

    due = client.get("/api/today").json()["due"]

    assert (due["done_today"], due["total_due"], due["shown"]) == (1, 1, 1)


def test_rate_solve(client: TestClient, seeded) -> None:
    response = client.post(
        f"/api/solves/{seeded['pending']}/rating", json={"choice": "saw_solution"}
    )

    assert response.status_code == 200
    assert response.json()["reps"] == 1
    assert client.get("/api/today").json()["pending"] == []
    timeline = client.get("/api/problems/fresh").json()["timeline"]
    assert (timeline[0]["choice"], timeline[0]["rating_source"]) == ("saw_solution", "user")


def test_confirm_all(client: TestClient, seeded) -> None:
    response = client.post("/api/solves/confirm", json={"solve_ids": [seeded["pending"]]})
    assert response.json() == {"confirmed": 1}
    assert client.get("/api/today").json()["pending"] == []


def test_problem_detail(client: TestClient, seeded) -> None:
    detail = client.get("/api/problems/hard-one").json()

    assert detail["problem"]["url"] == "https://leetcode.com/problems/hard-one/"
    assert detail["card"]["reps"] == 1
    assert 0 < detail["card"]["recall"] < 1
    assert [e["kind"] for e in detail["timeline"]] == ["solve"]


def test_problem_without_card(client: TestClient, seeded) -> None:
    assert client.get("/api/problems/stuck").json()["card"] is None
    assert client.post("/api/problems/stuck/review", json={"choice": "good"}).status_code == 409


def test_target_and_study_mode(client: TestClient, seeded) -> None:
    target = client.put(
        "/api/settings/target", json={"mode": "interview", "interview_end_date": "2099-01-01"}
    ).json()
    assert (target["mode"], target["daily_target"], target["retention"]) == ("interview", 15, 0.95)
    assert client.get("/api/settings/target").json()["previous_mode"] == "steady"

    study = client.put("/api/settings/study-mode", json={"enabled": True, "until": "2099-01-01"})
    assert study.json() == {"enabled": True, "until": "2099-01-01", "active": True}
    assert client.get("/api/today").json()["study_mode"]["active"] is True


@pytest.mark.parametrize(
    ("method", "path", "body", "status"),
    [
        ("get", "/api/problems/nope", None, 404),
        ("post", "/api/problems/nope/review", {"choice": "good"}, 404),
        ("post", "/api/solves/99999/rating", {"choice": "good"}, 404),
        ("post", "/api/solves/1/rating", {"choice": "meh"}, 422),
        ("post", "/api/solves/confirm", {"solve_ids": []}, 422),
        ("put", "/api/settings/target", {"mode": "hardcore"}, 422),
        ("put", "/api/settings/target", {"mode": "custom", "daily_target": 0}, 422),
        ("put", "/api/settings/target", {"mode": "custom", "retention": 0.5}, 422),
    ],
)
def test_errors(client: TestClient, seeded, method, path, body, status) -> None:
    response = client.request(method, path, json=body)
    assert response.status_code == status
