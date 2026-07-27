from __future__ import annotations

from typing import Any

import openai
from loguru import logger

from src.knowledge_base.config import get_settings, get_tenant_config
from src.orchestrator.prompts import SYSTEM_PROMPT_TEMPLATE

settings = get_settings()
from src.orchestrator.router import classify, DISCOVERY, BOOKING, QA
from src.orchestrator.discovery import execute_discovery
from src.orchestrator.booking import execute_booking


class Agent:
    """Plan-then-Execute agent that routes user queries to the right handler."""

    def __init__(
        self,
        llm_client: openai.AsyncAzureOpenAI,
        tool_map: dict[str, callable],
    ):
        self._llm = llm_client
        self._tool_map = tool_map

    async def run(
        self,
        messages: list[dict],
        tenant_id: str | None = None,
        client_id: str | None = None,
        session_id: str = "",
        max_turns: int = 6,
    ) -> list[dict]:
        if self._llm is None:
            return [
                *messages,
                {"role": "assistant", "content": "Agent is not available (LLM not configured). Please set up Azure OpenAI credentials in .env and restart."},
            ]

        last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if not last_user_msg:
            return [*messages, {"role": "assistant", "content": "How can I help you today?"}]

        domain = classify(last_user_msg)
        logger.info(f"Domain: {domain} | message: {last_user_msg[:80]}")

        try:
            if domain == DISCOVERY:
                response = await execute_discovery(self._llm, self._tool_map, last_user_msg, tenant_id)
            elif domain == BOOKING:
                response = await execute_booking(
                    self._llm, self._tool_map, last_user_msg, session_id, tenant_id, client_id)
            else:  # QA
                response = await self._qa_response(last_user_msg, tenant_id)
        except Exception as e:
            logger.error(f"Handler error: {e}")
            response = "I'm sorry, I encountered an error. Please try again."

        return [*messages, {"role": "assistant", "content": response}]

    async def _qa_response(self, message: str, tenant_id: str | None = None) -> str:
        """Handle general questions, greetings, chit-chat."""
        tc = get_tenant_config(tenant_id)
        system = tc.format(SYSTEM_PROMPT_TEMPLATE)
        try:
            resp = await self._llm.chat.completions.create(
                model=settings.azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                max_tokens=300,
                temperature=0.7,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"QA error: {e}")
            return f"Hello! I'm the {tc.brand_name} assistant. I can help you find doctors and book appointments. How can I help?"
