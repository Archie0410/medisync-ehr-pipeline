"""Stateless HTTP client — sends extracted data to MediSync backend."""

import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger("medisync.api_client")


class MediSyncClient:
    def __init__(self, base_url: str, api_key: str, max_retries: int = 3, backoff: int = 5):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-API-KEY": api_key})
        self.max_retries = max_retries
        self.backoff = backoff

    def _post(self, path: str, json_data: dict | None = None, files: dict | None = None, data: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        for attempt in range(1, self.max_retries + 1):
            try:
                if files:
                    resp = self.session.post(url, files=files, data=data)
                else:
                    resp = self.session.post(url, json=json_data)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                logger.warning("Attempt %d/%d failed for %s: %s", attempt, self.max_retries, path, e)
                if attempt < self.max_retries:
                    time.sleep(self.backoff * attempt)
                else:
                    raise

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    # -- Sync lifecycle --

    def start_sync(self, rpa_name: str, credential_name: str = "") -> str:
        result = self._post("/sync/start", {
            "rpa_name": rpa_name,
            "credential_name": credential_name,
        })
        run_id = result["run_id"]
        logger.info("Sync run started: %s", run_id)
        return run_id

    def complete_sync(self, run_id: str, patients: int, orders: int, errors: int, error_details: dict | None = None):
        status = "completed" if errors == 0 else "completed_with_errors"
        self._post(f"/sync/{run_id}/complete", {
            "status": status,
            "patients_processed": patients,
            "orders_processed": orders,
            "errors": errors,
            "error_details": error_details,
        })
        logger.info("Sync run %s completed: %d patients, %d orders, %d errors", run_id, patients, orders, errors)

    def log_event(self, run_id: str, event_type: str, message: str, metadata: dict | None = None):
        """Log an event (ERROR/WARNING/INFO) to a sync run."""
        try:
            self._post(f"/sync/{run_id}/event", {
                "event_type": event_type,
                "message": message,
                "metadata": metadata,
            })
        except Exception as e:
            logger.warning("Failed to log sync event: %s", e)

    # -- Patient --

    def upsert_patient(self, patient_data: dict) -> dict:
        return self._post("/patients", patient_data)

    # -- Episode --

    def upsert_episode(self, episode_data: dict) -> dict:
        return self._post("/episodes", episode_data)

    # -- Order --

    def upsert_order(self, order_data: dict) -> dict:
        return self._post("/orders", order_data)

    # -- Document (decoupled from orders) --

    def upload_document(self, order_id: str, pdf_path: str) -> dict:
        """Upload raw PDF to POST /documents with order_id as form field."""
        path = Path(pdf_path)
        with open(path, "rb") as f:
            return self._post(
                "/documents",
                files={"file": (path.name, f, "application/pdf")},
                data={"order_id": order_id},
            )
