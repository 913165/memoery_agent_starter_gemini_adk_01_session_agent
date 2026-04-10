"""
Creates the ADK v1 schema tables in the MySQL Docker container.
Make sure your MySQL Docker container is already running:

  docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 -e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0

Then run:  python docker_setup.py
"""
import asyncio
import sys
import aiomysql

HOST     = "127.0.0.1"
PORT     = 3306
USER     = "root"
PASSWORD = "root123"
DATABASE = "adk_sessions"

# ADK v1 schema — sourced directly from google.adk.sessions.schemas.v1
# Key insight: events uses a single event_data LONGTEXT column (JSON blob),
# NOT individual columns like actions/content/etc.
# adk_internal_metadata with schema_version='1' tells ADK to use v1 schema.

TABLES = [
    ("adk_internal_metadata", """
        CREATE TABLE IF NOT EXISTS adk_internal_metadata (
            `key`   VARCHAR(128) NOT NULL,
            value   VARCHAR(256) NOT NULL,
            PRIMARY KEY (`key`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
    ("sessions", """
        CREATE TABLE IF NOT EXISTS sessions (
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
        CREATE TABLE IF NOT EXISTS events (
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
        CREATE TABLE IF NOT EXISTS app_states (
            app_name    VARCHAR(128) NOT NULL,
            state       LONGTEXT,
            update_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                              ON UPDATE CURRENT_TIMESTAMP(6),
            PRIMARY KEY (app_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
    ("user_states", """
        CREATE TABLE IF NOT EXISTS user_states (
            app_name    VARCHAR(128) NOT NULL,
            user_id     VARCHAR(128) NOT NULL,
            state       LONGTEXT,
            update_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                              ON UPDATE CURRENT_TIMESTAMP(6),
            PRIMARY KEY (app_name, user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
]


async def wait_for_mysql(retries=30, delay=2):
    sys.stdout.write(f"Waiting for MySQL on {HOST}:{PORT} ")
    sys.stdout.flush()
    for i in range(retries):
        try:
            conn = await aiomysql.connect(
                host=HOST, port=PORT, user=USER,
                password=PASSWORD, db=DATABASE, charset="utf8mb4",
                connect_timeout=3
            )
            conn.close()
            sys.stdout.write(f" ready after ~{(i + 1) * delay}s\n")
            sys.stdout.flush()
            return True
        except Exception:
            sys.stdout.write(".")
            sys.stdout.flush()
            await asyncio.sleep(delay)
    sys.stdout.write("\n")
    return False


async def setup_tables():
    print(f"\n{'=' * 55}")
    print(" ADK MySQL v1 Schema Setup")
    print(f"{'=' * 55}")
    print(f"  Host    : {HOST}:{PORT}")
    print(f"  Database: {DATABASE}")
    print(f"  User    : {USER}\n")

    ready = await wait_for_mysql()
    if not ready:
        print("\nERROR: Could not connect to MySQL. Is Docker container running?")
        print("  Run: docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 "
              "-e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0")
        sys.exit(1)

    conn = await aiomysql.connect(
        host=HOST, port=PORT, user=USER,
        password=PASSWORD, db=DATABASE, charset="utf8mb4"
    )
    async with conn.cursor() as cur:
        print("Dropping old tables...")
        await cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for name, _ in reversed(TABLES):
            await cur.execute(f"DROP TABLE IF EXISTS {name}")
            print(f"  Dropped: {name}")
        await cur.execute("SET FOREIGN_KEY_CHECKS=1")
        await conn.commit()

        print("\nCreating v1 schema tables...")
        for name, ddl in TABLES:
            await cur.execute(ddl)
            print(f"  Created: {name}")

        await cur.execute(
            "INSERT INTO adk_internal_metadata (`key`, value) VALUES ('schema_version', '1')"
        )
        await conn.commit()

        await cur.execute("SHOW TABLES")
        tables = [r[0] for r in await cur.fetchall()]
        print(f"\n  Tables in '{DATABASE}': {tables}")

        await cur.execute("SELECT `key`, value FROM adk_internal_metadata")
        print(f"  Metadata: {dict(await cur.fetchall())}")

    conn.close()
    print(f"\n✅ Done! Run: python main.py")


if __name__ == "__main__":
    asyncio.run(setup_tables())
