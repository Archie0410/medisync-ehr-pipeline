"""Extract patient profile + schedule activity data from Axxess EHR.

Per-patient workflow:
  1. Navigate to Patients -> Patient Charts
  2. Iterate through ALL patients in the sidebar list
  3. For each patient:
     a. Click name -> open chart
     b. Click Patient Profile button -> extract demographics from iframe -> Close
     c. Change Schedule Activity date filter to "All"
     d. Scrape every row from the Schedule Activity table
     e. Click the blue download button (Actions column) to download each document
  4. Return list of patient profiles, each containing schedule_activities

RPA is stateless -- extracted data is sent to MediSync backend.
"""

import logging
import os
import re
import glob as glob_mod
import shutil
import time
from datetime import date

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver

logger = logging.getLogger("medisync.extractor.patient")


# ===================================================================
# Public API
# ===================================================================

def navigate_to_patient_charts(driver: WebDriver):
    """Hover Patients menu -> click Patient Charts.

    Selectors and timings match AxxessPatientOrder/Login_2.py.
    """
    try:
        patients_span = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Patients')]"))
        )
        ActionChains(driver).move_to_element(patients_span).perform()
        time.sleep(2)

        charts_div = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Patient Charts')]"))
        )
        charts_div.click()
        time.sleep(5)
        logger.info("Navigated to Patient Charts")
    except Exception as e:
        logger.error("Failed to navigate to Patient Charts: %s", e)
        raise


def extract_all_patients(
    driver: WebDriver, download_dir: str, max_patients: int | None = None,
) -> list[dict]:
    """
    Iterate through every patient in the Patient Charts sidebar.
    For each one: extract profile, extract schedule activities, download docs.
    Returns a list of profile dicts (each with a schedule_activities list).
    If max_patients is set, stops after processing that many patients.
    """
    patients_data = []
    processed_names: set[str] = set()

    patient_elements = _get_sidebar_patients(driver)
    total = len(patient_elements)
    logger.info("Found %d patients in sidebar", total)

    for idx in range(total):
        try:
            patient_elements = _get_sidebar_patients(driver)
            if idx >= len(patient_elements):
                logger.info("Reached end of patient list at index %d", idx)
                break

            el = patient_elements[idx]
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", el
            )
            time.sleep(0.5)

            name = el.text.strip()
            if not name or name in processed_names:
                continue
            processed_names.add(name)

            logger.info("Processing patient %d/%d: %s", idx + 1, total, name)
            el.click()
            time.sleep(3)

            # A) Extract Patient Profile (demographics, episode, physician)
            profile = _open_and_extract_profile(driver)
            profile["sidebar_name"] = name
            if not profile.get("first_name"):
                _parse_sidebar_name(name, profile)

            # B) Change date filter to "All", then scrape schedule activities
            _change_date_filter_to_all(driver)
            mrn = profile.get("mrn", "unknown")
            activities = _extract_schedule_activities(driver, download_dir, mrn)
            profile["schedule_activities"] = activities

            patients_data.append(profile)
            logger.info(
                "Extracted: %s (MRN: %s, %d activities)",
                name, mrn, len(activities),
            )
            if max_patients and len(patients_data) >= max_patients:
                logger.info("Reached max_patients limit (%d), stopping early", max_patients)
                break

        except Exception as e:
            logger.error("Failed on patient index %d: %s", idx, e)
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            continue

    logger.info("Total patients extracted: %d", len(patients_data))
    return patients_data


# ===================================================================
# Sidebar helpers
# ===================================================================

def _get_sidebar_patients(driver: WebDriver) -> list:
    """Return all patient-name elements from the left sidebar."""
    selectors = [
        (By.CSS_SELECTOR, "section.display-patient-name span"),
        (By.CSS_SELECTOR, ".display-patient-name"),
        (By.CSS_SELECTOR, ".patient-list-item"),
        (By.XPATH,
         "//div[contains(@class,'patient')]//a[string-length(normalize-space()) > 2]"),
    ]
    for by, sel in selectors:
        elements = driver.find_elements(by, sel)
        if elements:
            return elements
    return []


# ===================================================================
# Patient Profile extraction (modal / iframe)
# ===================================================================

def _open_and_extract_profile(driver: WebDriver) -> dict:
    """Click Patient Profile button, switch to iframe, extract, close."""
    data = _empty_profile()

    _extract_chart_header(driver, data)

    data["admission_periods"] = _extract_admission_periods(driver)

    try:
        profile_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(),'Patient Profile')]")
            )
        )
        profile_btn.click()
        time.sleep(10)
    except Exception as e:
        logger.warning("Patient Profile button not found: %s", e)
        return data

    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "window_ModalWindow"))
        )
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "printview"))
        )
    except Exception as e:
        logger.warning("Profile modal/iframe not ready: %s", e)
        _close_profile_modal(driver)
        return data

    try:
        expand_btn = driver.find_element(
            By.XPATH,
            "//*[@id='vue-window-container']/section/section/section"
            "/header/section/div/button[1]",
        )
        expand_btn.click()
        time.sleep(5)
    except Exception:
        pass

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        _parse_profile_text(body_text, data)
    except Exception as e:
        logger.warning("Could not read profile body text: %s", e)

    if not data.get("attending_npi"):
        try:
            npi_el = driver.find_element(
                By.XPATH, "//div[text()='NPI: ']/following-sibling::div[1]"
            )
            data["attending_npi"] = npi_el.text.strip()
        except Exception:
            pass

    driver.switch_to.default_content()
    _close_profile_modal(driver)

    return data


def _extract_chart_header(driver: WebDriver, data: dict):
    """Pull MRN, episode, SOC from the chart header."""
    try:
        mrn_label = driver.find_element(
            By.XPATH, "//label[contains(text(), 'MRN:')]"
        )
        mrn_span = mrn_label.find_element(By.XPATH, "following-sibling::span")
        data["mrn"] = mrn_span.text.strip().lstrip("#")
    except Exception:
        try:
            header = driver.find_element(By.XPATH, "//*[contains(text(),'MRN:')]")
            m = re.search(r"MRN:\s*([\w\-]+)", header.text)
            if m:
                data["mrn"] = m.group(1)
        except Exception:
            pass

    try:
        ep_label = driver.find_element(
            By.XPATH, "//label[contains(text(), 'Episode')]"
        )
        ep_span = ep_label.find_element(By.XPATH, "following-sibling::section/span")
        parts = ep_span.text.strip().split(" - ")
        if len(parts) == 2:
            data["episode"] = {
                "start_date": _parse_date(parts[0].strip()),
                "end_date": _parse_date(parts[1].strip()),
            }
    except Exception:
        pass

    try:
        soc_label = driver.find_element(
            By.XPATH, "//label[contains(text(), 'Start of Care Date')]"
        )
        soc_span = soc_label.find_element(
            By.XPATH, "following-sibling::div/section/span"
        )
        soc = _parse_date(soc_span.text.strip())
        if soc:
            ep = data.get("episode") or {}
            ep["soc_date"] = soc
            data["episode"] = ep
    except Exception:
        pass


# ===================================================================
# Admission Periods extraction
# ===================================================================

def _extract_admission_periods(driver: WebDriver) -> list[dict]:
    """Click 'View Admission Periods', scrape the table, close the dialog."""
    periods: list[dict] = []

    # Step 1: Click the "View Admission Periods" link on the chart header
    try:
        link = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable(
                (By.XPATH,
                 "//span[contains(@class,'text-link') and contains(.,'View Admission Periods')]"
                 " | //a[contains(.,'View Admission Periods')]"
                 " | //*[contains(text(),'View Admission Periods')]")
            )
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
        time.sleep(0.5)
        link.click()
        time.sleep(3)
    except Exception as e:
        logger.info("View Admission Periods link not found or not clickable: %s", e)
        return periods

    # Step 2: Wait for the dialog / table to appear
    try:
        WebDriverWait(driver, 12).until(
            lambda d: len(
                d.find_elements(
                    By.XPATH,
                    "//*[contains(normalize-space(.), 'Patient Admission Periods')]"
                    " | //div[starts-with(@id,'window_patientmanageddates') and contains(@class,'window')]"
                    " | //div[starts-with(@id,'window_patientmanageddates_content')]",
                )
            ) > 0
        )
        time.sleep(1)
    except Exception as e:
        logger.warning("Admission Periods dialog did not appear: %s", e)
        _close_admission_periods_dialog(driver)
        return periods

    # Step 3: Scrape rows from the table
    try:
        # Prefer rows from the specific Admission Periods window content container.
        rows = driver.find_elements(
            By.XPATH,
            "//div[starts-with(@id,'window_patientmanageddates_content')]//table//tr[td]"
        )
        if not rows:
            rows = driver.find_elements(
                By.XPATH,
                "//table[.//th[contains(normalize-space(.),'Admission Date')]]//tbody/tr"
            )

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 3:
                continue
            admission_raw = cells[0].text.strip()
            discharge_raw = cells[1].text.strip()
            current_raw = cells[2].text.strip() if len(cells) > 2 else ""
            episodes_raw = cells[3].text.strip() if len(cells) > 3 else ""

            periods.append({
                "admission_date": _parse_date(admission_raw),
                "discharge_date": _parse_date(discharge_raw) if discharge_raw else None,
                "is_current": current_raw.strip().lower().startswith("yes"),
                "associated_episodes": episodes_raw.strip().lower().startswith("yes"),
            })
        logger.info("Extracted %d admission periods", len(periods))
    except Exception as e:
        logger.warning("Failed to scrape admission periods table: %s", e)

    # Step 4: Close the dialog
    _close_admission_periods_dialog(driver)
    return periods


def _close_admission_periods_dialog(driver: WebDriver):
    """Close the Admission Periods popup window."""
    close_selectors = [
        # Axxess window header close icon (from your screenshot)
        (By.XPATH,
         "//div[contains(@class,'window-top')]"
         "[.//*[contains(normalize-space(.), 'Patient Admission Periods')]]"
         "//span[contains(@class,'window-close')]"),
        (By.XPATH, "//span[contains(@class,'window-close-span')]//span[contains(@class,'window-close')]"),
        (By.XPATH, "//span[contains(@class,'window-close')]"),
        (By.XPATH,
         "//*[contains(text(),'Patient Admission Periods')]"
         "/ancestor::div[1]//button[contains(@class,'close')]"),
        (By.XPATH,
         "//*[contains(text(),'Patient Admission Periods')]"
         "/ancestor::div[contains(@class,'modal') or contains(@class,'window')]"
         "//button[contains(@class,'close')]"),
        (By.XPATH, "//button[contains(@class,'close') and @aria-label='Close']"),
        (By.XPATH, "//button[normalize-space()='Close']"),
        (By.LINK_TEXT, "Close"),
    ]
    for by, sel in close_selectors:
        try:
            btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, sel)))
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
            logger.debug("Closed admission periods dialog via: %s='%s'", by, sel)
            return
        except Exception:
            continue

    try:
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(1)
        logger.debug("Closed admission periods dialog via Escape key")
    except Exception as e:
        logger.warning("Could not close admission periods dialog: %s", e)


# ===================================================================
# Schedule Activity table extraction
# ===================================================================

def _change_date_filter_to_all(driver: WebDriver):
    """Change the Date dropdown above the Schedule Activity table to 'All'.

    The Axxess UI has multiple ac-multiselect components on the Patient Charts
    page (Branch, Show, Date, etc.). We must target the Schedule Activity Date
    multiselect specifically — the one that displays "This Episode" before it
    is changed — rather than the first multiselect in the DOM.
    """
    trigger = None
    try:
        trigger = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//div[contains(@class, 'ac-multiselect')]"
                    "[.//div[contains(@class, 'ac-multiselect__input') "
                    "and normalize-space()='This Episode']]"
                    "//div[contains(@class, 'ac-multiselect__input')]",
                )
            )
        )
    except Exception:
        # Fallback: use the Date label if the selected value text is rendered
        # differently for this patient/state.
        try:
            trigger = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//label[normalize-space()='Date']"
                        "/following-sibling::div[contains(@class, 'ac-multiselect')][1]"
                        "//div[contains(@class, 'ac-multiselect__input')]"
                        " | "
                        "//span[normalize-space()='Date']"
                        "/following::div[contains(@class, 'ac-multiselect')][1]"
                        "//div[contains(@class, 'ac-multiselect__input')]",
                    )
                )
            )
        except Exception as e:
            logger.warning("Could not locate the Date filter multiselect: %s", e)
            return

    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", trigger
        )
        time.sleep(0.5)
        trigger.click()
        time.sleep(1)
        logger.info("Opened Date filter dropdown")
    except Exception as e:
        logger.warning("Could not click Date filter dropdown: %s", e)
        return

    # Step 2: Click the "All" option inside the now-open dropdown menu
    try:
        all_option = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//div[contains(@class, 'ac-multiselect--active')]"
                    "//span[contains(@class, 'ac-multiselect__option-text') "
                    "and normalize-space()='All']",
                )
            )
        )
        all_option.click()
        time.sleep(3)
        logger.info("Date filter changed to All")
    except Exception:
        try:
            all_div = driver.find_element(
                By.XPATH,
                "//div[contains(@class, 'ac-multiselect--active')]"
                "//div[contains(@class, 'ac-multiselect__option')]"
                "[.//span[normalize-space()='All']]"
            )
            all_div.click()
            time.sleep(3)
            logger.info("Date filter changed to All (fallback)")
        except Exception as e:
            logger.warning("Could not select 'All' in date filter: %s", e)


def _extract_schedule_activities(
    driver: WebDriver, download_dir: str, mrn: str,
) -> list[dict]:
    """Scrape the Schedule Activity table and download documents."""
    activities = []
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "tr.patient-activity-row")
            )
        )
        rows = driver.find_elements(By.CSS_SELECTOR, "tr.patient-activity-row")
        logger.info("Schedule Activity table: %d rows", len(rows))

        for row_idx, row in enumerate(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                # Schedule Activity column order (0-based):
                # 0=A/checkbox, 1=Task, 2=Schedule Date, 3=Assigned To,
                # 4=icon/extra, 5=Status, 6=Comments, ... , last=Actions
                if len(cells) < 6:
                    continue

                task = cells[1].text.strip()
                schedule_date = cells[2].text.strip()
                assigned_to = cells[3].text.strip()
                status = cells[5].text.strip()

                if not task:
                    continue

                doc_path = _download_activity_document(
                    driver, row, task, schedule_date, download_dir, mrn
                )

                activities.append({
                    "task": task,
                    "schedule_date": schedule_date,
                    "assigned_to": assigned_to,
                    "status": status,
                    "document_path": doc_path,
                })
                logger.info(
                    "  Row %d: %s (%s) - %s %s",
                    row_idx + 1, task, schedule_date, status,
                    "[downloaded]" if doc_path else "[no doc]",
                )
            except Exception as e:
                logger.warning("  Row %d scrape failed: %s", row_idx + 1, e)
                continue

    except Exception as e:
        logger.error("Schedule Activity table not found: %s", e)

    return activities


def _download_activity_document(
    driver: WebDriver,
    row,
    task: str,
    schedule_date: str,
    download_dir: str,
    mrn: str,
) -> str | None:
    """Click the blue download button in the Actions column, wait for file.

    The viewer modal MUST be closed before returning so subsequent rows
    can be processed. Close is attempted via multiple strategies and a
    guaranteed Escape-key fallback.
    """
    # Snapshot existing files before download
    existing = set(os.listdir(download_dir)) if os.path.isdir(download_dir) else set()

    # Find the Actions column cell (has class "actions-column")
    try:
        actions_cell = row.find_element(By.CSS_SELECTOR, "td.actions-column")
    except Exception:
        try:
            actions_cell = row.find_elements(By.TAG_NAME, "td")[-1]
        except Exception:
            return None

    download_btn = None
    btn_selectors = [
        "a span.img.icon.print",
        "a span.icon.print",
        "a .print",
        "a.btn-primary",
        "button.btn-primary",
        "a[class*='btn']",
        "a",
        "button",
        "i[class*='fa-']",
    ]
    for sel in btn_selectors:
        found = actions_cell.find_elements(By.CSS_SELECTOR, sel)
        for btn in found:
            if "post to" in (btn.text or "").lower():
                continue
            # If we matched an inner element (span inside <a>), click the parent <a>
            try:
                parent = btn.find_element(By.XPATH, "./ancestor::a")
                download_btn = parent
            except Exception:
                download_btn = btn
            break
        if download_btn:
            break

    if not download_btn:
        return None

    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", download_btn
        )
        time.sleep(0.5)
        download_btn.click()
        time.sleep(5)
    except Exception as e:
        logger.debug("Could not click download button: %s", e)
        return None

    # --- Handle the document viewer modal that Axxess opens ---
    # The viewer shows a PDF with Print/Close buttons at the bottom.
    # We must close it regardless of whether a separate download button
    # exists inside it, otherwise the modal blocks all subsequent rows.
    viewer_opened = _is_viewer_modal_open(driver)

    if viewer_opened:
        # Try to click an explicit download button inside the viewer first
        try:
            dl_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.ID, "downloadbutton"))
            )
            dl_btn.click()
            time.sleep(3)
        except Exception:
            pass

        # Always close the viewer before continuing
        _close_document_viewer(driver)

    # Wait for a new file to appear in the download directory
    new_file = _wait_for_new_download(download_dir, existing, timeout=20)
    if not new_file:
        return None

    # Rename the file: {mrn}_{task_sanitized}_{date}.pdf
    safe_task = re.sub(r"[^\w\-]", "_", task).strip("_")
    safe_date = schedule_date.replace("/", "")
    ext = os.path.splitext(new_file)[1] or ".pdf"
    new_name = f"{mrn}_{safe_task}_{safe_date}{ext}"
    dest = os.path.join(download_dir, new_name)

    try:
        src = os.path.join(download_dir, new_file)
        if src != dest:
            shutil.move(src, dest)
    except Exception as e:
        logger.warning("Could not rename downloaded file: %s", e)
        dest = os.path.join(download_dir, new_file)

    return dest


def _is_viewer_modal_open(driver: WebDriver) -> bool:
    """Return True if the Axxess document viewer modal is currently visible."""
    indicators = [
        (By.ID, "downloadbutton"),
        (By.CSS_SELECTOR, "button[onclick*='close'], button[data-dismiss='modal']"),
        (By.XPATH, "//button[normalize-space()='Close']"),
        (By.XPATH, "//a[normalize-space()='Close']"),
        (By.CSS_SELECTOR, ".modal.in, .modal[style*='display: block']"),
        (By.CSS_SELECTOR, "#window_ModalWindow"),
    ]
    for by, sel in indicators:
        try:
            elements = driver.find_elements(by, sel)
            if elements and elements[0].is_displayed():
                return True
        except Exception:
            pass
    return False


def _close_document_viewer(driver: WebDriver):
    """Robustly close the Axxess document viewer modal.

    Tries multiple selectors in order, then falls back to Escape key.
    Always ends with a switch to default content so the main page is active.
    """
    close_strategies = [
        # Text "Close" button/link (visible in the screenshot at bottom of viewer)
        (By.XPATH, "//button[normalize-space()='Close']"),
        (By.XPATH, "//a[normalize-space()='Close']"),
        (By.XPATH, "//input[@value='Close']"),
        # Bootstrap modal close (×)
        (By.CSS_SELECTOR, "button.close[data-dismiss='modal']"),
        (By.CSS_SELECTOR, ".modal-footer button"),
        # Generic close class
        (By.CLASS_NAME, "close"),
        # Link text
        (By.LINK_TEXT, "Close"),
        (By.PARTIAL_LINK_TEXT, "Close"),
    ]

    closed = False
    for by, sel in close_strategies:
        try:
            btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, sel)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            btn.click()
            time.sleep(2)
            closed = True
            logger.debug("Closed document viewer via: %s='%s'", by, sel)
            break
        except Exception:
            continue

    if not closed:
        # Fallback: press Escape — works for most modal overlays
        try:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(2)
            logger.debug("Closed document viewer via Escape key")
        except Exception as e:
            logger.warning("Could not close document viewer: %s", e)

    # Always switch back to main document context
    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    # Extra safety: if modal is still open after all attempts, try JS dismiss
    if _is_viewer_modal_open(driver):
        try:
            driver.execute_script(
                "var modals = document.querySelectorAll('.modal.in, .modal[style*=\"display: block\"]');"
                "modals.forEach(function(m){ m.style.display='none'; m.classList.remove('in'); });"
                "var backdrops = document.querySelectorAll('.modal-backdrop');"
                "backdrops.forEach(function(b){ b.remove(); });"
                "document.body.classList.remove('modal-open');"
            )
            time.sleep(1)
            logger.warning("Closed stuck document viewer via JS injection")
        except Exception as e:
            logger.error("JS modal dismiss failed: %s", e)


def _wait_for_new_download(
    directory: str, existing: set[str], timeout: int = 30,
) -> str | None:
    """Wait for a new file (not in `existing`) to appear in directory."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.isdir(directory):
            current = set(os.listdir(directory))
            new_files = current - existing
            complete = [
                f for f in new_files
                if not f.endswith(".crdownload") and not f.endswith(".tmp")
            ]
            if complete:
                return complete[0]
        time.sleep(1)
    return None


# ===================================================================
# Profile text parsing
# ===================================================================

def _parse_profile_text(text: str, data: dict):
    """Parse the full-text dump of the Patient Profile document.

    Labels and values are on SEPARATE lines in the Axxess PDF, e.g.:
        DOB:
        02/21/1939
    All patterns use re.DOTALL + re.IGNORECASE (applied in _rx).
    """

    # --- Demographics ---
    data["dob"] = _parse_date(_rx(text, r"DOB:\s*(\d{1,2}/\d{1,2}/\d{4})") or "")
    if not data.get("mrn"):
        data["mrn"] = _rx(text, r"MRN:\s*([\w\-]+)") or ""
    data["phone"] = _rx(text, r"Phone:\s*(\(\d{3}\)\s*\d{3}[\-\s]\d{4})")
    data["alternate_phone"] = _rx(
        text, r"Alternate Phone:\s*(\(\d{3}\)\s*\d{3}[\-\s]\d{4})"
    )
    data["ssn"] = _rx(text, r"Social Security Number:\s*(\d+)")
    data["sex"] = _rx(text, r"Sex:\s*(\w+)")
    data["race"] = _rx(text, r"Race:\s*(.+?)(?:Ethnicity:)", _normalize=True)

    # Ethnicity can span two lines ("E. Yes, another Hispanic, Latino, or\nSpanish origin")
    eth_raw = _rx(text, r"Ethnicity:\s*(.+?)(?:Marital Status:)", _normalize=True)
    data["ethnicity"] = eth_raw

    data["marital_status"] = _rx(text, r"Marital Status:\s*(.+?)(?:Primary Language:)", _normalize=True)
    data["primary_language"] = _rx(text, r"Primary Language:\s*(.+?)(?:Interpreter:|\n)", _normalize=True)
    data["interpreter"] = _rx(text, r"Interpreter:\s*(.+?)(?:Service Location:|\n)", _normalize=True)
    data["service_location"] = _rx(text, r"Service Location:\s*(.+?)(?:Auxiliary Aids:|\n)", _normalize=True)
    data["auxiliary_aids"] = _rx(text, r"Auxiliary Aids:\s*(.+?)(?:Payer|\n)", _normalize=True)

    # Primary Address: value runs until Mailing Address or Email Address
    addr = _rx(text, r"Primary Address:\s*(.+?)(?:Mailing Address:|Email Address:)")
    if addr:
        data["primary_address"] = " ".join(addr.split())

    mailing = _rx(text, r"Mailing Address:\s*(.+?)(?:Email Address:|Sex:)")
    if mailing:
        data["mailing_address"] = " ".join(mailing.split())

    email = _rx(text, r"Email Address:\s*(\S+)")
    data["email"] = None if email in ("N/A", "n/a") else email

    # --- Payer ---
    data["primary_insurance"] = _rx(text, r"Primary Insurance:\s*(.+?)(?:Medicare Part A|Medicare Part B|\n)", _normalize=True)
    data["medicare_part_a_effective"] = _parse_date(
        _rx(text, r"Medicare Part A Effective:\s*(\d{1,2}/\d{1,2}/\d{4})") or ""
    )
    data["medicare_part_b_effective"] = _parse_date(
        _rx(text, r"Medicare Part B Effective:\s*(\d{1,2}/\d{1,2}/\d{4})") or ""
    )
    data["mbi_number"] = _rx(text, r"MBI Number:\s*(\S+)")
    data["existing_prior_episodes"] = _rx(text, r"Existing Prior Episodes\s*(.+?)(?=Secondary Insurance:|\n)", _normalize=True)
    sec_ins = _rx(text, r"Secondary Insurance:\s*(.+?)(?:Advanced Directive|\n)")
    data["secondary_insurance"] = None if sec_ins in ("N/A", "n/a") else sec_ins
    data["advanced_directive_comments"] = _rx(
        text, r"Advanced Directive Comments\s*(.+?)(?:Pharmacy|Allergies|\n)", _normalize=True
    )

    # --- Pharmacy & Allergies ---
    data["pharmacy_name"] = _rx(text, r"Primary:\s*(.+?)(?:Address:|Phone:|\n)", _normalize=True)

    pharm_block = re.search(
        r"Pharmacy\s+Allergies.*?Primary:\s*(.+?)(?=NKD?A\b|Current Episode)",
        text, re.DOTALL | re.IGNORECASE,
    )
    if pharm_block:
        pblock = pharm_block.group(1)
        pa = re.search(r"Address:\s*(.+?)(?=Phone:|\n)", pblock, re.DOTALL | re.IGNORECASE)
        if pa and pa.group(1).strip() not in ("N/A", "n/a", ""):
            data["pharmacy_address"] = " ".join(pa.group(1).split())
        pp = re.search(r"Phone:\s*(\(\d{3}\)\s*\d{3}[\-\s]\d{4})", pblock)
        if pp:
            data["pharmacy_phone"] = pp.group(1).strip()

    nkda = re.search(r"(NKD?A[^\n]*)", text, re.IGNORECASE)
    if nkda:
        data["allergies"] = nkda.group(1).strip()
    else:
        data["allergies"] = _rx(text, r"Allergies\s*(.+?)(?:Advanced Directives|\n)", _normalize=True)

    # Advanced Directives type (e.g. "Surrogate Decision Maker")
    adv_dir = re.search(r"(?:NKD?A|NKA)[^\n]*\n\s*(.+?)(?=\nCurrent Episode)", text, re.IGNORECASE)
    if adv_dir and adv_dir.group(1).strip() not in ("N/A", "n/a", ""):
        data["advanced_directives_type"] = adv_dir.group(1).strip()

    # --- Current Episode ---
    ep_match = re.search(
        r"Current Episode:\s*(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})",
        text,
    )
    if ep_match:
        ep = data.get("episode") or {}
        ep["start_date"] = _parse_date(ep_match.group(1))
        ep["end_date"] = _parse_date(ep_match.group(2))
        data["episode"] = ep

    soc = _rx(text, r"Start of Care Date:\s*(\d{1,2}/\d{1,2}/\d{4})")
    if soc:
        ep = data.get("episode") or {}
        ep["soc_date"] = _parse_date(soc)
        data["episode"] = ep

    # Case Manager appears as "Case Manager:\nName RN Clinical Manager:\nName RN"
    cm_raw = _rx(text, r"Case Manager:\s*(.+?)(?:Clinical Manager:|\n)", _normalize=True)
    data["case_manager"] = cm_raw
    data["clinical_manager"] = _rx(text, r"Clinical Manager:\s*(.+?)(?:Services Required:|\n)", _normalize=True)
    data["primary_clinician"] = _rx(text, r"Primary Clinician:\s*(.+?)(?:Primary Diagnosis:|\n)", _normalize=True)
    data["services_required"] = _rx(text, r"Services Required:\s*(.+?)(?:Primary Clinician:|\n)", _normalize=True)
    data["primary_diagnosis"] = _rx(text, r"Primary Diagnosis:\s*(.+?)(?:Additional Diagnoses:|\n)", _normalize=True)

    additional_raw = _rx(text, r"Additional Diagnoses:\s*(.+?)(?=Physician\(s\)|Attending:)", _normalize=True)
    data["additional_diagnoses"] = additional_raw

    # --- Physicians ---
    att_block = re.search(
        r"Attending:\s*(.+?)(?:Other:|Referring:|Contacts|$)", text, re.DOTALL | re.IGNORECASE
    )
    if att_block:
        block = att_block.group(1)
        first_line = block.split("\n")[0].strip()
        data["attending_physician"] = first_line if first_line else None
        npi = re.search(r"NPI:\s*(\d+)", block)
        if npi:
            data["attending_npi"] = npi.group(1)
        _extract_physician_details(block, data, "attending")

    ref_block = re.search(
        r"Referring:\s*(.+?)(?:Certifying:|Contacts|$)", text, re.DOTALL | re.IGNORECASE
    )
    if ref_block:
        block = ref_block.group(1)
        data["referring_physician"] = block.split("\n")[0].strip() or None
        npi = re.search(r"NPI:\s*(\d+)", block)
        if npi:
            data["referring_npi"] = npi.group(1)

    cert_block = re.search(
        r"Certifying:\s*(.+?)(?:Contacts|Primary Emergency|$)", text, re.DOTALL | re.IGNORECASE
    )
    if cert_block:
        block = cert_block.group(1)
        data["certifying_physician"] = block.split("\n")[0].strip() or None
        npi = re.search(r"NPI:\s*(\d+)", block)
        if npi:
            data["certifying_npi"] = npi.group(1)

    # --- Contacts ---
    ec_block = re.search(
        r"Primary Emergency Contact:\s*(.+?)(?:Secondary Emergency Contact:|$)",
        text, re.DOTALL | re.IGNORECASE
    )
    if ec_block:
        block = ec_block.group(1)
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        data["emergency_contact_name"] = lines[0] if lines else None
        rel = re.search(r"Relationship:\s*(.+)", block)
        data["emergency_contact_relationship"] = rel.group(1).strip() if rel else None
        ph = re.search(r"Phone:\s*(\(\d{3}\)\s*\d{3}[\-\s]\d{4})", block)
        data["emergency_contact_phone"] = ph.group(1).strip() if ph else None

    # --- Legal Representative ---
    legal_block = re.search(
        r"Legal Representative\s*(.+?)(?=Secondary Emergency Contact:|$)",
        text, re.DOTALL | re.IGNORECASE,
    )
    if legal_block:
        lines = [l.strip() for l in legal_block.group(1).splitlines() if l.strip()]
        joined = " ".join(lines)
        if joined and joined not in ("N/A", "n/a"):
            data["legal_representative"] = joined

    # --- Secondary / Tertiary / CAHPS contacts ---
    data["secondary_emergency_contact"] = _rx(
        text, r"Secondary Emergency Contact:\s*(.+?)(?=Tertiary Emergency Contact:|\n)", _normalize=True,
    )
    data["tertiary_emergency_contact"] = _rx(
        text, r"Tertiary Emergency Contact:\s*(.+?)(?=CAHPS Contact:|\n)", _normalize=True,
    )
    data["cahps_contact"] = _rx(
        text, r"CAHPS Contact:\s*(.+?)(?=Referral Information|\n)", _normalize=True,
    )

    # --- Referral info (page 2) ---
    data["referral_date"] = _parse_date(
        _rx(text, r"Referral Date:\s*(\d{1,2}/\d{1,2}/\d{4})") or ""
    )
    data["admission_source"] = _rx(text, r"Admission Source:\s*(.+?)(?:Name of Referral Source:|\n)", _normalize=True)
    data["name_of_referral_source"] = _rx(text, r"Name of Referral Source:\s*(.+?)(?=Community Liaison:|\n)", _normalize=True)
    data["community_liaison"] = _rx(text, r"Community Liaison:\s*(.+?)(?:Internal Referral Source:|\n)", _normalize=True)
    data["internal_referral_source"] = _rx(text, r"Internal Referral Source:\s*(.+?)(?=Facility Referral Source:|\n)", _normalize=True)
    data["facility_referral_source"] = _rx(text, r"Facility Referral Source:\s*(.+?)(?:Face-to-Face|\n)", _normalize=True)
    data["face_to_face_date"] = _parse_date(
        _rx(text, r"Face-to-Face Eval Info:\s*(\d{1,2}/\d{1,2}/\d{4})") or ""
    )
    data["priority_visit_type"] = _rx(text, r"Priority \(Type of Visit\):\s*(.+?)(?:Emergency Triage|\n)", _normalize=True)
    triage = re.search(r"Emergency Triage Level:\s*(\d+)\.", text, re.IGNORECASE)
    data["emergency_triage_level"] = int(triage.group(1)) if triage else None
    triage_desc = re.search(
        r"Emergency Triage Level:\s*\d+\.\s*(.+?)(?=Additional Emergency|$)",
        text, re.DOTALL | re.IGNORECASE,
    )
    if triage_desc:
        data["emergency_triage_description"] = " ".join(triage_desc.group(1).split())

    # --- Emergency Preparedness ---
    data["emergency_preparedness"] = _rx(
        text, r"Additional Emergency Preparedness Information:\s*(.+?)(?=Equipment Needs:)", _normalize=True,
    )
    data["equipment_needs"] = _rx(
        text, r"Equipment Needs:\s*(.+?)(?=INTERIM HEALTHCARE|PATIENT PROFILE|\n)", _normalize=True,
    )

    # --- Patient name (from footer line after "PATIENT PROFILE") ---
    name_match = re.search(r"PATIENT PROFILE\s*\n\s*(.+?)(?:\n|$)", text)
    if name_match:
        full_name = name_match.group(1).strip()
        parts = full_name.split(",", 1)
        if len(parts) >= 2:
            data["last_name"] = parts[0].strip()
            first_parts = parts[1].strip().split()
            data["first_name"] = first_parts[0].rstrip(".") if first_parts else ""


# ===================================================================
# Physician detail helpers
# ===================================================================

def _extract_physician_details(block: str, data: dict, prefix: str):
    """Extract address, phone, fax, and careplan oversight from a physician block."""
    addr = re.search(r"Address:\s*(.+?)(?=Phone:|Fax:)", block, re.DOTALL | re.IGNORECASE)
    if addr:
        val = " ".join(addr.group(1).split())
        if val and val not in ("N/A", "n/a"):
            data[f"{prefix}_address"] = val

    phone = re.search(r"Phone:\s*(\(\d{3}\)\s*\d{3}[\-\s]\d{4})", block)
    if phone:
        data[f"{prefix}_phone"] = phone.group(1).strip()

    fax = re.search(r"Fax:\s*(\(\d{3}\)\s*\d{3}[\-\s]\d{4})", block)
    if fax:
        data[f"{prefix}_fax"] = fax.group(1).strip()

    if prefix == "attending" and "careplan oversight" in block.lower():
        data["careplan_oversight"] = True


# ===================================================================
# Modal / cleanup helpers
# ===================================================================

def _close_profile_modal(driver: WebDriver):
    """Close the Patient Profile modal overlay."""
    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Close"))
        )
        close_btn.click()
        time.sleep(2)
        return
    except Exception:
        pass
    try:
        close_btn = driver.find_element(By.XPATH, "//button[text()='Close']")
        close_btn.click()
        time.sleep(2)
    except Exception:
        logger.debug("Could not find Close button for profile modal")


def _parse_sidebar_name(name: str, data: dict):
    """Parse 'LAST, FIRST M' sidebar format into first/last name."""
    parts = name.split(",", 1)
    data["last_name"] = parts[0].strip().title()
    if len(parts) > 1:
        first_parts = parts[1].strip().split()
        data["first_name"] = first_parts[0].title() if first_parts else ""


# ===================================================================
# Utility
# ===================================================================

def _empty_profile() -> dict:
    return {
        # Identity
        "mrn": "",
        "first_name": "",
        "last_name": "",
        "dob": None,
        "phone": None,
        "alternate_phone": None,
        "ssn": None,
        # Address
        "primary_address": None,
        "mailing_address": None,
        # Demographics
        "email": None,
        "sex": None,
        "race": None,
        "ethnicity": None,
        "marital_status": None,
        "primary_language": None,
        "interpreter": None,
        "service_location": None,
        "auxiliary_aids": None,
        # Payer
        "primary_insurance": None,
        "medicare_part_a_effective": None,
        "medicare_part_b_effective": None,
        "mbi_number": None,
        "existing_prior_episodes": None,
        "secondary_insurance": None,
        "advanced_directive_comments": None,
        # Pharmacy / Allergies / Directives
        "pharmacy_name": None,
        "pharmacy_address": None,
        "pharmacy_phone": None,
        "allergies": None,
        "advanced_directives_type": None,
        # Episode
        "episode": None,
        # Admission Periods
        "admission_periods": [],
        # Clinical
        "case_manager": None,
        "clinical_manager": None,
        "primary_clinician": None,
        "services_required": None,
        "primary_diagnosis": None,
        "additional_diagnoses": None,
        # Physicians
        "attending_physician": None,
        "attending_npi": None,
        "attending_address": None,
        "attending_phone": None,
        "attending_fax": None,
        "careplan_oversight": None,
        "referring_physician": None,
        "referring_npi": None,
        "certifying_physician": None,
        "certifying_npi": None,
        # Emergency Contact
        "emergency_contact_name": None,
        "emergency_contact_relationship": None,
        "emergency_contact_phone": None,
        "legal_representative": None,
        "secondary_emergency_contact": None,
        "tertiary_emergency_contact": None,
        "cahps_contact": None,
        # Referral info (page 2)
        "referral_date": None,
        "admission_source": None,
        "name_of_referral_source": None,
        "community_liaison": None,
        "internal_referral_source": None,
        "facility_referral_source": None,
        "face_to_face_date": None,
        "priority_visit_type": None,
        "emergency_triage_level": None,
        "emergency_triage_description": None,
        # Emergency Preparedness
        "emergency_preparedness": None,
        "equipment_needs": None,
        # Internal
        "sidebar_name": "",
        "schedule_activities": [],
    }


def _rx(text: str, pattern: str, _normalize: bool = False) -> str | None:
    """Extract first capture group; return None for N/A or no match.

    If _normalize=True, collapses internal whitespace/newlines to a single space.
    This is needed for multi-line values like Ethnicity.
    """
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    # Use group(1) if there's a capture group, otherwise group(0) for plain matches
    try:
        result = match.group(1).strip()
    except IndexError:
        result = match.group(0).strip()
    if _normalize:
        result = " ".join(result.split())
    if result in ("N/A", "n/a", ""):
        return None
    return result


def _parse_date(text: str) -> str | None:
    """Convert MM/DD/YYYY (or similar) to ISO date string."""
    if not text:
        return None
    text = text.strip()
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return date(*time.strptime(text, fmt)[:3]).isoformat()
        except ValueError:
            continue
    return None
