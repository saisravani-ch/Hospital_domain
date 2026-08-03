from __future__ import annotations

import pytest

from tests.agent_scenarios import (
    ScenarioRunner,
    ScenarioResult,
    ALL_SCENARIOS,
    search_and_book_scenario,
    check_availability_scenario,
    cancel_appointment_scenario,
    reschedule_appointment_scenario,
    check_status_scenario,
    edge_case_no_results_scenario,
    booking_cancelled_at_confirmation_scenario,
    confused_user_scenario,
)

AGENT_URL = "http://localhost:8002"


@pytest.mark.asyncio
class TestAgentScenarioRunner:
    async def test_runner_initialization(self):
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            assert runner.agent_url == AGENT_URL
            assert runner.tenant_id == "glh-chn"
            assert runner.client_id == "gleneagles_001"

    async def test_run_single_scenario(self):
        scenario = check_availability_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert isinstance(result, ScenarioResult)
        assert result.scenario_name == "check_availability"
        assert len(result.turns) == 1

    async def test_run_search_and_book_scenario(self):
        scenario = search_and_book_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert result.scenario_name == "search_and_book"
        assert len(result.turns) == 3
        for turn in result.turns:
            assert turn.response is not None

    async def test_run_all_scenarios(self):
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            results = await runner.run_all(ALL_SCENARIOS)
        assert len(results) == len(ALL_SCENARIOS)
        for r in results:
            assert isinstance(r, ScenarioResult)
            assert r.scenario_name is not None

    async def test_pending_confirmation_detected(self):
        scenario = booking_cancelled_at_confirmation_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert any(t.expect_pending for t in result.turns)

    async def test_no_error_responses(self):
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            results = await runner.run_all(ALL_SCENARIOS)
        for r in results:
            for t in r.turns:
                assert t.status != "error", f"Turn {t.turn_index} in '{r.scenario_name}' returned error: {t.errors}"

    async def test_scenario_names_unique(self):
        names = [s.name for s in ALL_SCENARIOS]
        assert len(names) == len(set(names)), f"Duplicate scenario names: {names}"


@pytest.mark.asyncio
class TestSpecificScenarios:
    async def test_search_and_book_full_flow(self):
        scenario = search_and_book_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert result.overall_passed, (
            f"Search-and-book scenario failed: {[t.errors for t in result.turns if not t.passed]}"
        )

    async def test_check_availability_only(self):
        scenario = check_availability_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert result.overall_passed, (
            f"Availability check scenario failed: {[t.errors for t in result.turns if not t.passed]}"
        )

    async def test_cancel_appointment_flow(self):
        scenario = cancel_appointment_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert result.overall_passed, (
            f"Cancel appointment scenario failed: {[t.errors for t in result.turns if not t.passed]}"
        )

    async def test_reschedule_appointment_flow(self):
        scenario = reschedule_appointment_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert result.overall_passed, (
            f"Reschedule scenario failed: {[t.errors for t in result.turns if not t.passed]}"
        )

    async def test_check_appointment_status(self):
        scenario = check_status_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert result.overall_passed, (
            f"Check status scenario failed: {[t.errors for t in result.turns if not t.passed]}"
        )

    async def test_edge_case_no_results(self):
        scenario = edge_case_no_results_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert len(result.turns) >= 1

    async def test_booking_cancelled_at_confirmation(self):
        scenario = booking_cancelled_at_confirmation_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert len(result.turns) >= 1

    async def test_confused_user_scenario(self):
        scenario = confused_user_scenario()
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert len(result.turns) >= 1

    async def test_attender_persona(self):
        scenario = check_availability_scenario()
        assert scenario.persona == "attender"
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert len(result.turns) == 1

    async def test_existing_patient_persona(self):
        scenario = cancel_appointment_scenario()
        assert scenario.persona == "existing_patient"
        async with ScenarioRunner(agent_url=AGENT_URL) as runner:
            result = await runner.run_scenario(scenario)
        assert len(result.turns) >= 1