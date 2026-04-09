from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import google_search

load_dotenv()

# --- Agent Definitions for our Specialist Team (Refactored for Sequential Workflow) ---

foodie_agent = LlmAgent(
    name="foodie_agent",
    model="gemini-3.1-flash-lite-preview",
    description="Finds a high-quality restaurant destination based on the user's request.",
    instruction=(
        "You are a local food expert. Use Google Search when useful to identify one excellent "
        "restaurant that matches the user's request. Return only the restaurant name and full "
        "street address in one line."
    ),
    tools=[google_search],
    output_key="destination",
)

transportation_agent = LlmAgent(
    name="transportation_agent",
    model="gemini-3.1-flash-lite-preview",
    description="Provides practical travel directions to the selected destination.",
    instruction=(
        "You are a transportation expert. The destination selected by the foodie specialist is "
        "available as {destination}. Explain how to get there from downtown Caltrain station. "
        "Provide 2-3 realistic options (walk/transit/rideshare), with concise step-by-step guidance."
    ),
)

root_agent = SequentialAgent(
    name="travel_concierge_sequential",
    description="Coordinates restaurant discovery first, then transportation guidance.",
    sub_agents=[foodie_agent, transportation_agent],
)
