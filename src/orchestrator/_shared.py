from __future__ import annotations

from datetime import date
from typing import Any

from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from src.config import get_settings, get_tenant_config
from src.orchestrator.state import HospitalAgentState

settings = get_settings()


# ── MergingToolNode ──────────────────────────────────────────────────────────


class MergingToolNode(ToolNode):
    async def _afunc(self, input, config, runtime):
        result = await super()._afunc(input, config, runtime)
        return _merge_commands(result)

    def _func(self, input, config, runtime):
        result = super()._func(input, config, runtime)
        return _merge_commands(result)


def _merge_commands(outputs: list) -> list:
    merged: dict[str, Any] = {}
    merged_msgs = []
    rest = []
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
    return system
