# 002 — LeetCode client (build step 1, part 1)

## Context

Build step 1 (Sync + reviews) starts with `app/leetcode/`: the only code that talks to LeetCode. The design doc isolates it so that when LeetCode changes its undocumented GraphQL API, the fix stays in one module. This plan covers only the client (queries, response schemas, throttle, errors, auth check). Backfill/incremental sync, FSRS cards, and the Today screen come in later plans that build on it.

**Decisions made:**

- **Queries** are captured by the user from DevTools (exactly what leetcode.com sends).
- **Test fixtures** are small hand-written JSON fakes. Nothing recorded from the live account is committed. Fakes mirror the real shapes the user captures, trimmed and with placeholder code and usernames.
- **Premium** problems are out of scope for now. The user has no Premium, so this goes into the design doc as a later feature. The client only has to not crash when `content` is null / `isPaidOnly` is true.

**On approval:** copy this plan to `docs/plans/002 - LeetCode client.md` (never replace 001), and add the Premium later-feature bullet to `docs/DSA Recall - Design.md`.

## What we need before coding (user)

1. **`.env`** with `LEETCODE_USERNAME`, `LEETCODE_SESSION`, `LEETCODE_CSRFTOKEN` (DevTools → Application → Cookies → leetcode.com).
2. **Captured requests.** In DevTools → Network, filter `graphql`. For each request, copy the **request payload** (`query`, `variables`, `operationName`) and **one response**. Replace any solution code with `"..."` before pasting.

   | Operation | Where to trigger it |
   | --- | --- |
   | `userStatus` (often inside `globalData`) | Any page load while logged in |
   | `userProgressQuestionList` | leetcode.com/progress → the question list; also click "next page" once |
   | `questionSubmissionList` | Any solved problem → Submissions tab |
   | `submissionDetails` | Click one accepted submission in that tab |
   | `question` (problem statement, `similarQuestions`, `topicTags`, stats) | Open a problem's Description tab. Several queries fire; paste the ones containing `content`, `similarQuestions`, `topicTags`, `stats`/`acRate` |
   | `recentAcSubmissionList` | Your public profile page (leetcode.com/u/&lt;username&gt;) |

3. **Ordering check:** I need to know whether the progress list comes back ordered by most recent activity. This decides the incremental sync's early stop.

## Module design (`app/leetcode/`)

| File | Responsibility |
| --- | --- |
| `queries.py` | The captured GraphQL documents as constants, trimmed to the fields we use. Each has a comment saying which page it came from and the capture date. |
| `schemas.py` | Pydantic v2 models per response (camelCase aliases, `extra="ignore"`). They normalize at the boundary: epoch-string timestamps → UTC `datetime`, string IDs → `int`, `"52 ms"` → `runtime_ms: int \| None`, `stats`/`similarQuestions` JSON strings → parsed values, `acRate` → float. Models: `UserStatus`, `ProgressQuestion` + `ProgressPage`, `SubmissionSummary` + `SubmissionPage`, `SubmissionDetail`, `QuestionDetail`, `RecentAc`. |
| `throttle.py` | `Throttle(min_interval=1.0, clock, sleep)`: guarantees at least 1 s between request starts. The clock and sleep are injectable so tests don't wait. |
| `errors.py` | `LeetCodeError` base, plus `AuthExpiredError` (cookie invalid / `isSignedIn` false), `RateLimitedError` (retries exhausted), and `SchemaChangedError` (GraphQL `errors` or Pydantic validation failure; the UI later shows "sync broken" instead of storing bad data). |
| `client.py` | `LeetCodeClient(settings, http: httpx.Client \| None = None, throttle=None)`, a context manager. A private `_post(operation, query, variables, model)` handles headers (`Cookie`, `x-csrftoken`, `Referer`, `Content-Type`), the throttle, retries with exponential backoff on 429/403/5xx (4 attempts: 2 s, 4 s, 8 s), a 20 s timeout, GraphQL `errors`, and validation. |

Public client methods, one per design-doc query:

- `check_auth() -> UserStatus`: raises `AuthExpiredError` if not signed in, or if the username doesn't match `LEETCODE_USERNAME`
- `progress_page(skip, limit) -> ProgressPage` and `iter_progress() -> Iterator[ProgressQuestion]` (pages until `totalNum` is reached)
- `submissions(slug) -> Iterator[SubmissionSummary]`: newest first, following `offset`/`lastKey`/`hasNext`. The caller stops early at known IDs, which keeps incremental syncs cheap.
- `submission_detail(submission_id) -> SubmissionDetail`
- `question(slug) -> QuestionDetail`
- `recent_accepted(limit=20) -> list[RecentAc]`

A 403 from a bad cookie and a 403 from rate limiting look the same. So after retries are exhausted on 403, the client runs a single `userStatus` check to tell `AuthExpiredError` apart from `RateLimitedError`.

**Not in this plan:** writing to the DB, grouping into solves, resumable backfill state. All of that lives in `app/sync/` in the next plan.

## Tests (`tests/leetcode/`)

- `tests/fixtures/leetcode/*.json`: hand-written fakes, one per operation plus edge cases (paid-only question with `content: null`, a second page with `hasNext: false`, an empty submissions list, a response with `errors`)
- `httpx.MockTransport` routes on `operationName` to the fakes. The client gets a fake throttle clock.
- Cases:
  - Required headers and cookie are sent
  - Each schema parses its fake, and the normalizations are correct
  - Pagination (progress and submissions) stops correctly
  - Throttle spacing is ≥ 1 s using the fake clock
  - 429 → retry → success
  - 429 ×4 → `RateLimitedError`
  - `isSignedIn: false` → `AuthExpiredError`
  - Missing required field → `SchemaChangedError`
  - Paid-only question parses with `statement=None`

## Live smoke check (manual, nothing saved)

`python -m app.leetcode.smoke` uses the real `.env`. It prints the signed-in username, the total progress count, the first 3 progress items, one problem's submission count, and the detail of one accepted submission (without the code). It confirms the captured queries and schemas match reality. It's run manually, never in pytest.

## Files

- **New:** `app/leetcode/{queries,schemas,throttle,errors,client,smoke}.py`, `tests/leetcode/{__init__,conftest,test_client,test_schemas,test_throttle}.py`, `tests/fixtures/leetcode/*.json`, `docs/plans/002 - LeetCode client.md`
- **Edit:** `docs/DSA Recall - Design.md` (Later features: Premium problems)
- **Reuse:** `app/config.py` `Settings`/`get_settings` for credentials; no config changes needed

## Verification

1. `pytest` passes with no network access (MockTransport only); `ruff check .` is clean
2. `python -m app.leetcode.smoke` against the real account prints the expected username and counts that match leetcode.com/progress
3. Breaking the cookie in `.env` → the smoke check reports `AuthExpiredError` with a clear message
4. `git status` shows no `.env` and no real submission code in the fixtures

## Update 2026-09-29: queries verified live

Instead of a manual DevTools capture, the six queries were sent directly to `https://leetcode.com/graphql/` with the user's cookie (read-only, about 1 request per second). All six succeeded. Raw responses stayed in a local scratch folder; none are committed.

**Findings that shape the client:**

- **Operation name must match** the `query` document's name, or the server returns HTTP 400 "Unknown operation named …". Every query sends its own `operationName`.
- **`userStatus`:** `query globalData { userStatus { userId isSignedIn username } }` works.
- **`userProgressQuestionList(filters: {skip, limit})`:** returns `totalNum` and `questions`.
  - Results are **ordered by `lastSubmittedAt` descending**, so the incremental sync can stop at the first unchanged problem.
  - `lastSubmittedAt` is an ISO-8601 string with a timezone, e.g. `2026-09-27T21:34:09+00:00`.
  - `difficulty` is upper case (`EASY`/`MEDIUM`/`HARD`); `questionStatus` is `SOLVED`/`ATTEMPTED`; `lastResult` is a code such as `AC`/`WA`; `numSubmitted` is an int.
  - A skip past the end returns a short page (97 total, skip 80 → 17).
- **`questionSubmissionList`:**
  - Pages by **`offset`**. `lastKey` was always `null`, and `hasNext` drives paging; the last page can be empty.
  - Results come newest first.
  - `id` and `timestamp` (epoch seconds) are strings; `status` is an int code (10 Accepted, 14 TLE, 15 Runtime Error; others per LeetCode) and `statusDisplay` is the label.
  - `runtime`/`memory` are display strings (`"39 ms"`, `"36.6 MB"`), or `"N/A"` for failed runs.
- **`submissionDetails(submissionId: Int!)`:** `runtime` is an int in ms, `memory` an int in bytes, `timestamp` an int, `statusCode` an int; `lang { name verboseName }`, `question { questionId titleSlug }`, and `code` are present.
- **`question(titleSlug)`:**
  - `difficulty` is title case here (`Medium`), unlike the progress list, so normalize both to `Easy`/`Medium`/`Hard`.
  - **`acRate` is a direct float field** (59.50…), so there's no need to parse `stats`.
  - `similarQuestions` is a JSON-encoded string; `content` is HTML; `isPaidOnly` is a bool.
- **`recentAcSubmissionList(username, limit)`:** `id`/`timestamp` are strings; `limit: 20` returns 20.

**Consequences for the plan:** the "captured requests" step is done, and the smoke check becomes a regression check rather than the first validation. Fakes in `tests/fixtures/leetcode/` mirror these exact shapes, with placeholder code and usernames.

## Outcome (implemented 2026-09-29)

Implemented as planned in `app/leetcode/` (`queries`, `schemas`, `throttle`, `errors`, `client`, `smoke`), with 12 hand-written fakes in `tests/fixtures/leetcode/` and 30 tests in `tests/leetcode/`. Notes:

- Each query is an `Operation(name, field, document)` so the operation name, response field, and document can't drift apart.
- A 403 after all retries triggers one unretried `userStatus` check: signed out → `AuthExpiredError`, otherwise `RateLimitedError`. Persistent 5xx or network errors raise plain `LeetCodeError` (not rate limiting).
- A wrong account (cookie username ≠ `LEETCODE_USERNAME`) raises `LeetCodeError`, not `AuthExpiredError`.
- `question()` / `submission_detail()` raise `LeetCodeError` when LeetCode returns `null` (unknown slug, submission not visible).
- Verified live: `python -m app.leetcode.smoke` works against the real account (97 problems), and with a bogus session it exits 1 with `AuthExpiredError`.
