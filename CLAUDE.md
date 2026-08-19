# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/src/test_engine.py

# Run tests matching a keyword
uv run pytest -k "dedup"

# Run only unit tests (skip network-dependent integration tests)
uv run pytest -m unit
uv run pytest -m "not integration"

# CLI: fetch AI news from all sources
uv run python -m src.main fetch --limit 20

# CLI: specific sources, output to file
uv run python -m src.main fetch -s arxiv,hackernews -o markdown -f daily.md

# Start the FastAPI backend (with hot reload)
uv run uvicorn backend.main:app --reload
```

## Architecture

This is a **dual-mode Python application** (CLI tool + Web API) that aggregates AI research content from multiple sources. It uses `uv` for package management and requires Python ≥ 3.13.

### Two entry points, one engine

```
CLI (src/main.py) ──→ NewsEngine ──→ SourcePlugin.fetch() × N
                          │
Web API (backend/main.py) ┘
                          ↓
              deduplicate → rank → output / save to SQLite
```

**`src/`** — The headless data pipeline: data model, source plugins, engine, ranking, LLM integration, CLI entry point. No web awareness.

**`backend/`** — FastAPI layer: REST API, SQLite storage, APScheduler for periodic collection, and the AI Agent (LLM + tool-use loop). Depends on `src/` for the engine and models.

### Core data flow

1. **Source plugins** (`src/sources/`) inherit from `SourcePlugin` (abstract `async fetch(limit) → list[Article]`). Four sources: HackerNews (Firebase API), ArXiv (official library), HuggingFace Papers (`/api/papers`), and RSS (`rss.py`, a configurable RSS/Atom aggregator driven by `RSS_FEEDS`, used for Chinese sources). CLI (`src/main.py`) keeps the original three; the scheduler registers all four via `SOURCE_REGISTRY`.

2. **NewsEngine.run()** concurrently calls all registered sources via `asyncio.gather`, tolerates individual source failures, then runs **cross-source dedup** (arxiv ID fingerprint matching across arxiv ↔ pwc ↔ HN) and **composite ranking** (`pipeline/ranking.py`: `normalized_score × time_decay (48h half-life) × source_weight`).

3. **Output**: In CLI mode, results pass through `filters.py` (keyword-based AI relevance gate) then to formatters (text/json/markdown). In backend mode, results go to `backend/database.py` (SQLite, WAL mode).

### AI Agent (`backend/agent/`)

A **tool-use loop** (not LangChain) built directly on the OpenAI-compatible SDK:

- `core.py` — main loop: system prompt → LLM call with tools → execute tool calls concurrently → repeat (max 5 turns). `chat()` takes `reading_history` (titles) and injects it into the system prompt to avoid re-recommending.
- `tools.py` — 5 tools all implemented: search_articles (ChromaDB semantic search with SQLite summary backfill; falls back to SQLite keyword search `_keyword_fallback` when ChromaDB returns empty), get_article_detail (SQLite), summarize_articles (LLM), analyze_trend (semantic search + LLM hotspot detection), trigger_collection (scheduler.collect_once). get_article_detail/summarize_articles implicitly record read article IDs into `user_profile.reading_history` via `_record_reading_history` (dedup, newest-first, cap 50).
- `prompts.py` — system prompt with date anchor, data boundary rules, user preference injection

### Vector store (`backend/vector_store.py`)

ChromaDB with `PersistentClient` and SentenceTransformer embeddings (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim). Public API: `add_articles()`, `search()` (semantic with optional source/days filter using Unix timestamp metadata), `clear()`, `delete_article()`. Thread-safe lazy init via double-checked locking. `_get_embedding_fn()` lazily initializes the embedding function to avoid blocking on import. Index is maintained by the scheduler at collection time — Agent reads directly, no per-request rebuild.

### LLM integration (`src/pipeline/llm.py`)

LLM is accessed via **OpenAI-compatible endpoint** (DeepSeek by default, configurable via `.env`). Key design: **graceful degradation** — when the LLM is unavailable, AI relevance judgment falls back to keyword matching (`filters.py`), and quality scoring returns `None`.

### Database (`backend/database.py`)

Three SQLite tables: `articles` (INSERT OR REPLACE by id), `collection_runs` (logs each collection), `user_profile` (single-row, interests/reading_history/language). JSON columns (tags, interests) are serialized as strings and deserialized on read. Two aggregate queries: `get_source_stats()` (GROUP BY source), `get_collection_stats()` (total runs/articles + recent runs with parsed source_stats). Auto-init on import.

### Scheduler (`backend/scheduler.py`)

APScheduler `AsyncIOScheduler` with interval job. `start()` is idempotent — fires an immediate collection on startup via `asyncio.ensure_future`, then repeats every `COLLECTION_HOURS` (default 6h, from `.env`). `collect_once()` pipeline: instantiate sources per `user_profile.selected_sources` (empty = all, via `SOURCE_REGISTRY`) → engine.run() → `_filter_ai_related()` (LLM semantic AI-relevance filter, 4-thread concurrent, falls back to keyword matching when LLM unavailable) → save_articles (SQLite) → add_articles (ChromaDB). `_collect_lock` (asyncio.Lock) prevents concurrent collection. Source toggles via `PUT /api/sources/{name}` only affect the scheduler (CLI unaffected).

## Key conventions

- **Tests mirror source structure**: `tests/src/test_engine.py` tests `src/engine.py`; `tests/backend/agent/test_agent.py` tests `backend/agent/core.py`. pytest config in `pyproject.toml` uses markers `unit`, `integration`, `slow`.
- **Config via `.env`**: `SQLITE_PATH`, `CHROMA_DIR`, `COLLECTION_LIMIT`, `COLLECTION_HOURS`, `RSS_FEEDS`, `DEEPSEEK_API_KEY`, `LLM_MODEL_ID`, `LLM_BASE_URL`, `LLM_TIMEOUT`.
- **Docstrings are Google style**: `Args:` / `Returns:` / `Raises:` sections.
- **Logging, not print**: Use `logging` (stderr) for diagnostics; stdout is reserved for CLI output that may be piped.
- **`_chat_json` is the LLM call facade**: All LLM calls go through `src/pipeline/llm._chat_json(system_prompt, user_content, max_tokens) → str | None` with JSON mode and temperature=0.

## Current project phase

Phases 0-4 complete; Phase 5 batch 1 (quality optimization + memory P1) + batch 2 (source toggles + RSS aggregation) complete. `user_profile.selected_sources` drives scheduler source selection (empty = all); `PUT /api/sources/{name}` toggles. Next: batch 3 (frontend). Note: 机器之心 official RSS is configured in `RSS_FEEDS` (free quota — frequent requests trigger 429 rate-limiting; scheduler's 6h interval is safe, avoid over-using `trigger_collection`). 知乎 needs login, public RSSHub instances are unreliable — additional Chinese sources require a self-hosted RSSHub appended to `RSS_FEEDS`.

## Test structure

Tests mirror the source tree under `tests/` — `tests/src/sources/test_hackernews.py` tests `src/sources/hackernews.py`, `tests/backend/routers/test_sources.py` tests `backend/routers/sources.py`. 172 total cases (164 unit + 8 integration).
