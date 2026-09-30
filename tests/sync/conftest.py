import threading
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.leetcode import AuthExpiredError, LeetCodeError
from app.leetcode.schemas import (
    Lang,
    ProgressQuestion,
    QuestionDetail,
    QuestionRef,
    SubmissionDetail,
    SubmissionSummary,
    UserStatus,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def day(n: float) -> datetime:
    return T0 + timedelta(days=n)


@dataclass
class FakeSub:
    id: int
    status: str  # statusDisplay, e.g. "Accepted", "Wrong Answer", "Compile Error"
    at: datetime


@dataclass
class FakeProblem:
    slug: str
    subs: list[FakeSub]
    difficulty: str = "Medium"
    paid_only: bool = False


@dataclass
class FakeLeetCode:
    """In-memory stand-in for LeetCodeClient with the same methods and return types."""

    problems: list[FakeProblem]
    signed_in: bool = True
    calls: Counter[str] = field(default_factory=Counter)
    questions_requested: list[str] = field(default_factory=list)
    # method name -> (call number that fails, exception to raise)
    fail_on: dict[str, tuple[int, LeetCodeError]] = field(default_factory=dict)
    # set to make check_auth block until released (for concurrency tests)
    gate: threading.Event | None = None

    def __enter__(self) -> "FakeLeetCode":
        return self

    def __exit__(self, *_exc: object) -> None:
        pass

    def _call(self, name: str) -> None:
        self.calls[name] += 1
        rule = self.fail_on.get(name)
        if rule and self.calls[name] == rule[0]:
            raise rule[1]

    def _problem(self, slug: str) -> FakeProblem:
        return next(p for p in self.problems if p.slug == slug)

    def add(self, slug: str, sub: FakeSub) -> None:
        self._problem(slug).subs.append(sub)

    # --- LeetCodeClient API -------------------------------------------------------------

    def check_auth(self) -> UserStatus:
        if self.gate is not None:
            self.gate.wait(5)
        self._call("check_auth")
        if not self.signed_in:
            raise AuthExpiredError("signed out")
        return UserStatus(is_signed_in=True, username="testuser")

    def iter_progress(self, page_size: int = 50) -> Iterator[ProgressQuestion]:
        touched = sorted(
            (p for p in self.problems if p.subs),
            key=lambda p: max(s.at for s in p.subs),
            reverse=True,
        )
        for start in range(0, len(touched), page_size):
            self._call("progress")
            for p in touched[start : start + page_size]:
                latest = max(p.subs, key=lambda s: s.at)
                solved = any(s.status == "Accepted" for s in p.subs)
                yield ProgressQuestion(
                    frontend_id="1",
                    title=p.slug.replace("-", " ").title(),
                    title_slug=p.slug,
                    difficulty=p.difficulty,
                    last_submitted_at=latest.at,
                    num_submitted=len(p.subs),
                    question_status="SOLVED" if solved else "ATTEMPTED",
                    last_result="AC" if latest.status == "Accepted" else "WA",
                    topic_tags=[{"name": "Array", "slug": "array"}],
                )

    def submissions(self, slug: str, page_size: int = 20) -> Iterator[SubmissionSummary]:
        subs = sorted(self._problem(slug).subs, key=lambda s: s.id, reverse=True)
        for start in range(0, max(len(subs), 1), page_size):
            self._call("submissions")
            for s in subs[start : start + page_size]:
                accepted = s.status == "Accepted"
                yield SubmissionSummary(
                    id=s.id,
                    title_slug=slug,
                    status=10 if accepted else 11,
                    status_display=s.status,
                    lang="python3",
                    runtime="40 ms" if accepted else "N/A",
                    timestamp=s.at,
                )

    def submission_detail(self, submission_id: int) -> SubmissionDetail:
        self._call("submission_detail")
        slug, sub = next(
            (p.slug, s) for p in self.problems for s in p.subs if s.id == submission_id
        )
        return SubmissionDetail(
            runtime=40,
            memory=1000,
            code=f"# code for {submission_id}\n",
            timestamp=sub.at,
            status_code=10 if sub.status == "Accepted" else 11,
            lang=Lang(name="python3"),
            question=QuestionRef(question_id="1", title_slug=slug),
        )

    def question(self, slug: str) -> QuestionDetail:
        self._call("question")
        self.questions_requested.append(slug)
        p = self._problem(slug)
        return QuestionDetail(
            question_id="1",
            frontend_id="1",
            title=slug,
            title_slug=slug,
            statement=None if p.paid_only else "<p>statement</p>",
            difficulty=p.difficulty,
            is_paid_only=p.paid_only,
            ac_rate=50.0,
            similar_questions="[]",
        )


def sample_problems() -> list[FakeProblem]:
    """Newest first by last submission: walls-and-gates, two-sum, median."""
    return [
        FakeProblem(
            "two-sum",
            [
                FakeSub(101, "Wrong Answer", day(0)),
                FakeSub(102, "Compile Error", day(0.001)),
                FakeSub(103, "Accepted", day(0.002)),
                FakeSub(104, "Accepted", day(0.004)),  # 3 min later: merged
                FakeSub(105, "Accepted", day(30)),  # new solve, 0 wrong
            ],
            difficulty="Easy",
        ),
        FakeProblem("walls-and-gates", [FakeSub(201, "Accepted", day(50))], paid_only=True),
        FakeProblem(
            "median-of-two-sorted-arrays",
            [FakeSub(301, "Wrong Answer", day(9)), FakeSub(302, "Time Limit Exceeded", day(10))],
            difficulty="Hard",
        ),
    ]


@pytest.fixture
def fake() -> FakeLeetCode:
    return FakeLeetCode(sample_problems())
