from __future__ import annotations

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage

from apps.agent.skills.booking.graph import human_confirmation_node


def _make_ai_with_book_tool(doctor_id="dr-susan-george", date="2026-07-29", time="10:30", phone="+919999999999"):
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "book_appointment",
            "args": {
                "doctor_id": doctor_id,
                "patient_phone": phone,
                "date": date,
                "time": time,
            },
            "id": "call_book_1",
            "type": "tool_call",
        }],
    )


class TestHumanConfirmationNode:
    def test_no_book_tool_returns_empty(self, base_state):
        msg = AIMessage(content="hello")
        state = {**base_state, "messages": [msg]}
        result = human_confirmation_node(state)
        assert result == {}

    def test_no_ai_message_returns_empty(self, base_state):
        state = {**base_state, "messages": []}
        result = human_confirmation_node(state)
        assert result == {}

    def test_ai_with_other_tool_only_returns_empty(self, base_state):
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "search_doctors", "args": {}, "id": "c1", "type": "tool_call"}],
        )
        state = {**base_state, "messages": [msg]}
        result = human_confirmation_node(state)
        assert result == {}

    def test_interrupt_called_with_booking_details(self, base_state):
        msg = _make_ai_with_book_tool()
        state = {**base_state, "messages": [msg]}

        with patch("apps.agent.skills.booking.graph.interrupt", return_value="yes") as mock_interrupt:
            result = human_confirmation_node(state)

            mock_interrupt.assert_called_once()
            interrupt_arg = mock_interrupt.call_args[0][0]
            assert "dr-susan-george" in interrupt_arg
            assert "2026-07-29" in interrupt_arg
            assert "10:30" in interrupt_arg
            assert "+919999999999" in interrupt_arg
            assert result["current_phase"] == "booking_confirmed"

    def test_interrupt_cancelled_returns_cancelled_phase(self, base_state):
        msg = _make_ai_with_book_tool()
        state = {**base_state, "messages": [msg]}

        with patch("apps.agent.skills.booking.graph.interrupt", return_value="no") as mock_interrupt:
            result = human_confirmation_node(state)

            assert result["current_phase"] == "booking_cancelled"

    def test_interrupt_empty_response_returns_cancelled(self, base_state):
        msg = _make_ai_with_book_tool()
        state = {**base_state, "messages": [msg]}

        with patch("apps.agent.skills.booking.graph.interrupt", return_value="") as mock_interrupt:
            result = human_confirmation_node(state)

            assert result["current_phase"] == "booking_cancelled"

    def test_interrupt_with_yes_variants(self, base_state):
        msg = _make_ai_with_book_tool()
        state = {**base_state, "messages": [msg]}

        for variant in ["y", "Y", "yes", "Yes", "YES", "yeah sure"]:
            with patch("apps.agent.skills.booking.graph.interrupt", return_value=variant):
                result = human_confirmation_node(state)
                assert result["current_phase"] == "booking_confirmed", f"Failed for '{variant}'"

    def test_interrupt_with_no_variants(self, base_state):
        msg = _make_ai_with_book_tool()
        state = {**base_state, "messages": [msg]}

        for variant in ["n", "N", "no", "No", "NO", "not now"]:
            with patch("apps.agent.skills.booking.graph.interrupt", return_value=variant):
                result = human_confirmation_node(state)
                assert result["current_phase"] == "booking_cancelled", f"Failed for '{variant}'"

    def test_later_messages_shadow_earlier_ones(self, base_state):
        early = AIMessage(
            content="",
            tool_calls=[{"name": "search_doctors", "args": {}, "id": "c1", "type": "tool_call"}],
        )
        late = _make_ai_with_book_tool()
        state = {**base_state, "messages": [early, late]}

        with patch("apps.agent.skills.booking.graph.interrupt", return_value="yes"):
            result = human_confirmation_node(state)
            assert result["current_phase"] == "booking_confirmed"
