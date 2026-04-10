# 05 — PostgreSQL Persistent Agent 🐘

A conversational **Adaptive Trip Planner** agent backed by **PostgreSQL** for fully persistent memory.
Sessions survive process restarts, container restarts, and can be shared across multiple runs.

---

## 📁 Directory Structure

```
05_postgres_agent/
├── agent.py      # LlmAgent definition (postgres_trip_planner)
├── db_setup.py   # PostgreSQL schema setup (auto-run on startup)
├── main.py       # Entry point — runs 3 test cases
└── README.md     # This file
```

---

## 🖥️ Fresh Clone — What Happens on a New Machine

```bash
git clone <repo>
cd memory_agent_starter_googleai
pip install -r requirements.txt
# add GOOGLE_API_KEY + PostgreSQL credentials to .env
docker run --name adk-postgres -e POSTGRES_PASSWORD=postgres123 -e POSTGRES_DB=adk_sessions -p 5432:5432 -d postgres:16
# wait ~10 seconds for PostgreSQL to initialise
python 05_postgres_agent/main.py
```

That's all. Here's what happens internally on first run:

```
main.py starts
  │
  ├── ensure_tables()
  │     ├── PostgreSQL DB is empty (no tables)
  │     ├── Creates all 5 tables with v1 schema (JSONB columns)
  │     ├── Creates update_timestamp trigger for sessions/app_states/user_states
  │     └── Inserts adk_internal_metadata: schema_version = '1'
  │
  ├── DatabaseSessionService connects to PostgreSQL
  │     └── Reads adk_internal_metadata → schema_version = '1' → uses v1 JSON ✅
  │
  └── Agent runs normally ✅

Second run onwards:
  ├── ensure_tables()
  │     ├── adk_internal_metadata exists ✓
  │     ├── event_data column exists ✓
  │     └── Does nothing — zero SQL, zero warnings ✅
  └── Agent resumes from persisted sessions ✅
```

---

## 🐳 Docker — Start PostgreSQL

> **This is the only infrastructure you need before running the agent.**

### Start a fresh PostgreSQL 16 container

```bash
docker run --name adk-postgres \
  -e POSTGRES_PASSWORD=postgres123 \
  -e POSTGRES_DB=adk_sessions \
  -e POSTGRES_USER=postgres \
  -p 5432:5432 \
  -d postgres:16
```

**On Windows (single line):**
```cmd
docker run --name adk-postgres -e POSTGRES_PASSWORD=postgres123 -e POSTGRES_DB=adk_sessions -e POSTGRES_USER=postgres -p 5432:5432 -d postgres:16
```

| Flag | Value | Description |
|------|-------|-------------|
| `--name` | `adk-postgres` | Container name |
| `POSTGRES_PASSWORD` | `postgres123` | Password for postgres user |
| `POSTGRES_DB` | `adk_sessions` | Auto-created database |
| `POSTGRES_USER` | `postgres` | Default superuser |
| `-p 5432:5432` | host:container | Exposes PostgreSQL on localhost |
| `-d` | — | Run in background (detached) |
| `postgres:16` | — | PostgreSQL 16 image |

---

## ⚙️ Useful Docker Commands

```bash
# Check container is running
docker ps

# View PostgreSQL startup logs
docker logs -f adk-postgres

# Stop the container
docker stop adk-postgres

# Start it again (data is preserved)
docker start adk-postgres

# Stop and remove (DELETES ALL DATA)
docker stop adk-postgres && docker rm adk-postgres

# Open a psql shell inside the container
docker exec -it adk-postgres psql -U postgres -d adk_sessions

# From inside psql — inspect tables
\dt
SELECT id, app_name, user_id FROM sessions;
SELECT id, session_id, timestamp FROM events ORDER BY timestamp DESC LIMIT 10;
\q
```

---

## 🔧 Environment Variables

The `.env` file lives in the **project root**:

```dotenv
GOOGLE_API_KEY=your_google_api_key_here

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=adk_sessions
```

---

## 🧠 How It Works

### Architecture

```
main.py
  │
  ├── ensure_tables()       # Creates/validates PostgreSQL schema on startup
  │     └── db_setup.py
  │
  ├── DatabaseSessionService(db_url="postgresql+asyncpg://postgres:postgres123@127.0.0.1:5432/adk_sessions")
  │
  └── Runner
        └── LlmAgent (postgres_trip_planner)
              └── gemini-2.5-flash + google_search tool
```

### SQLite vs MySQL vs PostgreSQL — Comparison

| | SQLite (`03`) | MySQL (`04`) | PostgreSQL (`05`) |
|---|---|---|---|
| **Setup** | None — just a file | Docker required | Docker required |
| **Driver** | `aiosqlite` | `aiomysql` | `asyncpg` |
| **`db_url` prefix** | `sqlite+aiosqlite:///` | `mysql+aiomysql://` | `postgresql+asyncpg://` |
| **JSON columns** | `TEXT` | `LONGTEXT` | `JSONB` (binary, indexed) |
| **Timestamps** | `TEXT` | `DATETIME(6)` | `TIMESTAMPTZ` |
| **Auto-update time** | manual | `ON UPDATE` clause | managed by SQLAlchemy |
| **Schema reset** | delete `.db` file | `DROP TABLE` | `DROP TABLE CASCADE` |
| **Best for** | Local dev | Production (web apps) | Production (analytics, scale) |
| **`DatabaseSessionService`** | ✅ Same ADK API | ✅ Same ADK API | ✅ Same ADK API |

**The only real difference across all three is the `db_url`.**

---

## 🗃️ Database Schema (ADK v1)

All tables are created automatically by `db_setup.py` on first run.

```
adk_sessions database
├── adk_internal_metadata   ← schema version marker (schema_version=1)
├── sessions                ← one row per session, state as JSONB
├── events                  ← one row per event, event_data as JSONB
├── app_states              ← per-app state as JSONB
└── user_states             ← per-user state as JSONB
```

### PostgreSQL-specific features used
- **`JSONB`** — binary JSON storage with indexing support (faster than TEXT-based JSON)
- **`TIMESTAMPTZ`** — timezone-aware timestamps, managed by SQLAlchemy `onupdate`
- **`CASCADE`** on foreign keys — deleting a session removes all its events

> **Key:** The `adk_internal_metadata` table with `schema_version=1` tells ADK
> to use v1 JSON serialization. Without it, ADK misdetects the schema as
> legacy v0 (Pickle) and fails.

---

## 🧪 Test Cases in `main.py`

### Test 1 — New Session
Creates a fresh session and sends the first message.
Agent learns: destination = Kyoto, loves temples, vegetarian.

### Test 2 — Resume Session (Persistent Memory)
Re-fetches the **same session** from PostgreSQL (simulating a restart).
Agent remembers preferences from Test 1 — proves PostgreSQL persistence.

### Test 3 — Cross-Session Context Injection
Reads all events from the old session, extracts conversation text,
and injects it as context into a **brand new session** for a different city.
Demonstrates carrying user preferences across completely separate trips.

---

## 🐛 Troubleshooting

### `Connection refused on 127.0.0.1:5432`
PostgreSQL container is not running.
```bash
docker start adk-postgres
# or start fresh:
docker run --name adk-postgres -e POSTGRES_PASSWORD=postgres123 -e POSTGRES_DB=adk_sessions -p 5432:5432 -d postgres:16
```

### `password authentication failed`
Check `.env` — `POSTGRES_PASSWORD` must match what was used in `docker run`.

### `GOOGLE_API_KEY not found`
Create `.env` in the project root:
```dotenv
GOOGLE_API_KEY=your_actual_key_here
```

### Schema errors
`db_setup.py` auto-detects and fixes outdated schemas on every startup.
If problems persist, wipe and restart the container:
```bash
docker stop adk-postgres && docker rm adk-postgres
docker run --name adk-postgres -e POSTGRES_PASSWORD=postgres123 -e POSTGRES_DB=adk_sessions -p 5432:5432 -d postgres:16
```

---

## 📚 Key Dependencies

| Package | Purpose |
|---------|---------|
| `google-adk` | Agent Development Kit — agents, sessions, runners |
| `google-genai` | Gemini model access |
| `sqlalchemy[asyncio]` | Async ORM used by `DatabaseSessionService` |
| `asyncpg` | Async PostgreSQL driver for SQLAlchemy |
| `python-dotenv` | Load `.env` variables |

Install:
```bash
pip install asyncpg
```
Or add `asyncpg` to `requirements.txt`.

