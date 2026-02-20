# News Engine — Market Intelligence Platform

Production-grade Django application for monitoring the French digital & IT ecosystem (Lyon-focused), scraping curated sources, extracting structured signals via LLMs, and generating weekly executive reports for an IT/digital agency.

## Tech stack

- **Backend:** Django 4.2, Django REST Framework
- **Database:** PostgreSQL (SQLite for local dev without Docker)
- **Broker / results:** Redis, Celery
- **Scraping:** Playwright, Trafilatura
- **LLM:** Ollama (local LLaMA / Mistral), API-agnostic client
- **Deployment:** Docker, Gunicorn

## Project layout

```
engine/                 # Django project root (manage.py here)
  engine/               # Project package
    settings/            # base, development, production
    celery.py
    api_urls.py
  core/                  # Shared primitives (TimestampedModel, enums, utils)
  sources/               # Source model, ScrapingService, scrape_source task
  articles/              # Article, ContentChunk, ChunkingService, chunk_article task
  intelligence/         # Signal model, LLMClient, SignalExtractionService, prompts
  reports/               # WeeklyReport, ReportGenerationService, generate_report task
  pipeline/              # ProcessingRun, full/scrape/extract/report tasks, Beat schedule
  prompts/               # YAML prompt templates (signal_extraction, report_synthesis)
requirements/
  base.txt
  dev.txt
  prod.txt
docker-compose.yml
Dockerfile
```

## Quick start (development)

1. **Clone and enter project**
   ```bash
   cd news_engine/engine
   ```

2. **Virtualenv and install**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r ../requirements/base.txt
   ```

3. **Environment**
   ```bash
   copy ..\.env.example .env
   # Edit .env: set DJANGO_SETTINGS_MODULE=engine.settings.development
   ```

4. **Database and seed**
   ```bash
   python manage.py migrate
   python manage.py seed_sources
   python manage.py createsuperuser
   ```

5. **Run**
   ```bash
   python manage.py runserver
   ```
   - Admin: http://127.0.0.1:8000/admin/
   - API: http://127.0.0.1:8000/api/

6. **Celery (optional, for pipelines)**
   ```bash
   # Terminal 2: Redis (e.g. Docker or local Redis)
   celery -A engine.celery worker -l info
   # Terminal 3: Beat (scheduled runs)
   celery -A engine.celery beat -l info
   ```

7. **Local LLM — Llama 3.1 8B (required for signal extraction and reports)**  
   The app uses **Ollama** to run your local Llama 3.1 8B. Do this once:

   - **Install Ollama**  
     Download and install from [ollama.ai](https://ollama.ai). Start the Ollama app so the server runs (e.g. `http://localhost:11434`).

   - **Pull the model**  
     In a terminal:
     ```bash
     ollama pull llama3.1:8b
     ```
     Wait until the download finishes. You can confirm with:
     ```bash
     ollama list
     ```
     You should see `llama3.1:8b` (or the tag you used).

   - **Configure the app**  
     In your `.env` (or environment):
     ```
     OLLAMA_BASE_URL=http://localhost:11434
     LLM_DEFAULT_MODEL=llama3.1:8b
     ```
     If you use another tag (e.g. `llama3.1`), set `LLM_DEFAULT_MODEL` to that exact name.

   - **Verify**  
     After starting the Django server, run a scrape then trigger signal extraction (or the full pipeline). Check logs for Ollama HTTP calls; any connection error means Ollama is not running or the URL/model is wrong.

## Docker (full stack)

From repo root (parent of `engine/`):

```bash
cp .env.example .env
# Set ALLOWED_HOSTS and SECRET_KEY for production
docker compose up -d
# Migrate and seed
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_sources
```

Services: `web` (Django), `worker` (Celery), `beat`, `db` (PostgreSQL), `redis`.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | /api/sources/ | List/create sources |
| GET    | /api/articles/ | List articles (filter: source, status, language) |
| GET    | /api/signals/ | List signals (filter: category, date, relevance) |
| GET    | /api/reports/ | List weekly reports |
| GET    | /api/reports/{id}/ | Report detail |
| GET    | /api/pipeline/runs/ | List processing runs |
| POST   | /api/pipeline/runs/run/ | Trigger pipeline (body: `{"run_type": "full"\|"scrape"\|"extract"\|"report"}`) |

Pagination: `?page=1&page_size=20`. Filtering via query params (e.g. `?source=1&processing_status=pending`).

## Management commands

- `seed_sources` — Create default French IT/digital sources (idempotent).

## Domain concepts

- **Source** — Monitored website or feed (Playwright / Trafilatura / RSS).
- **Article** — Normalized scraped content (no raw HTML stored).
- **ContentChunk** — Text slice sent to the LLM for signal extraction.
- **Signal** — Structured intelligence (category, title, description, relevance, entities).
- **WeeklyReport** — Aggregated executive report (8 sections, markdown).
- **ProcessingRun** — Tracks each pipeline execution (scrape / extract / report / full).

## Compliance

- Scrape only publicly accessible content.
- Do not redistribute full articles; store summaries and signals only.
- Avoid storing personal data; design for GDPR/EU compliance.

## License

Proprietary. All rights reserved.
