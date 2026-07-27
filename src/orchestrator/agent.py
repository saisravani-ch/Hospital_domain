from __future__ import annotations

import json
from typing import Any

import openai
from loguru import logger

from src.knowledge_base.config import get_settings, get_tenant_config
from src.orchestrator.prompts import SYSTEM_PROMPT_TEMPLATE
from src.orchestrator.tools import TOOL_DEFS

settings = get_settings()


class Agent:
    """ReAct-style agent that routes user queries to RAG/workflow tools."""

    def __init__(
        self,
        llm_client: openai.AsyncAzureOpenAI,
        tool_map: dict[str, callable],
    ):
        self._llm = llm_client
        self._tool_map = tool_map

    def _build_system_prompt(self, tenant_id: str | None = None) -> str:
        tc = get_tenant_config(tenant_id)
        return tc.format(SYSTEM_PROMPT_TEMPLATE)

    async def run(
        self,
        messages: list[dict],
        tenant_id: str | None = None,
        max_turns: int = 6,
    ) -> list[dict]:
        """Process messages through the agent loop. Returns updated message list."""
        if self._llm is None:
            return [
                *messages,
                {"role": "assistant", "content": "Agent is not available (LLM not configured). Please set up Azure OpenAI credentials in .env and restart."},
            ]

        system_prompt = self._build_system_prompt(tenant_id)
        conversation = [{"role": "system", "content": system_prompt}, *messages]
        turn = 0

        while turn < max_turns:
            turn += 1
            try:
                response = await self._llm.chat.completions.create(
                    model=settings.azure_openai_deployment_name,
                    messages=conversation,
                    tools=TOOL_DEFS,
                    tool_choice="auto",
                    max_tokens=1024,
                    temperature=0.3,
                )
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                conversation.append({
                    "role": "assistant",
                    "content": "I'm sorry, I encountered an error processing your request. Please try again.",
                })
                break

            choice = response.choices[0]
            msg = choice.message

            if not msg.tool_calls:
                conversation.append({"role": "assistant", "content": msg.content or ""})
                break

            conversation.append(msg.model_dump(exclude={"function_call", "audio"}))

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = self._parse_args(fn_name, tool_call.function.arguments)
                logger.info(f"Tool call: {fn_name}({fn_args})")

                tool_fn = self._tool_map.get(fn_name)
                if not tool_fn:
                    result = {"error": f"Unknown tool: {fn_name}"}
                else:
                    try:
                        result = await tool_fn(**fn_args)
                    except Exception as e:
                        logger.error(f"Tool {fn_name} error: {e}")
                        result = {"error": str(e)}

                conversation.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str),
                })

        return conversation[1:]  # strip system prompt

    def _parse_args(self, fn_name: str, raw: str) -> dict:
        try:
            args = json.loads(raw)
            # Strip null-valued keys so tools use defaults
            return {k: v for k, v in args.items() if v is not None}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse args for {fn_name}: {raw}")
            return {}
