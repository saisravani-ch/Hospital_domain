# AGENTS.md — Hospital System

## Run commands (CWD = project root)

Two of the three services require Neo4j + ChromaDB + Azure OpenAI. The agent and UI can start without them (degraded responses).

| App | Port | Command |
|---|---|---|
| Knowledge Base (KB) | 8000 | `uvicorn apps.kb.api.main:app --reload --port 8000` |
| Workflows | 8001 | `uvicorn apps.workflows.main:app --reload --port 8001` |
| Agent (orchestrator) | 8002 | `uvicorn apps.agent.main:app --reload --port 8002` |
| Streamlit UI | 8501 | `streamlit run apps\ui\streamlit_app.py` |

`.\run_all.ps1` launches all four in separate terminal windows.

No `setup.py`/`pyproject.toml` — `pip install -r requirements.txt` is the only install.

## Two config systems, one env file

- **KB** (`apps/kb/config.py`): `pydantic-settings` reads `.env` from project root
- **Workflows** (`apps/workflows/config.py`): raw `os.getenv()` + **hardcoded CLIENTS dict** — `client_id` must be in `CLIENTS` or you get `ValueError`. Only `"gleneagles_001"` exists by default.
- **Orchestrator** imports KB's `get_settings()` — same env file
- **Tools** (`apps/agent/tools/graphrag_tool.py`, `apps/agent/tools/workflow_tool.py`): read `KB_URL` / `WF_URL` from env (default `http://localhost:8000` / `8001`)

## Architecture: LangGraph stateful agent (Command pattern)

```
User → POST /chat → CompiledStateGraph.ainvoke()
  └── assistant_node (LLM + 6 tool bindings)
       ├── tool_calls? → human_confirmation_node (interrupt for booking)
       │                     └── confirmed? → tool_node → assistant
       │                     └── cancelled? → assistant
       ├── tool_calls (other) → tool_node → assistant
       └── no tool_calls → END
```

The orchestrator (`graph.py`) is a `StateGraph` with 3 nodes:
- **assistant** — LLM with tool bindings, decides what to do
- **tools** — `ToolNode` runs all tool calls concurrently via `asyncio.gather`. Each tool returns a `Command(update=...)` that directly writes typed state fields (`search_results`, `available_slots`, `booking_result`, `current_phase`, etc.) — no separate `state_extractor` node needed
- **human_confirmation** — `interrupt()` pauses execution before `book_appointment`, waits for user confirmation

State persists across conversation turns via `MemorySaver` checkpointer (thread_id = session_id). Tool results, doctor IDs, and booking context survive between turns — no re-derivation needed.

The `status` field in `ChatResponse` tells the UI whether the graph completed or is waiting for confirmation (`"pending_confirmation"`).

### Key files:
- `apps/agent/state.py` — `HospitalAgentState` TypedDict with typed fields + `add_messages` reducer
- `apps/agent/skills/shared/doctor_tools.py` — `@tool` wrappers for doctor search, shared by BOTH skills (no skill-to-skill imports)
- `apps/agent/skills/search/tools.py` — thin re-export of the shared doctor tools
- `apps/agent/skills/booking/tools.py` — `@tool` wrappers around workflow HTTP calls, each returning `Command(update=...)` to emit state fields + `ToolMessage` directly. Injects `tenant_id`/`client_id` via `InjectedState`, and `tool_call_id` via `ToolRuntime`
- `apps/agent/graph.py` — `StateGraph` with `assistant` → `tools` → `assistant` loop, `human_confirmation` interrupt for booking

Skills are decoupled: no skill imports from another skill; tools never call other tools — the LLM orchestrates by calling tools in sequence.

Only `langgraph` + `langchain-openai` added to deps. No full LangChain agent frameworks.

## Tool HTTP boundaries

Tools in `apps/agent/tools/` call downstream services via `httpx.AsyncClient`:
- `search_doctors` / `get_doctor_info` → `KB_BASE/search/retrieve` (POST) / `KB_BASE/doctors/{id}` (GET)
- `check_availability` / `book_appointment` / `reschedule` / `cancel` → `WF_BASE/appointments/*`

## KB service endpoints

| Endpoint | Purpose |
|---|---|
| `POST /search/retrieve` | **Retrieval-only** — vector + graph search, **no LLM** on KB side. Used by orchestrator search_doctors tool. |
| `POST /appointment/assist` | Old full-stack endpoint — intent classify + retrieve + synthesize (4 LLM calls). Kept for backward compat. |
| `GET /search/doctors?q=...` | GraphRAG search using `engine.query()` (full stack). |
| `GET /doctors/{id}` | Doctor profile from Neo4j via `Neo4jQueryEngine.get_doctor_context()`. |

## No MongoDB at runtime

`lib/memory/conversation_memory.py` stores conversations in a plain `dict` in memory. The `mongodb.py` module exists but is unused. No MongoDB instance needed. State persistence is now handled by LangGraph's `MemorySaver` checkpointer (in-memory, same limitation — restart loses state).

## Tests

`pytest` and `pytest-asyncio` are in `requirements.txt`. Tests are in `tests/`:
- `test_full_flow.py` — multi-turn conversation flows (search, availability, booking with confirmation, cancellation)
- `test_routing.py` — graph conditional edges (`should_continue`, `after_confirmation`)
- `test_human_confirmation.py` — interrupt behavior, yes/no confirmation variants

Mock tools return `Command(update=...)` to simulate the real tools' state emission pattern.

### MergingToolNode

`graph.py` uses `MergingToolNode(ToolNode)` — overrides `_run_one()` to merge multiple `Command.update` dicts from concurrent tool calls into a single `Command`, avoiding `InvalidUpdateError` on `LastValue` channels. Relevant when multiple `check_availability` calls run simultaneously via `asyncio.gather`.

## Observability: LangSmith

`LANGCHAIN_TRACING_V2=true` in `.env` enables LangSmith tracing via the `LANGCHAIN_API_KEY`. No Langfuse — removed due to hard S3 dependency in v3.

## Data pipeline (order matters)

1. **SQLite** (`apps/kb/db/`) — hospitals, doctors, schedules, time_slots
2. **Neo4j** (`apps/kb/graph/`) — Doctor/Hospital/PracticesAt/SpecializesIn/Speaks nodes/edges
3. **ChromaDB** (`apps/kb/rag/`) — vector embeddings via `all-MiniLM-L6-v2`

Expects `data/raw/` and `data/processed/` at project root. No sample data committed.

`neo4j_schema.cypher` is a **reference file** — `Neo4jEngine.apply_schema()` runs a different (smaller) set of constraints.

### Ingestion from Excel

`doctors_data_enriched.xlsx` at project root can be loaded into all three stores via:

```cmd
python ingest_doctors.py
```

This script reads the Excel file and upserts into:
1. **SQLite** — hospitals + doctors tables (via SQLAlchemy ORM `Doctor`/`Hospital` models)
2. **Neo4j** — clears existing graph, recreates schema, loads Doctor/Hospital/Specialization/Language nodes and edges
3. **ChromaDB** — upserts doctor profile text chunks with embeddings

The Excel columns map to the `Doctor` model fields. `tenant_id` in the Excel scopes which hospital branch each doctor belongs to. `location_id` is derived from `tenants.json` via `TENANT_META` in `lib/config.py`.

## Multi-tenant

Two distinct IDs, never interchangeable:

- **tenant_id** — hospital **branch** (e.g. `glh-chn`); scopes KB search (Chroma/Neo4j filters) + branding. `TENANT_META` in `lib/config.py` maps 7 tenant IDs → location IDs
- **client_id** — hospital **group** (e.g. `gleneagles_001`); scopes booking/workflow endpoints. `TENANT_CLIENTS` maps each branch → its client; `resolve_booking_client_id()` in `lib/config.py` must be applied before any workflow call (agent does this in `main.py` + `assistant_node`)

- `TenantConfig` branding loaded from DB `hospitals` table at runtime via `get_tenant_config_from_db()`
- Fallback to `Settings` fields for currency/names/booking URL
- `client_id` is required by workflow endpoints — maps to `CLIENTS` dict in `apps/workflows/config.py` (hospital-group keys only, never branch ids)

## streamlit_app.py quirks

- Uses **urllib** (sync), not httpx — all requests block the UI
- MUST call `st.rerun()` after appending assistant message (already done — don't remove it)
- Sidebar text inputs for all 3 service URLs with default `localhost:port` values

## Test Agent (`tests/agent_scenarios/`)

A standalone test agent system that simulates real user personas interacting with the agent's `/chat` API endpoint — the same endpoint the Streamlit UI uses. Completely separate from application code.

### Structure

```
tests/agent_scenarios/
├── __init__.py          # Public API exports
├── personas.py          # User personas (Patient, Attender, ConfusedUser, ExistingPatient)
├── scenarios.py         # Scenario definitions (multi-turn conversation sequences)
├── runner.py            # Async ScenarioRunner that calls /chat API and validates responses
└── run.py               # Standalone CLI runner for manual execution
tests/test_agent_scenarios.py   # Pytest integration with all scenarios
```

### Personas

| Persona | Role | Style |
|---|---|---|
| `PatientPersona` | Patient | First-person, casual, direct |
| `AttenderPersona` | Caregiver/family | Third-person, formal |
| `ConfusedUserPersona` | Unsure user | Vague, needs follow-up |
| `ExistingPatientPersona` | Returning patient | References past appointments |

### Scenarios (8 total)

| Scenario | Flow |
|---|---|
| `search_and_book` | Search doctors → check availability → book with confirmation |
| `check_availability` | Attender checks slots for a known doctor |
| `cancel_appointment` | Existing patient cancels a booking |
| `reschedule_appointment` | Reschedule to a new date/time |
| `check_status_scenario` | Look up appointments by phone number |
| `edge_case_no_results` | Search for a specialty with no matching doctors |
| `booking_cancelled_at_confirmation` | Say "no" when asked to confirm a booking |
| `confused_user` | Vague queries needing agent guidance |

### Running the test agent

```bash
# Make sure the agent service is running on port 8002
uvicorn apps.agent.main:app --reload --port 8002

# Run as pytest (integration tests)
pytest tests/test_agent_scenarios.py -v

# Run the standalone CLI runner (shows detailed output)
python -m tests.agent_scenarios.run http://localhost:8002

# Or from project root:
python -m tests.agent_scenarios.run
```

### How it works

1. `ScenarioRunner` sends messages to the `/chat` endpoint (same as Streamlit) using `httpx.AsyncClient`
2. Each `Turn` defines expected response content and whether a `pending_confirmation` status is expected
3. When `pending_confirmation` is detected, the runner automatically sends "yes" or "no" on the next turn
4. Responses are validated against `expected_in_response` keywords and `expected_not_in_response` exclusions
5. `ScenarioResult` provides per-turn pass/fail with error details and timing

### Adding new scenarios

```python
from tests.agent_scenarios import Scenario, _t

my_scenario = Scenario(
    name="my_scenario",
    description="What this scenario tests",
    persona="patient",  # or "attender", "confused", "existing_patient"
    turns=[
        _t("First user message", expected_contains=["keyword"]),
        _t("Follow-up message", expect_pending_confirmation=True),
    ],
)
```
