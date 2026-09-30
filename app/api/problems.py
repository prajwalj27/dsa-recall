from fastapi import APIRouter, HTTPException

from app.api.deps import Db
from app.api.schemas import (
    CardOut,
    ChangedOut,
    ChoiceIn,
    PauseIn,
    ProblemDetailOut,
    ProblemOut,
    ResumeIn,
    TimelineEntryOut,
)
from app.db.models import Card, Problem
from app.engines.reviews import (
    mark_reviewed,
    pause,
    problem_timeline,
    recall,
    resume,
    resume_all,
)
from app.timeutil import as_utc

router = APIRouter(prefix="/problems", tags=["problems"])


def leetcode_url(slug: str) -> str:
    return f"https://leetcode.com/problems/{slug}/"


def card_out(card: Card | None) -> CardOut | None:
    if card is None:
        return None
    return CardOut(
        due=as_utc(card.due),
        recall=recall(card),
        reps=card.reps,
        lapses=card.lapses,
        last_review=as_utc(card.last_review) if card.last_review else None,
    )


@router.post("/pause")
def pause_problems(body: PauseIn, db: Db) -> ChangedOut:
    """Take problems out of the review queue until resumed or solved again."""
    changed = pause(db, body.slugs)
    db.commit()
    return ChangedOut(changed=changed)


@router.post("/resume")
def resume_problems(body: ResumeIn, db: Db) -> ChangedOut:
    changed = resume_all(db) if body.all else resume(db, body.slugs)
    db.commit()
    return ChangedOut(changed=changed)


@router.get("/{slug}")
def problem_detail(slug: str, db: Db) -> ProblemDetailOut:
    problem = db.get(Problem, slug)
    if problem is None:
        raise HTTPException(404, f"Unknown problem '{slug}'")
    return ProblemDetailOut(
        problem=ProblemOut(
            slug=problem.slug,
            title=problem.title,
            difficulty=problem.difficulty,
            frontend_id=problem.frontend_id,
            topic_tags=problem.topic_tags or [],
            ac_rate=problem.ac_rate,
            is_paid_only=problem.is_paid_only,
            url=leetcode_url(problem.slug),
            paused=problem.paused,
        ),
        card=card_out(db.get(Card, slug)),
        timeline=[TimelineEntryOut.model_validate(e) for e in problem_timeline(db, slug)],
    )


@router.post("/{slug}/review")
def review_problem(slug: str, body: ChoiceIn, db: Db) -> CardOut | None:
    """Mark reviewed: a re-solve LeetCode won't show us."""
    if db.get(Problem, slug) is None:
        raise HTTPException(404, f"Unknown problem '{slug}'")
    try:
        card = mark_reviewed(db, slug, body.choice)
    except LookupError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    return card_out(card)
