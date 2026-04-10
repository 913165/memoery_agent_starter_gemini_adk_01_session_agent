import asyncio
import sys
import os
from pathlib import Path

# Add the current directory to sys.path to ensure we can import agent.py
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from google.adk.agents import Agent
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import Session, DatabaseSessionService
from agent import root_agent

# ---------------------------------------------------------------------------
# SQLite vs MySQL — what changes:
#
#   MySQL  → db_url = "mysql+aiomysql://user:pass@host:port/dbname"
#   SQLite → db_url = "sqlite+aiosqlite:///path/to/sessions.db"
#
# Everything else (DatabaseSessionService, Runner, sessions, events) is
# identical. ADK abstracts the database completely behind the same API.
#
# Schema note: ADK v1 stores ALL event fields in a single 'event_data'
# JSON column. It detects the schema version via 'adk_internal_metadata'.
# If that table is missing, ADK misdetects v0 (Pickle) and fails.
# ensure_tables() below creates the correct schema before ADK connects.
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent / "sessions.db"
DB_URL  = f"sqlite+aiosqlite:///{DB_PATH}"

# ADK v1 schema DDL — same for both SQLite and MySQL (column names/types identical)
# SQLite uses TEXT for all string/JSON fields; MySQL uses LONGTEXT.
# We use TEXT here which works for SQLite.
_DDL = [
    ("adk_internal_metadata",
     """CREATE TABLE IF NOT EXISTS adk_internal_metadata (
            key   TEXT NOT NULL PRIMARY KEY,
            value TEXT NOT NULL
        )"""),
    ("sessions",
     """CREATE TABLE IF NOT EXISTS sessions (
            app_name    TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            id          TEXT NOT NULL,
            state       TEXT,
            create_time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            update_time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            PRIMARY KEY (app_name, user_id, id)
        )"""),
    ("events",
     """CREATE TABLE IF NOT EXISTS events (
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
        )"""),
    ("app_states",
     """CREATE TABLE IF NOT EXISTS app_states (
            app_name    TEXT NOT NULL PRIMARY KEY,
            state       TEXT,
            update_time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
        )"""),
    ("user_states",
     """CREATE TABLE IF NOT EXISTS user_states (
            app_name    TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            state       TEXT,
            update_time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            PRIMARY KEY (app_name, user_id)
        )"""),
]


async def ensure_tables():
    """
    Creates ADK v1 schema tables in SQLite if not present, or recreates them
    if the old multi-column events schema (missing event_data) is detected.

    Comparison with MySQL agent:
      MySQL  → uses aiomysql, VARCHAR(128), LONGTEXT, InnoDB ENGINE
      SQLite → uses aiosqlite, TEXT columns, no ENGINE clause
      Logic  → identical: check adk_internal_metadata + event_data column
    """
    import aiosqlite

    db_exists = DB_PATH.exists()

    if db_exists:
        async with aiosqlite.connect(DB_PATH) as db:
            # Check for adk_internal_metadata
            cur = await db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='adk_internal_metadata'"
            )
            metadata_exists = (await cur.fetchone())[0] > 0

            # Check for event_data column in events table
            cur = await db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='events'"
            )
            events_exists = (await cur.fetchone())[0] > 0

            event_data_exists = False
            if events_exists:
                cur = await db.execute("PRAGMA table_info(events)")
                cols = [row[1] for row in await cur.fetchall()]
                event_data_exists = "event_data" in cols

        if not metadata_exists or not event_data_exists:
            print("⚠️  Outdated SQLite schema detected — deleting and recreating sessions.db...")
            DB_PATH.unlink()  # Delete the old .db file — easiest way to reset SQLite
            db_exists = False

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        for _, ddl in _DDL:
            await db.execute(ddl)
        await db.execute(
            "INSERT OR IGNORE INTO adk_internal_metadata (key, value) VALUES ('schema_version', '1')"
        )
        await db.commit()

    print("✅ SQLite database tables ready (v1 JSON schema).")
    print(f"   Database file: {DB_PATH}")


# TODO: Configuration for Persistent Sessions

# --- A Helper Function to Run Our Agents ---
async def run_agent_query(agent: Agent, query: str, session: Session, user_id: str,
                          session_service: DatabaseSessionService, is_router: bool = False):
    """Initializes a runner and executes a query for a given agent and session."""
    print(f"\n🚀 Running query for agent: '{agent.name}' in session: '{session.id}'...")

    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name=agent.name
    )

    final_response = ""
    try:
        async for event in runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=types.Content(parts=[types.Part(text=query)], role="user")
        ):
            if not is_router:
                # Let's see what the agent is thinking!
                # print(f"EVENT: {event}")
                pass
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


async def main():
    # Ensure correct v1 schema before ADK connects
    await ensure_tables()

    # SQLite-backed persistent session service
    # 👆 Only difference from MySQL agent:
    #    MySQL  → "mysql+aiomysql://root:root123@127.0.0.1:3306/adk_sessions"
    #    SQLite → "sqlite+aiosqlite:///path/to/sessions.db"
    session_service = DatabaseSessionService(db_url=DB_URL)

    # --- Test Case 1: New Session ---
    print("\n" + "=" * 50)
    print("TEST CASE 1: New Session (Setting Context)")
    print("=" * 50)

    session_id = "my_persistent_trip"

    # Ensure we start fresh for this test by creating a new session if needed,
    # or just using the existing one but acknowledging we are 'starting' a flow.
    # In a real app, you might generate a random UUID for a truly new session.

    # Get or create session
    session = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=session_id
    )
    if not session:
        session = await session_service.create_session(
            app_name=root_agent.name, user_id="user_01", session_id=session_id
        )
        print(f"Created new session: {session_id}")
    else:
        print(f"Resumed existing session: {session_id}")

    # Turn 1: Tell the agent something about ourselves
    query_1 = "Hi! I'm planning a trip to Tokyo. I love ramen and I'm a vegetarian."
    await run_agent_query(root_agent, query_1, session, "user_01", session_service)

    # --- Test Case 2: Resume Session ---
    print("\n" + "=" * 50)
    print("TEST CASE 2: Resume Session (Verifying Memory)")
    print("=" * 50)

    # Simulate a break in conversation or a new request coming in later
    # We re-fetch the session to prove persistence works (though in this script it's the same object,
    # the service abstraction handles the DB sync).

    session_resumed = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=session_id
    )

    # Turn 2: Ask for a recommendation that requires remembering Turn 1
    query_2 = "Where should I go for dinner?"
    await run_agent_query(root_agent, query_2, session_resumed, "user_01", session_service)

    # --- Test Case 3: Cross-Session Retrieval ---
    print("\n" + "=" * 50)
    print("TEST CASE 3: Cross-Session Retrieval (Manual Context Injection)")
    print("=" * 50)

    # Scenario: User starts a completely NEW trip (new session ID) but wants to reference
    # preferences from the previous trip ("my_persistent_trip").

    new_session_id = "my_second_trip"
    print(f"Starting NEW session: {new_session_id}")

    # TODO: retrieve the previous session manually
    old_session = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=session_id
    )

    # 2. Extract relevant info (naive approach: get all user/model turns)
    # In a real app, you might use an LLM to summarize this, or filter for specific 'preferences'.
    previous_context = ""
    if old_session and old_session.events:
        print(f"Found {len(old_session.events)} events in old session.")
        previous_context = "PREVIOUS TRIP CONTEXT:\n"
        for event in old_session.events:
            # Assuming event structure has 'role' and 'parts' (standard GenAI types)
            # We need to be careful with the structure. Let's just dump the text.
            # The 'event' in session.events is likely a Turn or similar object.
            # Let's inspect it or just try to access standard attributes.
            # Based on standard ADK, it might be a Pydantic model with 'role' and 'parts'.
            # Let's try to stringify it safely.
            try:
                role = getattr(event, 'role', 'unknown')
                text = ""
                if hasattr(event, 'parts'):
                    text = " ".join([p.text for p in event.parts if hasattr(p, 'text')])
                elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
                    text = " ".join([p.text for p in event.content.parts if hasattr(p, 'text')])

                if text:
                    previous_context += f"{role}: {text}\n"
            # TODO: Extract content from the OLD session

            except Exception as e:
                print(f"Error parsing event: {e}")

    print(f"Extracted Context:\n{previous_context}")

    # 3. Create the NEW session
    new_session = await session_service.create_session(
        app_name=root_agent.name, user_id="user_01", session_id=new_session_id
    )

    # 4. Inject the context into the FIRST query of the new session
    # We explicitly tell the agent: "Here is what we know from a past trip..."
    # TODO: Manually inject the context to the query
    query_3 = (
        f"{previous_context}\n"
        "Based on my previous preferences above, can you recommend a good first day itinerary for my new trip?"
    )

    await run_agent_query(root_agent, query_3, new_session, "user_01", session_service)


if __name__ == "__main__":
    asyncio.run(main())