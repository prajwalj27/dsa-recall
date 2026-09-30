"""Use the review engine from the terminal (until the Today screen exists).

python -m app.engines.reviews due [--limit N]
python -m app.engines.reviews pending
python -m app.engines.reviews rate SOLVE_ID {again,hard,good,easy,saw}
python -m app.engines.reviews review SLUG {again,hard,good,easy,saw}
python -m app.engines.reviews study-mode {on,off} [--until YYYY-MM-DD]
python -m app.engines.reviews rebuild
"""

import argparse
import sys
from datetime import date

from sqlalchemy import func, select

from app.config import get_settings
from app.db.migrate import upgrade_to_head
from app.db.models import Card
from app.db.session import get_sessionmaker
from app.engines.reviews import (
    Choice,
    due_reviews,
    mark_reviewed,
    pending_ratings,
    rebuild_all,
    set_rating,
)
from app.settings_store import get_study_mode, set_study_mode

CHOICES = {"again": Choice.AGAIN, "hard": Choice.HARD, "good": Choice.GOOD, "easy": Choice.EASY}
CHOICES["saw"] = Choice.SAW_SOLUTION


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.engines.reviews", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    due = sub.add_parser("due", help="reviews due now, lowest recall first")
    due.add_argument("--limit", type=int, default=20)

    sub.add_parser("pending", help="solves awaiting your rating")

    rate = sub.add_parser("rate", help="rate (or re-rate) a solve")
    rate.add_argument("solve_id", type=int)
    rate.add_argument("choice", choices=CHOICES)

    review = sub.add_parser("review", help="mark a problem reviewed (re-solved elsewhere)")
    review.add_argument("slug")
    review.add_argument("choice", choices=CHOICES)

    study = sub.add_parser("study-mode", help="first solves default to 'Saw solution'")
    study.add_argument("state", choices=["on", "off"])
    study.add_argument("--until", type=date.fromisoformat, help="last day, YYYY-MM-DD")

    sub.add_parser("rebuild", help="rebuild every card from the review log")
    return parser


def main() -> int:
    args = _parser().parse_args()
    upgrade_to_head(get_settings().database_url)

    with get_sessionmaker()() as session, session.begin():
        match args.command:
            case "due":
                items = due_reviews(session)
                total_cards = session.scalar(select(func.count()).select_from(Card))
                print(f"{len(items)} of {total_cards} problems due for review")
                for item in items[: args.limit]:
                    overdue = f"{item.days_overdue}d overdue" if item.days_overdue else "due today"
                    print(f"  {item.recall:>4.0%}  {overdue:>13}  {item.title} ({item.difficulty})")
            case "pending":
                items = pending_ratings(session)
                print(f"{len(items)} solves awaiting a rating")
                for item in items:
                    print(
                        f"  #{item.solve_id}  {item.title} ({item.difficulty}), "
                        f"{item.wrong_before_ac} wrong, {item.accepted_at:%Y-%m-%d}, "
                        f"default: {item.default}"
                    )
            case "rate":
                card = set_rating(session, args.solve_id, CHOICES[args.choice])
                print(f"Rated #{args.solve_id} {args.choice}; next review {card.due:%Y-%m-%d}")
            case "review":
                card = mark_reviewed(session, args.slug, CHOICES[args.choice])
                print(f"Reviewed {args.slug}; next review {card.due:%Y-%m-%d}")
            case "study-mode":
                set_study_mode(session, args.state == "on", args.until)
                mode = get_study_mode(session)
                until = f" until {mode.until}" if mode.until else ""
                print(f"Study mode {'on' + until if mode.enabled else 'off'}")
            case "rebuild":
                print(f"Rebuilt {rebuild_all(session)} cards")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LookupError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
