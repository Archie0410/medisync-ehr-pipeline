# MediSync

MediSync is a healthcare data pipeline that extracts patient/order data from Axxess (via Selenium RPA), stores and serves it through a FastAPI backend, and visualizes it in a React dashboard.

## Architecture

```
RPA (Selenium)  ->  Backend (FastAPI)  ->  PostgreSQL
     |                     |
  PDF downloads        File storage
```

## Prerequisites

- Python 3.11+ (recommended)
- Node.js 18+ and npm
- Docker Desktop (optional, for DB/backend via compose)
- Google Chrome (for RPA browser automation)

## Configuration

### 1) Backend environment

Copy `.env.example` to `.env` in the repo root and update values as needed:

```bash
cp .env.example .env
```

Current `.env.example` fields:

- `DATABASE_URL`
- `API_KEY`
- `STORAGE_PATH`

### 2) Frontend environment

Copy `frontend/.env.example` to `frontend/.env`:

```bash
cp frontend/.env.example frontend/.env
```

Current frontend env fields:

- `VITE_API_BASE` (default: `http://localhost:8000/api/v1`)
- `VITE_API_KEY` (must match backend `API_KEY`)

### 3) RPA configuration

Create `rpa/config.json` from the example and fill your real Axxess credentials:

```bash
cp rpa/config.example.json rpa/config.json
```

Required keys inside `rpa/config.json`:

- `backend_url`
- `api_key`
- `axxess.url`
- `axxess.email`
- `axxess.password`
- `axxess.agency_name`

## Option A: Run with Docker (DB + Backend)

From project root:

```bash
docker-compose up -d --build
```

Services:

- Backend: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

Then run frontend and RPA locally (see below).

## Option B: Run fully local (without Docker)

Use 4 terminals.

### Terminal 1 - PostgreSQL

```bash
docker run -d --name medisync-db \
  -e POSTGRES_DB=medisync \
  -e POSTGRES_USER=medisync \
  -e POSTGRES_PASSWORD=medisync_dev \
  -p 5432:5432 postgres:16-alpine
```

### Terminal 2 - Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Terminal 3 - Frontend

```bash
cd frontend
npm install
npm run dev
```

### Terminal 4 - RPA

```bash
cd rpa
pip install -r requirements.txt
python -m medisync_rpa.main
```

## Dashboard Usage Flow

1. Run RPA to ingest patient/profile/order/document data.
2. Open frontend dashboard.
3. On the **Home Health dashboard (Patients list page)** click **Sync NPI**.
4. Backend syncs unique NPIs across all patients using NPPES and stores enriched physician data.
5. Open any patient profile:
   - NPPES data appears inline in:
     - `Attending Physician`
     - `Referring Physician`
     - `Certifying Physician`

## Key API Endpoints

All mutating endpoints require `X-API-KEY` header.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/v1/sync/start` | Start a sync run |
| POST | `/api/v1/sync/{run_id}/complete` | Complete a sync run |
| GET | `/api/v1/sync/metrics` | Sync metrics |
| GET | `/api/v1/patients/overview` | Dashboard patient list |
| POST | `/api/v1/patients` | Upsert patient |
| GET | `/api/v1/patients/{mrn}` | Get patient with profile data |
| GET | `/api/v1/patients` | List patients |
| POST | `/api/v1/patients/sync-npi` | Bulk sync NPIs for all patients |
| POST | `/api/v1/orders` | Upsert order |
| GET | `/api/v1/orders?mrn={mrn}` | Orders by patient MRN |
| GET | `/api/v1/documents/by-mrn?mrn={mrn}` | Documents by patient MRN |
| GET | `/api/v1/documents/{id}/file` | Download/view document PDF |

## Project Structure

```
MediSync/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── config.py
│   │   └── main.py
│   ├── init.sql
│   └── requirements.txt
├── frontend/
│   ├── .env.example
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── types/
│   └── package.json
├── rpa/
│   ├── config.example.json
│   ├── config.json            # local-only, do not commit secrets
│   ├── downloads/
│   └── medisync_rpa/
└── storage/
    ├── documents/
    └── extractions/
```

## Troubleshooting

- Backend cannot connect to DB:
  - Verify PostgreSQL is running on `5432`.
  - Verify `DATABASE_URL` in `.env`.
- Frontend request failures:
  - Check `VITE_API_BASE` and `VITE_API_KEY` in `frontend/.env`.
  - Ensure backend `API_KEY` matches frontend key.
- RPA auth issues:
  - Re-check `rpa/config.json` Axxess credentials and agency name.
- NPI sync returns no data:
  - Ensure patient profile contains `attending_npi`, `referring_npi`, or `certifying_npi`.
