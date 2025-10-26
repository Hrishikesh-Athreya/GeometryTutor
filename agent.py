# main.py (uAgents + Groq-backed tutor + Chat example using Groq)

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from uagents import Protocol, Context, Agent

# Match the example's import path so class identity is identical on both sides
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

# --- Your app-level models ---
from models import (
    GetCourseRequest, GetCourseResponse,
    AnswerStepRequest, AnswerStepResponse,
    TutorInfoRequest, TutorInfoResponse,
    Slide,  # Pydantic model: {content:str, image_url: Optional[str]}
)

# --- Groq client (pip install groq) ---
try:
    from groq import Groq
except ImportError:
    Groq = None

MODEL_ID = os.getenv("MODEL_ID", "meta-llama/llama-4-scout-17b-16e-instruct")
WINDOW_TURNS = 100
SESSIONS: Dict[str, List[Dict[str, Any]]] = {}

# Protocols & agent
tutor_proto_v1 = Protocol(name="StudySnapsTutorProtocol", version="1.0.0")
chat_proto = Protocol(spec=chat_protocol_spec)
agent = Agent(name="tutor_agent", seed=os.getenv("TUTOR_AGENT_SEED", "dev-seed"))

# ----- Pydantic DTO for structured Groq output (used by tutor protocol path) -----
class TutorResult(BaseModel):
    answer_value: str
    solving_completed: bool
    model_config = ConfigDict(extra="forbid")

SYSTEM_PROMPT = (
    "You are a Geometry AI tutor, your goals and tasks are as below : \n"
    "1. Understand the images and text uploaded to you as a part of the context you'll need to answer questions that are coming to you next.\n"
    "2. The user will then upload a question that you have to help with. \n"
    "3. To help the user you will perform the below actions : \n"
    "3.1. You create a step by step plan to tackle the problem. Don't output the plan as a part of your answer. Just come up with a plan in your memory.\n"
    "3.2. You will use these steps to nudge the user towards the solution. Always begin the nudge with a short, friendly welcoming phrase (e.g., 'Great! Let's get started...')\n"
    '3.3. All Nudges. should have meaningful action to do next. Do not include trivial steps like "Write down the equation". '
    "The nudges should only cover one step and should never contain the answer\n\n"
    "If the question gets solved, then you don't have to output a nudge, you can just output something encouraging for successfully completing the problem and you can declare the question as completed"
    "After a question has been uploaded your response will be the first nudge.\n"
    "When you're generating subsequent nudges, don't expand too much on the answer the user just gave you in the previous nudge if the answer was correct. "
    "Simply say something encouraging and friendly and move on.\n\n"
    "ALL OF YOUR ANSWERS HAVE TO BE SHORT AND CRISP, DO NOT GENERATE LONG ANSWERS"
)

def _ensure_client() -> Groq:
    if Groq is None:
        raise RuntimeError("groq package is not installed. `pip install groq`")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Set GROQ_API_KEY environment variable.")
    return Groq(api_key=api_key)

def _window(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not messages:
        return messages
    sys = [m for m in messages if m["role"] == "system"]
    non_sys = [m for m in messages if m["role"] != "system"]
    return (sys[:1] if sys else []) + non_sys[-(WINDOW_TURNS * 2):]

def _call_model_and_structure(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    client = _ensure_client()
    schema = TutorResult.model_json_schema()
    resp = client.chat.completions.create(
        model=MODEL_ID,
        messages=messages,
        response_format={"type": "json_schema", "json_schema": {"name": "tutor_result", "schema": schema, "strict": True}},
        temperature=1,
        top_p=1,
        max_tokens=512,
        stream=False,
    )
    content = resp.choices[0].message.content or "{}"
    try:
        parsed = TutorResult.model_validate(json.loads(content))
        return {"answer_value": parsed.answer_value, "solving_completed": parsed.solving_completed}
    except Exception:
        return {"answer_value": content, "solving_completed": False}

def _make_turn(text: Optional[str], image_url: Optional[str]) -> List[Dict[str, Any]]:
    content = []
    if text:
        content.append({"type": "text", "text": text})
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    return [{"role": "user", "content": content}]

def _append_and_respond(history: List[Dict[str, Any]], session_id: str) -> Dict[str, Any]:
    messages = _window(history)
    result = _call_model_and_structure(messages)
    history.append({"role": "assistant", "content": result["answer_value"]})
    if result.get("solving_completed") is True:
        SESSIONS.pop(session_id, None)
    else:
        SESSIONS[session_id] = history
    return {"answer_value": result["answer_value"], "solving_completed": result["solving_completed"]}

async def run_step(text: Optional[str], image_url: Optional[str], session_id: str) -> Dict[str, Any]:
    history = SESSIONS.get(session_id) or [{"role": "system", "content": SYSTEM_PROMPT}]
    history.extend(_make_turn(text, image_url))
    return _append_and_respond(history, session_id)

# ===== Demo course content (Pydantic Slide) =====
COURSE: List[Slide] = [
    Slide(content="Lets get started with this geometry lesson! Rule 1: Two opposite vertical angles formed when two lines intersect each other are always equal to each other"),
    Slide(content="Moving on to rule two, Angles made by a transversal with parallel lines — corresponding or alternate interior angles are congruent"),
    Slide(content="And finally adjacent angles on a straight line sum to 180 degrees."),
    Slide(
        content="That's it for the lesson! Let's move on to a simple problem. Can you find the value of x such that line L and line M are parallel to each other? Let's start by writing down the problem.",
        image_url="https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/visor/question/geometry_problem.jpeg",
    ),
]

# ===== Tutor protocol handlers =====
@tutor_proto_v1.on_message(model=TutorInfoRequest, replies=TutorInfoResponse)
async def handle_tutor_info(ctx: Context, sender: str, msg: TutorInfoRequest):
    await ctx.send(sender, TutorInfoResponse(tutor_id="GEOMETRY"))

@tutor_proto_v1.on_message(model=GetCourseRequest, replies=GetCourseResponse)
async def handle_get_course(ctx: Context, sender: str, msg: GetCourseRequest):
    await ctx.send(sender, GetCourseResponse(courses=COURSE))

@tutor_proto_v1.on_message(model=AnswerStepRequest, replies=AnswerStepResponse)
async def handle_answer_step(ctx: Context, sender: str, msg: AnswerStepRequest):
    result = await run_step(text=msg.request, image_url=getattr(msg, "image_url", None), session_id=msg.session_id)
    await ctx.send(sender, AnswerStepResponse(**result))

# ===== Chat protocol (example integrated, uses Groq) =====
@chat_proto.on_message(model=ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id))

    text = "".join(item.text for item in msg.content if isinstance(item, TextContent))

    response = "I am afraid something went wrong and I am unable to answer your question at the moment"
    try:
        client = _ensure_client()
        def _call():
            return client.chat.completions.create(
                model=MODEL_ID,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": text}],
                max_tokens=512,
                temperature=0.7,
            )
        r = await asyncio.to_thread(_call)   # <-- offload sync call
        response = (r.choices[0].message.content or "").strip() or response
    except Exception:
        ctx.logger.exception("Error querying Groq")

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=str(uuid4()),  # ensure string
            content=[TextContent(type="text", text=response),
                     EndSessionContent(type="end-session")],
        ),
    )

@chat_proto.on_message(model=ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # No-op (useful for read receipts if needed)
    pass

# Wire up
agent.include(tutor_proto_v1, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
