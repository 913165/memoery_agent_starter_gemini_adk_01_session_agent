"""
ADK v1 SQLite schema setup.
Ensures all tables exist with the correct v1 schema before ADK connects.

Why this is needed:
  - If tables don't exist, ADK auto-creates them with the legacy v0 Pickle schema.
  - ADK detects schema version via 'adk_internal_metadata' table.
  - v1 stores ALL event fields in a single 'event_data' TEXT column.
  - If schema is outdated, the .db file is simply deleted and recreated.
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

