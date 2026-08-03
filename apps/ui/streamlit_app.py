"""Streamlit interface for testing the Hospital System."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any
from urllib import request as urllib_req
from urllib.error import URLError

import streamlit as st

try:
    from tests.agent_scenarios import (
        ALL_SCENARIOS,
        Scenario,
        ScenarioResult,
        Turn,
        TurnResult,
    )
    HAS_TEST_AGENT = True
except ImportError:
    HAS_TEST_AGENT = False

st.set_page_config(
    page_title="Hospital System Tester",
    page_icon="🏥",
    layout="wide",
)

# ── Server URLs ─────────────────────────────────────────────────────────────────
KB_URL = st.sidebar.text_input("Knowledge Base URL", value="http://localhost:8000")
WORKFLOW_URL = st.sidebar.text_input("Workflows URL", value="http://localhost:8001")
AGENT_URL = st.sidebar.text_input("Agent URL", value="http://localhost:8002")

# ── HTTP helpers ─────────────────────────────────────────────────────────────────


def get(url: str) -> dict[str, Any]:
    """Synchronous GET using urllib (stdlib, no compat issues)."""
    try:
        with urllib_req.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except URLError as e:
        return {"error": f"Cannot connect: {url} — {e.reason}"}
    except Exception as e:
        return {"error": f"GET {url} failed: {e}"}


def post(url: str, json_data: dict) -> dict[str, Any]:
    """Synchronous POST with JSON body using urllib."""
    try:
        data = json.dumps(json_data).encode()
        req = urllib_req.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib_req.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except URLError as e:
        return {"error": f"Cannot connect: {url} — {e.reason}"}
    except Exception as e:
        return {"error": f"POST {url} failed: {e}"}


# ── Tabs ─────────────────────────────────────────────────────────────────────────

tab_chat, tab_doctors, tab_appointments, tab_health, tab_test = st.tabs(
    ["💬 Chat", "🔍 Doctors", "📅 Appointments", "❤️ Health", "🧪 Test Agent"]
)

# ── Tab 1: Chat ──────────────────────────────────────────────────────────────────

with tab_chat:
    st.header("Conversation Agent")

    if "session_id" not in st.session_state:
        st.session_state.session_id = f"test_{uuid.uuid4().hex[:8]}"
    if "messages" not in st.session_state:
        st.session_state.messages = []

    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.text_input("Session ID", value=st.session_state.session_id, key="session_input",
                       on_change=lambda: setattr(st.session_state, "session_id", st.session_state.session_input))
    with col2:
        st.text_input("Tenant ID (branch)", value="", key="tenant_input",
                       placeholder="branch tenant id (e.g. glh-chn)")
    with col3:
        st.text_input("Client ID (hospital group)", value="gleneagles_001", key="client_input",
                       placeholder="hospital group client id (e.g. gleneagles_001)")
    with col4:
        if st.button("🔄 New Session"):
            st.session_state.session_id = f"test_{uuid.uuid4().hex[:8]}"
            st.session_state.messages = []
            st.session_state.pending_confirmation = False
            st.rerun()

    if "pending_confirmation" not in st.session_state:
        st.session_state.pending_confirmation = False

    def _send_message(text: str) -> None:
        """Send a message to the agent and append the response to session state."""
        st.session_state.messages.append({"role": "user", "content": text})
        with st.spinner("Thinking..."):
            payload = {
                "message": text,
                "session_id": st.session_state.session_id,
            }
            if st.session_state.tenant_input:
                payload["tenant_id"] = st.session_state.tenant_input
            payload["client_id"] = st.session_state.client_input or "gleneagles_001"

            url = f"{AGENT_URL}/chat"
            result = post(url, payload)
            if "error" in result:
                response = f"I'm sorry, I couldn't reach the agent server.\n\n> {result['error']}"
            else:
                response = result.get("response", str(result))

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.pending_confirmation = result.get("status") == "pending_confirmation"
        st.rerun()

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Confirmation buttons (shown when graph is paused for booking approval)
    if st.session_state.pending_confirmation:
        st.warning("🛑 The agent is waiting for your confirmation to book.")
        conf_cols = st.columns([1, 1, 6])
        with conf_cols[0]:
            if st.button("✅ Yes, confirm booking", type="primary", use_container_width=True):
                st.session_state.pending_confirmation = False
                _send_message("yes")
        with conf_cols[1]:
            if st.button("❌ No, cancel", use_container_width=True):
                st.session_state.pending_confirmation = False
                _send_message("no")

    # Chat input (disabled while waiting for confirmation — use buttons instead)
    chat_disabled = st.session_state.pending_confirmation
    if prompt := st.chat_input("Ask about doctors, book appointments...", disabled=chat_disabled):
        _send_message(prompt)

    # Quick action buttons (hidden during confirmation)
    if not st.session_state.pending_confirmation:
        st.divider()
        st.caption("Quick test queries")
        qa_cols = st.columns(2)
        quick_queries = [
            "I need a heart doctor in chennai",
            "book an appointment with Dr. Guru Prasad S",
            "Find a Tamil-speaking doctor",
            "Orthopaedic surgeon with 10+ years experience",
            "Show me available slots for today",
        ]
        for i, q in enumerate(quick_queries):
            with qa_cols[i % 2]:
                if st.button(q, key=f"qq_{i}", use_container_width=True):
                    _send_message(q)

# ── Tab 2: Doctors ───────────────────────────────────────────────────────────────

with tab_doctors:
    st.header("Doctor Knowledge Base Search")

    search_type = st.radio(
        "Search type",
        ["GraphRAG (vector + graph)", "Semantic (vector only)", "By Specialization", "Doctor Profile"],
        horizontal=True,
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Search query", placeholder="e.g. heart specialist Tamil speaking" if "GraphRAG" in search_type or "Semantic" in search_type
                              else "e.g. Cardiology" if "Specialization" in search_type
                              else "e.g. dr-j-ajith-kumar-chn")
    with col2:
        n_results = st.number_input("Max results", min_value=1, max_value=20, value=6)
        tenant_search = st.text_input("Tenant ID (optional)", placeholder="e.g. glh-chn")

    if st.button("🔍 Search", type="primary", use_container_width=True) and query:
        with st.spinner("Searching..."):
            if "GraphRAG" in search_type:
                url = f"{KB_URL}/search/doctors?q={query}&n={n_results}"
                if tenant_search:
                    url += f"&tenant_id={tenant_search}"
                result = get(url)

            elif "Semantic" in search_type:
                url = f"{KB_URL}/search/doctors/semantic?q={query}&n={n_results}"
                result = get(url)

            elif "Specialization" in search_type:
                url = f"{KB_URL}/search/doctors/by-specialization?specialization={query}&n={n_results}"
                result = get(url)

            elif "Profile" in search_type:
                url = f"{KB_URL}/doctors/{query}"
                result = get(url)

            if isinstance(result, dict) and "error" not in result:
                if "Profile" in search_type:
                    st.json(result)
                elif "Specialization" in search_type:
                    doctors = result.get("doctors", [])
                    st.success(f"Found {len(doctors)} doctors")
                    for doc in doctors:
                        with st.expander(f"{doc.get('name', 'Unknown')} — {doc.get('designation', '')}"):
                            st.json(doc)
                elif "Semantic" in search_type:
                    results = result.get("results", [])
                    st.success(f"Found {len(results)} results")
                    for r in results:
                        with st.expander(r.get("metadata", {}).get("name", r.get("id", "Unknown"))):
                            st.markdown(f"**Score:** {r.get('score', 0):.3f}")
                            st.markdown(f"**Text:** {r.get('text', '')[:500]}")
                            st.json(r.get("metadata", {}))
                else:  # GraphRAG
                    doctors = result.get("doctors", [])
                    ai_response = result.get("ai_response", "")
                    st.success(f"Found {len(doctors)} doctors (intent: {result.get('intent', 'N/A')})")
                    if ai_response:
                        st.info(ai_response)
                    for doc in doctors:
                        with st.expander(f"{doc.get('name', 'Unknown')} — {doc.get('designation', '')}"):
                            cols = st.columns(2)
                            with cols[0]:
                                st.markdown(f"**Specializations:** {doc.get('specializations', 'N/A')}")
                                st.markdown(f"**Experience:** {doc.get('experience_years', 'N/A')} years")
                                st.markdown(f"**Fee:** ₹{doc.get('consultation_fee', 'N/A')}")
                            with cols[1]:
                                st.markdown(f"**Languages:** {doc.get('languages', 'N/A')}")
                                st.markdown(f"**Hospital:** {doc.get('hospitals', doc.get('hospital_ids', 'N/A'))}")
                            bl = result.get("booking_links", [])
                            if bl:
                                st.markdown(f"🔗 [Book]({bl[0].get('booking_url', '#')})")
            else:
                error_msg = result.get("error", str(result)) if isinstance(result, dict) else str(result)
                st.error(f"Search failed: {error_msg}")

# ── Tab 3: Appointments ─────────────────────────────────────────────────────────

with tab_appointments:
    st.header("Appointment Workflows")

    apt_tab_avail, apt_tab_book, apt_tab_resched, apt_tab_cancel = st.tabs(
        ["Check Availability", "Book", "Reschedule", "Cancel"]
    )

    with apt_tab_avail:
        st.subheader("Check Available Slots")
        col1, col2, col3 = st.columns(3)
        with col1:
            doc_id = st.text_input("Doctor ID", key="avail_doc", placeholder="dr-...")
        with col2:
            date_str = st.date_input("Date", key="avail_date")
        with col3:
            client_id = st.text_input("Client ID", key="avail_client", placeholder="e.g. acme_001")

        if st.button("🔍 Check Availability", type="primary", key="btn_avail") and doc_id:
            with st.spinner("Checking..."):
                url = f"{WORKFLOW_URL}/appointments/availability?doctor_id={doc_id}&date={date_str}&client_id={client_id}"
                result = get(url)
                if isinstance(result, dict) and "error" not in result:
                    slots = result.get("slots", [])
                    st.success(f"{len(slots)} slot(s) available on {result.get('date')}")
                    for s in slots:
                        st.markdown(f"🕐 `{s['time']}` ({s.get('period', '')}) — Slot ID: {s['slot_id']}")
                else:
                    err = result.get("error", str(result)) if isinstance(result, dict) else str(result)
                    st.error(err)

    with apt_tab_book:
        st.subheader("Book Appointment")
        col1, col2 = st.columns(2)
        with col1:
            b_doc = st.text_input("Doctor ID", key="book_doc", placeholder="dr-...")
            b_phone = st.text_input("Patient Phone", key="book_phone", placeholder="e.g. +919999999999")
            b_date = st.date_input("Date", key="book_date")
        with col2:
            b_time = st.text_input("Time", key="book_time", placeholder="10:30")
            b_client = st.text_input("Client ID", key="book_client", placeholder="e.g. acme_001")
            b_notes = st.text_input("Notes (optional)", key="book_notes", placeholder="Reason for visit")

        if st.button("📅 Book Appointment", type="primary", key="btn_book") and b_doc and b_phone and b_date and b_time:
            with st.spinner("Booking..."):
                payload = {
                    "client_id": b_client,
                    "patient_phone": b_phone,
                    "doctor_id": b_doc,
                    "date": str(b_date),
                    "time": b_time,
                    "notes": b_notes or None,
                }
                result = post(f"{WORKFLOW_URL}/appointments/book", payload)
                if isinstance(result, dict) and "error" not in result:
                    st.success(f"✅ Booked! Appointment ID: `{result.get('appointment_id')}`")
                    st.json(result)
                else:
                    err = result.get("error", str(result)) if isinstance(result, dict) else str(result)
                    st.error(err)

    with apt_tab_resched:
        st.subheader("Reschedule Appointment")
        col1, col2 = st.columns(2)
        with col1:
            r_id = st.text_input("Appointment ID", key="resched_id", placeholder="apt_...")
            r_date = st.date_input("New Date", key="resched_date")
        with col2:
            r_time = st.text_input("New Time", key="resched_time", placeholder="14:00")
            r_client = st.text_input("Client ID", key="resched_client", placeholder="e.g. acme_001")

        if st.button("🔄 Reschedule", type="primary", key="btn_resched") and r_id and r_date and r_time:
            with st.spinner("Rescheduling..."):
                payload = {
                    "appointment_id": r_id,
                    "new_date": str(r_date),
                    "new_time": r_time,
                    "client_id": r_client,
                }
                result = post(f"{WORKFLOW_URL}/appointments/reschedule", payload)
                if isinstance(result, dict) and "error" not in result:
                    st.success(f"✅ Rescheduled! New: {result.get('new_date')} at {result.get('new_time')}")
                    st.json(result)
                else:
                    err = result.get("error", str(result)) if isinstance(result, dict) else str(result)
                    st.error(err)

    with apt_tab_cancel:
        st.subheader("Cancel Appointment")
        col1, col2 = st.columns([2, 1])
        with col1:
            c_id = st.text_input("Appointment ID", key="cancel_id", placeholder="apt_...")
        with col2:
            c_client = st.text_input("Client ID", key="cancel_client", placeholder="e.g. acme_001")

        if st.button("❌ Cancel Appointment", type="primary", key="btn_cancel") and c_id:
            with st.spinner("Cancelling..."):
                payload = {
                    "appointment_id": c_id,
                    "client_id": c_client,
                }
                result = post(f"{WORKFLOW_URL}/appointments/cancel", payload)
                if isinstance(result, dict) and "error" not in result:
                    st.success(f"✅ Cancelled! Status: {result.get('status')}")
                    st.json(result)
                else:
                    err = result.get("error", str(result)) if isinstance(result, dict) else str(result)
                    st.error(err)

# ── Tab 4: Health ────────────────────────────────────────────────────────────────

with tab_health:
    st.header("Server Health Check")

    servers = [
        ("🧠 Knowledge Base", KB_URL, "/health"),
        ("📋 Workflows", WORKFLOW_URL, "/health"),
        ("🤖 Agent (Orchestrator)", AGENT_URL, "/health"),
    ]

    cols = st.columns(3)
    for i, (name, base, path) in enumerate(servers):
        with cols[i]:
            st.subheader(name)
            result = get(f"{base}{path}")
            if isinstance(result, dict) and result.get("status") == "ok":
                st.success("✅ Online")
            else:
                st.error(f"❌ Offline — {result.get('error', str(result)) if isinstance(result, dict) else result}")
            st.caption(f"{base}")

    st.divider()
    st.subheader("Raw API Test")
    test_endpoint = st.text_input("Endpoint path", value="/", key="raw_endpoint")
    test_server = st.selectbox("Server", [s[0] for s in servers], key="raw_server")
    server_map = dict((s[0], s[1]) for s in servers)

    if st.button("Send Request", key="btn_raw"):
        url = f"{server_map[test_server]}{test_endpoint}"
        with st.spinner(f"GET {url}"):
            result = get(url)
            if isinstance(result, dict):
                st.json(result)
            else:
                st.text(str(result))

st.sidebar.divider()
st.sidebar.markdown("### How to use")
st.sidebar.markdown(
    """
1. Start the three servers (see `AGENTS.md`)
2. Update URLs in the sidebar if needed
3. Use the **Chat** tab to test the conversation agent
4. Use **Doctors** / **Appointments** to test endpoints directly
5. Use **🧪 Test Agent** to run automated scenarios

```bash
# Start all three (separate terminals)
uvicorn src.knowledge_base.api.main:app --port 8000
uvicorn src.workflows.main:app --port 8001
uvicorn src.orchestrator.main:app --port 8002

# Then run this app
streamlit run streamlit_app.py
```
"""
)


# ══════════════════════════════════════════════════════════════════


def _run_scenario_sync(
    scenario: Scenario, agent_url: str
) -> ScenarioResult:
    """Synchronous scenario runner using urllib (same as Streamlit app)."""
    session_id = f"test_{scenario.name}_{int(time.time())}"
    results = ScenarioResult(
        scenario_name=scenario.name,
        description=scenario.description,
        persona=scenario.persona,
    )
    pending_confirmation = False
    start = time.monotonic()

    for idx, turn in enumerate(scenario.turns):
        turn_start = time.monotonic()

        if pending_confirmation and not turn.expect_pending_confirmation:
            user_msg = "yes" if turn.confirm_on_pending else "no"
        else:
            user_msg = turn.user_message

        payload = {
            "message": user_msg,
            "session_id": session_id,
            "client_id": scenario.client_id,
        }
        if scenario.tenant_id:
            payload["tenant_id"] = scenario.tenant_id

        try:
            data = json.dumps(payload).encode()
            req = urllib_req.Request(
                f"{agent_url.rstrip('/')}/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib_req.urlopen(req, timeout=30) as resp:
                api_result = json.loads(resp.read().decode())
        except Exception as e:
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
            results.turns.append(tr)
            results.overall_passed = False
            continue

        if "error" in api_result and api_result["error"]:
            elapsed = (time.monotonic() - turn_start) * 1000
            tr = TurnResult(
                turn_index=idx,
                user_message=user_msg,
                response=str(api_result),
                status="error",
                expect_pending=turn.expect_pending_confirmation,
                pending_received=False,
                passed=False,
                errors=[f"API error: {api_result}"],
                elapsed_ms=elapsed,
            )
            results.turns.append(tr)
            results.overall_passed = False
            continue

        response_text = api_result.get("response", "")
        status = api_result.get("status", "completed")
        pending_received = status == "pending_confirmation"
        elapsed = (time.monotonic() - turn_start) * 1000

        errors: list[str] = []

        if turn.expect_pending_confirmation and not pending_received:
            errors.append(
                f"Expected pending_confirmation but got status '{status}'"
            )
        if (
            not turn.expect_pending_confirmation and pending_received
        ):
            errors.append(
                f"Did not expect pending_confirmation but got status '{status}'"
            )

        if turn.expect_pending_confirmation and pending_received:
            pending_confirmation = True
        elif not turn.expect_pending_confirmation:
            pending_confirmation = False

        if not turn.expect_error:
            for keyword in turn.expected_in_response:
                if keyword.lower() not in response_text.lower():
                    errors.append(
                        f"Expected '{keyword}' in response but not found"
                    )
            for keyword in turn.expected_not_in_response:
                if keyword.lower() in response_text.lower():
                    errors.append(
                        f"Expected '{keyword}' NOT in response but found it"
                    )

        passed = len(errors) == 0
        if not passed:
            results.overall_passed = False

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
        results.turns.append(tr)

        if pending_received and not turn.expect_pending_confirmation:
            break

    results.total_time_ms = (time.monotonic() - start) * 1000
    return results


# ══════════════════════════════════════════════════════════════════
# 🧪 Test Agent Tab (inserted after the sidebar so it appears last)
# ══════════════════════════════════════════════════════════════════

with tab_test:
    st.header("🧪 Automated Test Agent")

    if not HAS_TEST_AGENT:
        st.warning(
            "The test agent module could not be imported. Make sure the "
            "`tests/agent_scenarios/` directory exists and the agent service "
            "is running on port 8002."
        )
        st.stop()

    st.markdown(
        "Run automated multi-turn conversation scenarios against the agent, "
        "simulating different user personas. Results show pass/fail per turn "
        "with timing and error details."
    )

    # ── Controls ─────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_scenario = st.selectbox(
            "Scenario",
            options=ALL_SCENARIOS,
            format_func=lambda s: f"{s.name}: {s.description[:60]}...",
        )
    with col2:
        st.markdown("**Persona**")
        persona_label = {
            "patient": "😊 Patient",
            "attender": "👨‍⚕️ Attender",
            "confused": "😕 Confused",
            "existing_patient": "🔁 Existing Patient",
        }
        persona = selected_scenario.persona_obj
        st.text_input("Role", value=persona.role, disabled=True, key="test_persona_role")
    with col3:
        st.markdown("**Agent URL**")
        test_agent_url = st.text_input("URL", value="http://localhost:8002", key="test_agent_url")

    # ── Run button ──────────────────────────────────────────────
    if st.button("▶ Run Scenario", type="primary", use_container_width=True):
        if not test_agent_url:
            st.error("Agent URL is required.")
            st.stop()

        results = _run_scenario_sync(selected_scenario, test_agent_url)

        # Summary
        total = len(results.turns)
        passed = sum(1 for t in results.turns if t.passed)
        failed = total - passed

        if results.overall_passed:
            st.success(
                f"✅ All {total} turns passed in {results.total_time_ms:.0f}ms"
            )
        else:
            st.error(
                f"❌ {failed}/{total} turns failed in {results.total_time_ms:.0f}ms"
            )

        st.divider()

        # Per-turn results
        for i, turn in enumerate(results.turns):
            status_icon = "✅" if turn.passed else "❌"
            with st.expander(
                f"{status_icon} Turn {i+1}: {turn.user_message[:80]}",
                expanded=not turn.passed,
            ):
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    st.markdown("**User:**")
                    st.code(turn.user_message, language="text")
                    st.markdown("**Status:** " + turn.status)
                    st.markdown(f"**Time:** {turn.elapsed_ms:.0f}ms")
                    if turn.expect_pending and not turn.pending_received:
                        st.warning(
                            f"⚠️ Expected pending_confirmation but got '{turn.status}'"
                        )
                    if turn.pending_received:
                        st.info("🔒 Graph paused for confirmation")

                with col_b:
                    st.markdown("**Agent Response:**")
                    st.write(turn.response if turn.response else "(empty)")

                if turn.errors:
                    st.markdown("**Errors:**")
                    for err in turn.errors:
                        st.error(err)

                if not turn.passed and turn.response:
                    st.markdown("**Full Response:**")
                    st.code(turn.response[:500])

