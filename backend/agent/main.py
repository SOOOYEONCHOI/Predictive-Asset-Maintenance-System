# Agent API FastAPI 진입점 (:8001) — SSE /chat/stream 엔드포인트
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from agent.graph import RECURSION_LIMIT, build_graph
from pm_api.predictor import Predictor

load_dotenv()

CARD_TOOLS = {"classify_fault_type", "estimate_rul"}


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    Predictor.get_instance()
    if os.environ.get("MONITORING_BACKEND") == "langsmith" and os.environ.get("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    app.state.graph = build_graph()
    yield


app = FastAPI(title="Agent API", lifespan=lifespan)


def _sse(event_type: str, content) -> str:
    return f"data: {json.dumps({'type': event_type, 'content': content}, ensure_ascii=False)}\n\n"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.delete("/chat/threads/{thread_id}")
def delete_thread(thread_id: str):
    app.state.graph.checkpointer.delete_thread(thread_id)
    return {"status": "deleted", "thread_id": thread_id}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    graph = app.state.graph
    thread_id = req.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}

    async def event_generator():
        yield _sse("thread_id", thread_id)

        async for event in graph.astream_events(
            {"messages": [HumanMessage(content=req.message)]}, config=config, version="v2"
        ):
            kind = event["event"]

            if kind == "on_tool_start":
                yield _sse("tool_call", f"[도구 호출] {event['name']}")

            elif kind == "on_tool_end":
                tool_name = event["name"]
                output = event["data"].get("output")
                content = getattr(output, "content", output)
                preview = str(content)
                if len(preview) > 200:
                    preview = preview[:200] + "..."
                yield _sse("tool_result", f"[도구 결과] {preview}")

                if tool_name in CARD_TOOLS:
                    try:
                        data = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        data = None
                    if data:
                        if tool_name == "classify_fault_type":
                            yield _sse("fault_card", {
                                "fault_type": data.get("fault_type"),
                                "confidence": data.get("confidence"),
                                "evidence": data.get("evidence"),
                            })
                        elif tool_name == "estimate_rul":
                            yield _sse("rul_card", {
                                "rul_days": data.get("rul_days"),
                                "confidence": data.get("confidence"),
                                "basis": data.get("basis"),
                            })

            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield _sse("answer", chunk.content)

        yield _sse("done", "")

    return StreamingResponse(event_generator(), media_type="text/event-stream")