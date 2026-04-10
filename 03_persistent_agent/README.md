# 03 — SQLite Persistent Agent 🗃️

A conversational **Adaptive Trip Planner** agent backed by **SQLite** for persistent memory.
Sessions survive process restarts and are stored in a local `sessions.db` file — no server or Docker required.

---

## 📁 Directory Structure

```
03_persistent_agent/
├── agent.py      # LlmAgent definition (profile_planner)
├── db_setup.py   # SQLite schema setup (auto-run on startup)
├── mian.py       # Entry point — runs 3 test cases
├── sessions.db   # Auto-created SQLite database file
└── README.md     # This file
```

---

## 🚀 Setup & Run

### 1. Prerequisites
- Python 3.8+
- Dependencies installed (`pip install -r requirements.txt` from project root)
- `.env` file in the project root with your API key:

```dotenv
GOOGLE_API_KEY=your_google_api_key_here
```

### 2. Run

```bash
python 03_persistent_agent/mian.py
```

That's it. **No Docker, no database server, no manual setup.**
`sessions.db` is created automatically on first run.

---

## 🧠 How It Works

### Architecture

```
mian.py
  │
  ├── ensure_tables()       # Creates sessions.db with v1 schema on first run
  │     └── db_setup.py
  │
  ├── DatabaseSessionService(db_url="sqlite+aiosqlite:///sessions.db")
  │
  └── Runner
        └── LlmAgent (profile_planner)
              └── gemini-2.5-flash + google_search tool
```

### Why SQLite?
SQLite is a zero-configuration, file-based database — perfect for local development and demos.
Sessions persist across runs without any server infrastructure.

---

## 🗃️ Database Schema (ADK v1)

All tables are created automatically by `db_setup.py` on first run.

```
sessions.db
├── adk_internal_metadata   ← schema version marker (schema_version=1)
├── sessions                ← one row per session
├── events                  ← one row per event, event_data as JSON blob
├── app_states              ← per-app state storage
└── user_states             ← per-user state storage
```

> **Key:** The `adk_internal_metadata` table with `schema_version=1` tells ADK
> to use v1 JSON serialization. Without it, ADK misdetects the schema as
> legacy v0 (Pickle) and fails.

---

## 🧪 Test Cases in `mian.py`

### Test 1 — New Session
Creates a fresh session and sends the first message.
Agent learns: destination = Tokyo, loves ramen, vegetarian.

### Test 2 — Resume Session (Persistent Memory)
Re-fetches the **same session** from `sessions.db`.
Agent remembers preferences from Test 1 — proves SQLite persistence.

### Test 3 — Cross-Session Context Injection
Reads all events from the old session, extracts conversation text,
and injects it as context into a **brand new session**.
Demonstrates carrying user preferences across completely separate trips.

---

## 🔄 SQLite vs MySQL — Key Difference

| | SQLite (`03`) | MySQL (`04`) |
|---|---|---|
| **Setup** | None — just a file | Docker container required |
| **`db_url`** | `sqlite+aiosqlite:///sessions.db` | `mysql+aiomysql://root:root123@127.0.0.1:3306/adk_sessions` |
| **Schema reset** | Delete `sessions.db` file | `DROP TABLE` via aiomysql |
| **Best for** | Local dev & demos | Production & shared environments |
| **`DatabaseSessionService`** | ✅ Same ADK API | ✅ Same ADK API |

**The only real difference between `03` and `04` is the `db_url`.**
ADK's `DatabaseSessionService` abstracts everything else identically.

---

## 🐛 Troubleshooting

### `ModuleNotFoundError: No module named 'aiosqlite'`
```bash
pip install aiosqlite
```

### `GOOGLE_API_KEY not found`
Create `.env` in the project root:
```dotenv
GOOGLE_API_KEY=your_actual_key_here
```

### Agent gives wrong/stale responses
Delete `sessions.db` to start fresh:
```bash
del 03_persistent_agent\sessions.db   # Windows
rm 03_persistent_agent/sessions.db    # Mac/Linux
```
Then re-run — `db_setup.py` recreates it automatically.

### Schema warnings or errors
`db_setup.py` auto-detects and fixes outdated schemas by deleting and
recreating `sessions.db`. Just re-run `mian.py`.

---

## 📚 Key Dependencies

| Package | Purpose |
|---------|---------|
| `google-adk` | Agent Development Kit — agents, sessions, runners |
| `google-genai` | Gemini model access |
| `sqlalchemy[asyncio]` | Async ORM used by `DatabaseSessionService` |
| `aiosqlite` | Async SQLite driver for SQLAlchemy |
| `python-dotenv` | Load `.env` variables |

