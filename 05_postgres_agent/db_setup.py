"""
ADK v1 PostgreSQL schema setup.

Fresh clone / first run behaviour:
  - PostgreSQL DB is empty (no tables) → all 5 tables created here with v1 schema
  - adk_internal_metadata inserted with schema_version='1'
  - ADK reads this marker → uses v1 JSON serialization ✅

Subsequent runs:
  - adk_internal_metadata present + event_data column exists
  - ensure_tables() does nothing (no SQL executed, no warnings) ✅

Why this is needed:
  - ADK does NOT auto-create tables.
  - If tables are missing, ADK fails on first session operation.
  - If adk_internal_metadata is missing, ADK inspects the events table and
    misdetects the schema as legacy v0 (Pickle), causing serialization errors.

PostgreSQL differences from MySQL:
  - Driver      : asyncpg  (not aiomysql)
  - JSON columns: JSONB    (native binary JSON, faster queries)
  - No ENGINE / CHARSET clauses
  - Timestamps  : TIMESTAMPTZ (timezone-aware)
  - Auto-update : trigger required (no ON UPDATE clause like MySQL)
  - No backtick quoting — use double quotes for reserved words
"""
import os
import asyncpg

_TABLES = [
    ("adk_internal_metadata", """
        CREATE TABLE adk_internal_metadata (
            key   VARCHAR(128) NOT NULL,
            value VARCHAR(256) NOT NULL,
            PRIMARY KEY (key)
        )
    """),
    ("sessions", """
        CREATE TABLE sessions (
            id          VARCHAR(128)  NOT NULL,
            app_name    VARCHAR(128)  NOT NULL,
            user_id     VARCHAR(128)  NOT NULL,
            state       JSONB,
            create_time TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            update_time TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            PRIMARY KEY (app_name, user_id, id)
        )
    """),
    ("events", """
        CREATE TABLE events (
            id            VARCHAR(128) NOT NULL,
            app_name      VARCHAR(128) NOT NULL,
            user_id       VARCHAR(128) NOT NULL,
            session_id    VARCHAR(128) NOT NULL,
            invocation_id VARCHAR(256) NOT NULL DEFAULT '',
            timestamp     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            event_data    JSONB,
            PRIMARY KEY (app_name, user_id, session_id, id),
            CONSTRAINT fk_events_session
                FOREIGN KEY (app_name, user_id, session_id)
                REFERENCES sessions (app_name, user_id, id)
                ON DELETE CASCADE
        )
    """),
    ("app_states", """
        CREATE TABLE app_states (
            app_name    VARCHAR(128) NOT NULL,
            state       JSONB,
            update_time TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            PRIMARY KEY (app_name)
        )
    """),
    ("user_states", """
        CREATE TABLE user_states (
            app_name    VARCHAR(128) NOT NULL,
            user_id     VARCHAR(128) NOT NULL,
            state       JSONB,
            update_time TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            PRIMARY KEY (app_name, user_id)
        )
    """),
]



def build_postgres_url() -> str:
    user     = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host     = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port     = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "adk_sessions")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


async def ensure_tables():
    """Creates ADK v1 schema tables. Drops and recreates if schema is outdated."""
    user     = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host     = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port     = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DB", "adk_sessions")

    conn = await asyncpg.connect(
        host=host, port=port, user=user,
        password=password, database=database
    )

    # Check adk_internal_metadata exists
    metadata_exists = await conn.fetchval(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='adk_internal_metadata'"
    ) > 0

    # Check event_data column exists in events table
    event_data_exists = await conn.fetchval(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='events' AND column_name='event_data'"
    ) > 0

    # Check if the old update_timestamp trigger exists — must remove it as it
    # interferes with ADK's optimistic concurrency check (update_time marker)
    trigger_exists = await conn.fetchval(
        "SELECT COUNT(*) FROM information_schema.triggers "
        "WHERE trigger_name='trg_sessions_update'"
    ) > 0

    if not metadata_exists or not event_data_exists or trigger_exists:
        print("⚠️  Schema outdated — dropping and recreating all tables...")
        await conn.execute("DROP TABLE IF EXISTS events CASCADE")
        await conn.execute("DROP TABLE IF EXISTS sessions CASCADE")
        await conn.execute("DROP TABLE IF EXISTS app_states CASCADE")
        await conn.execute("DROP TABLE IF EXISTS user_states CASCADE")
        await conn.execute("DROP TABLE IF EXISTS adk_internal_metadata CASCADE")
        await conn.execute("DROP FUNCTION IF EXISTS update_timestamp() CASCADE")

        # Create tables fresh — only runs when tables were just dropped
        for _, ddl in _TABLES:
            await conn.execute(ddl)
        await conn.execute(
            "INSERT INTO adk_internal_metadata (key, value) VALUES ('schema_version', '1')"
        )

    await conn.close()
    print("✅ PostgreSQL tables ready (ADK v1 schema).")

