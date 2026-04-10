# 04 — MySQL Persistent Agent 🗄️

A conversational **Adaptive Trip Planner** agent backed by **MySQL** for fully persistent memory.
Sessions survive process restarts, container restarts, and can be shared across multiple runs.

---

## 📁 Directory Structure

```
04_mysql_agent/
├── agent.py      # LlmAgent definition (mysql_trip_planner)
├── db_setup.py   # MySQL schema setup (auto-run on startup)
├── main.py       # Entry point — runs 3 test cases
└── README.md     # This file
```

---

## 🖥️ Fresh Clone — What Happens on a New Machine

```bash
git clone <repo>
cd memory_agent_starter_googleai
pip install -r requirements.txt
# add GOOGLE_API_KEY + MySQL credentials to .env
docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 -e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0
# wait ~20 seconds for MySQL to initialise
python 04_mysql_agent/main.py
```

That's all. Here's what happens internally on first run:

```
main.py starts
  │
  ├── ensure_tables()
  │     ├── MySQL DB is empty (no tables)
  │     ├── Creates all 5 tables with v1 schema
  │     └── Inserts adk_internal_metadata: schema_version = '1'
  │
  ├── DatabaseSessionService connects to MySQL
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

## 🐳 Docker — Start MySQL

> **This is the only infrastructure you need before running the agent.**

### Start a fresh MySQL 8.0 container

```bash
docker run --name adk-mysql \
  -e MYSQL_ROOT_PASSWORD=root123 \
  -e MYSQL_DATABASE=adk_sessions \
  -p 3306:3306 \
  -d mysql:8.0
```

**On Windows (single line):**
```cmd
docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 -e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0
```

| Flag | Value | Description |
|------|-------|-------------|
| `--name` | `adk-mysql` | Container name |
| `MYSQL_ROOT_PASSWORD` | `root123` | Root password (matches `.env`) |
| `MYSQL_DATABASE` | `adk_sessions` | Auto-created database |
| `-p 3306:3306` | host:container | Exposes MySQL on localhost |
| `-d` | — | Run in background (detached) |
| `mysql:8.0` | — | MySQL 8.0 image |

---

## ⚙️ Useful Docker Commands

```bash
# Check container is running
docker ps

# View MySQL startup logs (wait for "ready for connections")
docker logs -f adk-mysql

# Stop the container
docker stop adk-mysql

# Start it again (data is preserved)
docker start adk-mysql

# Stop and remove (DELETES ALL DATA)
docker stop adk-mysql && docker rm adk-mysql

# Open a MySQL shell inside the container
docker exec -it adk-mysql mysql -u root -proot123 adk_sessions

# Inspect saved sessions and events
SHOW TABLES;
SELECT id, app_name, user_id FROM sessions;
SELECT id, session_id, timestamp FROM events ORDER BY timestamp DESC LIMIT 10;
```

---

## 🔧 Environment Variables

The `.env` file lives in the **project root**:

```dotenv
GOOGLE_API_KEY=your_google_api_key_here

MYSQL_USER=root
MYSQL_PASSWORD=root123
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=adk_sessions
```

---

## 🚀 Setup & Run

```bash
# 1. Start MySQL
docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 -e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0

# 2. Wait ~20 seconds for MySQL to initialise, then run the agent
python 04_mysql_agent/main.py
```

> **No manual table creation needed.**
> `db_setup.py` runs automatically on startup — creates tables on first run,
> detects and fixes outdated schemas, does nothing when everything is already correct.

---

## 🧠 How It Works

### Architecture

```
main.py
  │
  ├── ensure_tables()       # Creates/validates MySQL schema on startup
  │     └── db_setup.py
  │
  ├── DatabaseSessionService(db_url="mysql+aiomysql://root:root123@127.0.0.1:3306/adk_sessions")
  │
  └── Runner
        └── LlmAgent (mysql_trip_planner)
              └── gemini-2.5-flash + google_search tool
```

### SQLite vs MySQL — Key Difference

| | SQLite (`03`) | MySQL (`04`) |
|---|---|---|
| **Setup** | None — just a file | Docker container required |
| **`db_url`** | `sqlite+aiosqlite:///sessions.db` | `mysql+aiomysql://root:root123@127.0.0.1:3306/adk_sessions` |
| **Schema reset** | Delete `sessions.db` file | `DROP TABLE` via aiomysql |
| **Best for** | Local dev & demos | Production & shared environments |
| **`DatabaseSessionService`** | ✅ Same ADK API | ✅ Same ADK API |

**The only real difference between `03` and `04` is the `db_url`.**

---

## 🗃️ Database Schema (ADK v1)

All tables are created automatically by `db_setup.py` on first run.

```
adk_sessions database
├── adk_internal_metadata   ← schema version marker (schema_version=1)
├── sessions                ← one row per session
├── events                  ← one row per event, event_data as JSON blob
├── app_states              ← per-app state storage
└── user_states             ← per-user state storage
```

> **Key:** The `adk_internal_metadata` table with `schema_version=1` tells ADK
> to use v1 JSON serialization. Without it, ADK misdetects the schema as
> legacy v0 (Pickle) and fails with a binary charset error.

---

## 🧪 Test Cases in `main.py`

### Test 1 — New Session
Creates a fresh session and sends the first message.
Agent learns: destination = Kyoto, loves temples, vegetarian.

### Test 2 — Resume Session (Persistent Memory)
Re-fetches the **same session** from MySQL (simulating a restart).
Agent remembers preferences from Test 1 — proves MySQL persistence.

### Test 3 — Cross-Session Context Injection
Reads all events from the old session, extracts conversation text,
and injects it as context into a **brand new session** for a different city.
Demonstrates carrying user preferences across completely separate trips.

---

## 🐛 Troubleshooting

### `Can't connect to MySQL server on '127.0.0.1'`
MySQL container is not running.
```bash
docker start adk-mysql
# or start a fresh one:
docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 -e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0
```

### `GOOGLE_API_KEY not found`
Create `.env` in the project root:
```dotenv
GOOGLE_API_KEY=your_actual_key_here
```

### Schema errors or warnings
`db_setup.py` auto-detects and fixes outdated schemas on every startup.
If problems persist, wipe and restart the container:
```bash
docker stop adk-mysql && docker rm adk-mysql
docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 -e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0
```

---

## 📚 Key Dependencies

| Package | Purpose |
|---------|---------|
| `google-adk` | Agent Development Kit — agents, sessions, runners |
| `google-genai` | Gemini model access |
| `sqlalchemy[asyncio]` | Async ORM used by `DatabaseSessionService` |
| `aiomysql` | Async MySQL driver for SQLAlchemy |
| `python-dotenv` | Load `.env` variables |

