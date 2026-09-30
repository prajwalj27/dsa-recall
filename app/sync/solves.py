"""Group a problem's submissions into solves.

A solve is one accepted submission plus the failed attempts before it; each solve becomes one
FSRS review (plan 004). Accepts within MERGE_WINDOW of a solve's first accept (runtime tweaks,
same-day resubmits) are merged into that solve rather than counted as new reviews.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

MERGE_WINDOW = timedelta(hours=24)
MAX_FAILED_DETAILS = 3  # failed attempts per solve whose code we fetch for mistake analysis


@dataclass(frozen=True)
class Attempt:
    id: int
    accepted: bool
    at: datetime


@dataclass(frozen=True)
class SolveSpec:
    accepted_submission_id: int
    accepted_at: datetime
    wrong_before_ac: int  # every failure counts, including Compile Error
    failed_submission_ids: tuple[int, ...]  # up to MAX_FAILED_DETAILS, most recent last


def group_solves(attempts: Iterable[Attempt]) -> list[SolveSpec]:
    solves: list[SolveSpec] = []
    pending: list[int] = []  # failures since the last solve (or merged accept)

    for attempt in sorted(attempts, key=lambda a: (a.at, a.id)):
        if not attempt.accepted:
            pending.append(attempt.id)
        elif solves and attempt.at - solves[-1].accepted_at < MERGE_WINDOW:
            pending.clear()  # same session as the current solve
        else:
            solves.append(
                SolveSpec(
                    accepted_submission_id=attempt.id,
                    accepted_at=attempt.at,
                    wrong_before_ac=len(pending),
                    failed_submission_ids=tuple(pending[-MAX_FAILED_DETAILS:]),
                )
            )
            pending.clear()

    return solves
