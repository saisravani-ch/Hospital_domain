from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from httpx import HTTPError, TimeoutException

from .personas import ALL_PERSONAS
from .scenarios import Scenario, Turn

DEFAULT_AGENT_URL = "http://localhost:8002"
DEFAULT_TENANT_ID = "glh-chn"
DEFAULT_CLIENT_ID = "gleneagles_001"
DEFAULT_TIMEOUT = 30


@dataclass
class TurnResult:
    turn_index: int
    user_message: str
    response: str
    status: str
    expect_pending: bool
    pending_received: bool
    passed: bool
    errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


@dataclass
class ScenarioResult:
    scenario_name: str
    description: str
    persona: str
    turns: list[TurnResult] = field(default_factory=list)
    overall_passed: bool = True
    total_time_ms: float = 0.0

    @property
    def failed_turns(self) -> list[TurnResult]:
        return [t for t in self.turns if not t.passed]

    @property
    def error_messages(self) -> list[str]:
        msgs = []
        for t in self.turns:
            msgs.extend(t.errors)
        return msgs


class ScenarioRunner:
    def __init__(
        self,
        agent_url: str = DEFAULT_AGENT_URL,
        tenant_id: str = DEFAULT_TENANT_ID,
        client_id: str = DEFAULT_CLIENT_ID,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.agent_url = agent_url.rstrip("/")
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> ScenarioRunner:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def run_scenario(self, scenario: Scenario) -> ScenarioResult:
        start = time.monotonic()
        result = ScenarioResult(
            scenario_name=scenario.name,
            description=scenario.description,
            persona=scenario.persona,
        )
        session_id = f"test_{scenario.name}_{int(time.time())}"
        pending_confirmation = False

        for idx, turn in enumerate(scenario.turns):
            turn_start = time.monotonic()

            if pending_confirmation and not turn.expect_pending_confirmation:
                if turn.confirm_on_pending:
                    user_msg = "yes"
                else:
                    user_msg = "no"
            else:
                user_msg = turn.user_message

            try:
                resp = await self._post_chat(
                    session_id=session_id,
                    message=user_msg,
                    tenant_id=scenario.tenant_id or self.tenant_id,
                    client_id=scenario.client_id or self.client_id,
                )
            except (HTTPError, TimeoutException, ConnectionError) as e:
                elapsed = (time.monotonic() - turn_start) * 1000
                tr = TurnResult(
                    turn_index=idx,
                    user_message=user_msg,
                    response="",
                    status="error",
                    expect_pending=turn.expect_pending_confirmation,
                    pending_received=False,
                    passed=False,
                    errors=[f"HTTP error: {e}"],
                    elapsed_ms=elapsed,
                )
                result.turns.append(tr)
                result.overall_passed = False
                continue

            if "error" in resp and resp["error"]:
                elapsed = (time.monotonic() - turn_start) * 1000
                tr = TurnResult(
                    turn_index=idx,
                    user_message=user_msg,
                    response=str(resp),
                    status="error",
                    expect_pending=turn.expect_pending_confirmation,
                    pending_received=False,
                    passed=False,
                    errors=[f"API error response: {resp}"],
                    elapsed_ms=elapsed,
                )
                result.turns.append(tr)
                result.overall_passed = False
                continue

            response_text = resp.get("response", "")
            status = resp.get("status", "completed")
            pending_received = status == "pending_confirmation"
            elapsed = (time.monotonic() - turn_start) * 1000

            errors: list[str] = []

            if turn.expect_pending_confirmation and not pending_received:
                errors.append(f"Expected pending_confirmation but got status '{status}'")
            if not turn.expect_pending_confirmation and pending_received:
                errors.append(f"Did not expect pending_confirmation but got status '{status}'")
            if turn.expect_pending_confirmation and pending_received:
                pending_confirmation = True
            elif not turn.expect_pending_confirmation:
                pending_confirmation = False

            if not turn.expect_error:
                for keyword in turn.expected_in_response:
                    if keyword.lower() not in response_text.lower():
                        errors.append(f"Expected '{keyword}' in response but not found")
                for keyword in turn.expected_not_in_response:
                    if keyword.lower() in response_text.lower():
                        errors.append(f"Expected '{keyword}' NOT in response but found it")
            else:
                if not response_text:
                    errors.append("Expected error response but got empty response")

            passed = len(errors) == 0
            if not passed:
                result.overall_passed = False

            tr = TurnResult(
                turn_index=idx,
                user_message=user_msg,
                response=response_text,
                status=status,
                expect_pending=turn.expect_pending_confirmation,
                pending_received=pending_received,
                passed=passed,
                errors=errors,
                elapsed_ms=elapsed,
            )
            result.turns.append(tr)

            if pending_received and not turn.expect_pending_confirmation:
                break

        result.total_time_ms = (time.monotonic() - start) * 1000
        return result

    async def run_all(self, scenarios: list[Scenario]) -> list[ScenarioResult]:
        results = []
        for scenario in scenarios:
            r = await self.run_scenario(scenario)
            results.append(r)
        return results

    async def _post_chat(self, session_id: str, message: str, tenant_id: str, client_id: str) -> dict[str, Any]:
        url = f"{self.agent_url}/chat"
        payload: dict[str, Any] = {
            "message": message,
            "session_id": session_id,
            "client_id": client_id,
        }
        if tenant_id:
            payload["tenant_id"] = tenant_id

        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


async def run_scenario_inline(scenario: Scenario, agent_url: str = DEFAULT_AGENT_URL) -> ScenarioResult:
    async with ScenarioRunner(agent_url=agent_url) as runner:
        return await runner.run_scenario(scenario)


async def run_all_scenarios(agent_url: str = DEFAULT_AGENT_URL) -> list[ScenarioResult]:
    async with ScenarioRunner(agent_url=agent_url) as runner:
        return await runner.run_all(ALL_SCENARIOS)