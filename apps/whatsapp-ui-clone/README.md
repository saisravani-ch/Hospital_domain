# Hospital System — React Frontend (WhatsApp-style)

A React frontend for the hospital conversation system (the backend lives in
`hospital_system/`). It keeps the WhatsApp-style chat layout while exposing the
same functionality as the reference **Streamlit UI**
(`hospital_system/apps/ui/streamlit_app.py`).

## Features

- **💬 Chat** — WhatsApp-style conversation with the LangGraph agent
  (`POST /chat`). Multi-turn session state is persisted in `localStorage`, so a
  page reload keeps the conversation and session. When the agent pauses to
  confirm a booking, an inline **Yes / No** confirmation bar appears and the
  chat input is disabled (matching the Streamlit behaviour).
- **🔍 Doctors** — Knowledge Base search with 4 modes:
  - GraphRAG (vector + graph) → `GET /search/doctors`
  - Semantic (vector only) → `GET /search/doctors/semantic`
  - By Specialization → `GET /search/doctors/by-specialization`
  - Doctor Profile → `GET /doctors/{id}`
- **📅 Appointments** — Workflow operations:
  - Check Availability → `GET /appointments/availability`
  - Book → `POST /appointments/book`
  - Reschedule → `POST /appointments/reschedule`
  - Cancel → `POST /appointments/cancel`
- **❤️ Health** — live health checks for the three services plus a raw API test
  panel.
- **⚙️ Settings** — configure the Knowledge Base / Workflows / Agent base URLs
  and the tenant / client IDs (persisted in `localStorage`).

## Prerequisites

Start the three backend services (see `hospital_system/AGENTS.md`):

| Service | Port | Command (from `hospital_system/`) |
|---|---|---|
| Knowledge Base | 8000 | `uvicorn apps.kb.api.main:app --reload --port 8000` |
| Workflows | 8001 | `uvicorn apps.workflows.main:app --reload --port 8001` |
| Agent (orchestrator) | 8002 | `uvicorn apps.agent.main:app --reload --port 8002` |

The default URLs are `http://localhost:8000/8001/8002` — override them via the
⚙️ Settings button if yours differ.

## Run

```bash
yarn start        # or: npm start
```

Open [http://localhost:3000](http://localhost:3000).

## Project structure

```
src/
  api/
    config.js       # service URLs + tenant/client, persisted in localStorage
    agents.js       # POST /chat
    kb.js           # doctor search endpoints
    workflows.js    # appointment endpoints
    health.js       # /health checks + raw GET
  components/
    TopNav.js               # tab navigation + settings modal
    doctors/DoctorsView.js  # 4 search modes
    appointments/AppointmentsView.js  # availability / book / reschedule / cancel
    health/HealthView.js    # health checks + raw API test
    ... (WhatsApp chat components: Avatar, ContactBox, MessagesBox, ...)
  App.js            # view orchestration + agent chat state
```

## Notes

- The agent chat thread and the settings are stored in `localStorage`
  (`hospital_agent_thread`, `hospital_config`).
- The fake contact list is regenerated on every load (demo data); only the AI
  Agent conversation persists.

---

This project was bootstrapped with
[Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

### `yarn start`

Runs the app in the development mode.<br />
Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

The page will reload if you make edits.<br />
You will also see any lint errors in the console.

### `yarn test`

Launches the test runner in the interactive watch mode.

### `yarn build`

Builds the app for production to the `build` folder.

### `yarn eject`

**Note: this is a one-way operation. Once you `eject`, you can’t go back!**


### Deployment

This section has moved here: https://facebook.github.io/create-react-app/docs/deployment

### `yarn build` fails to minify

This section has moved here: https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify
