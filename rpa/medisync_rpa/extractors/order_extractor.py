"""Extract orders from Axxess EHR "Orders To Be Sent" grid.

Workflow (mirrors AxxessPatientOrder/Login_2.py order grid flow):
  1. Navigate to View → Orders Management → Orders To Be Sent
  2. Set date filters
  3. Click Generate
  4. Scrape table rows → list of order dicts
  5. Optionally trigger Bulk Print for PDFs
"""

import logging
import time
import os
import glob as glob_mod
from datetime import date, datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver

logger = logging.getLogger("medisync.extractor.order")


def navigate_to_orders(driver: WebDriver):
    """Navigate: View -> Orders Management -> Orders To Be Sent.

    Selectors and timings match AxxessPatientOrder/Login_2.py.
    """
    try:
        view_span = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'View')]"))
        )
        ActionChains(driver).move_to_element(view_span).perform()
        time.sleep(5)

        orders_mgmt_span = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Orders Management')]"))
        )
        ActionChains(driver).move_to_element(orders_mgmt_span).perform()
        time.sleep(10)

        to_be_sent = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class, 'sub-menu-item') and contains(text(), 'Orders To Be Sent')]")
            )
        )
        to_be_sent.click()
        time.sleep(10)
        logger.info("Navigated to Orders To Be Sent")
    except Exception as e:
        logger.error("Failed to navigate to Orders: %s", e)
        raise


def extract_orders(
    driver: WebDriver,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """
    Filter the orders grid by date range, then scrape all rows.

    Returns list of dicts: {order_id, patient_name, order_date, doc_type, physician_name}
    """
    _apply_date_filter(driver, start_date, end_date)

    orders = []
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "div.t-grid-content table tbody tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 5:
                continue
            orders.append({
                "order_id": _cell_text(cells, 0),
                "patient_name": _cell_text(cells, 1),
                "doc_type": _cell_text(cells, 2),
                "physician_name": _cell_text(cells, 3),
                "order_date": _cell_text(cells, 4),
            })
        logger.info("Extracted %d orders from grid", len(orders))
    except Exception as e:
        logger.error("Grid scrape failed: %s", e)

    return orders


def download_order_pdf(driver: WebDriver, order_id: str, download_dir: str) -> str | None:
    """
    Download the PDF for a single order by clicking its print/download link.
    Returns path to downloaded PDF or None.

    Axxess renders a print icon or link per row in the orders grid.
    After clicking, the PDF downloads to Chrome's download directory.
    """
    try:
        row = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, f"//tr[td[contains(text(), '{order_id}')]]")
            )
        )
        download_link = row.find_element(
            By.CSS_SELECTOR, "a.print-order, a[title='Print'], a[href*='Print'], .fa-print"
        )
        download_link.click()
        time.sleep(3)

        pdf_path = _wait_for_download(download_dir, "*.pdf", timeout=30)
        if pdf_path:
            logger.info("Downloaded PDF for order %s: %s", order_id, pdf_path)
        else:
            logger.warning("No PDF downloaded for order %s", order_id)
        return pdf_path
    except Exception as e:
        logger.error("PDF download failed for order %s: %s", order_id, e)
        return None


def _apply_date_filter(driver: WebDriver, start: str | None, end: str | None):
    today = date.today().strftime("%m/%d/%Y")
    start = start or today
    end = end or today

    try:
        start_input = driver.find_element(By.ID, "OrdersManagement_OrdersToBeSent_StartDate")
        start_input.clear()
        start_input.send_keys(start)

        end_input = driver.find_element(By.ID, "OrdersManagement_OrdersToBeSent_EndDate")
        end_input.clear()
        end_input.send_keys(end)

        gen_btn = driver.find_element(
            By.XPATH, "//button[contains(text(), 'Generate') or contains(@id, 'Generate')]"
        )
        gen_btn.click()
        time.sleep(5)
        logger.info("Date filter applied: %s to %s", start, end)
    except Exception as e:
        logger.warning("Date filter failed: %s", e)


def _cell_text(cells: list, idx: int) -> str:
    try:
        return cells[idx].text.strip()
    except (IndexError, AttributeError):
        return ""


def _wait_for_download(directory: str, pattern: str, timeout: int = 60) -> str | None:
    """Poll download directory until a file matching pattern appears."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        matches = glob_mod.glob(os.path.join(directory, pattern))
        # Filter out partial downloads (.crdownload)
        complete = [f for f in matches if not f.endswith(".crdownload")]
        if complete:
            return max(complete, key=os.path.getmtime)
        time.sleep(2)
    return None
