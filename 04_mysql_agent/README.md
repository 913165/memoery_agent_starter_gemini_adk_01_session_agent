# 04 — MySQL Persistent Agent 🗄️

A conversational **Adaptive Trip Planner** agent backed by **MySQL** for fully persistent memory.
Sessions survive process restarts, container restarts, and can be shared across multiple runs.

---

## 📁 Directory Structure

```
04_mysql_agent/
├── agent.py           # LlmAgent definition (mysql_trip_planner)
├── main.py            # Entry point — runs 3 test cases
├── setup_mysql.sql    # Manual SQL script (alternative to auto-setup)
├── docker_setup.py    # Utility: drops & recreates tables with v1 schema
├── reset_db.py        # Utility: drops tables only (clean slate)
└── README.md          # This file
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

# From inside the MySQL shell — inspect tables
SHOW TABLES;
SELECT id, app_name, user_id FROM sessions;
SELECT id, session_id, author, timestamp FROM events ORDER BY timestamp DESC LIMIT 10;
```

---

## 🔧 Environment Variables

The `.env` file lives in the **project root** (`memory_agent_starter_googleai/.env`):

```dotenv
GOOGLE_API_KEY=your_google_api_key_here

# MySQL connection — must match the Docker run command above
MYSQL_USER=root
MYSQL_PASSWORD=root123
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=adk_sessions
```

---

## 🚀 Running the Agent

```bash
# From the project root
python 04_mysql_agent/main.py

# Or from inside the 04_mysql_agent directory
python main.py
```

> **No manual table creation needed.**
> `main.py` calls `ensure_tables()` on every startup which automatically
> creates the tables if they don't exist, or recreates them if a legacy
> v0 (Pickle/binary) schema is detected.

---

## 🧠 How It Works

### Architecture

```
main.py
  │
  ├── ensure_tables()          # Creates/validates MySQL schema on startup
  │
  ├── DatabaseSessionService   # ADK session backend (MySQL via SQLAlchemy + aiomysql)
  │     └── db_url: mysql+aiomysql://root:root123@127.0.0.1:3306/adk_sessions
  │
  └── Runner
        └── LlmAgent (mysql_trip_planner)
              └── gemini-2.5-flash + google_search tool
```

### Why MySQL instead of InMemory?

| Feature | InMemorySessionService | DatabaseSessionService (MySQL) |
|---------|----------------------|-------------------------------|
| Survives restart | ❌ | ✅ |
| Shared across processes | ❌ | ✅ |
| Production ready | ❌ | ✅ |
| Cross-session context | ❌ | ✅ |
| Setup required | None | Docker + DB |

---

## 🗃️ Database Schema (ADK v1)

> Tables are created automatically by `main.py`. Shown here for reference.

### `sessions` table
```sql
CREATE TABLE sessions (
    id          VARCHAR(191) NOT NULL,
    app_name    VARCHAR(191) NOT NULL,
    user_id     VARCHAR(191) NOT NULL,
    state       JSON,
    create_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    update_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                      ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (app_name, user_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### `events` table
```sql
CREATE TABLE events (
    id                         VARCHAR(191) NOT NULL,
    app_name                   VARCHAR(191) NOT NULL,
    user_id                    VARCHAR(191) NOT NULL,
    session_id                 VARCHAR(191) NOT NULL,
    invocation_id              VARCHAR(191) NOT NULL DEFAULT '',
    author                     VARCHAR(255),
    actions                    JSON,                  -- ⚠️ Must be JSON not BLOB
    long_running_tool_ids_json JSON,
    branch                     VARCHAR(255),
    timestamp                  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    content                    JSON,
    grounding_metadata         JSON,
    custom_metadata            JSON,
    usage_metadata             JSON,
    citation_metadata          JSON,
    partial                    TINYINT(1),
    turn_complete              TINYINT(1),
    error_code                 VARCHAR(255),
    error_message              TEXT,
    interrupted                TINYINT(1),
    input_transcription        JSON,
    output_transcription       JSON,
    PRIMARY KEY (app_name, user_id, session_id, id),
    CONSTRAINT fk_events_session
        FOREIGN KEY (app_name, user_id, session_id)
        REFERENCES sessions (app_name, user_id, id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

> **Why `VARCHAR(191)` instead of `VARCHAR(255)` on key columns?**
> MySQL limits composite primary keys to **3072 bytes**.
> With `utf8mb4` (4 bytes/char): `4 cols × 191 × 4 = 3056 bytes` — just under the limit.
> Using `VARCHAR(255)` would give `4 × 255 × 4 = 4080 bytes` → error 1071.

---

## 🧪 Test Cases in `main.py`

### Test 1 — New Session
Creates a fresh session and sends the first message.
Agent greets and asks for trip details.

### Test 2 — Resume Session (Persistent Memory)
Re-fetches the **same session** from MySQL (simulating a restart).
Agent remembers the previous conversation from the database.

### Test 3 — Cross-Session Context Injection
Reads all events from the old session, extracts conversation text,
and injects it as context into a **brand new session** for a different city.
Demonstrates how to carry user preferences across completely separate trips.

---

## 🔄 Full Demo Flow (Step by Step)

```bash
# Step 1: Start MySQL via Docker
docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 -e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0

# Step 2: Wait ~20 seconds for MySQL to initialise, then verify it's ready
docker logs adk-mysql | findstr "ready for connections"

# Step 3: Run the agent (tables are auto-created on first run)
python 04_mysql_agent/main.py

# Step 4: Run again — agent resumes from MySQL memory
python 04_mysql_agent/main.py

# Step 5 (optional): Inspect what was saved
docker exec -it adk-mysql mysql -u root -proot123 adk_sessions -e "SELECT id, user_id, app_name FROM sessions;"
docker exec -it adk-mysql mysql -u root -proot123 adk_sessions -e "SELECT id, author, timestamp FROM events ORDER BY timestamp DESC LIMIT 5;"
```

---

## 🛠️ Utility Scripts

### `docker_setup.py` — Reset & recreate tables
Drops existing tables and recreates them with the correct v1 JSON schema.
Use this if you get schema errors or want a completely fresh database.

```bash
python 04_mysql_agent/docker_setup.py
```

### `setup_mysql.sql` — Manual SQL setup
If you prefer to run SQL directly in MySQL Workbench, DBeaver, or phpMyAdmin:

```bash
# From command line (if mysql client is in PATH)
mysql -u root -proot123 < 04_mysql_agent/setup_mysql.sql

# Or via Docker exec
docker exec -i adk-mysql mysql -u root -proot123 < 04_mysql_agent/setup_mysql.sql
```

---

## 🐛 Troubleshooting

### `Can't connect to MySQL server on '127.0.0.1'`
MySQL container is not running.
```bash
docker start adk-mysql
# or start a fresh one:
docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 -e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0
```

### `Cannot create a JSON value from a string with CHARACTER SET 'binary'`
Old v0 (Pickle) schema tables exist. `main.py` detects and fixes this automatically on next run.
Or force a reset manually:
```bash
python 04_mysql_agent/docker_setup.py
```

### `Specified key was too long; max key length is 3072 bytes`
You are running an old version of `setup_mysql.sql` that uses `VARCHAR(255)` on key columns.
Use the latest `setup_mysql.sql` which uses `VARCHAR(191)`.

### `RuntimeError: Event loop is closed`
Harmless warning on Python 3.12+ with `aiomysql`. Already suppressed in `main.py` via engine dispose.

### `Unknown column 'events.long_running_tool_ids_json'`
Tables were created by an older ADK version with fewer columns.
Drop and recreate:
```bash
python 04_mysql_agent/docker_setup.py
```

---

## 📚 Key Dependencies

| Package | Purpose |
|---------|---------|
| `google-adk` | Agent Development Kit — agents, sessions, runners |
| `google-genai` | Gemini model access |
| `sqlalchemy[asyncio]` | Async ORM used by `DatabaseSessionService` |
| `aiomysql` | Async MySQL driver for SQLAlchemy |
| `PyMySQL` | Sync MySQL driver (used internally) |
| `python-dotenv` | Load `.env` variables |

Install all:
```bash
pip install -r requirements.txt
```

