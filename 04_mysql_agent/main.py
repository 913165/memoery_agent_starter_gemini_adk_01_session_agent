import asyncio
import os
import sys

# Add the current directory to sys.path to ensure we can import agent.py
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, Session
from google.genai import types

from agent import root_agent

load_dotenv()


def build_mysql_url() -> str:
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DATABASE", "adk_sessions")
    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"


# ---------------------------------------------------------------------------
# Auto setup: ensures tables exist with the correct ADK v1 JSON schema.
# Safe to call every run — uses CREATE TABLE IF NOT EXISTS.
# Without this, ADK auto-creates tables with the legacy v0 Pickle schema
# which causes: OperationalError: Cannot create a JSON value from a string
# with CHARACTER SET 'binary'
# ---------------------------------------------------------------------------
CREATE_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id            VARCHAR(191) NOT NULL,
    app_name      VARCHAR(191) NOT NULL,
    user_id       VARCHAR(191) NOT NULL,
    state         JSON,
    create_time   DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    update_time   DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (app_name, user_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

CREATE_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id                         VARCHAR(191) NOT NULL,
    app_name                   VARCHAR(191) NOT NULL,
    user_id                    VARCHAR(191) NOT NULL,
    session_id                 VARCHAR(191) NOT NULL,
    invocation_id              VARCHAR(191) NOT NULL DEFAULT '',
    author                     VARCHAR(255),
    actions                    JSON,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


async def ensure_tables():
    """
    Creates the ADK v1 schema tables if they don't exist yet.
    Also validates that the existing 'actions' column is JSON (not BLOB/binary).
    If BLOB is detected (legacy v0), the tables are dropped and recreated.
    """
    import aiomysql

    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "adk_sessions")

    conn = await aiomysql.connect(
        host=host, port=port, user=user,
        password=password, db=database, charset="utf8mb4"
    )
    async with conn.cursor() as cur:
        # Check if events table exists and inspect the 'actions' column type
        await cur.execute(
            "SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='events' AND COLUMN_NAME='actions'",
            (database,)
        )
        row = await cur.fetchone()

        if row and row[0].lower() in ("blob", "longblob", "mediumblob", "tinyblob"):
            # Legacy v0 schema detected — drop and recreate
            print("⚠️  Legacy v0 schema detected (BLOB actions). Recreating tables with v1 JSON schema...")
            await cur.execute("SET FOREIGN_KEY_CHECKS=0")
            await cur.execute("DROP TABLE IF EXISTS events")
            await cur.execute("DROP TABLE IF EXISTS sessions")
            await cur.execute("SET FOREIGN_KEY_CHECKS=1")
            await conn.commit()

        # Create tables (IF NOT EXISTS — safe to run every time)
        await cur.execute(CREATE_SESSIONS_SQL)
        await cur.execute(CREATE_EVENTS_SQL)
        await conn.commit()

    conn.close()
    print("✅ Database tables ready (v1 JSON schema).")


# ---------------------------------------------------------------------------
# Helper: run a single agent query inside a session
# ---------------------------------------------------------------------------
async def run_agent_query(
    agent: Agent,
    query: str,
    session: Session,
    user_id: str,
    session_service: DatabaseSessionService,
    is_router: bool = False,
) -> str:
    """Initializes a Runner and executes one query, returning the final response."""
    print(f"\n🚀 Running query for agent: '{agent.name}' in session: '{session.id}'...")

    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name=agent.name,
    )

    final_response = ""
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(parts=[types.Part(text=query)], role="user"),
        ):
            if event.is_final_response():
                final_response = event.content.parts[0].text
    except Exception as e:
        final_response = f"An error occurred: {e}"

    if not is_router:
        print("\n" + "-" * 50)
        print("✅ Final Response:")
        print(final_response)
        print("-" * 50 + "\n")

    return final_response


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    # --- Ensure correct v1 schema tables exist before ADK connects ---
    await ensure_tables()

    # --- Create MySQL-backed DatabaseSessionService ---
    mysql_url = build_mysql_url()
    print(f"🔌 Connecting to MySQL: {mysql_url.split('@')[-1]}")  # hide credentials in log
    session_service = DatabaseSessionService(db_url=mysql_url)

    # -----------------------------------------------------------------------
    # TEST CASE 1: New Session (Setting Context)
    # -----------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("TEST CASE 1: New Session (Setting Context)")
    print("=" * 50)

    session_id = "mysql_persistent_trip"

    # Get existing session or create a fresh one
    session = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=session_id
    )
    if not session:
        session = await session_service.create_session(
            app_name=root_agent.name, user_id="user_01", session_id=session_id
        )
        print(f"✨ Created new session: {session_id}")
    else:
        print(f"🔄 Resumed existing session: {session_id}")

    query_1 = "Hi! I'm planning a trip to Kyoto. I love temples and I'm a vegetarian."
    await run_agent_query(root_agent, query_1, session, "user_01", session_service)

    # -----------------------------------------------------------------------
    # TEST CASE 2: Resume Session (Verifying Persistent Memory)
    # -----------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("TEST CASE 2: Resume Session (Verifying Persistent Memory)")
    print("=" * 50)

    # Re-fetch from MySQL to prove persistence
    session_resumed = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=session_id
    )

    query_2 = "What vegetarian restaurants would you recommend near the temples?"
    await run_agent_query(root_agent, query_2, session_resumed, "user_01", session_service)

    # -----------------------------------------------------------------------
    # TEST CASE 3: Cross-Session Context Injection
    # -----------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("TEST CASE 3: Cross-Session Retrieval (Manual Context Injection)")
    print("=" * 50)

    new_session_id = "mysql_second_trip"
    print(f"Starting NEW session: {new_session_id}")

    # 1. Retrieve the OLD session from MySQL
    old_session = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=session_id
    )

    # 2. Extract conversation text from old session events
    previous_context = ""
    if old_session and old_session.events:
        print(f"Found {len(old_session.events)} events in old session.")
        previous_context = "PREVIOUS TRIP CONTEXT:\n"
        for event in old_session.events:
            try:
                role = getattr(event, "role", "unknown")
                text = ""
                if hasattr(event, "parts"):
                    text = " ".join([p.text for p in event.parts if hasattr(p, "text")])
                elif hasattr(event, "content") and hasattr(event.content, "parts"):
                    text = " ".join(
                        [p.text for p in event.content.parts if hasattr(p, "text")]
                    )
                if text:
                    previous_context += f"{role}: {text}\n"
            except Exception as e:
                print(f"Error parsing event: {e}")
    else:
        print("No previous session events found.")

    print(f"Extracted Context:\n{previous_context}")

    # 3. Create the NEW session in MySQL
    new_session = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=new_session_id
    )
    if not new_session:
        new_session = await session_service.create_session(
            app_name=root_agent.name, user_id="user_01", session_id=new_session_id
        )

    # 4. Inject previous context into the first message of the new session
    query_3 = (
        f"{previous_context}\n"
        "Based on my previous preferences above, "
        "can you recommend a great first day itinerary for my new trip to Osaka?"
    )
    await run_agent_query(root_agent, query_3, new_session, "user_01", session_service)

    # Cleanly dispose the async SQLAlchemy engine so all aiomysql connections
    # are closed before the event loop shuts down.
    # (prevents: RuntimeError: Event loop is closed)
    try:
        from sqlalchemy.ext.asyncio import AsyncEngine
        for attr_val in vars(session_service).values():
            if isinstance(attr_val, AsyncEngine):
                await attr_val.dispose()
                break
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
    import gc
    gc.collect()

