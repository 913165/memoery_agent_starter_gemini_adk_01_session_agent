
# Memory Agent Starter with Google AI

A starter project demonstrating how to build a conversational AI agent using **Google ADK (Agent Development Kit)** that maintains memory across multiple sessions.

## 🎯 What This Project Does

This project creates a **travel planning assistant** that:
- Remembers user preferences and interests within a session
- Demonstrates how sessions maintain conversation history
- Shows the difference between memory retention (same session) vs. memory loss (different sessions)

## 📦 Prerequisites

- Python 3.8+
- Google Gemini API Key (get one free at [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey))

## 🚀 Setup Instructions

### 1. Clone or Download the Project
```bash
cd memory_agent_starter_googleai
```

### 2. Create a Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Your API Key
Create a `.env` file in the project root:
```
GOOGLE_API_KEY=your_api_key_here
```

Replace `your_api_key_here` with your actual API key from [Google AI Studio](https://aistudio.google.com/apikey).

### 5. Run the Project
```bash
python main.py
```

## 📁 Project Structure

```
memory_agent_starter_googleai/
├── agent.py           # Defines the AI agent
├── main.py            # Main script with scenarios
├── .env               # API key configuration (create this)
├── requirements.txt   # Project dependencies
└── README.md          # This file
```

## 🧠 Understanding Google ADK

### What is Google ADK?

Google ADK (Agent Development Kit) is a framework for building AI agents that can:
- Use Large Language Models (LLMs) for intelligent responses
- Maintain conversation history through sessions
- Work with tools and external services
- Handle asynchronous operations

### Key Concepts

#### 1. **Agent**
An agent is your AI assistant. It's configured with:
- **name**: Identifier for the agent
- **model**: The LLM to use (e.g., `gemini-2.5-flash-lite`)
- **description**: What the agent does
- **instruction**: System prompt that guides the agent's behavior

```python
root_agent = Agent(
    name="memory_agent",
    model="gemini-2.5-flash-lite",
    description="A helpful travel planning agent...",
    instruction="You are a friendly travel planning assistant..."
)
```

#### 2. **Session**
A session represents a conversation thread. It stores:
- User messages
- Agent responses
- Conversation history for context

**Same session = Agent remembers previous messages**
**Different session = Agent has no memory of previous conversations**

```python
# Create a session
session = await session_service.create_session(
    app_name=agent.name,
    user_id="user_id_123"
)
```

#### 3. **Runner**
The runner executes the agent within a session. It processes user input and returns responses.

```python
runner = Runner(
    agent=agent,
    app_name=agent.name,
    session_service=session_service
)

# Send a message and get streaming responses
async for event in runner.run_async(
    user_id=user_id,
    session_id=session.id,
    new_message=types.Content(parts=[types.Part(text=query)], role="user")
):
    if event.is_final_response():
        response = event.content.parts[0].text
```

#### 4. **Session Service**
Manages all sessions for your application. In this project, we use `InMemorySessionService` which stores sessions in memory.

```python
session_service = InMemorySessionService()
```

## 📖 Code Walkthrough

### agent.py
Defines the AI agent configuration:

```python
from dotenv import load_dotenv
from google.adk.agents import Agent

load_dotenv()  # Load API key from .env

root_agent = Agent(
    name="memory_agent",
    model="gemini-2.5-flash-lite",
    description="A helpful travel planning agent that remembers user preferences...",
    instruction="You are a friendly travel planning assistant..."
)
```

**Key imports:**
- `Agent`: The main agent class
- `load_dotenv()`: Loads environment variables from `.env` file

### main.py

#### Helper Function: `run_agent_query()`
Executes a query and returns the agent's response:

```python
async def run_agent_query(agent, query, session, user_id, session_service):
    runner = Runner(agent=agent, app_name=agent.name, session_service=session_service)
    
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=types.Content(parts=[types.Part(text=query)], role="user")
    ):
        if event.is_final_response():
            final_response = event.content.parts[0].text
    
    return final_response
```

#### Scenario 1: Same Session (Memory Retained)
```python
# Create ONE session
trip_session = await session_service.create_session(...)

# Turn 1: User tells agent about preferences
query1 = "Hi! I want to plan a 2-day trip to Tokyo. I'm interested in historic sites and sushi."
await run_agent_query(multi_day_agent, query1, trip_session, ...)

# Turn 2: Use the SAME session - agent remembers!
query2 = "That sounds pretty good, do you remember what I liked about the food?"
await run_agent_query(multi_day_agent, query2, trip_session, ...)
# ✅ Agent remembers "sushi" from Turn 1
```

#### Scenario 2: Different Sessions (Memory Lost)
```python
# Create first session and query
tokyo_session = await session_service.create_session(...)
await run_agent_query(multi_day_agent, query1, tokyo_session, ...)

# Create a DIFFERENT session
tokyo_session_2 = await session_service.create_session(...)

# Query in new session - agent has NO memory!
await run_agent_query(multi_day_agent, query2, tokyo_session_2, ...)
# ❌ Agent doesn't remember preferences from previous session
```

## 🔄 Async/Await Explained

This project uses Python's `async/await` for asynchronous operations:

```python
async def main():
    # Code runs asynchronously
    await run_trip_same_session_scenario(...)
```

**Why?** Because:
- Waiting for API responses doesn't block other operations
- Multiple conversations can run concurrently
- More efficient use of system resources

## 🛠️ Available Models

You can use any of these models (check availability for your API tier):

- `gemini-2.5-flash-lite` (Recommended - fast & efficient)
- `gemini-2.5-flash-preview-tts`
- `gemini-3-flash-preview`
- `gemini-pro-latest`

Check available models by running:
```python
from google import genai
client = genai.Client(api_key='your_key')
for model in client.models.list():
    print(model.name)
```

## 📝 Common Tasks

### Add a New Scenario
```python
async def run_custom_scenario(session_service, user_id):
    session = await session_service.create_session(
        app_name=multi_day_agent.name,
        user_id=user_id
    )
    
    query = "Your question here"
    response = await run_agent_query(multi_day_agent, query, session, user_id, session_service)
    print(response)
```

### Modify Agent Instructions
Edit `agent.py`:
```python
instruction=(
    "You are a helpful assistant that specializes in [YOUR SPECIALTY]"
)
```

### Add Tools to Agent
```python
from google.adk.tools import google_search

root_agent = Agent(
    ...
    tools=[google_search],  # Add tools here
)
```

## 🐛 Troubleshooting

### "404 NOT_FOUND: This model is no longer available"
Update the model in `agent.py`:
```python
model="gemini-2.5-flash-lite",  # Try a different available model
```

### "GOOGLE_API_KEY not found"
Make sure:
1. You created a `.env` file in the project root
2. It contains: `GOOGLE_API_KEY=your_actual_key`
3. The key is valid from [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### "ModuleNotFoundError: No module named 'google.adk'"
Install dependencies:
```bash
pip install -r requirements.txt
```

## 📚 Resources

- [Google ADK Documentation](https://ai.google.dev/)
- [Gemini API Guide](https://ai.google.dev/gemini-api)
- [Google AI Studio](https://aistudio.google.com/)
- [Python AsyncIO Docs](https://docs.python.org/3/library/asyncio.html)

## 🎓 Learning Path

1. **Understand Sessions**: Run the project and observe how Scenario 1 vs Scenario 2 differ
2. **Modify Instructions**: Change the agent's behavior by editing the `instruction` field
3. **Add Tools**: Integrate external APIs using the tools framework
4. **Build Custom Agents**: Create your own agent for a different use case
5. **Deploy**: Use Google Cloud to deploy your agent

## 💡 Key Takeaways

- **Sessions** = Conversation memory
- **Same session** = Agent remembers context
- **Different sessions** = Fresh conversation (no memory)
- **Async** = Non-blocking operations
- **Runner** = The engine that executes agents
- **Agent** = The AI personality and configuration

## 📄 License

This is a starter project based on Google's ADK examples.

---

**Happy building! 🚀** If you have questions, check the [Google ADK docs](https://ai.google.dev/) or experiment with the scenarios in `main.py`.

#
