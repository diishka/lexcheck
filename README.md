# LexCheck UZ

Локальный проект для поиска и анализа законодательства Узбекистана:
- `lexcheck/frontend` — React/Vite интерфейс
- `lexcheck/backend` — FastAPI + PostgreSQL + Ollama
- `lexai` — основная PostgreSQL база

## Структура

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

## Быстрый старт

Нужно:
- Python 3
- PostgreSQL
- Node.js / npm
- Ollama, если используете локальную LLM

Установка:

```bash
chmod +x lexcheck/setup.sh
./lexcheck/setup.sh
```

Важно:
- `setup.sh` больше не заливает `schema.sql` в `lexai`
- если у вас уже есть рабочая база, она не будет перетираться
- чтобы загрузить реальные данные, используйте backup restore

Запуск:

```bash
chmod +x run.sh
./run.sh
```

Адреса:
- frontend: `http://localhost:3000`
- backend: `http://127.0.0.1:8000`

## База данных

Пример `backend/.env`:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lexai
ACTIVE_DOCUMENT_LIMIT=20
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

`ACTIVE_DOCUMENT_LIMIT=20` включает быстрый режим:
- frontend показывает только 20 активных документов
- поиск, категории и ассистент работают по этому же ограниченному набору
- это заметно ускоряет приложение

Шаблон env:
- [lexcheck/backend/.env.example](/home/diishka/Desktop/projects/lexcheck/lexcheck/backend/.env.example)

## Передача базы другому человеку

Экспорт:

```bash
chmod +x scripts/db_export.sh
./scripts/db_export.sh
```

Это создаст файл вида:

```text
backups/lexai_YYYYMMDD_HHMMSS.dump
```

Восстановление на другой машине:

```bash
chmod +x scripts/db_import.sh
./scripts/db_import.sh backups/lexai_YYYYMMDD_HHMMSS.dump
```

После восстановления:

```bash
./run.sh
```

## Ollama

Локальная модель:

```bash
ollama pull qwen2.5:7b
```

Потом в `backend/.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b
```

## GitHub

Обычный flow:

```bash
git add .
git commit -m "Audit project and enable fast 20-document mode"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

Примечания:
- `.env` не уходит в git
- `backups/` не уходит в git
- runtime cache и локальные служебные файлы тоже игнорируются
