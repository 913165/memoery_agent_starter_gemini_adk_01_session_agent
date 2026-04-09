
from dotenv import load_dotenv
from google.adk.agents import Agent

load_dotenv()

root_agent = Agent(
    name="memory_agent",
    model="gemini-3.1-flash-lite-preview",
    description="A helpful travel planning agent that remembers user preferences and adapts its recommendations.",
    instruction=(
        "You are a friendly and knowledgeable travel planning assistant. "
        "Remember details the user shares (interests, food preferences, travel style) "
        "and use them to give personalized, context-aware recommendations. "
        "When asked if you remember something, refer back to what the user told you earlier in the conversation."
    ),
)

print(f"🗺️ Agent '{root_agent.name}' is created and ready to plan and adapt!")