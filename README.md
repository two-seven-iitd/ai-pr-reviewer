# AI PR Reviewer

A GitHub Action that automatically reviews pull requests using LLMs. When a PR is opened or updated, it analyzes the code changes, identifies bugs and security vulnerabilities, and posts review comments directly on the PR.

**Zero infrastructure required** — no servers, no databases, no Docker to manage. Add one workflow file, set one secret, done.

![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![Tests](https://img.shields.io/badge/tests-51%20passed-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Quick start (2 minutes)

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
      - uses: two-seven-iitd/ai-pr-reviewer@main
        with:
          openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}
```

**That's it.** Open a PR and the bot reviews it automatically.

---

## How it works

```
Developer opens PR
        │
        ▼
GitHub triggers the Action
        │
        ▼
┌───────────────────────────────────────────────┐
│              AI PR Reviewer                   │
│                                               │
│  1. Fetch PR diff from GitHub API             │
│  2. Parse unified diff → per-file changes     │
│  3. Skip lock files, images, generated code   │
│  4. Chunk code using AST (Python) or blocks   │
│  5. Send chunks to LLM concurrently           │
│  6. Map issues to exact diff positions        │
│  7. Post review with inline comments          │
└───────────────────────────────────────────────┘
        │
        ▼
Review comments appear on the PR
```

### What gets posted

- **Critical/High** severity issues → inline comments on the exact line in the diff
- **Medium/Low** severity issues → listed in the review summary (not inline, to avoid noise)
- All issues grouped by file, sorted by line number

---

## Configuration

All inputs are optional except `openrouter_api_key`:

```yaml
- uses: two-seven-iitd/ai-pr-reviewer@main
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

### Review profiles

| Profile | What it checks |
|---------|---------------|
| `all` | Security, bugs, performance, and code quality |
| `security` | SQL injection, XSS, auth bypass, secrets in code, path traversal |
| `performance` | N+1 queries, unnecessary allocations, blocking I/O, inefficient algorithms |
| `bugs` | Null references, off-by-one errors, race conditions, unhandled exceptions |
| `style` | Naming, DRY violations, complexity, missing error handling |

### Files automatically skipped

Lock files (`package-lock.json`, `yarn.lock`, `go.sum`, etc.), minified code (`.min.js`, `.min.css`), images, fonts, `node_modules/`, `__pycache__/`, `migrations/`, `generated/`, `vendor/`, `dist/`, `build/`.

Add more via the `exclude` input.

---

## Architecture

```
main.py                       ← GitHub Action entry point
app/
├── models.py                 ← Severity, ReviewComment, DiffFile, CodeChunk
├── review.py                 ← Orchestration pipeline + review body builder
├── github/
│   ├── client.py             ← GitHub REST API (fetch diff, post review)
│   ├── diff_parser.py        ← Unified diff → structured DiffFile objects
│   └── position_mapper.py    ← Source line number → GitHub diff position
└── analysis/
    ├── chunker.py            ← AST-aware (Python) + block-based code chunking
    ├── prompts.py            ← LLM system/user prompt construction
    └── llm.py                ← OpenAI SDK client with concurrent review
```

**8 source files.** No framework, no database, no cache, no config management. Just the review logic.

### How each piece works

**Diff parsing** — GitHub returns a unified diff (the text format with `+` and `-` lines). The parser converts this into `DiffFile` objects with structured hunks, tracking both old and new line numbers and diff positions.

**AST-aware chunking** — For Python files, the AST module parses the code into its syntax tree and extracts each function/class as a separate chunk. This gives the LLM complete logical units instead of arbitrary line ranges. Non-Python files use block-based chunking with 5-line overlap at boundaries so bugs that span chunk edges aren't missed.

**Concurrent LLM calls** — Multiple chunks are reviewed simultaneously using `asyncio.gather` with a semaphore (default: 5 concurrent). A 30-chunk PR finishes in ~15 seconds instead of ~90 seconds.

**Position mapping** — The LLM reports issues by source line number (e.g., "line 42"). But GitHub's review API needs the position within the diff. The mapper walks the diff's hunks to find the exact position, with a fallback that finds the nearest commentable line within 5 lines.

---

## Tests

```bash
pip install pydantic httpx pytest
pytest -v
```

```
51 passed in 2.5s
```

| Test file | Tests | What it verifies |
|-----------|-------|-----------------|
| `test_diff_parser.py` | 10 | Parsing unified diffs, multi-file diffs, language detection |
| `test_chunker.py` | 14 | AST chunking, block chunking with overlap, content hashing |
| `test_position_mapper.py` | 7 | Line-to-position mapping, nearest line fallback |
| `test_prompts.py` | 5 | Prompt construction, profile focus, line numbering |
| `test_review_builder.py` | 10 | Review body formatting, severity-based inline filtering |

No mocks, no external services needed — all tests run against pure logic.

---

## Design decisions

**Why a GitHub Action instead of a self-hosted server?**
A self-hosted bot needs Docker, PostgreSQL, Redis, a webhook tunnel (ngrok/Cloudflare), and ongoing maintenance. A GitHub Action needs one YAML file and one secret. It runs on GitHub's infrastructure, scales automatically, and costs nothing for public repos.

**Why AST-aware chunking?**
Sending an entire file to the LLM is wasteful and expensive. Splitting by line count risks cutting a function in half — the LLM might miss a bug that spans the boundary. AST parsing extracts complete functions and classes as natural review units. Block-based chunking with overlap is the fallback for non-Python files.

**Why concurrent LLM calls?**
A large PR might have 30+ relevant code chunks. Reviewing them sequentially takes minutes. `asyncio.gather` with a semaphore (configurable via `max_concurrent`) parallelizes the work while respecting API rate limits.

**Why only inline comments for critical/high?**
Too many inline comments make a PR noisy and developers start ignoring them. Critical bugs (security vulnerabilities, crashes) deserve direct attention on the code. Style suggestions belong in the summary where they're visible but not disruptive.

**Why OpenRouter instead of calling OpenAI/Anthropic directly?**
OpenRouter is a proxy that supports 100+ models from different providers through a single API (compatible with the OpenAI SDK). Switching models is a one-line config change — no code modifications, no new API keys.

---

## Action outputs

The action sets these outputs for use in subsequent workflow steps:

| Output | Description |
|--------|------------|
| `issues` | Total number of issues found |
| `comments` | Number of inline comments posted |
| `files_reviewed` | Number of files reviewed |
| `time_ms` | Review duration in milliseconds |

Example: fail the PR check if critical issues are found:

```yaml
steps:
  - uses: two-seven-iitd/ai-pr-reviewer@main
    id: review
    with:
      openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}

  - name: Check results
    if: steps.review.outputs.issues > 0
    run: echo "Found ${{ steps.review.outputs.issues }} issues"
```

## License

MIT
