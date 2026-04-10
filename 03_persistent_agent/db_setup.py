"""
ADK v1 SQLite schema setup.

Fresh clone / first run behaviour:
  - sessions.db does not exist → created here with full v1 schema
  - adk_internal_metadata inserted with schema_version='1'
  - ADK reads this marker → uses v1 JSON serialization ✅

Subsequent runs:
  - sessions.db exists + adk_internal_metadata present + event_data column exists
  - ensure_tables() does nothing (no SQL executed, no warnings) ✅

Why this is needed:
  - ADK does NOT auto-create tables.
  - If tables are missing, ADK fails on first session operation.
  - If adk_internal_metadata is missing, ADK inspects the events table and
    misdetects the schema as legacy v0 (Pickle), causing serialization errors.
"""
from pathlib import Path
import aiosqlite

DB_PATH = Path(__file__).parent / "sessions.db"
DB_URL  = f"sqlite+aiosqlite:///{DB_PATH}"

_TABLES = [
    ("adk_internal_metadata", """
        CREATE TABLE adk_internal_metadata (
            key   TEXT NOT NULL PRIMARY KEY,
            value TEXT NOT NULL
        )
    """),
    ("sessions", """
        CREATE TABLE sessions (
            app_name    TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            id          TEXT NOT NULL,
            state       TEXT,
            create_time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            update_time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            PRIMARY KEY (app_name, user_id, id)
        )
    """),
    ("events", """
        CREATE TABLE events (
            app_name      TEXT NOT NULL,
            user_id       TEXT NOT NULL,
            session_id    TEXT NOT NULL,
            id            TEXT NOT NULL,
            invocation_id TEXT NOT NULL DEFAULT '',
            timestamp     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            event_data    TEXT,
            PRIMARY KEY (app_name, user_id, session_id, id),
            FOREIGN KEY (app_name, user_id, session_id)
                REFERENCES sessions (app_name, user_id, id)
                ON DELETE CASCADE
        )
    """),
    ("app_states", """
        CREATE TABLE app_states (
            app_name    TEXT NOT NULL PRIMARY KEY,
            state       TEXT,
            update_time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
        )
    """),
    ("user_states", """
        CREATE TABLE user_states (
            app_name    TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            state       TEXT,
            update_time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            PRIMARY KEY (app_name, user_id)
        )
    """),
]


async def ensure_tables():
    """Creates ADK v1 schema tables. Deletes and recreates .db if schema is outdated."""
    if DB_PATH.exists():
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='adk_internal_metadata'"
            )
            metadata_exists = (await cur.fetchone())[0] > 0

            cur = await db.execute("PRAGMA table_info(events)")
            cols = [row[1] for row in await cur.fetchall()]
            event_data_exists = "event_data" in cols

        if not metadata_exists or not event_data_exists:
            print("⚠️  Schema outdated — deleting and recreating sessions.db...")
            DB_PATH.unlink()

    if not DB_PATH.exists():
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            for _, ddl in _TABLES:
                await db.execute(ddl)
            await db.execute(
                "INSERT INTO adk_internal_metadata (key, value) VALUES ('schema_version', '1')"
            )
            await db.commit()

    print("✅ SQLite tables ready (ADK v1 schema).")
    print(f"   DB file: {DB_PATH}")

