-- MediSync PostgreSQL Schema (v1.2 — production hardened)
-- Tables auto-created by SQLAlchemy on startup; this file is for reference / manual setup.

CREATE TABLE IF NOT EXISTS physicians (
    id SERIAL PRIMARY KEY,
    npi VARCHAR(10) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    mrn VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE,
    phone VARCHAR(20),
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS episodes (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    start_date DATE NOT NULL,
    end_date DATE,
    soc_date DATE,
    physician_id INTEGER REFERENCES physicians(id),  -- INFORMATIONAL ONLY, not authoritative
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(patient_id, start_date, end_date)
);

-- Fix 1: UNIQUE(order_id, patient_id) instead of UNIQUE(order_id)
-- Allows same order_id across different patients (cross-patient safety)
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    episode_id INTEGER REFERENCES episodes(id),
    physician_id INTEGER REFERENCES physicians(id),
    order_date DATE NOT NULL,
    doc_type VARCHAR(100),
    status VARCHAR(30) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(order_id, patient_id)
);

-- Fix 2: storage_type + storage_path (replaces file_path)
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    filename VARCHAR(255) NOT NULL,
    storage_type VARCHAR(10) NOT NULL DEFAULT 'local',
    storage_path TEXT,
    file_hash VARCHAR(64) NOT NULL,
    page_count INTEGER,
    extracted_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(order_id, file_hash)
);

-- Fix 3: status default is 'RUNNING', enum: RUNNING/COMPLETED/FAILED/PARTIAL
CREATE TABLE IF NOT EXISTS sync_runs (
    id SERIAL PRIMARY KEY,
    run_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    rpa_name VARCHAR(100),
    credential_name VARCHAR(100),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    patients_processed INTEGER DEFAULT 0,
    orders_processed INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    error_details JSONB,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS sync_events (
    id SERIAL PRIMARY KEY,
    sync_run_id INTEGER NOT NULL REFERENCES sync_runs(id),
    event_type VARCHAR(20) NOT NULL,
    entity_type VARCHAR(30),
    entity_id VARCHAR(50),
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_patients_mrn ON patients(mrn);
CREATE INDEX IF NOT EXISTS idx_physicians_npi ON physicians(npi);
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_patient ON orders(patient_id);
CREATE INDEX IF NOT EXISTS idx_orders_episode ON orders(episode_id);
CREATE INDEX IF NOT EXISTS idx_episodes_patient ON episodes(patient_id);
-- Partial unique index: enforces uniqueness when end_date IS NULL
-- (PostgreSQL treats NULLs as distinct in standard UNIQUE constraints)
CREATE UNIQUE INDEX IF NOT EXISTS uq_episode_null_end
    ON episodes(patient_id, start_date) WHERE end_date IS NULL;
CREATE INDEX IF NOT EXISTS idx_documents_order ON documents(order_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_sync_runs_run_id ON sync_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_status ON sync_runs(status);
CREATE INDEX IF NOT EXISTS idx_sync_events_run ON sync_events(sync_run_id);
