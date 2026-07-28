# AI PR Reviewer

A GitHub Action that automatically reviews pull requests using LLMs. When a PR is opened or updated, it analyzes the changed code, identifies bugs, security vulnerabilities, and performance problems, and posts review comments directly on the PR — with inline comments on the exact lines that need attention.

**Zero infrastructure required** — no servers, no databases, no Docker to manage. Add one workflow file, set one secret, done.

![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![Tests](https://img.shields.io/badge/tests-53%20passed-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Category

**Backend / DevOps / Developer Tooling**

- **Type:** GitHub Action (Docker container action)
- **Language:** Python 3.11
- **Domain:** Automated Code Review, Static Analysis, CI/CD
- **Runs on:** GitHub Actions infrastructure (Ubuntu runners)

---

## Tech Stack

| Layer | Technology | Why |
|:------|:-----------|:----|
| **Runtime** | Python 3.11 | AST module for syntax-aware code parsing, asyncio for concurrency |
| **LLM Gateway** | [OpenRouter](https://openrouter.ai) via OpenAI SDK | Single API for 100+ models — switch models with one config change, no code modifications |
| **HTTP Client** | httpx (async) | Non-blocking GitHub API calls with connection pooling |
| **Data Validation** | Pydantic v2 | Type-safe models for review comments, diff files, and code chunks |
| **Packaging** | Docker (python:3.11-slim) | Reproducible container action that GitHub Actions pulls and runs |
| **Testing** | pytest | 53 tests, no mocks, no external services needed |
| **CI/CD** | GitHub Actions | The project *is* a GitHub Action — it runs inside GitHub's infrastructure |

**Total dependencies: 3** — `httpx`, `openai`, `pydantic`. No framework, no database, no cache, no config management.

---

## Quick Start (2 minutes)

### 1. Get an OpenRouter API key

Go to [openrouter.ai/keys](https://openrouter.ai/keys), sign up (free credits included), and create an API key.

### 2. Add the key to your repository

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

- **Name:** `OPENROUTER_API_KEY`
- **Secret:** paste your API key

### 3. Add the workflow file

Create `.github/workflows/ai-review.yml` in your repository:

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: two-seven-iitd/ai-pr-reviewer@v1
        with:
          openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}
```

**That's it.** Open a PR and the bot reviews it automatically.

---

## How It Works

```
Developer opens/updates a PR
         │
         ▼
GitHub triggers the Action
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                    AI PR Reviewer                       │
│                                                         │
│  1. Fetch the unified diff via GitHub REST API          │
│  2. Parse diff into structured per-file objects         │
│  3. Filter out lock files, images, generated code       │
│  4. Fetch full file content for each changed file       │
│  5. Chunk code — AST-aware for Python, blocks for rest  │
│  6. Keep only chunks that overlap with changed lines    │
│  7. Send chunks to LLM concurrently (semaphore-bound)  │
│  8. Parse JSON response into typed ReviewComment models │
│  9. Map issue line numbers → GitHub diff positions      │
│ 10. Post review: table summary + inline comments        │
└─────────────────────────────────────────────────────────┘
         │
         ▼
Review appears on the PR with inline comments
```

### What gets posted

- **Critical/High** severity → inline comments on the exact diff line + listed in a summary table
- **Medium/Low** severity → listed as bullet-point suggestions in the summary only (not inline, to reduce noise)
- Issues grouped by file, sorted by line number

**Example review comment format:**

> ## AI Code Review
>
> Found **5 issues** across **2 files** — **3 require attention**
>
> ### `app/payment.py`
>
> **Issues**
>
> | Line | Severity | Problem | Fix |
> |:-----|:---------|:--------|:----|
> | L8 | CRITICAL | SQL injection via string formatting | Use parameterized queries |
> | L26 | CRITICAL | Command injection via os.system() | Use subprocess with shell=False |
>
> **Suggestions**
>
> - **L40**: Division by zero when b is 0 — *Add a zero check before dividing*

---

## Architecture

```
ai-pr-reviewer/
├── action.yml                    ← GitHub Action definition (inputs, outputs, branding)
├── Dockerfile                    ← Container: python:3.11-slim + 3 pip packages
├── main.py                       ← Entry point: reads GitHub env vars, runs the pipeline
├── requirements.txt              ← httpx, openai, pydantic (3 dependencies total)
│
├── app/
│   ├── models.py                 ← Pydantic models: Severity, ReviewComment, DiffFile, CodeChunk
│   ├── review.py                 ← Orchestration: fetch → parse → chunk → review → post
│   │
│   ├── github/
│   │   ├── client.py             ← Async GitHub REST API client (diff, file content, reviews)
│   │   ├── diff_parser.py        ← Unified diff text → structured DiffFile objects
│   │   └── position_mapper.py    ← Source line number → GitHub diff position mapping
│   │
│   └── analysis/
│       ├── chunker.py            ← AST-aware (Python) + block-based code chunking
│       ├── prompts.py            ← LLM system/user prompt construction per profile
│       └── llm.py                ← OpenAI SDK client with concurrent review + retries
│
└── tests/
    ├── test_diff_parser.py       ← 10 tests: diff parsing, multi-file, language detection
    ├── test_chunker.py           ← 14 tests: AST chunking, block overlap, hashing
    ├── test_position_mapper.py   ←  7 tests: line-to-position, nearest-line fallback
    ├── test_prompts.py           ←  5 tests: prompt construction, profiles, line numbering
    └── test_review_builder.py    ← 12 tests: review body format, severity filtering
```

**8 source files. ~500 lines of application code. 53 tests.**

### Module Responsibilities

#### `main.py` — Entry Point
Reads GitHub Action environment variables (`GITHUB_TOKEN`, `GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`, `INPUT_*`), parses the PR event payload, constructs the `GitHubClient` and `LLMReviewer`, calls `run_review()`, and writes outputs to `GITHUB_OUTPUT`.

#### `app/models.py` — Data Models
Defines four Pydantic models that flow through the entire pipeline:
- **`Severity`** — enum with `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` and emoji mapping
- **`ReviewComment`** — a single issue: file, line, severity, issue text, suggestion, code context
- **`DiffFile`** — a parsed file from the diff: path, added/removed lines, hunks, language
- **`CodeChunk`** — a unit of code sent to the LLM: file path, code text, line range, type (function/class/block)

#### `app/review.py` — Orchestration Pipeline
The main `run_review()` function coordinates the full pipeline:
1. Fetch the PR diff via GitHub API
2. Parse it into `DiffFile` objects
3. Skip files matching ignore patterns (lock files, images, generated code, etc.)
4. Fetch full file content and chunk it
5. Filter to only chunks that overlap with changed lines
6. Send chunks to the LLM concurrently
7. Map each issue's line number to a diff position
8. Build the markdown review body (table for critical/high, bullets for medium/low)
9. Post the review with inline comments via GitHub API

Also contains `build_review_body()` which formats the final markdown, and `_should_skip()` which filters files against skip patterns.

#### `app/github/client.py` — GitHub API Client
Async HTTP client using httpx with three methods:
- `get_pr_diff()` — fetches the unified diff using the `application/vnd.github.v3.diff` accept header
- `get_file_content()` — fetches raw file content at a specific commit SHA
- `post_review()` — posts a review with a body and inline comments using the Pull Request Reviews API

#### `app/github/diff_parser.py` — Diff Parser
Parses GitHub's unified diff format line by line into structured `DiffFile` objects. Tracks:
- Added lines (with line numbers)
- Removed lines (with line numbers)
- Hunks with per-line diff positions (needed for GitHub's review comment API)
- Automatic language detection based on file extension (supports 16 languages)

#### `app/github/position_mapper.py` — Position Mapper
Solves the critical problem: the LLM reports issues by **source line number** (e.g., "line 42"), but GitHub's review API needs the **position within the diff**. Two strategies:
- `map_line_to_position()` — exact match: walks the diff hunks to find the target line
- `find_nearest_position()` — fallback: finds the closest commentable line within 5 lines (for when the exact line isn't in the diff)

#### `app/analysis/chunker.py` — Code Chunking
Splits file content into review-sized pieces:
- **AST-aware chunking (Python):** Uses `ast.parse()` to extract each function and class as a separate chunk. The LLM gets complete logical units instead of arbitrary line ranges. Falls back to block-based on syntax errors.
- **Block-based chunking (all other languages):** 60-line blocks with 5-line overlap at boundaries, so bugs that span chunk edges aren't missed.

#### `app/analysis/prompts.py` — Prompt Engineering
Constructs the system prompt and per-chunk user prompts:
- System prompt instructs the LLM to output a strict JSON array of issues with `line`, `severity`, `issue`, and `suggestion` fields
- User prompt includes the file path, line range, profile-specific focus instructions, and the code with absolute line numbers
- Profile focus overrides narrow the LLM's attention (security-only, bugs-only, etc.)

#### `app/analysis/llm.py` — LLM Client
Wraps the OpenAI SDK pointed at OpenRouter (`base_url="https://openrouter.ai/api/v1"`):
- `review_chunk()` — reviews a single chunk with 3 retries and exponential backoff
- `review_chunks()` — reviews multiple chunks concurrently using `asyncio.gather` with a configurable semaphore (default: 5 concurrent calls)
- Strips markdown fences from LLM responses before JSON parsing

---

## Configuration

All inputs are optional except `openrouter_api_key`:

```yaml
- uses: two-seven-iitd/ai-pr-reviewer@v1
  with:
    # Required
    openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}

    # Optional — all have sensible defaults
    model: 'deepseek/deepseek-v4-flash'     # Any model on OpenRouter
    profile: 'all'                           # all | security | performance | bugs | style
    max_files: '20'                          # Stop after reviewing this many files
    max_concurrent: '5'                      # Parallel LLM API calls
    exclude: 'docs/,scripts/'               # Extra paths to skip (comma-separated)
```

### Review Profiles

| Profile | What it checks |
|:--------|:---------------|
| `all` | Security, bugs, performance, and code quality |
| `security` | SQL injection, XSS, CSRF, auth bypass, secrets in code, path traversal |
| `performance` | N+1 queries, unnecessary allocations, blocking I/O, inefficient algorithms |
| `bugs` | Null references, off-by-one errors, race conditions, unhandled exceptions |
| `style` | Naming, DRY violations, complexity, missing error handling |

### Files Automatically Skipped

Lock files (`package-lock.json`, `yarn.lock`, `go.sum`, etc.), minified code (`.min.js`, `.min.css`), source maps, images, fonts, `node_modules/`, `__pycache__/`, `migrations/`, `generated/`, `vendor/`, `dist/`, `build/`.

Add more via the `exclude` input.

---

## Action Outputs

The action sets these outputs for use in subsequent workflow steps:

| Output | Description |
|:-------|:------------|
| `issues` | Total number of issues found |
| `comments` | Number of inline comments posted |
| `files_reviewed` | Number of files reviewed |
| `time_ms` | Review duration in milliseconds |

**Example:** fail the workflow if issues are found:

```yaml
steps:
  - uses: two-seven-iitd/ai-pr-reviewer@v1
    id: review
    with:
      openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}

  - name: Check results
    if: steps.review.outputs.issues > 0
    run: echo "Found ${{ steps.review.outputs.issues }} issues"
```

---

## Testing

```bash
pip install pydantic httpx pytest
pytest -v
```

```
53 passed in 2.5s
```

| Test File | Tests | What it verifies |
|:----------|:------|:-----------------|
| `test_diff_parser.py` | 10 | Parsing unified diffs, multi-file diffs, hunk positions, language detection |
| `test_chunker.py` | 14 | AST chunking for Python, block chunking with overlap, empty files, content hashing |
| `test_position_mapper.py` | 7 | Exact line-to-position mapping, nearest-line fallback, max-distance enforcement |
| `test_prompts.py` | 5 | Prompt construction, profile focus injection, line numbering format |
| `test_review_builder.py` | 12 | Table format for critical/high, bullet suggestions for medium/low, multi-file grouping |

All tests are pure-logic unit tests — no mocks, no external services, no API keys needed.

---

## Design Decisions

### Why a GitHub Action instead of a self-hosted server?

A self-hosted review bot needs Docker, PostgreSQL, Redis, a webhook tunnel (ngrok/Cloudflare), domain setup, SSL, and ongoing maintenance. That's 12+ setup steps before it reviews a single line of code.

A GitHub Action needs **one YAML file** and **one secret**. It runs on GitHub's infrastructure, scales automatically, and costs nothing for public repos. Two setup steps, done in 2 minutes.

### Why AST-aware chunking?

Sending an entire file to the LLM is wasteful and expensive. Splitting by line count risks cutting a function in half — the LLM might miss a bug that spans the boundary, or hallucinate issues from incomplete context.

AST parsing (`ast.parse()`) extracts complete functions and classes as natural review units. Each chunk is a self-contained logical block that the LLM can reason about fully. Block-based chunking with 5-line overlap is the fallback for non-Python files.

### Why concurrent LLM calls?

A large PR might have 30+ relevant code chunks. Reviewing them sequentially takes minutes. `asyncio.gather` with a configurable semaphore parallelizes the work while respecting API rate limits. A 30-chunk PR finishes in ~15 seconds instead of ~90 seconds.

### Why only inline comments for critical/high?

Too many inline comments make a PR noisy and developers start ignoring them. Critical bugs (security vulnerabilities, crashes) deserve direct attention on the code. Style suggestions belong in the summary where they're visible but not disruptive.

### Why OpenRouter instead of calling OpenAI/Anthropic directly?

OpenRouter is a proxy that supports 100+ models from different providers through a single API (compatible with the OpenAI SDK). Switching from DeepSeek to GPT-4o to Claude is a one-line config change — no code modifications, no new API keys, no SDK swaps.

### Why only 3 dependencies?

Every dependency is an attack surface and a maintenance burden. `httpx` for async HTTP, `openai` for the LLM SDK (reused via OpenRouter), `pydantic` for data validation. That's everything the action needs. No web framework, no ORM, no task queue, no config library.

---

## Potential Interview Questions & Answers

<details>
<summary><strong>Q: Walk me through what happens when a developer opens a PR.</strong></summary>

GitHub fires a `pull_request` webhook event. The Action runner starts a Docker container from our image. `main.py` reads the event payload from `GITHUB_EVENT_PATH` to get the PR number, repo, and head SHA. It creates an `httpx`-based GitHub client and an OpenAI SDK client pointed at OpenRouter.

The `run_review()` pipeline fetches the unified diff, parses it into per-file objects with line-level tracking, skips irrelevant files (lock files, images, etc.), fetches full file content for each changed file, chunks it using AST parsing for Python or 60-line blocks with overlap for other languages, filters to only chunks that touch changed lines, sends them to the LLM concurrently, maps the response line numbers back to diff positions, and posts a review with inline comments on critical/high issues and a summary table.
</details>

<details>
<summary><strong>Q: How do you handle the line number mapping problem?</strong></summary>

The LLM reports issues by absolute source line number (e.g., "bug on line 42"). But GitHub's Pull Request Review API requires a position relative to the diff — the nth line in the diff output, not the file.

The `position_mapper` module solves this in two steps:
1. **Exact match:** Walk all hunks in the diff file, check each added or context line for a matching `new_line` number.
2. **Nearest fallback:** If the exact line isn't in the diff (e.g., the issue is on a line just above a changed line), find the closest commentable line within 5 lines.

If neither matches (the line is completely outside the diff), the issue still appears in the summary but doesn't get an inline comment.
</details>

<details>
<summary><strong>Q: Why did you use AST parsing instead of just splitting by lines?</strong></summary>

Line-based splitting has a fundamental problem: it can cut a function in half. If a 40-line function starts at line 55 and you split at line 60, the LLM sees the first 5 lines of the function in one chunk and the remaining 35 in another — neither chunk has enough context to understand the logic.

AST parsing extracts each function and class as a complete unit. The LLM gets the full function body, including its signature, branches, return statements, and error handling. It can reason about the complete control flow.

The tradeoff is that AST parsing only works for Python. For other languages, I use block-based chunking with 5-line overlap at boundaries — so if a bug spans a chunk boundary, it appears in both chunks and the LLM has a chance to catch it.
</details>

<details>
<summary><strong>Q: How do you handle concurrency and rate limiting?</strong></summary>

I use `asyncio.gather` with an `asyncio.Semaphore` to limit concurrent LLM calls (default: 5). Each chunk review is wrapped in an `async with sem:` block, so at most 5 API calls are in flight at once.

Each individual call has 3 retries with exponential backoff (1s, 2s, 4s delays). If all retries fail for a chunk, that chunk is skipped silently — the rest of the review continues. This means a single flaky API response doesn't kill the entire review.

The semaphore limit is configurable via the `max_concurrent` input, so users can tune it based on their API plan's rate limits.
</details>

<details>
<summary><strong>Q: How do you ensure the LLM output is parseable?</strong></summary>

The system prompt strictly instructs the LLM to respond with only a JSON array — no markdown, no explanation, no fences. Each object must have exactly four fields: `line`, `severity`, `issue`, `suggestion`.

Despite this, LLMs sometimes wrap their response in markdown code fences. The `_strip_markdown_fences()` function handles that by stripping leading/trailing ` ``` ` lines.

The parsed JSON is then validated through Pydantic's `ReviewComment` model, which enforces types (line must be int, severity must be one of the enum values). If parsing fails entirely after 3 retries, the chunk is skipped and the review continues with whatever other chunks succeeded.
</details>

<details>
<summary><strong>Q: How would you scale this to handle very large PRs?</strong></summary>

Several mechanisms are already in place:
- **`max_files` limit (default: 20):** Caps the number of files reviewed, so a 200-file refactor doesn't trigger 200 API calls.
- **Relevance filtering:** Only chunks that overlap with changed lines are sent to the LLM. A 1000-line file with 5 changed lines might only send 1-2 chunks.
- **File skip patterns:** Lock files, images, generated code, and build artifacts are filtered out automatically.
- **Concurrent processing:** 5 parallel API calls (configurable) means a 20-chunk PR finishes in the time of 4 sequential calls.

For further scaling: you could add a token budget (stop reviewing when estimated cost exceeds a threshold), chunk deduplication via content hashing (the `hash_content()` function already exists), or a cache layer that skips re-reviewing unchanged chunks across PR updates.
</details>

<details>
<summary><strong>Q: Why did you choose to build this as a Docker container action vs. a JavaScript action?</strong></summary>

JavaScript actions are faster to start (no Docker build), but Python has two critical advantages for this project:
1. **`ast` module:** Python's built-in AST parser lets me extract functions and classes as natural code review units. There's no equivalent in Node.js without pulling in a large dependency like Babel or tree-sitter.
2. **`asyncio`:** Native async/await with `asyncio.gather` and semaphores gives fine-grained concurrency control for parallel LLM calls. Node.js has `Promise.all`, but Python's semaphore pattern is cleaner for rate limiting.

The Docker build adds ~15 seconds to the action startup, which is negligible compared to the LLM review time (typically 15-60 seconds).
</details>

<details>
<summary><strong>Q: What security considerations did you build in?</strong></summary>

- **No secrets in logs:** The API key is passed via GitHub Secrets and read from environment variables — never logged or exposed.
- **Minimal permissions:** The action only needs `contents: read` (to fetch file content) and `pull-requests: write` (to post reviews). No admin access, no push access.
- **Input validation:** All LLM responses are parsed through Pydantic models with strict types. Malformed responses are caught and skipped.
- **No code execution:** The action reads code and posts comments. It never executes, imports, or evaluates the PR's code.
- **Dependency minimalism:** 3 dependencies = 3 attack surfaces. No framework, no ORM, no middleware.
</details>

<details>
<summary><strong>Q: How is this different from existing tools like CodeRabbit, Codium, or GitHub Copilot code review?</strong></summary>

- **Self-owned:** You control the model, the prompts, and the data flow. No third-party SaaS sees your code beyond the LLM API.
- **Model-agnostic:** Switch between any of OpenRouter's 100+ models with one config line. Use a cheap model for style checks, an expensive one for security audits.
- **Transparent:** ~500 lines of Python. You can read every line, understand every decision, and modify anything. No black box.
- **Free for public repos:** Runs on GitHub Actions (free for public repos). Only cost is the LLM API calls via OpenRouter (which offers free-tier models).
</details>

---

## License

MIT
