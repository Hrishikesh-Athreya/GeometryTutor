# 🧠 Geometry teacher - StudySnaps

This agent is an AI-powered geometry tutor that helps users learn and solve geometry problems step-by-step.  
It uses **Groq** as the language model backend and supports both **structured tutoring requests** and **chat-based conversations** using the `chat_protocol_spec`.

Implements the **StudySnapsTutorProtocol** and is a part of the **StudySnap Agentverse.**

---

## Agents deployments
https://agentverse.ai/agents/details/agent1q0678mr2q6p9235y4g8ax8tvjzgqwk0slxxddkrkjysye99a4rgysxvpcrv/profile
https://agentverse.ai/agents/details/agent1qwxepmyk063m8r0sj6l6wk2lzgg94mxwdvv8wa7k4wgd779yajz0ushqkj2/profile
https://agentverse.ai/agents/details/agent1qflfta8hj3vujvz23mjcgssqug2mcghkdhzavaekvn5akw0at86wu5ezm5u/profile

### Example input

```python
question = "Given 2 parallel lines, and an intersecting line, what should the value of the sum of expertiot opposite angles be?"
```
### Example output
```python
AnswerStepResponse(
    answer_value="Great! Let's get started. When two lines are parallel, they never meet — even if extended infinitely. Can you recall how their corresponding angles relate?",
    solving_completed=False
```

### Usage Example
```python 
from uagents import Agent, Context
from models import AnswerStepRequest, AnswerStepResponse

# Replace with your hosted Tutor Agent address
TUTOR_AGENT_ADDRESS = "agent1q0678mr2q6p9235y4g8ax8tvjzgqwk0slxxddkrkjysye99a4rgysxvpcrv"

question = "Given 2 parallel lines, and an intersecting line, what should the value of the sum of expertiot opposite angles be?"

agent = Agent(name="student")

@agent.on_event("startup")
async def send_question(ctx: Context):
    await ctx.send(
        TUTOR_AGENT_ADDRESS,
        AnswerStepRequest(
            request=question,
            session_id="session-123"
        )
    )
    ctx.logger.info(f"Sent question: {question}")

@agent.on_message(AnswerStepResponse)
async def handle_response(ctx: Context, sender: str, msg: AnswerStepResponse):
    ctx.logger.info(f"Received response from {sender}:")
    ctx.logger.info(f"Answer: {msg.answer_value}")
    ctx.logger.info(f"Solved: {msg.solving_completed}")

if __name__ == "__main__":
    agent.run()
```
### ⚙️ Environment Variables
```
export GROQ_API_KEY="your_groq_api_key_here"
```

### 🧩 Local Agent Setup
1. Install dependencies
```
pip install uagents groq
```
2. Run the Tutor Agent
```
python main.py
```
3. Start a Chat
Once connected, you can use the Agentverse Chat Interface
 to send messages to your tutor’s address.
