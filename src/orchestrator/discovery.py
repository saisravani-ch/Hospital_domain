from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.knowledge_base.config import get_settings

settings = get_settings()

_SYSTEM = """You are a medical search planner. Given the user's query, extract structured search parameters for finding doctors.
Return ONLY a JSON object with these optional fields:
- "query" (str): full natural language query for vector search
- "specialization" (str or null): medical specialty mentioned
- "doctor_name" (str or null): specific doctor name if mentioned
- "language" (str or null): preferred language
- "min_experience" (int or null): minimum years of experience
- "tenant_id" (str or null): hospital branch filter

If user asks about availability too, include an "also_check_availability": true flag.
If no meaningful search params can be extracted, return {"query": ""}."""


@dataclass
class DiscoveryPlan:
    params: dict[str, Any] = field(default_factory=dict)
    check_availability: bool = False


async def _extract_search_params(llm, message: str) -> DiscoveryPlan:
    """Single LLM call to extract structured search parameters."""
    try:
        resp = await llm.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": message},
            ],
            max_tokens=300,
            temperature=0.0,
        )
        raw = resp.choices[0].message.content or ""
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
    except Exception as e:
        logger.warning(f"Discovery LLM parse error: {e}")
        return DiscoveryPlan(params={"query": message})

    plan = DiscoveryPlan(
        params={k: v for k, v in data.items() if v is not None and k != "also_check_availability"},
        check_availability=data.get("also_check_availability", False),
    )
    if not plan.params.get("query"):
        plan.params["query"] = message
    return plan


async def execute_discovery(
    llm,
    tool_map: dict[str, callable],
    message: str,
    tenant_id: str | None = None,
) -> str:
    """Discovery flow: plan → execute → synthesize. Returns response text."""
    plan = await _extract_search_params(llm, message)

    if not plan.params.get("query"):
        return "I can help you find a doctor. What kind of specialist are you looking for?"

    if tenant_id and "tenant_id" not in plan.params:
        plan.params["tenant_id"] = tenant_id

    search_fn = tool_map.get("search_doctors")
    if not search_fn:
        return "Search is unavailable right now."

    import time
    t0 = time.time()
    search_result = await search_fn(**plan.params)
    logger.info(f"Discovery search took {time.time()-t0:.2f}s, result keys: {list(search_result.keys())}")

    if "error" in search_result:
        return f"I'm sorry, I couldn't search for doctors: {search_result['error']}"

    doctors = search_result.get("doctors", [])
    logger.info(f"Discovery got {len(doctors)} doctors")

    context = _build_context(doctors)
    t1 = time.time()
    response = await _synthesize(llm, message, context)
    logger.info(f"Discovery synthesis took {time.time()-t1:.2f}s")
    return response


def _build_context(doctors: list[dict]) -> str:
    if not doctors:
        return "No matching doctors found."
    lines = [f"Found {len(doctors)} doctor(s):"]
    for i, d in enumerate(doctors[:5], 1):
        name = d.get("name") or d.get("doctor_name", "Unknown")
        spec = d.get("specializations", d.get("speciality", ""))
        if isinstance(spec, list):
            spec = ", ".join(spec)
        exp = d.get("experience_years", "")
        fee = d.get("consultation_fee", "")
        langs = d.get("languages", "")
        if isinstance(langs, list):
            langs = ", ".join(langs)
        lines.append(f"{i}. {name}")
        if spec:
            lines.append(f"   Specialization: {spec}")
        if exp:
            lines.append(f"   Experience: {exp} years")
        if fee:
            try:
                fee_num = int(str(fee).replace(",", "").replace("₹", ""))
                lines.append(f"   Fee: ₹{fee_num}")
            except (ValueError, TypeError):
                lines.append(f"   Fee: {fee}")
            lines.append(f"   Languages: {langs}")
    return "\n".join(lines)


async def _synthesize(llm, query: str, context: str) -> str:
    system = """You are a booking assistant for a hospital. The user is looking for a doctor.

Present the most relevant doctors clearly. Use this format per doctor:
- Name, Specialization, Experience, Fee, Languages

IMPORTANT: You can book appointments directly. End with:
  "Would you like me to book an appointment with any of these doctors? Just tell me which one and your preferred date and time." """
    try:
        resp = await llm.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"User query: {query}\n\nSearch results:\n{context}"},
            ],
            max_tokens=512,
            temperature=0.3,
        )
        return resp.choices[0].message.content or "Here are the doctors I found. Please review the suggestions above."
    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        return f"Here are the doctors I found:\n\n{context}"
