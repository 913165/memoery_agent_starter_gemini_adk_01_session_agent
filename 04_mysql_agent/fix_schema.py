"""
One-shot fix: drops all ADK tables and recreates them with the correct v1 schema,
including adk_internal_metadata which ADK uses to detect v1 vs v0.
Results written to fix_schema_result.txt next to this script.
"""
import asyncio
import os
import sys

RESULT_FILE = os.path.join(os.path.dirname(__file__), "fix_schema_result.txt")

HOST     = "127.0.0.1"
PORT     = 3306
USER     = "root"
PASSWORD = "root123"
DATABASE = "adk_sessions"

SQL = [
    ("FOREIGN_KEY_CHECKS off", "SET FOREIGN_KEY_CHECKS=0"),
    ("drop events",            "DROP TABLE IF EXISTS events"),
    ("drop sessions",          "DROP TABLE IF EXISTS sessions"),
    ("drop metadata",          "DROP TABLE IF EXISTS adk_internal_metadata"),
    ("FOREIGN_KEY_CHECKS on",  "SET FOREIGN_KEY_CHECKS=1"),
    ("create metadata", """
        CREATE TABLE adk_internal_metadata (
            `key`  VARCHAR(128) NOT NULL,
            value  VARCHAR(256) NOT NULL,
            PRIMARY KEY (`key`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
    ("insert schema_version=1",
        "INSERT INTO adk_internal_metadata (`key`, value) VALUES ('schema_version', '1')"),
    ("create sessions", """
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
    ("create events", """
        CREATE TABLE events (
            id                         VARCHAR(128) NOT NULL,
            app_name                   VARCHAR(128) NOT NULL,
            user_id                    VARCHAR(128) NOT NULL,
            session_id                 VARCHAR(128) NOT NULL,
            invocation_id              VARCHAR(128) NOT NULL DEFAULT '',
            author                     VARCHAR(256),
            actions                    LONGTEXT,
            long_running_tool_ids_json LONGTEXT,
            branch                     VARCHAR(256),
            timestamp                  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            content                    LONGTEXT,
            grounding_metadata         LONGTEXT,
            custom_metadata            LONGTEXT,
            usage_metadata             LONGTEXT,
            citation_metadata          LONGTEXT,
            partial                    TINYINT(1),
            turn_complete              TINYINT(1),
            error_code                 VARCHAR(256),
            error_message              LONGTEXT,
            interrupted                TINYINT(1),
            input_transcription        LONGTEXT,
            output_transcription       LONGTEXT,
            PRIMARY KEY (app_name, user_id, session_id, id),
            CONSTRAINT fk_events_session
                FOREIGN KEY (app_name, user_id, session_id)
                REFERENCES sessions (app_name, user_id, id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """),
]


async def run():
    import aiomysql
    lines = []

    def log(msg):
        lines.append(msg)
        print(msg, flush=True)

    log(f"Connecting to {HOST}:{PORT}/{DATABASE} ...")
    try:
        conn = await aiomysql.connect(
            host=HOST, port=PORT, user=USER,
            password=PASSWORD, db=DATABASE, charset="utf8mb4"
        )
    except Exception as e:
        log(f"FAILED to connect: {e}")
        with open(RESULT_FILE, "w") as f:
            f.write("\n".join(lines))
        return

    log("Connected.")
    async with conn.cursor() as cur:
        for label, stmt in SQL:
            try:
                await cur.execute(stmt)
                log(f"  OK  : {label}")
            except Exception as e:
                log(f"  FAIL: {label} -> {e}")
        await conn.commit()

        # Verify
        await cur.execute("SHOW TABLES")
        tables = [r[0] for r in await cur.fetchall()]
        log(f"\nTables now: {tables}")

        await cur.execute("SELECT `key`, value FROM adk_internal_metadata")
        meta = dict(await cur.fetchall())
        log(f"Metadata  : {meta}")

    conn.close()
    log("\nDONE. Run main.py now.")

    with open(RESULT_FILE, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(run())

