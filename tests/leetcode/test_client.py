import httpx
import pytest

from app.leetcode import (
    AuthExpiredError,
    LeetCodeError,
    RateLimitedError,
    SchemaChangedError,
)
from tests.leetcode.conftest import load, payload_of

# --- Auth & headers ---------------------------------------------------------------------


def test_sends_auth_headers_and_operation_name(make_client, sent) -> None:
    make_client(lambda p: load("user_status")).check_auth()

    request = sent[0]
    assert request.url == "https://leetcode.com/graphql/"
    assert request.headers["cookie"] == "LEETCODE_SESSION=sess-cookie; csrftoken=csrf-token"
    assert request.headers["x-csrftoken"] == "csrf-token"
    assert request.headers["referer"] == "https://leetcode.com"
    assert payload_of(request)["operationName"] == "globalData"


def test_check_auth_returns_status(make_client) -> None:
    status = make_client(lambda p: load("user_status")).check_auth()
    assert status.is_signed_in and status.username == "testuser"


def test_check_auth_signed_out_raises_auth_expired(make_client) -> None:
    with pytest.raises(AuthExpiredError):
        make_client(lambda p: load("user_status_signed_out")).check_auth()


def test_check_auth_wrong_account_is_not_an_expiry(make_client, settings) -> None:
    settings.leetcode_username = "someone-else"
    with pytest.raises(LeetCodeError) as exc_info:
        make_client(lambda p: load("user_status")).check_auth()
    assert not isinstance(exc_info.value, AuthExpiredError)


def test_check_auth_without_cookie_sends_nothing(make_client, settings, sent) -> None:
    settings.leetcode_session = ""
    with pytest.raises(AuthExpiredError):
        make_client(lambda p: load("user_status")).check_auth()
    assert sent == []


# --- Pagination -----------------------------------------------------------------------


def test_iter_progress_pages_until_total(make_client, sent) -> None:
    def handler(p):
        skip = p["variables"]["filters"]["skip"]
        return load("progress_page_1" if skip == 0 else "progress_page_2")

    slugs = [q.title_slug for q in make_client(handler).iter_progress(page_size=2)]

    assert slugs == ["rotting-oranges", "median-of-two-sorted-arrays", "two-sum"]
    assert [payload_of(r)["variables"]["filters"]["skip"] for r in sent] == [0, 2]


def test_submissions_follow_offset_until_no_next(make_client, sent) -> None:
    def handler(p):
        offset = p["variables"]["offset"]
        return load("submissions_page_1" if offset == 0 else "submissions_page_2")

    ids = [s.id for s in make_client(handler).submissions("two-sum", page_size=2)]

    assert ids == [3003, 3002, 3001]
    assert [payload_of(r)["variables"]["offset"] for r in sent] == [0, 2]
    assert payload_of(sent[0])["variables"]["questionSlug"] == "two-sum"


def test_submissions_stop_early_without_fetching_more(make_client, sent) -> None:
    newest = next(make_client(lambda p: load("submissions_page_1")).submissions("two-sum"))
    assert newest.id == 3003
    assert len(sent) == 1


def test_submissions_empty(make_client) -> None:
    assert list(make_client(lambda p: load("submissions_empty")).submissions("two-sum")) == []


# --- Single lookups ---------------------------------------------------------------------


def test_submission_detail(make_client, sent) -> None:
    detail = make_client(lambda p: load("submission_detail")).submission_detail(3003)
    assert detail.runtime_ms == 39
    assert payload_of(sent[0])["variables"] == {"submissionId": 3003}


def test_paid_only_question(make_client) -> None:
    question = make_client(lambda p: load("question_paid_only")).question("walls-and-gates")
    assert question.is_paid_only and question.statement is None


def test_unknown_question_raises(make_client) -> None:
    with pytest.raises(LeetCodeError, match="not found"):
        make_client(lambda p: {"data": {"question": None}}).question("no-such-problem")


def test_recent_accepted_uses_username(make_client, sent) -> None:
    recent = make_client(lambda p: load("recent_ac")).recent_accepted()
    assert [r.title_slug for r in recent] == ["two-sum", "rotting-oranges"]
    assert payload_of(sent[0])["variables"] == {"username": "testuser", "limit": 20}


# --- Schema drift ---------------------------------------------------------------------


def test_graphql_errors_raise_schema_changed(make_client) -> None:
    client = make_client(lambda p: httpx.Response(400, json=load("graphql_errors")))
    with pytest.raises(SchemaChangedError, match="numSubmitted"):
        client.progress_page()


def test_missing_field_raises_schema_changed(make_client) -> None:
    body = load("progress_page_1")
    del body["data"]["userProgressQuestionList"]["questions"][0]["numSubmitted"]
    with pytest.raises(SchemaChangedError):
        make_client(lambda p: body).progress_page()


def test_non_json_response_raises_schema_changed(make_client) -> None:
    client = make_client(lambda p: httpx.Response(200, text="<html>Just a moment...</html>"))
    with pytest.raises(SchemaChangedError):
        client.progress_page()


# --- Throttle, retries, backoff ---------------------------------------------------------


def test_consecutive_requests_are_throttled(make_client, fake_clock) -> None:
    client = make_client(lambda p: load("user_status"))
    client.check_auth()
    client.check_auth()
    assert fake_clock.sleeps == [1.0]


def test_retries_429_then_succeeds(make_client, sent, fake_clock) -> None:
    responses = iter([httpx.Response(429), load("user_status")])
    status = make_client(lambda p: next(responses)).check_auth()

    assert status.is_signed_in
    assert len(sent) == 2
    assert fake_clock.sleeps == [2.0]


def test_persistent_429_raises_rate_limited_after_backoff(make_client, sent, fake_clock) -> None:
    with pytest.raises(RateLimitedError):
        make_client(lambda p: httpx.Response(429)).progress_page()
    assert len(sent) == 4
    assert fake_clock.sleeps == [2.0, 4.0, 8.0]


def test_persistent_403_with_signed_out_session_is_auth_expired(make_client) -> None:
    def handler(p):
        if p["operationName"] == "globalData":
            return load("user_status_signed_out")
        return httpx.Response(403)

    with pytest.raises(AuthExpiredError):
        make_client(handler).progress_page()


def test_persistent_403_with_valid_session_is_rate_limited(make_client) -> None:
    def handler(p):
        if p["operationName"] == "globalData":
            return load("user_status")
        return httpx.Response(403)

    with pytest.raises(RateLimitedError):
        make_client(handler).progress_page()


def test_persistent_server_errors_are_not_rate_limiting(make_client) -> None:
    with pytest.raises(LeetCodeError) as exc_info:
        make_client(lambda p: httpx.Response(503)).progress_page()
    assert type(exc_info.value) is LeetCodeError
