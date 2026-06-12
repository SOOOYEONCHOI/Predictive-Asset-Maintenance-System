# Agent API FastAPI 진입점 (:8001) — SSE /chat/stream 엔드포인트
import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from agent.graph import DB_PATH, RECURSION_LIMIT, build_graph
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
    app.state.graph = await build_graph()

    app.state.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    app.state.db.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    app.state.db.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            equip_cd TEXT,
            tool_name TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    app.state.db.commit()

    yield


app = FastAPI(title="Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    db = app.state.db
    thread_id = req.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}

    db.execute(
        "INSERT INTO chat_messages (thread_id, role, content) VALUES (?, ?, ?)",
        (thread_id, "user", req.message),
    )
    db.commit()

    async def event_generator():
        yield _sse("thread_id", thread_id)
        answer_parts = []

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
                        db.execute(
                            "INSERT INTO diagnosis_results (thread_id, equip_cd, tool_name, result_json) "
                            "VALUES (?, ?, ?, ?)",
                            (thread_id, data.get("equip_cd"), tool_name, content),
                        )
                        db.commit()

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

                elif tool_name == "make_work_order_draft":
                    yield _sse("work_order", content)

            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    answer_parts.append(chunk.content)
                    yield _sse("answer", chunk.content)

        if answer_parts:
            db.execute(
                "INSERT INTO chat_messages (thread_id, role, content) VALUES (?, ?, ?)",
                (thread_id, "assistant", "".join(answer_parts)),
            )
            db.commit()

        yield _sse("done", "")

    return StreamingResponse(event_generator(), media_type="text/event-stream")