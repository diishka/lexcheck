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
<<<<<<< HEAD
=======

Persistent response cache:

```env
PERSISTENT_CACHE_ENABLED=true
PERSISTENT_CHAT_CACHE_TTL=43200
PERSISTENT_ANALYZE_CACHE_TTL=43200
```

Repeated identical requests can then return much faster, even after backend restart.

Template file:
- [lexcheck/backend/.env.example](/home/diishka/Desktop/projects/lexcheck/lexcheck/backend/.env.example)

## How To Send Database To Someone

Export the current database into a backup file:

```bash
chmod +x scripts/db_export.sh
./scripts/db_export.sh
```

This creates a file like:

```text
backups/lexai_20260325_153000.dump
```

You can send that `.dump` file to another person together with the project.

## How Another Person Restores The Database

```bash
chmod +x scripts/db_import.sh
./scripts/db_import.sh backups/lexai_20260325_153000.dump
```

After restore, they can run:

```bash
./run.sh
```

## GitHub Push

Typical flow:

```bash
git add .
git commit -m "Prepare project for GitHub and DB sharing"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

Notes:
- `.env` is ignored by git
- `backups/` is ignored by git
- send the database dump separately, not through GitHub

## Recommended Workflow

1. Push code to GitHub.
2. Export DB with `./scripts/db_export.sh`.
3. Send the `.dump` file separately.
4. On another machine restore it with `./scripts/db_import.sh ...`.
5. Start the app with `./run.sh`.
>>>>>>> 084dd92 (updated)
