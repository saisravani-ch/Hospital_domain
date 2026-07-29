from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

# Load .env into os.environ so LangSmith tracing vars are visible
load_dotenv()

from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from loguru import logger
from pydantic import BaseModel
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from src.knowledge_base.config import get_settings, get_tenant_config
from src.orchestrator.langgraph_tools import (
    book_appointment,
    cancel_appointment,
    check_availability,
    get_doctor_info,
    reschedule_appointment,
    search_doctors,
)
from src.orchestrator.prompts import SYSTEM_PROMPT_TEMPLATE
from src.orchestrator.state import HospitalAgentState

settings = get_settings()

_TOOLS = [
    search_doctors,
    get_doctor_info,
    check_availability,
    book_appointment,
    reschedule_appointment,
    cancel_appointment,
]


def _merge_commands(outputs: list) -> list:
    """Merge state updates from concurrent Commands into one to avoid channel conflicts.

    LangGraph crashes if two Commands write to the same plain-list channel
    in one step.  This combines all update dicts (last-write-wins) and all
    Command messages into a single Command.
    """
    merged: dict[str, Any] = {}
    merged_msgs: list[ToolMessage] = []
    rest: list = []

    for item in outputs:
        if isinstance(item, Command):
            update = item.update if isinstance(item.update, dict) else {}
            for k, v in update.items():
                if k == "messages":
                    if isinstance(v, list):
                        merged_msgs.extend(v)
                    else:
                        merged_msgs.append(v)
                else:
                    merged[k] = v
        else:
            rest.append(item)

    if merged or merged_msgs:
        cmd_update = {**merged}
        if merged_msgs:
            cmd_update["messages"] = merged_msgs
        rest.insert(0, Command(update=cmd_update))
    return rest


class MergingToolNode(ToolNode):
    """ToolNode that merges concurrent Command updates to prevent channel write conflicts."""

    async def _afunc(
        self,
        input: list[AnyMessage] | dict[str, Any] | BaseModel,
        config: RunnableConfig,
        runtime: Runtime,
    ) -> Any:
        result = await super()._afunc(input, config, runtime)
        return _merge_commands(result)

    def _func(
        self,
        input: list[AnyMessage] | dict[str, Any] | BaseModel,
        config: RunnableConfig,
        runtime: Runtime,
    ) -> Any:
        result = super()._func(input, config, runtime)
        return _merge_commands(result)


tool_node = MergingToolNode(_TOOLS)


def _build_llm() -> AzureChatOpenAI:
    kwargs = dict(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        deployment_name=settings.azure_openai_deployment_name,
        temperature=0.3,
        max_tokens=1024,
    )
    return AzureChatOpenAI(**kwargs)


def _build_system(state: HospitalAgentState) -> str:
    from datetime import date
    tc = get_tenant_config(state.get("tenant_id"))
    system = tc.format(SYSTEM_PROMPT_TEMPLATE)
    system += f"\nToday's date: {date.today().isoformat()}"
    cid = state.get("client_id")
    if cid:
        system += f"\n\nClient/hospital ID for booking: {cid}"
    return system


async def assistant_node(state: HospitalAgentState) -> dict[str, Any]:
    llm = _build_llm().bind_tools(_TOOLS)
    system = _build_system(state)
    messages = [SystemMessage(content=system)] + list(state["messages"])
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


def human_confirmation_node(state: HospitalAgentState) -> dict[str, Any]:
    last_ai = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            last_ai = msg
            break

    if last_ai:
        for tc in last_ai.tool_calls:
            if tc.get("name") == "book_appointment":
                args = tc.get("args", {})
                msg = (
                    f"Please confirm the appointment:\n"
                    f"  Doctor ID: {args.get('doctor_id', 'unknown')}\n"
                    f"  Date: {args.get('date', 'unknown')}\n"
                    f"  Time: {args.get('time', 'unknown')}\n"
                    f"  Phone: {args.get('patient_phone', 'unknown')}\n"
                    f"\nReply 'yes' to confirm or 'no' to cancel."
                )
                confirmation = interrupt(msg)
                if confirmation and str(confirmation).strip().lower()[:1] == "y":
                    return {"current_phase": "booking_confirmed"}
                return {"current_phase": "booking_cancelled"}

    return {}


def should_continue(state: HospitalAgentState) -> str:
    if not state["messages"]:
        return END
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        for tc in last.tool_calls:
            if tc.get("name") == "book_appointment":
                return "human_confirmation"
        return "tools"
    return END


def after_confirmation(state: HospitalAgentState) -> str:
    phase = state.get("current_phase", "")
    if phase == "booking_confirmed":
        return "tools"
    return "assistant"


def create_graph(
    *,
    assistant_node_override: callable | None = None,
    tool_node_override: ToolNode | None = None,
) -> Any:
    actual_assistant = assistant_node_override or assistant_node
    actual_tool_node = tool_node_override or tool_node

    workflow = StateGraph(HospitalAgentState)

    workflow.add_node("assistant", actual_assistant)
    workflow.add_node("tools", actual_tool_node)
    workflow.add_node("human_confirmation", human_confirmation_node)

    workflow.set_entry_point("assistant")

    workflow.add_conditional_edges("assistant", should_continue, {
        "tools": "tools",
        "human_confirmation": "human_confirmation",
        END: END,
    })

    workflow.add_edge("tools", "assistant")

    workflow.add_conditional_edges("human_confirmation", after_confirmation, {
        "tools": "tools",
        "assistant": "assistant",
    })

    return workflow.compile(checkpointer=MemorySaver())
