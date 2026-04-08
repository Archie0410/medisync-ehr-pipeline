# MediSync

Healthcare data pipeline: extracts data from Axxess EHR via Selenium RPA and processes it through a FastAPI backend into PostgreSQL.

## Architecture

```
RPA (Selenium)  →  Backend (FastAPI)  →  PostgreSQL
     ↓                    ↓
  Downloads          File Storage
  (bulk PDFs)        (per-order PDFs)
```

## Quick Start

### 1. Start PostgreSQL + Backend

```bash
docker-compose up -d
```

Backend available at `http://localhost:8000`.  
API docs at `http://localhost:8000/docs`.

### 2. Run Without Docker

```bash
# Terminal 1 — Database
docker run -d --name medisync-db \
  -e POSTGRES_DB=medisync \
  -e POSTGRES_USER=medisync \
  -e POSTGRES_PASSWORD=medisync_dev \
  -p 5432:5432 postgres:16-alpine

# Terminal 2 — Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Terminal 3 — RPA
cd rpa
pip install -r requirements.txt
python -m medisync_rpa.main

# Terminal 4 — Frontend
cd frontend
npm install
npm run dev
```

### 3. Configuration

- Backend: set env vars or `.env` file (see `.env.example`)
- RPA: edit `rpa/config.json` with Axxess credentials and backend URL

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/sync/start` | Start a sync run |
| POST | `/api/v1/sync/{run_id}/complete` | Complete a sync run |
| GET | `/api/v1/sync/metrics` | Monitoring dashboard |
| POST | `/api/v1/patients` | Upsert patient by MRN |
| GET | `/api/v1/patients/{mrn}` | Get patient |
| GET | `/api/v1/patients` | List patients |
| POST | `/api/v1/orders` | Upsert order by order_id |
| GET | `/api/v1/orders?mrn=X` | Orders for patient |
| POST | `/api/v1/orders/{id}/document` | Upload PDF |
| GET | `/health` | Health check |

All mutating endpoints require `X-API-KEY` header.

## Project Structure

```
MediSync/
├── docker-compose.yml
├── frontend/
│   ├── src/
│   │   ├── api/                # API client layer
│   │   ├── components/         # Reusable UI blocks
│   │   ├── hooks/              # Data hooks
│   │   └── types/              # Shared TS models
│   ├── index.html
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app
│   │   ├── config.py          # Settings
│   │   ├── database.py        # Async SQLAlchemy
│   │   ├── models/            # ORM models
│   │   ├── schemas/           # Pydantic request/response
│   │   ├── services/          # Business logic
│   │   ├── api/routes/        # API endpoints
│   │   └── core/security.py   # API key auth
│   ├── init.sql               # Reference schema
│   └── requirements.txt
├── rpa/
│   ├── config.json
│   ├── medisync_rpa/
│   │   ├── main.py            # Orchestrator
│   │   ├── config.py          # Config loader
│   │   ├── browser.py         # Chrome lifecycle
│   │   ├── auth.py            # Axxess login
│   │   ├── api_client.py      # Backend HTTP client
│   │   └── extractors/
│   │       ├── patient_extractor.py
│   │       ├── order_extractor.py
│   │       └── pdf_extractor.py
│   └── requirements.txt
└── storage/documents/
```
