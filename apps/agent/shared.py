from __future__ import annotations

from datetime import date
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from lib.config import get_settings, get_tenant_config
from apps.agent.state import HospitalAgentState

settings = get_settings()


# ── MergingToolNode ──────────────────────────────────────────────────────────


class MergingToolNode(ToolNode):
    async def _afunc(self, input, config, runtime):
        result = await super()._afunc(input, config, runtime)
        return _merge_commands(result)

    def _func(self, input, config, runtime):
        result = super()._func(input, config, runtime)
        return _merge_commands(result)


def _merge_commands(outputs) -> list:
    """Merge concurrent tool outputs into a single Command update.

    ToolNode returns a list of Commands when tools succeed, but falls back to
    a dict form ``{"messages": [...]}`` when NO tool returned a Command (e.g.
    all calls failed validation). Accept both shapes plus mixed
    Command/ToolMessage lists and fold everything into one Command.
    """
    if isinstance(outputs, dict):
        return [Command(update=outputs)]
    if not isinstance(outputs, list):
        outputs = [outputs]

    merged: dict[str, Any] = {}
    merged_msgs: list[Any] = []
    rest: list[Any] = []
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
        elif isinstance(item, BaseMessage):
            merged_msgs.append(item)
        else:
            rest.append(item)
    if merged or merged_msgs:
        cmd_update = {**merged}
        if merged_msgs:
            cmd_update["messages"] = merged_msgs
        rest.insert(0, Command(update=cmd_update))
    elif not rest:
        rest = [Command(update={})]
    return rest


# ── Shared helpers ──────────────────────────────────────────────────────────


def _sub_deployment() -> str:
    return settings.azure_openai_deployment2_name or settings.azure_openai_deployment_name


def build_llm(temperature: float = 0.3, max_tokens: int = 1024) -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        deployment_name=_sub_deployment(),
        temperature=temperature,
        max_tokens=max_tokens,
    )


def build_system(state: HospitalAgentState, prompt_template: str) -> str:
    tc = get_tenant_config(state.get("tenant_id"))
    system = tc.format(prompt_template)
    system += f"\nToday's date: {date.today().isoformat()}"
    cid = state.get("client_id")
    if cid:
        system += f"\n\nClient/hospital ID for booking: {cid}"
    phone = state.get("patient_phone")
    if phone:
        system += f"\n\nPatient phone (resolved from their WhatsApp account): {phone}"
    name = state.get("patient_name")
    if name:
        system += f"\nPatient name (resolved from their WhatsApp account): {name}"
    return system
