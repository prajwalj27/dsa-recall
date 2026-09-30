from datetime import UTC

from app.leetcode.schemas import (
    ProgressPage,
    QuestionDetail,
    RecentAc,
    SubmissionDetail,
    SubmissionPage,
)
from tests.leetcode.conftest import load


def test_progress_page_normalizes_difficulty_and_dates() -> None:
    page = ProgressPage.model_validate(load("progress_page_1")["data"]["userProgressQuestionList"])

    oranges, median = page.questions
    assert page.total_num == 3
    assert (oranges.difficulty, median.difficulty) == ("Medium", "Hard")
    assert oranges.last_submitted_at.isoformat() == "2026-09-27T21:34:09+00:00"
    assert oranges.solved and not median.solved
    assert [t.slug for t in oranges.topic_tags] == ["array", "breadth-first-search"]


def test_submission_summary_parses_ids_runtime_and_epoch() -> None:
    page = SubmissionPage.model_validate(
        load("submissions_page_1")["data"]["questionSubmissionList"]
    )

    accepted, failed = page.submissions
    assert accepted.id == 3003 and accepted.accepted
    assert accepted.runtime_ms == 39
    assert accepted.timestamp.tzinfo == UTC
    assert int(accepted.timestamp.timestamp()) == 1790370665
    assert not failed.accepted and failed.runtime_ms is None  # "N/A"


def test_submission_detail_uses_numeric_runtime_and_memory() -> None:
    detail = SubmissionDetail.model_validate(load("submission_detail")["data"]["submissionDetails"])

    assert detail.runtime_ms == 39
    assert detail.memory_bytes == 36_600_000
    assert int(detail.timestamp.timestamp()) == 1790370665
    assert detail.lang.name == "python3"
    assert detail.question.title_slug == "two-sum"


def test_question_parses_similar_questions_json_string() -> None:
    question = QuestionDetail.model_validate(load("question")["data"]["question"])

    assert question.frontend_id == "994"
    assert question.statement and question.statement.startswith("<p>")
    assert question.ac_rate is not None and round(question.ac_rate, 1) == 59.5
    assert [(s.title_slug, s.difficulty) for s in question.similar_questions] == [
        ("walls-and-gates", "Medium")
    ]


def test_paid_only_question_has_no_statement() -> None:
    question = QuestionDetail.model_validate(load("question_paid_only")["data"]["question"])

    assert question.is_paid_only
    assert question.statement is None
    assert question.similar_questions == []


def test_recent_ac_ids_are_ints() -> None:
    items = load("recent_ac")["data"]["recentAcSubmissionList"]
    assert [RecentAc.model_validate(x).id for x in items] == [3003, 2001]
