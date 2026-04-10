"""
Creates the ADK v1 schema tables in the MySQL Docker container.
Make sure your MySQL Docker container is already running:

  docker run --name adk-mysql \
    -e MYSQL_ROOT_PASSWORD=root123 \
    -e MYSQL_DATABASE=adk_sessions \
    -p 3306:3306 \
    -d mysql:8.0

Then run:  python docker_setup.py
"""
import asyncio
import sys
import time
import aiomysql

HOST = "127.0.0.1"
PORT = 3306
USER = "root"
PASSWORD = "root123"
DATABASE = "adk_sessions"

CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id            VARCHAR(191)  NOT NULL,
    app_name      VARCHAR(191)  NOT NULL,
    user_id       VARCHAR(191)  NOT NULL,
    state         JSON,
    create_time   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    update_time   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                         ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (app_name, user_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id                          VARCHAR(191)  NOT NULL,
    app_name                    VARCHAR(191)  NOT NULL,
    user_id                     VARCHAR(191)  NOT NULL,
    session_id                  VARCHAR(191)  NOT NULL,
    invocation_id               VARCHAR(191)  NOT NULL DEFAULT '',
    author                      VARCHAR(255),
    actions                     JSON,
    long_running_tool_ids_json  JSON,
    branch                      VARCHAR(255),
    timestamp                   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    content                     JSON,
    grounding_metadata          JSON,
    custom_metadata             JSON,
    usage_metadata              JSON,
    citation_metadata           JSON,
    partial                     TINYINT(1),
    turn_complete               TINYINT(1),
    error_code                  VARCHAR(255),
    error_message               TEXT,
    interrupted                 TINYINT(1),
    input_transcription         JSON,
    output_transcription        JSON,
    PRIMARY KEY (app_name, user_id, session_id, id),
    CONSTRAINT fk_events_session
        FOREIGN KEY (app_name, user_id, session_id)
        REFERENCES sessions (app_name, user_id, id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


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
            sys.stdout.write(f" ready after ~{(i+1)*delay}s\n")
            sys.stdout.flush()
            return True
        except Exception:
            sys.stdout.write(".")
            sys.stdout.flush()
            await asyncio.sleep(delay)
    sys.stdout.write("\n")
    return False


async def setup_tables():
    print(f"\n{'='*55}")
    print(" ADK MySQL v1 Schema Setup")
    print(f"{'='*55}")
    print(f"  Host    : {HOST}:{PORT}")
    print(f"  Database: {DATABASE}")
    print(f"  User    : {USER}")
    print()

    ready = await wait_for_mysql()
    if not ready:
        print("\nERROR: Could not connect to MySQL. Is Docker container running?")
        print("  Run: docker run --name adk-mysql -e MYSQL_ROOT_PASSWORD=root123 -e MYSQL_DATABASE=adk_sessions -p 3306:3306 -d mysql:8.0")
        sys.exit(1)

    conn = await aiomysql.connect(
        host=HOST, port=PORT, user=USER,
        password=PASSWORD, db=DATABASE, charset="utf8mb4"
    )
    async with conn.cursor() as cur:
        # Drop old tables (in case of old v0 schema)
        print("Dropping old tables (if any)...")
        await cur.execute("SET FOREIGN_KEY_CHECKS=0")
        await cur.execute("DROP TABLE IF EXISTS events")
        await cur.execute("DROP TABLE IF EXISTS sessions")
        await cur.execute("SET FOREIGN_KEY_CHECKS=1")
        await conn.commit()
        print("  Dropped: events, sessions")

        # Create fresh v1 tables
        print("Creating v1 schema tables...")
        await cur.execute(CREATE_SESSIONS)
        print("  Created: sessions")
        await cur.execute(CREATE_EVENTS)
        print("  Created: events")
        await conn.commit()

        # Verify
        await cur.execute("SHOW TABLES")
        tables = [r[0] for r in await cur.fetchall()]
        print(f"\n  Tables in '{DATABASE}': {tables}")

        await cur.execute("DESCRIBE events")
        cols = [r[0] for r in await cur.fetchall()]
        print(f"  events columns ({len(cols)}): {cols}")

    conn.close()
    print(f"\n✅ Done! MySQL is ready for ADK v1 schema.")
    print(f"   Now run: python main.py")


if __name__ == "__main__":
    asyncio.run(setup_tables())
