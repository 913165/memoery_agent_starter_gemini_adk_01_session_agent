import asyncio

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

try:
    from . import agent as agent_module
except ImportError:
    # Fallback for direct script execution: `python 01_session_agent/main.py`
    import agent as agent_module

multi_day_agent = agent_module.root_agent


async def run_agent_query(
    agent: Agent,
    query: str,
    session: Session,
    user_id: str,
    session_service: InMemorySessionService,
    is_router: bool = False,
):
    """Initializes a runner and executes a query for a given agent and session."""
    print(f"\nRunning query for agent: '{agent.name}' in session: '{session.id}'...")

    runner = Runner(agent=agent, app_name=agent.name, session_service=session_service)

    final_response = ""
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(parts=[types.Part(text=query)], role="user"),
        ):
            if not is_router:
                pass
            if event.is_final_response():
                final_response = event.content.parts[0].text
    except Exception as e:
        final_response = f"An error occurred: {e}"

    if not is_router:
        print("\n" + "-" * 50)
        print("Final Response:")
        print(final_response)
        print("-" * 50 + "\n")

    return final_response


async def run_trip_same_session_scenario(session_service: InMemorySessionService, user_id: str):
    print("### SCENARIO 1: TOKYO TRIP (Adaptive Memory) ###")

    trip_session = await session_service.create_session(
        app_name=multi_day_agent.name,
        user_id=user_id,
    )
    print(f"Created a single session for our trip: {trip_session.id}")

    query1 = "Hi! I want to plan a 2-day trip to Tokyo. I'm interested in historic sites and sushi."
    print(f"\nUser (Turn 1): '{query1}'")
    await run_agent_query(multi_day_agent, query1, trip_session, user_id, session_service)

    query2 = "That sounds pretty good, do you remember what I liked about the food?"
    print(f"\nUser (Turn 2 - Feedback): '{query2}'")
    await run_agent_query(multi_day_agent, query2, trip_session, user_id, session_service)


async def run_trip_different_session_scenario(session_service: InMemorySessionService, user_id: str):
    print("\n\n### SCENARIO 2: TOKYO TRIP (New Destination) ###")

    tokyo_session = await session_service.create_session(
        app_name=multi_day_agent.name,
        user_id=user_id,
    )
    print(f"Created a new session for Tokyo trip: {tokyo_session.id}")

    query1 = "Hi! I want to plan a 2-day trip to Tokyo. I'm interested in historic sites and sushi."
    print(f"\nUser (Turn 1): '{query1}'")
    await run_agent_query(multi_day_agent, query1, tokyo_session, user_id, session_service)

    tokyo_session_2 = await session_service.create_session(
        app_name=multi_day_agent.name,
        user_id=user_id,
    )
    print(f"Created a DIFFERENT session to test memory loss: {tokyo_session_2.id}")

    query2 = "That sounds pretty good, do you remember what I liked about the food?"
    print(f"\nUser (Turn 2): '{query2}'")
    await run_agent_query(multi_day_agent, query2, tokyo_session_2, user_id, session_service)


async def main():
    session_service = InMemorySessionService()
    my_user_id = "adk_adventurer_001"

    await run_trip_same_session_scenario(session_service, my_user_id)
    await run_trip_different_session_scenario(session_service, my_user_id)


if __name__ == "__main__":
    asyncio.run(main())
