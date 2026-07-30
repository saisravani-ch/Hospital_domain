from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, StateGraph

from src.orchestrator._shared import MergingToolNode, build_llm, build_system
from src.orchestrator.state import HospitalAgentState
from src.orchestrator.skills.search.prompts import SYSTEM_PROMPT
from src.orchestrator.skills.search.tools import search_doctors, get_doctor_info

_SEARCH_TOOLS = [search_doctors, get_doctor_info]


@lru_cache(1)
def _build_llm_cached():
    return build_llm(temperature=0.3, max_tokens=1024)


async def assistant_node(state: HospitalAgentState) -> dict[str, Any]:
    llm = _build_llm_cached().bind_tools(_SEARCH_TOOLS)
    system = SystemMessage(content=build_system(state, SYSTEM_PROMPT))
    messages = [system] + list(state["messages"])
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


def should_continue(state: HospitalAgentState) -> str:
    if not state["messages"]:
        return END
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


_search_tool_node = MergingToolNode(_SEARCH_TOOLS)

_search_workflow = StateGraph(HospitalAgentState)
_search_workflow.add_node("assistant", assistant_node)
_search_workflow.add_node("tools", _search_tool_node)
_search_workflow.set_entry_point("assistant")
_search_workflow.add_conditional_edges("assistant", should_continue, {
    "tools": "tools",
    END: END,
})
_search_workflow.add_edge("tools", "assistant")

search_graph = _search_workflow.compile()
