# DSA Recall — Design (local, LLM-based)

Sep 29, 2026 · @Prajwal Jaiswal

## Overview

DSA Recall is an open-source app you run locally that syncs your own LeetCode history and turns it into spaced-repetition reviews, suggestions for skills you struggle with, and an LLM-built skill tree of what you've learned. You keep solving on leetcode.com; the app only tracks.

**Goals**

- Track progress directly from LeetCode, with no manual logging beyond a one-click rating.
- Schedule re-solves with spaced repetition so solved problems stay remembered.
- Recognize the skills and mistakes you struggle with, and suggest more problems like them.
- Show where you stand as a skill tree that grows from the problems you've solved.

**Non-goals**

- A problem-solving platform, code editor, or judge.
- Curated playlists, "must solve" lists, or interview-readiness advice. Users solve whatever they want (Blind 75, NeetCode 150, anything else).
- Hosting, accounts, or a browser extension.

**Principles**

- **Local-first:** runs on the user's machine; data stays in one SQLite file.
- **LLM-based analysis, deterministic numbers:** the LLM produces labels and explanations; code computes schedules and scores.
- **Bring your own LLM:** users configure a provider in `.env` (OpenRouter, Ollama, or any OpenAI-compatible API). An LLM is required.
- **Polite to LeetCode:** one request at a time, about one per second.

## Architecture

&#91;embedded content: local architecture · 5 components, 2 external services\]

Sync pulls new submissions from LeetCode and hands new solves to the LLM pipeline. The engines compute schedules and scores, and the UI reads computed views, so viewing never triggers an LLM call. Every component reads and writes the same SQLite file.

## LeetCode sync

All data comes from LeetCode's GraphQL endpoint (`https://leetcode.com/graphql`) using the user's session cookie. A one-time backfill loads full history; incremental syncs fetch only what changed.

**Authentication (every request)**

- Headers: `Cookie: LEETCODE_SESSION=...; csrftoken=...`, `x-csrftoken: <csrftoken>`, `Referer: https://leetcode.com`, `Content-Type: application/json`.
- Every sync starts with `userStatus { isSignedIn username }`. If `isSignedIn` is false, the cookie has expired and the app asks for a fresh one.

**Queries**

| Query | Returns | Used for |
| --- | --- | --- |
| `userProgressQuestionList` (paged) | Every problem touched: slug, status (solved or attempted), last submitted time, submission count | Master list of what to fetch |
| `questionSubmissionList(questionSlug)` | All submissions for one problem: ID, status, language, runtime, timestamp | Attempt history, wrong counts, grouping into solves |
| `submissionDetails(submissionId)` | Code, runtime, memory | Solution analysis |
| `question(titleSlug)` | Statement, difficulty, tags, acceptance rate, similar questions | Problem analysis, suggestion candidates |
| `recentAcSubmissionList(username)` | Last \~20 accepted submissions | Cheap first check in incremental syncs |

These are LeetCode's internal, undocumented names. Before writing the client, copy the exact current queries from DevTools → Network → `graphql` on the Progress page and a problem's Submissions tab.

**Backfill (first run)**

1. Page through `userProgressQuestionList` for every solved or attempted problem.
2. Per problem: `question(titleSlug)`, then `questionSubmissionList`, then `submissionDetails` for each accepted submission plus up to 3 failed attempts before it.
3. Group attempts into solves, create FSRS cards, and replay solve history into FSRS in date order.
4. Queue LLM analysis for every solved problem.

For \~300 problems this is about 1,000–1,200 requests, roughly 20 minutes at 1 request per second. Each problem is marked done in `sync_state`, so an interrupted backfill resumes where it stopped.

**Incremental sync (on app open or "Sync")**

1. Auth check with `userStatus`.
2. Fetch the first page of `userProgressQuestionList` and compare each problem's last submitted time and submission count with stored values. If results come ordered by recent activity, stop at the first unchanged problem.
3. For each changed problem: new submissions from `questionSubmissionList` (stop at known IDs), `submissionDetails` for new accepted submissions and the failed attempts just before them, and `question(titleSlug)` only if the problem is new.
4. Update records: an accepted submission on a due problem counts as a review; a first accepted submission creates a card; failed-only submissions mark the problem "attempted, not yet solved."
5. Queue LLM analysis for anything new.

A typical daily sync is 5–15 requests.

**Politeness:** one request at a time, about one per second, exponential backoff on 429 or 403.

## LLM pipeline

Five LLM tasks produce labels and explanations; every number shown to the user comes from deterministic code. All results are cached, so viewing the app never triggers a call.

| Task | Input | Output (JSON) | Runs |
| --- | --- | --- | --- |
| Problem analysis | Statement, tags, difficulty | Techniques required, key insight, what makes it hard, optimal time/space | Once per problem |
| Taxonomy step | New technique labels from problem analysis | Map each label to an existing skill node, or create a node with links to related skills | When new labels appear, batched per sync |
| Solution analysis | Accepted code plus up to 3 failed attempts | Approach used, its complexity, whether it matches the optimal, mistakes in failed attempts | Once per accepted submission; skipped when a re-solve's normalized code hash matches an analyzed one |
| Profile insights | Aggregated stats from the engines | Short readable summary of patterns and recurring mistakes | Weekly or on demand |
| Suggestion rerank | Candidate list from the recommender, plus profile | Ordered picks with a reason each | At most once a day |

**Consolidation:** every \~20 new skill nodes (or weekly), one call merges near-duplicate nodes, such as "variable-size window" and "sliding window with hashmap." Node IDs stay stable; merged nodes point to their replacement through `merged_into`.

**Reliability**

- Every call returns JSON validated against a Pydantic schema, retried once on failure, at temperature 0.
- Reranking only chooses from the candidate list, and every returned slug is checked against the database.
- Results are keyed by problem slug or submission ID plus `prompt_version`; changing a prompt re-runs only the affected rows.
- Failed calls (rate limit, outage) mark items "pending analysis" and retry on the next sync.

**Provider**

- One OpenAI-compatible adapter covers OpenRouter, Ollama, and other compatible APIs.
- The model is configurable per task, e.g., a stronger code model for solution analysis and a cheaper one for taxonomy and insights.
- Set reasoning effort low where the model supports it; hidden reasoning tokens are billed as output.

**Call volume**

- Backfill: about 600–700 calls for \~300 solved problems, once.
- Typical day: 10–20 calls early on, settling to 5–8 as the problem cache fills; zero on days with no solves.
- Under 100k tokens a day, which is cents a month on hosted models and free on a local model.

## Spaced repetition

Each solved problem is one FSRS card scheduled by `py-fsrs`. A review means re-solving the problem on LeetCode; the next sync detects it and checks the review off.

**The user loop**

1. Solve on LeetCode as usual.
2. Open the app. It syncs and lists new solves under "Rate your new solves": Again / Hard / Good / Easy, with an inferred option pre-selected.
3. The app schedules the next review. Each successful review pushes the next one further out; Again brings it back soon.
4. On the due date the problem appears under "Due for review" with a link to LeetCode.
5. Re-solving it (a new accepted submission) checks it off at the next sync and asks for a rating. A "Mark reviewed" button covers re-solves done elsewhere.

**Inferred rating** (used when the user skips rating)

| Wrong submissions before accepted | Inferred rating |
| --- | --- |
| 3 or more | Again |
| 1–2 | Hard |
| 0 | Good |

**Daily target**

The user picks a mode in Settings. The target counts reviews only; suggestions show separately and never count toward it, and users can solve as much beyond the target as they like.

| Mode | Daily review target | Desired retention |
| --- | --- | --- |
| Casual | 3–5 | 0.90 |
| Steady | 6–10 | 0.90 |
| Interview prep | 10–20 | 0.95, with an optional end date after which the previous mode returns |
| Custom | Any number | User-set |

- More due than the target: show up to the target, lowest recall first; the rest roll over.
- Solving beyond the target: a re-solve of a card not yet due is logged as an early review, which FSRS handles; a new problem becomes a new card.
- Every review is kept in `review_log`, so FSRS parameters can later be tuned to the user's own history.

**Overdue reviews**

- They stay in the queue, labeled with days overdue; recall % keeps dropping.
- A late successful review is not wasted: FSRS pushes the next one further out.
- Snooze delays a review a few days; suspend removes a problem from reviews entirely.
- No escalating reminders; the due count simply stays visible.

**Returning users**

History is always kept. After a long break, FSRS decay has already lowered recall, so the queue shows the lowest-recall cards first; among long-idle cards, the ones learned least firmly surface first. Re-solve ratings then decide: Good after a long gap pushes a card far out, and Again brings it back to frequent practice. The app never defines basics or a learning order.

## Mastery and suggestions

Mastery is computed per skill node by code, not the LLM. Suggestions are chosen by code and ordered and explained by the LLM.

**Skill mastery**

For a skill with solved problems i, each problem contributes its current recall probability R\_i, weighted by difficulty and reduced by struggle:

```latex
\text{skill} = \frac{\sum_i w_i \, R_i \, (1 - s_i)}{\sum_i w_i}
```

- w\_i: difficulty weight, 1 / 1.5 / 2 for Easy / Medium / Hard.
- s\_i: struggle penalty from the latest rating: 0.3 for Again, 0.15 for Hard, 0 otherwise.

Then scale by coverage, so 2 solved problems count as weaker evidence than 8:

```latex
\text{mastery} = \text{skill} \times \min\left(1, \frac{n}{k}\right)
```

n is the number of solved problems in the skill; k is the coverage target (default 8). Mastery runs from 0 to 1.

**Weak skills:** mastery below 0.5 with struggle signals (wrong attempts, Again/Hard ratings). Skills below 0.5 mainly from time decay are dormant instead. Ranked lowest mastery first.

**Suggestions**

1. **Candidates (code):** unsolved problems in the weakest skills, within a difficulty band set by acceptance rate (higher acceptance at low mastery, lower as mastery rises), plus LeetCode's "similar questions" of problems the user struggled with. Capped at \~10 per day.
2. **Analysis:** candidates get problem analysis (cached), but don't join the skill tree until solved.
3. **Rerank (LLM):** orders candidates using the user's profile and gives a reason for each, e.g., "targets the boundary mistakes in your last 3 binary search attempts."

Suggestions are framed as "more problems like the ones you found hard," not as advice on what to solve to get hired.

## Skill tree

The skill tree is built entirely by the LLM from the problems the user has solved. It starts empty, grows as they solve, and shows only their own journey, not LeetCode's whole catalog.

**How it builds**

1. A solved problem gets problem analysis, which names the techniques it requires.
2. The taxonomy step maps each technique to an existing node, or creates a new node linked to related nodes already in the tree.
3. Consolidation periodically merges near-duplicate nodes, keeping IDs stable.
4. On first run, the backfill builds the tree from the user's full history.

Nodes appear only after an accepted solve. Edges connect only existing nodes; a new skill with no related node yet stands alone until one appears.

**Node states** (from mastery, computed on view)

| State | Condition |
| --- | --- |
| Active | Solved at least once; brightness shows mastery |
| Weak | Low mastery from struggle (wrong attempts, Again/Hard ratings) |
| Dormant | Solved before, but recall has faded from inactivity; shown as a faint outline until re-solved |
| Needs review | Has overdue reviews |
| Mastered | Mastery 0.8 or higher |

**Look and interactions**

- A force-directed "brain map" of glowing nodes on a dark canvas, loosely inspired by game status-window UIs; original styling, no copied names or art.
- Click a node: side panel with mastery, solved problems with recall %, due reviews, and suggestions for that skill.
- Hover: mastery and due count.
- Built with `react-force-graph-2d`, which draws nodes on a canvas so glow effects stay cheap.

## UI

Five pages in a sidebar, plus a problem detail panel that opens from any page. The top bar on every page shows a Sync button and the last-synced time; the sidebar shows the due count beside Today.

| Page | Purpose | Contents |
| --- | --- | --- |
| Today (home) | What to do now | Rate your new solves; Due for review (up to the daily target); Attempted, not yet solved; Suggested (not counted toward the target) |
| Skill tree | Where the user stands | Full-screen brain map; node side panel |
| Solved | Full record | Sortable, filterable table: problem, difficulty, skills, times solved, last solved, next review, status (learning, reviewing, mastered) |
| Insights | Trends | Solves and reviews per week, retention rate, most common mistake types, weekly LLM summary |
| Settings | Setup | LeetCode connection status, LLM provider and model per task, daily target mode (Casual, Steady, Interview prep, Custom), notifications, manual resync, export data |

**Today screen**

```
┌─ Today ─────────────────────────────────────────────┐
│ Rate your new solves (2)                            │
│   Longest Consecutive Sequence  Medium              │
│     [Again] [Hard] [Good●] [Easy]                   │
├─────────────────────────────────────────────────────┤
│ Due for review (3 of 5 today)                       │
│   ☐ Group Anagrams      Hashing   recall 71%  ↗     │
│   ☐ Kth Largest Elem.   Heaps     2 days overdue ↗  │
├─────────────────────────────────────────────────────┤
│ Attempted, not yet solved (1)                       │
│   ☐ Median of Two Sorted Arrays  Hard  last: TLE ↗  │
├─────────────────────────────────────────────────────┤
│ Suggested (2)                                       │
└─────────────────────────────────────────────────────┘
```

**Problem detail panel**

- Difficulty, skills (each links to its node in the tree), "Open on LeetCode"
- Timeline of submissions: failed attempts, accepts, reviews
- Approach and complexity from solution analysis, and whether it was optimal
- Next review date, recall %, snooze and suspend

**First run**

1. Validate LeetCode username and session cookie from `.env`.
2. Validate the LLM config with one test call; stop with a specific error if it fails.
3. Run the backfill with progress bars for syncing and analysis.
4. Open Today, with the skill tree already built.

**Notifications**

- Always: due count in the app, the browser tab title, and the favicon.
- Optional: a browser notification at a chosen time while the tab is open.
- Later: live desktop notifications (see Later features).
- No email or mobile push (no server).

## Data model

One local SQLite file with 14 tables in four groups. Mastery, node states, and due counts are computed on view, not stored. The session cookie and LLM key live only in `.env`.

| Table | One row per | Key columns |
| --- | --- | --- |
| `problems` | Problem solved or considered as a suggestion | `slug` (PK), `title`, `difficulty`, `ac_rate`, `topic_tags` (JSON), `similar_questions` (JSON), `statement`, `fetched_at` |
| `submissions` | Submission, accepted or failed | `submission_id` (PK), `slug`, `status`, `lang`, `timestamp`, `runtime_ms`, `code`, `code_hash` |
| `solves` | Accepted solve grouped with the failed attempts before it | `id`, `slug`, `accepted_submission_id`, `wrong_before_ac`, `accepted_at`, `rating` (1–4), `rating_inferred` |
| `cards` | Solved problem | `slug` (PK), `due`, `stability`, `difficulty`, `reps`, `lapses`, `state`, `last_review`, `suspended` |
| `review_log` | Review event | `slug`, `solve_id`, `rating`, `reviewed_at` |
| `skills` | Skill tree node | `id` (PK), `name`, `description`, `aliases` (JSON), `created_at`, `merged_into` |
| `skill_edges` | Link between two nodes | `from_skill`, `to_skill`, `type` (prerequisite or related) |
| `problem_skills` | Problem–skill link | `slug`, `skill_id`, `confidence` |
| `problem_analysis` | Problem | `slug` (PK), `techniques` (JSON), `key_insight`, `optimal_time`, `optimal_space`, `model`, `prompt_version` |
| `solution_analysis` | Analyzed accepted submission | `submission_id` (PK), `approach`, `time_complexity`, `space_complexity`, `is_optimal`, `mistakes` (JSON), `model`, `prompt_version` |
| `insights` | Insights summary | `created_at`, `text`, `stats_snapshot` (JSON) |
| `suggestions` | Daily suggestion | `date`, `slug`, `skill_id`, `reason`, `rank` |
| `settings` | Key-value setting | `target_mode`, `daily_target`, `desired_retention`, `interview_end_date`, `previous_mode` |
| `sync_state` | Key-value entry | `last_sync_at`, `backfill_done`, per-problem backfill progress |

The user's code stays in this file. It leaves the machine only when sent to the configured LLM provider, or never with a local model.

## Configuration, stack, and repo

A Python backend serves the built React frontend, so the app runs with one command and opens on `localhost`.

**`.env`** (the repo ships `.env.example` with OpenRouter and Ollama samples; `.env` is in `.gitignore`)

```
LEETCODE_USERNAME=
LEETCODE_SESSION=
LEETCODE_CSRFTOKEN=
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=            # empty for Ollama
LLM_MODEL=              # default for all tasks
LLM_MODEL_SOLUTION=     # optional per-task overrides
```

The session cookie gives full account access and expires every few weeks. The app only reads data and prompts for a fresh cookie when the auth check fails.

| Layer | Choice |
| --- | --- |
| Backend | Python, FastAPI |
| Scheduling | `py-fsrs` |
| Validation | Pydantic for LeetCode and LLM responses |
| Database | SQLite (SQLAlchemy) |
| LLM | One OpenAI-compatible adapter |
| Frontend | React, built and served by the backend |
| Skill tree | `react-force-graph-2d` |
| Tests | pytest with recorded LeetCode responses |

```
dsa-recall/
├── app/
│   ├── leetcode/      # client, queries, schemas, throttle
│   ├── sync/          # backfill, incremental, merge into solves
│   ├── llm/           # adapter, prompts, the five tasks
│   ├── engines/       # fsrs, mastery, recommender
│   ├── db/            # models, migrations
│   └── api/           # FastAPI routes for the UI
├── web/               # React app: today, skill-tree, solved, insights, settings
├── tests/
├── .env.example
└── README.md
```

## Build order

Each step is usable before the next starts.

1. **Sync + reviews:** LeetCode client, backfill and incremental sync, SQLite, FSRS cards, and the Today screen with rating and due reviews.
2. **LLM pipeline:** provider adapter and config check, problem analysis, solution analysis, taxonomy step, caching.
3. **Mastery + suggestions:** mastery scoring, candidate selection, rerank, Solved page.
4. **Skill tree:** brain map, node states, side panel.
5. **Insights + polish:** Insights page, notifications, snooze/suspend, settings, export.

Before step 2, hand-label 20–30 problems you know well (techniques, your approach) and use them to pick models per task.

## Risks and later features

The main risk is LeetCode changing its undocumented API; all LeetCode code lives in one module so fixes stay in one place.

| Risk | Mitigation |
| --- | --- |
| LeetCode renames queries or fields | Isolated `app/leetcode/` client, Pydantic validation, recorded-response tests, a "sync broken" message instead of bad data |
| Session cookie expires | `userStatus` check at every sync; prompt for a fresh cookie |
| Rate limiting | One request at a time, \~1/s, backoff on 429/403, resumable backfill |
| LLM output inconsistent across calls | Temperature 0, schema validation, stable node IDs, consolidation pass |
| LLM provider down or rate-limited | Items marked "pending analysis" and retried next sync |
| Leaked secrets | `.env` in `.gitignore`; cookie and key never written to the database |

**Later features**

- Manual "save for later" list: paste a LeetCode link to track a problem you haven't started, e.g., while working through a playlist.
- Live desktop notifications: a standalone script opens the SQLite file read-only every few minutes, finds cards whose due time has passed, and sends one native notification when reviews become due (via `desktop-notifier`). It runs at login or once a day via Task Scheduler, and keeps a small state file so it doesn't repeat itself. Optionally it runs a quick incremental sync first, so problems re-solved since the last sync aren't reported as due.
