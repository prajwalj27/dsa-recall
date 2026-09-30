"""GraphQL documents for LeetCode's internal API (https://leetcode.com/graphql/).

These are undocumented. All were verified live on 2026-09-29 and trimmed to the fields we
use. The operation name sent with each request must match the name in its document.
If LeetCode renames something, fix it here and in `schemas.py` only.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Operation:
    name: str  # operationName; must match the document's query name
    field: str  # top-level field under "data" in the response
    document: str


USER_STATUS = Operation(
    name="globalData",
    field="userStatus",
    document="""
query globalData {
  userStatus { userId isSignedIn username }
}""",
)

# Ordered by lastSubmittedAt, most recent first. Variables: {"filters": {"skip", "limit"}}.
USER_PROGRESS_QUESTION_LIST = Operation(
    name="userProgressQuestionList",
    field="userProgressQuestionList",
    document="""
query userProgressQuestionList($filters: UserProgressQuestionListInput) {
  userProgressQuestionList(filters: $filters) {
    totalNum
    questions {
      frontendId title titleSlug difficulty lastSubmittedAt numSubmitted questionStatus lastResult
      topicTags { name slug }
    }
  }
}""",
)

# Newest first. Pages by offset; lastKey has been null in practice but is passed through.
QUESTION_SUBMISSION_LIST = Operation(
    name="submissionList",
    field="questionSubmissionList",
    document="""
query submissionList($offset: Int!, $limit: Int!, $lastKey: String, $questionSlug: String!) {
  questionSubmissionList(
    offset: $offset, limit: $limit, lastKey: $lastKey, questionSlug: $questionSlug
  ) {
    lastKey
    hasNext
    submissions { id titleSlug status statusDisplay lang runtime timestamp }
  }
}""",
)

SUBMISSION_DETAILS = Operation(
    name="submissionDetails",
    field="submissionDetails",
    document="""
query submissionDetails($submissionId: Int!) {
  submissionDetails(submissionId: $submissionId) {
    runtime memory code timestamp statusCode
    lang { name verboseName }
    question { questionId titleSlug }
  }
}""",
)

QUESTION = Operation(
    name="questionData",
    field="question",
    document="""
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId questionFrontendId title titleSlug content difficulty isPaidOnly acRate
    similarQuestions
    topicTags { name slug }
  }
}""",
)

RECENT_AC_SUBMISSIONS = Operation(
    name="recentAcSubmissions",
    field="recentAcSubmissionList",
    document="""
query recentAcSubmissions($username: String!, $limit: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit) { id title titleSlug timestamp }
}""",
)
