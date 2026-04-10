import asyncio
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, Session
from google.genai import types

from agent import root_agent
from db_setup import ensure_tables, build_postgres_url

load_dotenv()


async def run_agent_query(agent: Agent, query: str, session: Session,
                          user_id: str, session_service: DatabaseSessionService) -> str:
    print(f"\n🚀 Running query for agent: '{agent.name}' in session: '{session.id}'...")
    runner = Runner(agent=agent, session_service=session_service, app_name=agent.name)
    final_response = ""

    # Re-fetch session before running to avoid stale concurrency marker.
    # PostgreSQL's update_time trigger updates on every write, so the
    # in-memory session object becomes stale after the first event is saved.
    fresh_session = await session_service.get_session(
        app_name=agent.name, user_id=user_id, session_id=session.id
    )
    if fresh_session:
        session = fresh_session

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
    print("\n" + "-" * 50)
    print("✅ Final Response:")
    print(final_response)
    print("-" * 50 + "\n")
    return final_response


async def main():
    await ensure_tables()

    pg_url = build_postgres_url()
    print(f"🔌 Connecting to PostgreSQL: {pg_url.split('@')[-1]}")
    session_service = DatabaseSessionService(db_url=pg_url)

    # ── TEST CASE 1: New Session ──────────────────────────────────────────
    print("\n" + "=" * 50)
    print("TEST CASE 1: New Session (Setting Context)")
    print("=" * 50)

    session_id = "pg_persistent_trip"
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

    await run_agent_query(root_agent,
                          "Hi! I'm planning a trip to Kyoto. I love temples and I'm a vegetarian.",
                          session, "user_01", session_service)

    # ── TEST CASE 2: Resume Session ───────────────────────────────────────
    print("\n" + "=" * 50)
    print("TEST CASE 2: Resume Session (Verifying Persistent Memory)")
    print("=" * 50)

    session_resumed = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=session_id
    )
    await run_agent_query(root_agent,
                          "What vegetarian restaurants would you recommend near the temples?",
                          session_resumed, "user_01", session_service)

    # ── TEST CASE 3: Cross-Session Context Injection ──────────────────────
    print("\n" + "=" * 50)
    print("TEST CASE 3: Cross-Session Retrieval (Manual Context Injection)")
    print("=" * 50)

    new_session_id = "pg_second_trip"
    print(f"Starting NEW session: {new_session_id}")

    old_session = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=session_id
    )

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
                    text = " ".join([p.text for p in event.content.parts if hasattr(p, "text")])
                if text:
                    previous_context += f"{role}: {text}\n"
            except Exception as e:
                print(f"Error parsing event: {e}")
    else:
        print("No previous session events found.")

    new_session = await session_service.get_session(
        app_name=root_agent.name, user_id="user_01", session_id=new_session_id
    )
    if not new_session:
        new_session = await session_service.create_session(
            app_name=root_agent.name, user_id="user_01", session_id=new_session_id
        )

    await run_agent_query(root_agent,
                          f"{previous_context}\nBased on my previous preferences above, "
                          "can you recommend a great first day itinerary for my new trip to Osaka?",
                          new_session, "user_01", session_service)

    # Cleanly dispose engine to prevent RuntimeError: Event loop is closed
    try:
        from sqlalchemy.ext.asyncio import AsyncEngine
        for v in vars(session_service).values():
            if isinstance(v, AsyncEngine):
                await v.dispose()
                break
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
    import gc; gc.collect()

