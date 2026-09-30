"""The only code that talks to LeetCode.

One request at a time, at most about one per second, with exponential backoff on 429/403/5xx.
Responses are validated into `schemas` models; anything unexpected raises `SchemaChangedError`.
"""

import time
from collections.abc import Callable, Iterator
from functools import cache
from typing import Any, Self

import httpx
from pydantic import TypeAdapter, ValidationError

from app import __version__
from app.config import Settings
from app.leetcode import queries
from app.leetcode.errors import (
    AuthExpiredError,
    LeetCodeError,
    RateLimitedError,
    SchemaChangedError,
)
from app.leetcode.queries import Operation
from app.leetcode.schemas import (
    ProgressPage,
    ProgressQuestion,
    QuestionDetail,
    RecentAc,
    SubmissionDetail,
    SubmissionPage,
    SubmissionSummary,
    UserStatus,
)
from app.leetcode.throttle import Throttle

BASE_URL = "https://leetcode.com"
GRAPHQL_PATH = "/graphql/"
RETRY_STATUSES = {403, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BACKOFF_BASE = 2.0  # seconds; waits 2, 4, 8 between attempts


@cache
def _adapter(tp: Any) -> TypeAdapter[Any]:
    return TypeAdapter(tp)


class LeetCodeClient:
    def __init__(
        self,
        settings: Settings,
        http: httpx.Client | None = None,
        throttle: Throttle | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._http = http or httpx.Client(base_url=BASE_URL, timeout=20.0)
        self._http.headers.update(
            {
                "Cookie": (
                    f"LEETCODE_SESSION={settings.leetcode_session}; "
                    f"csrftoken={settings.leetcode_csrftoken}"
                ),
                "x-csrftoken": settings.leetcode_csrftoken,
                "Referer": BASE_URL,
                "Content-Type": "application/json",
                "User-Agent": f"Mozilla/5.0 (compatible; dsa-recall/{__version__})",
            }
        )
        self._throttle = throttle or Throttle()
        self._sleep = sleep

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # --- Public API --------------------------------------------------------------------

    def check_auth(self) -> UserStatus:
        """Run at the start of every sync. Raises AuthExpiredError if the cookie is bad."""
        if not (self._settings.leetcode_session and self._settings.leetcode_csrftoken):
            raise AuthExpiredError("LEETCODE_SESSION and LEETCODE_CSRFTOKEN must be set in .env")
        status = self._query(queries.USER_STATUS, {}, UserStatus)
        if not status.is_signed_in:
            raise AuthExpiredError(
                "LeetCode session expired. Copy a fresh LEETCODE_SESSION and csrftoken "
                "from your browser into .env."
            )
        expected = self._settings.leetcode_username
        if expected and (status.username or "").lower() != expected.lower():
            raise LeetCodeError(
                f"Cookie belongs to '{status.username}', but LEETCODE_USERNAME is '{expected}'."
            )
        return status

    def progress_page(self, skip: int = 0, limit: int = 50) -> ProgressPage:
        """One page of problems the user has touched, most recently submitted first."""
        variables = {"filters": {"skip": skip, "limit": limit}}
        return self._query(queries.USER_PROGRESS_QUESTION_LIST, variables, ProgressPage)

    def iter_progress(self, page_size: int = 50) -> Iterator[ProgressQuestion]:
        skip = 0
        while True:
            page = self.progress_page(skip, page_size)
            yield from page.questions
            skip += len(page.questions)
            if not page.questions or skip >= page.total_num:
                return

    def submissions(self, slug: str, page_size: int = 20) -> Iterator[SubmissionSummary]:
        """All submissions for one problem, newest first. Stop iterating early at known IDs."""
        offset, last_key = 0, None
        while True:
            variables = {
                "offset": offset,
                "limit": page_size,
                "lastKey": last_key,
                "questionSlug": slug,
            }
            page = self._query(queries.QUESTION_SUBMISSION_LIST, variables, SubmissionPage)
            yield from page.submissions
            if not page.has_next or not page.submissions:
                return
            offset += len(page.submissions)
            last_key = page.last_key

    def submission_detail(self, submission_id: int) -> SubmissionDetail:
        detail = self._query(
            queries.SUBMISSION_DETAILS, {"submissionId": submission_id}, SubmissionDetail | None
        )
        if detail is None:
            raise LeetCodeError(f"Submission {submission_id} not found or not visible.")
        return detail

    def question(self, slug: str) -> QuestionDetail:
        detail = self._query(queries.QUESTION, {"titleSlug": slug}, QuestionDetail | None)
        if detail is None:
            raise LeetCodeError(f"Problem '{slug}' not found.")
        return detail

    def recent_accepted(self, limit: int = 20) -> list[RecentAc]:
        variables = {"username": self._settings.leetcode_username, "limit": limit}
        return self._query(queries.RECENT_AC_SUBMISSIONS, variables, list[RecentAc])

    # --- Transport ------------------------------------------------------------------

    def _query(self, op: Operation, variables: dict[str, Any], tp: Any) -> Any:
        payload = {"operationName": op.name, "query": op.document, "variables": variables}
        response = self._send(payload)

        if response.status_code == 401:
            raise AuthExpiredError("LeetCode rejected the session cookie (HTTP 401).")
        try:
            body = response.json()
        except ValueError as exc:
            raise SchemaChangedError(
                f"{op.name}: expected JSON, got HTTP {response.status_code}"
            ) from exc
        if body.get("errors"):
            messages = "; ".join(str(e.get("message", e)) for e in body["errors"])
            raise SchemaChangedError(f"{op.name}: {messages}")
        if response.status_code != 200:
            raise LeetCodeError(f"{op.name}: unexpected HTTP {response.status_code}")

        data = (body.get("data") or {}).get(op.field)
        try:
            return _adapter(tp).validate_python(data)
        except ValidationError as exc:
            raise SchemaChangedError(f"{op.name}: response shape changed\n{exc}") from exc

    def _send(self, payload: dict[str, Any]) -> httpx.Response:
        """POST with throttle and retries. Returns any non-retryable response."""
        last_error = ""
        last_status: int | None = None
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                self._sleep(BACKOFF_BASE * 2 ** (attempt - 1))
            self._throttle.wait()
            try:
                response = self._http.post(GRAPHQL_PATH, json=payload)
            except httpx.TransportError as exc:
                last_error, last_status = f"network error: {exc}", None
                continue
            if response.status_code not in RETRY_STATUSES:
                return response
            last_error, last_status = f"HTTP {response.status_code}", response.status_code

        if last_status == 403 and not self._signed_in():
            raise AuthExpiredError("LeetCode returned 403 and the session is not signed in.")
        if last_status in (403, 429):
            raise RateLimitedError(f"LeetCode is rate limiting ({last_error}); try again later.")
        raise LeetCodeError(f"LeetCode unreachable after {MAX_ATTEMPTS} attempts ({last_error}).")

    def _signed_in(self) -> bool:
        """One unretried auth probe, to tell an expired cookie apart from rate limiting."""
        op = queries.USER_STATUS
        self._throttle.wait()
        try:
            response = self._http.post(
                GRAPHQL_PATH, json={"operationName": op.name, "query": op.document}
            )
            status = UserStatus.model_validate(response.json()["data"][op.field])
        except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError):
            return True  # can't tell; assume rate limiting rather than a bad cookie
        return status.is_signed_in
