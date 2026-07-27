# 🏥 Hospital System — AI-Powered Medical Assistant

A multi-agent AI system for hospital knowledge management, appointment workflows, and intelligent query resolution using **GraphRAG**, **ChromaDB**, **Neo4j**, and **Azure OpenAI**.

---

## 🧠 Architecture Overview

```
hospital_system/
├── src/
│   ├── knowledge_base/      # GraphRAG pipeline (Neo4j + ChromaDB)
│   │   ├── api/             # FastAPI routes for knowledge queries
│   │   ├── db/              # SQLite/SQLAlchemy models & loaders
│   │   ├── graph/           # Neo4j graph loader & Cypher schema
│   │   ├── pipeline/        # Merge & ingestion pipeline
│   │   ├── query/           # GraphRAG query engine
│   │   └── rag/             # Vector store (ChromaDB)
│   ├── memory/              # Conversation memory & state management
│   │   ├── conversation_memory.py
│   │   ├── message_store.py
│   │   ├── mongodb.py       # MongoDB persistence layer
│   │   ├── state_manager.py
│   │   └── models.py
│   ├── orchestrator/        # LangGraph agent orchestration
│   │   ├── agent.py
│   │   ├── main.py
│   │   ├── prompts.py
│   │   └── toools.py
│   └── workflows/           # Appointment & booking workflows
│       ├── api/             # FastAPI endpoints
│       ├── data/db/         # SQLite database
│       └── services/        # Booking service logic
├── tools/                   # Shared agent tools
├── requirements.txt
└── .env.example             # Environment variable template
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| LLM / Intent Router | Azure OpenAI (GPT-4.1) |
| Agent Orchestration | LangGraph |
| Knowledge Graph | Neo4j AuraDB |
| Vector Store | ChromaDB (embedded) |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`) |
| Memory / History | MongoDB Atlas |
| Workflows DB | SQLite + SQLAlchemy |
| API Framework | FastAPI + Uvicorn |
| Web Scraping | Playwright + BeautifulSoup4 |

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/praveenkumar889/hospital_system.git
cd hospital_system
```

### 2. Create and activate virtual environment
```bash
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp src/.env.example src/.env
# Edit src/.env and fill in your API keys
```

### 5. Run the API server
```bash
uvicorn src.knowledge_base.api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔐 Environment Variables

Copy `src/.env.example` to `src/.env` and configure:

| Variable | Description |
|---|---|
| `NEO4J_URI` | Neo4j AuraDB connection URI |
| `NEO4J_USERNAME` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name (e.g. `gpt-4.1`) |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `MONGODB_URL` | MongoDB Atlas connection string |
| `CHROMA_PERSIST_DIR` | Local ChromaDB persistence path |

> ⚠️ **Never commit your `.env` file.** It is excluded via `.gitignore`.

---

## 📄 License

MIT
