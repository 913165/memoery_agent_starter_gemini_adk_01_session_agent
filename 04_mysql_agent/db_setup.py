"""
ADK v1 MySQL schema setup.
Ensures all tables exist with the correct v1 schema before ADK connects.

Why this is needed:
  - If tables don't exist, ADK auto-creates them with the legacy v0 Pickle schema.
  - v0 schema causes: OperationalError: Cannot create a JSON value from a string
    with CHARACTER SET 'binary'.
  - ADK detects schema version via 'adk_internal_metadata' table.
  - v1 stores ALL event fields in a single 'event_data' LONGTEXT column.
"""
import os
import aiomysql

_TABLES = [
    ("adk_internal_metadata", """
        CREATE TABLE adk_internal_metadata (
            `key`   VARCHAR(128) NOT NULL,
            value   VARCHAR(256) NOT NULL,
            PRIMARY KEY (`key`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
    ("sessions", """
        CREATE TABLE sessions (
            id          VARCHAR(128) NOT NULL,
            app_name    VARCHAR(128) NOT NULL,
            user_id     VARCHAR(128) NOT NULL,
            state       LONGTEXT,
            create_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            update_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                              ON UPDATE CURRENT_TIMESTAMP(6),
            PRIMARY KEY (app_name, user_id, id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
    ("events", """
        CREATE TABLE events (
            id            VARCHAR(128) NOT NULL,
            app_name      VARCHAR(128) NOT NULL,
            user_id       VARCHAR(128) NOT NULL,
            session_id    VARCHAR(128) NOT NULL,
            invocation_id VARCHAR(256) NOT NULL DEFAULT '',
            timestamp     DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            event_data    LONGTEXT,
            PRIMARY KEY (app_name, user_id, session_id, id),
            CONSTRAINT fk_events_session
                FOREIGN KEY (app_name, user_id, session_id)
                REFERENCES sessions (app_name, user_id, id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
    ("app_states", """
        CREATE TABLE app_states (
            app_name    VARCHAR(128) NOT NULL,
            state       LONGTEXT,
            update_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                              ON UPDATE CURRENT_TIMESTAMP(6),
            PRIMARY KEY (app_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
    ("user_states", """
        CREATE TABLE user_states (
            app_name    VARCHAR(128) NOT NULL,
            user_id     VARCHAR(128) NOT NULL,
            state       LONGTEXT,
            update_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                              ON UPDATE CURRENT_TIMESTAMP(6),
            PRIMARY KEY (app_name, user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
]


def build_mysql_url() -> str:
    user     = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    host     = os.getenv("MYSQL_HOST", "127.0.0.1")
    port     = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DATABASE", "adk_sessions")
    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"


async def ensure_tables():
    """Creates ADK v1 schema tables. Drops and recreates if schema is outdated."""
    host     = os.getenv("MYSQL_HOST", "127.0.0.1")
    port     = int(os.getenv("MYSQL_PORT", "3306"))
    user     = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "adk_sessions")

    conn = await aiomysql.connect(
        host=host, port=port, user=user,
        password=password, db=database, charset="utf8mb4"
    )
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='adk_internal_metadata'", (database,)
        )
        metadata_exists = (await cur.fetchone())[0] > 0

        await cur.execute(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='events' AND COLUMN_NAME='event_data'", (database,)
        )
        event_data_exists = (await cur.fetchone())[0] > 0

        if not metadata_exists or not event_data_exists:
            print("⚠️  Schema outdated — dropping and recreating all tables...")
            await cur.execute("SET FOREIGN_KEY_CHECKS=0")
            for name, _ in reversed(_TABLES):
                await cur.execute(f"DROP TABLE IF EXISTS {name}")
            await cur.execute("SET FOREIGN_KEY_CHECKS=1")
            await conn.commit()

            # Create tables fresh — only runs when tables were just dropped
            for _, ddl in _TABLES:
                await cur.execute(ddl)
            await cur.execute(
                "INSERT INTO adk_internal_metadata (`key`, value) VALUES ('schema_version', '1')"
            )
            await conn.commit()

    conn.close()
    print("✅ MySQL tables ready (ADK v1 schema).")

