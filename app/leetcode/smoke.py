"""Manual check of the LeetCode client against your real account.

    python -m app.leetcode.smoke

Read-only; prints a short summary (never your code or cookie) and saves nothing.
"""

import sys

from app.config import get_settings
from app.leetcode import LeetCodeClient, LeetCodeError


def main() -> int:
    try:
        with LeetCodeClient(get_settings()) as client:
            status = client.check_auth()
            print(f"Signed in as {status.username}")

            page = client.progress_page(limit=3)
            print(f"Problems touched: {page.total_num}")
            for q in page.questions:
                print(
                    f"  {q.title} [{q.difficulty}] {q.question_status}, last {q.last_submitted_at}"
                )

            slug = next((q.title_slug for q in page.questions if q.solved), None)
            if slug is None:
                print("No solved problem on the first page; skipping submission checks.")
                return 0

            subs = list(client.submissions(slug))
            accepted = [s for s in subs if s.accepted]
            print(f"{slug}: {len(subs)} submissions, {len(accepted)} accepted")

            if accepted:
                detail = client.submission_detail(accepted[0].id)
                print(
                    f"  latest accepted: {detail.lang.verbose_name}, {detail.runtime_ms} ms, "
                    f"{detail.memory_bytes} bytes, code {len(detail.code)} chars"
                )

            question = client.question(slug)
            print(
                f"  question: #{question.frontend_id} {question.difficulty}, "
                f"acceptance {question.ac_rate:.1f}%, {len(question.topic_tags)} tags, "
                f"{len(question.similar_questions)} similar"
            )

            recent = client.recent_accepted()
            print(f"Recent accepted submissions: {len(recent)}")
    except LeetCodeError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
