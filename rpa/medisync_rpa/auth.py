"""Axxess EHR authentication.

Mirrors login_to_EHR from AxxessPatientOrder/CommonUtil.py:
  1. Enter email → click Next
  2. Enter password → click Secure Login
  3. Dismiss popups (ok button, notifications)
  4. Select agency (if multi-agency account)
  5. Manual OTP prompt before login completes

Kept as pure Selenium — no database, no state.
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver

logger = logging.getLogger("medisync.auth")


def login_to_axxess(
    driver: WebDriver,
    url: str,
    email: str,
    password: str,
    agency_name: str | None = None,
    otp_callback=None,
):
    """
    Full login flow for Axxess EHR.
    Timings and selectors match AxxessPatientOrder/CommonUtil.login_to_EHR.

    Args:
        otp_callback: Optional callable that returns OTP string.
                      If None, uses input() prompt for manual entry.
    """
    logger.info("Navigating to %s", url)
    driver.get(url)
    time.sleep(10)

    # Email
    email_input = WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='Email Address or Domain']"))
    )
    email_input.clear()
    email_input.send_keys(email)
    driver.find_element(By.CLASS_NAME, "btn-axxess").click()
    logger.info("Email entered, proceeding to password")

    # Password
    password_input = WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "input[placeholder='Password']"))
    )
    password_input.send_keys(password)
    driver.find_element(By.CLASS_NAME, "btn-axxess").click()
    logger.info("Password submitted")

    # Dismiss "ok" popup if present
    try:
        ok_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "btn_ok"))
        )
        ok_btn.click()
    except Exception:
        pass

    time.sleep(5)

    # Handle OTP / MFA — prompt user to complete it manually, then press Enter
    _handle_otp(driver, otp_callback)

    # Dismiss notification overlay (exact XPath from AxxessPatientOrder)
    try:
        notify_close = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='vue-app']/div[1]/div/button"))
        )
        notify_close.click()
    except Exception:
        pass

    time.sleep(10)

    # Agency selection for multi-agency accounts
    if agency_name:
        try:
            agency_btn = WebDriverWait(driver, 25).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//button[contains(normalize-space(), '{agency_name}')]")
                )
            )
            agency_btn.click()
            logger.info("Selected agency: %s", agency_name)
            time.sleep(10)
        except Exception:
            logger.warning("Agency selection skipped — button not found for '%s'", agency_name)

    logger.info("Login complete")


def _handle_otp(driver: WebDriver, otp_callback):
    """
    OTP handling matching the reference project style:
    prompt the user to complete OTP in the browser, then press Enter to continue.
    """
    try:
        otp_input = WebDriverWait(driver, 8).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "input[placeholder*='code'], input[placeholder*='OTP'], input[name*='otp']")
            )
        )
    except Exception:
        return

    logger.info("OTP screen detected")
    if otp_callback:
        code = otp_callback()
    else:
        code = input(">> Enter OTP code and press ENTER: ").strip()

    otp_input.send_keys(code)

    try:
        submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .btn-axxess")
        submit.click()
    except Exception:
        pass

    time.sleep(5)
    logger.info("OTP submitted")
