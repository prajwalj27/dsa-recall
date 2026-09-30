"""Copy the user's LeetCode history into SQLite.

One algorithm serves both backfill and incremental sync. The progress list comes newest first,
and each problem's LeetCode change markers (last_submitted_at, num_submitted) are stored in the
same transaction as its submissions. So a problem with matching markers is fully synced:

- backfill (until `backfill_done`): walk the whole list, skipping unchanged problems. An
  interrupted backfill resumes by itself.
- incremental: stop at the first unchanged problem; everything older is unchanged too.
"""

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Problem, Solve, Submission, SyncState
from app.engines.reviews import HISTORY, INFERRED, schedule_new_solves
from app.leetcode import (
    AuthExpiredError,
    LeetCodeClient,
    LeetCodeError,
    RateLimitedError,
    SchemaChangedError,
)
from app.leetcode.schemas import ProgressQuestion
from app.sync.codehash import code_hash
from app.sync.progress import ErrorKind, RunState, SyncProgress
from app.sync.solves import Attempt, group_solves
from app.timeutil import utc_naive, utc_now

log = logging.getLogger(__name__)

ACCEPTED_STATUS = "Accepted"
# LeetCode's own failures: stored, but not the user's mistake, so not a wrong attempt.
# (LeetCode's numSubmitted leaves these out too.)
IGNORED_STATUSES = {"Internal Error"}
INCREMENTAL_PAGE_SIZE = 20

SessionFactory = Callable[[], Session]
Reporter = Callable[[SyncProgress], None]


def get_state(session: Session, key: str, default: Any = None) -> Any:
    row = session.get(SyncState, key)
    return default if row is None else row.value


def set_state(session: Session, key: str, value: Any) -> None:
    session.merge(SyncState(key=key, value=value))


def run_sync(
    session_factory: SessionFactory,
    client: LeetCodeClient,
    progress: SyncProgress | None = None,
    *,
    full: bool = False,
    report: Reporter | None = None,
) -> SyncProgress:
    """Run one sync, then schedule reviews for new solves.

    Never raises for LeetCode or DB problems; the outcome is in the returned progress.
    """
    progress = progress or SyncProgress()
    progress.reset()  # the manager reuses one instance across runs
    progress.state = RunState.RUNNING
    progress.started_at = utc_now()
    notify = report or (lambda _p: None)

    try:
        _walk(session_factory, client, progress, full, notify)
    except LeetCodeError as exc:
        _fail(progress, _error_kind(exc), str(exc))
    except Exception as exc:
        log.exception("Sync failed")
        _fail(progress, ErrorKind.OTHER, f"{type(exc).__name__}: {exc}")

    # Even if the walk stopped early, solves it committed should get cards.
    progress.phase = "scheduling"
    progress.current_slug = None
    notify(progress)
    try:
        with session_factory() as session, session.begin():
            progress.scheduled = schedule_new_solves(session)
    except Exception as exc:
        log.exception("Scheduling reviews failed")
        if progress.error_kind is None:
            _fail(progress, ErrorKind.OTHER, f"Scheduling reviews failed: {exc}")

    if progress.error_kind is None:
        progress.state = RunState.SUCCEEDED
    progress.phase = "done"
    progress.finished_at = utc_now()
    notify(progress)
    return progress


def _walk(
    session_factory: SessionFactory,
    client: LeetCodeClient,
    progress: SyncProgress,
    full: bool,
    notify: Reporter,
) -> None:
    progress.phase = "auth"
    notify(progress)
    client.check_auth()

    with session_factory() as session:
        backfill_done = bool(get_state(session, "backfill_done", False))
    backfill = full or not backfill_done
    # Solves found before the first backfill finishes are history: rated silently.
    rating_source = HISTORY if not backfill_done else INFERRED
    progress.mode = "backfill" if backfill else "incremental"

    progress.phase = "listing"
    notify(progress)
    if backfill:
        remote = list(client.iter_progress())
        progress.total = len(remote)
    else:
        remote = client.iter_progress(page_size=INCREMENTAL_PAGE_SIZE)

    progress.phase = "problems"
    for question in remote:
        progress.current_slug = question.title_slug
        with session_factory() as session, session.begin():
            problem = session.get(Problem, question.title_slug)
            unchanged = problem is not None and _markers_match(problem, question)
            if unchanged and not backfill:
                break
            if not unchanged:
                _sync_problem(session, client, question, problem, progress, rating_source)
        progress.done += 1
        notify(progress)

    with session_factory() as session, session.begin():
        set_state(session, "last_sync_at", utc_now().isoformat())
        if backfill:
            set_state(session, "backfill_done", True)


def _fail(progress: SyncProgress, kind: ErrorKind, message: str) -> None:
    progress.state = RunState.FAILED
    progress.error_kind = kind
    progress.error = message


def _markers_match(problem: Problem, question: ProgressQuestion) -> bool:
    return (
        problem.last_submitted_at == utc_naive(question.last_submitted_at)
        and problem.num_submitted == question.num_submitted
    )


def _error_kind(exc: LeetCodeError) -> ErrorKind:
    if isinstance(exc, AuthExpiredError):
        return ErrorKind.AUTH_EXPIRED
    if isinstance(exc, RateLimitedError):
        return ErrorKind.RATE_LIMITED
    if isinstance(exc, SchemaChangedError):
        return ErrorKind.SCHEMA_CHANGED
    return ErrorKind.OTHER


def _sync_problem(
    session: Session,
    client: LeetCodeClient,
    question: ProgressQuestion,
    problem: Problem | None,
    progress: SyncProgress,
    rating_source: str,
) -> None:
    """Bring one problem fully up to date. Runs inside the caller's transaction."""
    slug = question.title_slug
    if problem is None:
        problem = Problem(slug=slug)
        session.add(problem)
    problem.title = question.title
    problem.difficulty = question.difficulty
    problem.frontend_id = question.frontend_id
    problem.topic_tags = [tag.model_dump() for tag in question.topic_tags]
    problem.question_status = question.question_status
    problem.last_result = question.last_result

    if problem.fetched_at is None:
        detail = client.question(slug)
        problem.statement = detail.statement
        problem.ac_rate = detail.ac_rate
        problem.is_paid_only = detail.is_paid_only
        problem.similar_questions = [q.model_dump() for q in detail.similar_questions]
        problem.fetched_at = utc_naive(utc_now())

    # New submissions: newest first, stop at the first one we already have.
    known = set(session.scalars(select(Submission.submission_id).where(Submission.slug == slug)))
    new = []
    for summary in client.submissions(slug):
        if summary.id in known:
            break
        new.append(summary)
    session.add_all(
        Submission(
            submission_id=s.id,
            slug=slug,
            status=s.status_display,
            lang=s.lang,
            timestamp=utc_naive(s.timestamp),
            runtime_ms=s.runtime_ms,
        )
        for s in new
    )
    session.flush()
    progress.new_submissions += len(new)

    # Regroup everything; only solves we don't have yet are inserted, so existing ones
    # (and ratings attached to them later) never change.
    submissions = session.scalars(select(Submission).where(Submission.slug == slug)).all()
    attempts = [
        Attempt(s.submission_id, s.status == ACCEPTED_STATUS, s.timestamp)
        for s in submissions
        if s.status not in IGNORED_STATUSES
    ]
    existing = set(session.scalars(select(Solve.accepted_submission_id).where(Solve.slug == slug)))
    for spec in group_solves(attempts):
        if spec.accepted_submission_id in existing:
            continue
        session.add(
            Solve(
                slug=slug,
                accepted_submission_id=spec.accepted_submission_id,
                wrong_before_ac=spec.wrong_before_ac,
                accepted_at=spec.accepted_at,
                rating_source=rating_source,
            )
        )
        for submission_id in (spec.accepted_submission_id, *spec.failed_submission_ids):
            _fetch_code(session, client, submission_id)
        progress.new_solves += 1

    problem.last_submitted_at = utc_naive(question.last_submitted_at)
    problem.num_submitted = question.num_submitted


def _fetch_code(session: Session, client: LeetCodeClient, submission_id: int) -> None:
    submission = session.get(Submission, submission_id)
    if submission is None or submission.code is not None:
        return
    detail = client.submission_detail(submission_id)
    submission.code = detail.code
    submission.code_hash = code_hash(detail.code)
    if submission.runtime_ms is None:
        submission.runtime_ms = detail.runtime_ms
