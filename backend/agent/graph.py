# LangGraph ReAct Single Agent 그래프
import os
from pathlib import Path

import aiosqlite
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.prompts.system_prompt import build_system_prompt
from agent.tools import ALL_TOOLS

RECURSION_LIMIT = int(os.environ.get("RECURSION_LIMIT", "20"))
DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
DB_PATH = DATA_DIR / "pm_agent.sqlite"


async def build_graph():
    llm = ChatOpenAI(model=os.environ.get("LLM_MODEL", "gpt-4o-mini"), temperature=0, streaming=True)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def agent_node(state: MessagesState):
        messages = [build_system_prompt(), *state["messages"]]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    graph_builder = StateGraph(MessagesState)
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", ToolNode(ALL_TOOLS))
    graph_builder.set_entry_point("agent")
    graph_builder.add_conditional_edges("agent", tools_condition)
    graph_builder.add_edge("tools", "agent")

    conn = await aiosqlite.connect(str(DB_PATH))
    return graph_builder.compile(checkpointer=AsyncSqliteSaver(conn))