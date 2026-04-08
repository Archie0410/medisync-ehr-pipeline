"""MediSync RPA Orchestrator.

End-to-end per-patient pipeline:
  1. Start sync run via backend
  2. Login to Axxess EHR
  3. Navigate to Patient Charts
  4. For each patient in the sidebar:
     a. Extract demographics from Patient Profile
     b. Change date filter to "All"
     c. Scrape Schedule Activity table (orders)
     d. Download documents via the Actions column
  5. Push to backend: patient, episodes (computed from SOC + current episode),
     orders (from schedule activities, assigned to correct episode), documents
  6. Complete sync run

RPA is stateless -- all persistent data lives in the backend.
"""

import logging
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from medisync_rpa.config import load_config, RPAConfig
from medisync_rpa.browser import create_driver, close_driver
from medisync_rpa.auth import login_to_axxess
from medisync_rpa.api_client import MediSyncClient
from medisync_rpa.extractors.patient_extractor import (
    navigate_to_patient_charts, extract_all_patients,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"medisync_rpa_{date.today().isoformat()}.log"),
    ],
)
logger = logging.getLogger("medisync.main")


def run(config_path: str = "config.json"):
    cfg = load_config(config_path)
    client = MediSyncClient(
        cfg.backend_url, cfg.api_key,
        cfg.retry.max_attempts, cfg.retry.backoff_seconds,
    )

    run_id = client.start_sync(cfg.rpa_name, cfg.axxess.email)
    logger.info("=== MediSync RPA Run Started: %s ===", run_id)

    stats = {"patients": 0, "orders": 0, "errors": 0}
    error_details = {}
    driver = None

    try:
        driver = create_driver(cfg.chrome)
        download_dir = str(Path(cfg.chrome.download_dir).resolve())
        Path(download_dir).mkdir(parents=True, exist_ok=True)

        # Step 1: Login
        _login_with_retry(driver, cfg, client, run_id)

        # Step 2: Navigate to Patient Charts and extract everything per-patient
        navigate_to_patient_charts(driver)
        all_patients = extract_all_patients(
            driver, download_dir, max_patients=cfg.max_patients
        )
        client.log_event(
            run_id, "INFO",
            f"Extracted {len(all_patients)} patients with schedule activities",
        )

        # Step 3: Push data to backend for each patient
        for profile in all_patients:
            _push_patient_data(profile, client, run_id, stats, error_details)

    except Exception as e:
        logger.exception("Fatal error in RPA run")
        client.log_event(run_id, "ERROR", f"Fatal RPA error: {e}")
        stats["errors"] += 1
        error_details["fatal"] = str(e)
    finally:
        if driver:
            close_driver(driver)
        client.complete_sync(
            run_id, stats["patients"], stats["orders"], stats["errors"],
            error_details if error_details else None,
        )
        logger.info("=== Run complete: %s ===", stats)


# -------------------------------------------------------------------
# Per-patient backend push
# -------------------------------------------------------------------

def _push_patient_data(
    profile: dict,
    client: MediSyncClient,
    run_id: str,
    stats: dict,
    error_details: dict,
):
    """Push one patient's data to the backend: patient, episodes, orders, docs."""
    sidebar_name = profile.get("sidebar_name", "unknown")
    mrn = (profile.get("mrn") or "").strip()

    if not mrn:
        logger.warning("No MRN for '%s', skipping", sidebar_name)
        client.log_event(run_id, "WARNING", f"No MRN for patient '{sidebar_name}'")
        stats["errors"] += 1
        return

    # -- Upsert patient --
    try:
        _blob_keys = [
            # Demographics
            "alternate_phone", "ssn", "sex", "race", "ethnicity",
            "marital_status", "primary_language", "interpreter",
            "service_location", "auxiliary_aids",
            # Address
            "primary_address", "mailing_address", "email",
            # Payer
            "primary_insurance", "medicare_part_a_effective", "medicare_part_b_effective",
            "mbi_number", "secondary_insurance", "advanced_directive_comments",
            # Pharmacy / Allergies
            "pharmacy_name", "allergies",
            # Clinical
            "case_manager", "clinical_manager", "primary_clinician",
            "services_required", "primary_diagnosis", "additional_diagnoses",
            # Physicians
            "attending_physician", "attending_npi",
            "referring_physician", "referring_npi",
            "certifying_physician", "certifying_npi",
            # Emergency contact
            "emergency_contact_name", "emergency_contact_relationship", "emergency_contact_phone",
            # Referral
            "referral_date", "admission_source", "community_liaison",
            "facility_referral_source", "face_to_face_date",
            "priority_visit_type", "emergency_triage_level",
        ]
        profile_blob = {k: profile.get(k) for k in _blob_keys if profile.get(k) is not None}

        client.upsert_patient({
            "mrn": mrn,
            "first_name": profile.get("first_name", ""),
            "last_name": profile.get("last_name", ""),
            "dob": profile.get("dob"),
            "phone": profile.get("phone"),
            "address_line1": profile.get("primary_address"),
            "profile_data": profile_blob if profile_blob else None,
            "sync_run_id": run_id,
        })
        stats["patients"] += 1
    except Exception as e:
        logger.error("Patient push failed for '%s': %s", sidebar_name, e)
        client.log_event(run_id, "ERROR", f"Patient push failed: {sidebar_name}", {"error": str(e)})
        stats["errors"] += 1
        error_details[f"patient:{sidebar_name}"] = str(e)
        return

    # -- Compute and upsert all episodes --
    episode_info = profile.get("episode") or {}
    current_start = episode_info.get("start_date")
    current_end = episode_info.get("end_date")
    soc_date = episode_info.get("soc_date")
    npi = profile.get("attending_npi")

    all_episodes = []
    episode_id_map: dict[tuple[str, str | None], int] = {}
    if soc_date and current_start and current_end:
        all_episodes = compute_all_episodes(soc_date, current_start, current_end)
        for ep in all_episodes:
            try:
                result = client.upsert_episode({
                    "patient_mrn": mrn,
                    "start_date": ep["start_date"],
                    "end_date": ep["end_date"],
                    "soc_date": soc_date,
                    "physician_npi": npi,
                    "sync_run_id": run_id,
                })
                episode_id_map[(ep["start_date"], ep["end_date"])] = result["episode_id"]
            except Exception as e:
                logger.warning("Episode push failed for %s (%s): %s", mrn, ep, e)
    elif current_start and current_end:
        try:
            result = client.upsert_episode({
                "patient_mrn": mrn,
                "start_date": current_start,
                "end_date": current_end,
                "soc_date": soc_date,
                "physician_npi": npi,
                "sync_run_id": run_id,
            })
            all_episodes = [{"start_date": current_start, "end_date": current_end}]
            episode_id_map[(current_start, current_end)] = result["episode_id"]
        except Exception as e:
            logger.warning("Episode push failed for %s: %s", mrn, e)

    # -- Push schedule activities as orders --
    for activity in profile.get("schedule_activities", []):
        try:
            task = activity.get("task", "")
            sched_date_raw = activity.get("schedule_date", "")
            sched_date_iso = _parse_date_to_iso(sched_date_raw)

            order_id = _generate_order_id(task, sched_date_raw, mrn)
            episode_match = find_episode_for_date(sched_date_iso, all_episodes)
            episode_id = None
            if episode_match:
                episode_id = episode_id_map.get(
                    (episode_match.get("start_date"), episode_match.get("end_date"))
                )

            client.upsert_order({
                "order_id": order_id,
                "patient_mrn": mrn,
                "episode_id": episode_id,
                "order_date": sched_date_iso or date.today().isoformat(),
                "doc_type": task,
                "status": activity.get("status", ""),
                "sync_run_id": run_id,
            })
            stats["orders"] += 1

            # Upload document if downloaded
            doc_path = activity.get("document_path")
            if doc_path and Path(doc_path).is_file():
                try:
                    client.upload_document(order_id, doc_path)
                    logger.info("Uploaded doc for order %s", order_id)
                except Exception as e:
                    logger.warning("Doc upload failed for %s: %s", order_id, e)
                    client.log_event(
                        run_id, "WARNING",
                        f"Doc upload failed: {order_id}", {"error": str(e)},
                    )

        except Exception as e:
            logger.error("Order push failed (%s): %s", task, e)
            client.log_event(
                run_id, "ERROR",
                f"Order push failed: {task} for {sidebar_name}", {"error": str(e)},
            )
            stats["errors"] += 1
            error_details[f"order:{sidebar_name}:{task}"] = str(e)


# -------------------------------------------------------------------
# Episode computation
# -------------------------------------------------------------------

def compute_all_episodes(
    soc_date_str: str, current_start_str: str, current_end_str: str,
) -> list[dict]:
    """Build every 60-day episode from Start of Care through current episode.

    Each episode: start -> start + 59 days  (= 60 calendar days inclusive).
    Next episode starts at previous end + 1 day.
    """
    soc = _iso_to_date(soc_date_str)
    current_end = _iso_to_date(current_end_str)
    if not soc or not current_end:
        return []

    episodes = []
    ep_start = soc
    while ep_start <= current_end:
        ep_end = ep_start + timedelta(days=59)
        episodes.append({
            "start_date": ep_start.isoformat(),
            "end_date": ep_end.isoformat(),
        })
        ep_start = ep_end + timedelta(days=1)
    return episodes


def find_episode_for_date(
    schedule_date_iso: str | None, episodes: list[dict],
) -> dict | None:
    """Return the episode whose date range contains schedule_date."""
    if not schedule_date_iso:
        return None
    for ep in episodes:
        if ep["start_date"] <= schedule_date_iso <= ep["end_date"]:
            return ep
    return None


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _login_with_retry(driver, cfg: RPAConfig, client: MediSyncClient, run_id: str):
    for attempt in range(1, cfg.retry.max_attempts + 1):
        try:
            login_to_axxess(
                driver, cfg.axxess.url, cfg.axxess.email, cfg.axxess.password,
                agency_name=cfg.axxess.agency_name or None,
            )
            client.log_event(run_id, "INFO", "Login successful")
            return
        except Exception as e:
            logger.warning("Login attempt %d failed: %s", attempt, e)
            client.log_event(run_id, "WARNING", f"Login attempt {attempt} failed: {e}")
            if attempt < cfg.retry.max_attempts:
                time.sleep(cfg.retry.backoff_seconds * attempt)
            else:
                raise RuntimeError("All login attempts exhausted") from e


def _generate_order_id(task: str, schedule_date: str, mrn: str) -> str:
    """Generate a deterministic order ID from schedule activity data."""
    safe_task = re.sub(r"[^a-zA-Z0-9]", "_", task).strip("_")
    safe_date = schedule_date.replace("/", "")
    return f"{safe_task}_{safe_date}_{mrn}"


def _parse_date_to_iso(raw: str) -> str | None:
    """Convert MM/DD/YYYY to YYYY-MM-DD."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return date(*time.strptime(raw, fmt)[:3]).isoformat()
        except ValueError:
            continue
    return None


def _iso_to_date(iso_str: str | None):
    """Parse YYYY-MM-DD string into a date object."""
    if not iso_str:
        return None
    try:
        return datetime.strptime(iso_str, "%Y-%m-%d").date()
    except ValueError:
        return None


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    run(config)
