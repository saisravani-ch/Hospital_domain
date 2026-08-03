from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END

from apps.agent.skills.booking.graph import after_confirmation, should_continue


class TestShouldContinue:
    def test_empty_messages_returns_end(self, base_state):
        state = {**base_state, "messages": []}
        assert should_continue(state) == END

    def test_last_message_not_ai_returns_end(self, base_state):
        state = {**base_state, "messages": [HumanMessage(content="hello")]}
        assert should_continue(state) == END

    def test_ai_no_tool_calls_returns_end(self, base_state):
        state = {**base_state, "messages": [AIMessage(content="hello")]}
        assert should_continue(state) == END

    def test_ai_with_search_tool_returns_tools(self, base_state):
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "search_doctors", "args": {"query": "heart doctor"}, "id": "c1", "type": "tool_call"}],
        )
        state = {**base_state, "messages": [msg]}
        assert should_continue(state) == "tools"

    def test_ai_with_availability_tool_returns_tools(self, base_state):
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "check_availability", "args": {}, "id": "c1", "type": "tool_call"}],
        )
        state = {**base_state, "messages": [msg]}
        assert should_continue(state) == "tools"

    def test_ai_with_book_appointment_routes_to_human_confirmation(self, base_state):
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "book_appointment", "args": {"doctor_id": "dr-1"}, "id": "c1", "type": "tool_call"}],
        )
        state = {**base_state, "messages": [msg]}
        assert should_continue(state) == "human_confirmation"

    def test_book_appointment_takes_priority_over_other_tools(self, base_state):
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "search_doctors", "args": {}, "id": "c1", "type": "tool_call"},
                {"name": "book_appointment", "args": {}, "id": "c2", "type": "tool_call"},
            ],
        )
        state = {**base_state, "messages": [msg]}
        assert should_continue(state) == "human_confirmation"


class TestAfterConfirmation:
    def test_booking_confirmed_routes_to_tools(self, base_state):
        state = {**base_state, "current_phase": "booking_confirmed"}
        assert after_confirmation(state) == "tools"

    def test_booking_cancelled_routes_to_assistant(self, base_state):
        state = {**base_state, "current_phase": "booking_cancelled"}
        assert after_confirmation(state) == "assistant"

    def test_idle_routes_to_assistant(self, base_state):
        state = {**base_state, "current_phase": "idle"}
        assert after_confirmation(state) == "assistant"

    def test_done_routes_to_assistant(self, base_state):
        state = {**base_state, "current_phase": "done"}
        assert after_confirmation(state) == "assistant"
