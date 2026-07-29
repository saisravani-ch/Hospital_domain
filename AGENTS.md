# AGENTS.md — Hospital System

## Run commands (CWD = project root)

Two of the three services require Neo4j + ChromaDB + Azure OpenAI. The agent and UI can start without them (degraded responses).

| App | Port | Command |
|---|---|---|
| Knowledge Base (KB) | 8000 | `uvicorn src.knowledge_base.api.main:app --reload --port 8000` |
| Workflows | 8001 | `uvicorn src.workflows.main:app --reload --port 8001` |
| Agent (orchestrator) | 8002 | `uvicorn src.orchestrator.main:app --reload --port 8002` |
| Streamlit UI | 8501 | `streamlit run streamlit_app.py` |

`.\run_all.ps1` launches all four in separate terminal windows.

No `setup.py`/`pyproject.toml` — `pip install -r requirements.txt` is the only install.

## Two config systems, one env file

- **KB** (`knowledge_base/config.py`): `pydantic-settings` reads `.env` from project root
- **Workflows** (`workflows/config.py`): raw `os.getenv()` + **hardcoded CLIENTS dict** — `client_id` must be in `CLIENTS` or you get `ValueError`. Only `"gleneagles_001"` exists by default.
- **Orchestrator** imports KB's `get_settings()` — same env file
- **Tools** (`src/tools/graphrag_tool.py`, `workflow_tool.py`): read `KB_URL` / `WF_URL` from env (default `http://localhost:8000` / `8001`)

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
- `state.py` — `HospitalAgentState` TypedDict with typed fields + `add_messages` reducer
- `langgraph_tools.py` — `@tool` wrappers around HTTP tools, each returning `Command(update={...})` to emit state fields + `ToolMessage` directly. Injects `tenant_id`/`client_id` via `InjectedState`, and `tool_call_id` via `ToolRuntime`
- `graph.py` — `StateGraph` with `assistant` → `tools` → `assistant` loop, `human_confirmation` interrupt for booking

Only `langgraph` + `langchain-openai` added to deps. No full LangChain agent frameworks.

## Tool HTTP boundaries

Tools in `src/tools/` call downstream services via `httpx.AsyncClient`:
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

`src/memory/conversation_memory.py` stores conversations in a plain `dict` in memory. The `mongodb.py` module exists but is unused. No MongoDB instance needed. State persistence is now handled by LangGraph's `MemorySaver` checkpointer (in-memory, same limitation — restart loses state).

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

1. **SQLite** (`knowledge_base/db/`) — hospitals, doctors, schedules, time_slots
2. **Neo4j** (`knowledge_base/graph/`) — Doctor/Hospital/PracticesAt/SpecializesIn/Speaks nodes/edges
3. **ChromaDB** (`knowledge_base/rag/`) — vector embeddings via `all-MiniLM-L6-v2`

Expects `data/raw/` and `data/processed/` at project root. No sample data committed.

`neo4j_schema.cypher` is a **reference file** — `Neo4jLoader.apply_schema()` runs a different (smaller) set of constraints.

## Multi-tenant

- `TENANT_META` in `config.py` maps 7 tenant IDs → location IDs (Gleneagles branches)
- `TenantConfig` branding loaded from DB `hospitals` table at runtime via `get_tenant_config_from_db()`
- Fallback to `Settings` fields for currency/names/booking URL
- `client_id` is required by workflow endpoints — maps to `CLIENTS` dict in `workflows/config.py`

## streamlit_app.py quirks

- Uses **urllib** (sync), not httpx — all requests block the UI
- MUST call `st.rerun()` after appending assistant message (already done — don't remove it)
- Sidebar text inputs for all 3 service URLs with default `localhost:port` values
