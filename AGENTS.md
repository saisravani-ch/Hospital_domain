# AGENTS.md — Hospital System

## Architecture

Three independent FastAPI apps under `src/`:

| App | Entrypoint | Run command |
|---|---|---|
| Knowledge Base (GraphRAG) | `src.knowledge_base.api.main:app` | `uvicorn src.knowledge_base.api.main:app --reload --port 8000` |
| Workflows (booking) | `src.workflows.main:app` | `uvicorn src.workflows.main:app --reload --port 8001` |
| Conversation Agent | `src.orchestrator.main:app` | `uvicorn src.orchestrator.main:app --reload --port 8002` |

The **Conversation Agent** (`orchestrator/`) routes user queries via a ReAct loop — it calls RAG tools (`search_doctors`, `get_doctor_info`) from `knowledge_base` or workflow tools (`check_availability`, `book_appointment`, etc.) from `workflows` depending on user intent. The agent uses Azure OpenAI function calling instead of the separate intent-classifier LLM call that `GraphRAGEngine.query()` previously made.

- **No `setup.py` / `pyproject.toml`**. All commands **must** run from project root so `src.*` imports resolve.
- `.env` loaded from project root by `pydantic-settings` (in `knowledge_base/config.py`). Workflows uses raw `os.getenv()` in `workflows/config.py` — two separate config systems.

## Python path

`knowledge_base` and `orchestrator` use `from src.xxx import yyy` (absolute). `workflows` now uses `from src.workflows.xxx import yyy` (fixed from flat relative). All need CWD = project root.

## Data pipeline

Three layers, processed in order:
1. **SQLite** (`knowledge_base/db/`) — transactional/denormalized (hospitals, doctors, schedules, time_slots)
2. **Neo4j** (`knowledge_base/graph/`) — semantic graph (Doctor/Hospital nodes, PRACTICES_AT/SPECIALIZES_IN/SPEAKS edges)
3. **ChromaDB** (`knowledge_base/rag/`) — vector embeddings via `all-MiniLM-L6-v2`

Pipeline data: expects `data/raw/` and `data/processed/` at project root. No sample data committed.

`neo4j_schema.cypher` is a **reference file** — the Python `Neo4jLoader.apply_schema()` executes a different (smaller) set of constraints. Do not assume the `.cypher` is what runs.

## Module boundaries

| Module | Status | What it provides |
|---|---|---|
| `knowledge_base/` | Populated | GraphRAG pipeline, FastAPI API (port 8000), config via pydantic-settings |
| `workflows/` | Populated | Booking service, FastAPI API (port 8001), config via os.getenv |
| `orchestrator/` | Populated | ReAct agent, `/chat` endpoint (port 8002), depends on both above |
| `memory/` | Populated | In-memory conversation store (no MongoDB runtime required) |
| `tools/` | Populated | Thin wrappers: `graphrag_tool`, `workflow_tool`, `memory_tool` |

## Agent flow

```
User → POST /chat → Agent.run()
  ├── LLM decides tool(s) to call from user message
  ├── executes tool (RAG or workflow, no separate intent LLM call)
  ├── tool results fed back to LLM
  └── LLM synthesizes final response
```

- Tools: `search_doctors`, `get_doctor_info`, `check_availability`, `book_appointment`, `reschedule_appointment`, `cancel_appointment`
- Max 6 agent turns per request. Conversation history (user + assistant text) persisted per `session_id`.

## Key dependencies

- **Pydantic v2** (`BaseModel`, `field_validator`, `ConfigDict`)
- **FastAPI** DI via `Depends()` singletons in `knowledge_base/api/dependencies.py`; separate singleton init in `orchestrator/dependencies.py`
- **Azure OpenAI GPT-4.1** for agent reasoning + response synthesis (not used for separate intent classification)
- **Sentence Transformers** local embedding (no API key needed)
- **pytest + pytest-asyncio** listed but **zero tests exist** in the repo

## Known quirks

- Multi-tenant design: `tenant_id` on all models, `TENANT_META` dict with 7 hospital branches
- GraphRAG engine: `retrieve_context()` method does retrieval-only (no LLM). The old `query()` method (intent + synthesize) kept for backward compat.
- Workflows booking generates IDs as `apt_{uuid4.hex[:8]}`, manages `time_slots.available` flag
- `.venv/`, `*.db`, `data/chroma/`, `models/`, `logs/` all gitignored
