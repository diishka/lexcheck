# LexCheck UZ

LexCheck UZ is a full-stack legal analysis project for Uzbekistan legislation:
- `frontend` — React/Vite UI
- `backend` — FastAPI + PostgreSQL + Ollama
- `lexai` — main PostgreSQL database

## Project Layout

```text
.
├── lexcheck/
│   ├── backend/
│   ├── frontend/
│   └── setup.sh
├── run.sh
├── requirements.txt
└── scripts/
    ├── db_export.sh
    └── db_import.sh
```

## Quick Start

Prerequisites:
- Python 3.10+
- PostgreSQL
- Node.js / npm
- Ollama if you use local LLM

Setup:

```bash
chmod +x lexcheck/setup.sh
./lexcheck/setup.sh
```

Run:

```bash
chmod +x run.sh
./run.sh
```

App URLs:
- frontend: `http://localhost:3000`
- backend: `http://127.0.0.1:8000`

## Database

The app uses PostgreSQL database `lexai` by default.

Environment example:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lexai
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```
