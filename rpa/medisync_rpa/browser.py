"""Chrome browser lifecycle management.

Based on patterns from AxxessPatientOrder/CommonUtil.py but cleaned up
for single-responsibility and configurability.
"""

import logging
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from medisync_rpa.config import ChromeConfig

logger = logging.getLogger("medisync.browser")


def create_driver(config: ChromeConfig) -> webdriver.Chrome:
    download_dir = str(Path(config.download_dir).resolve())
    Path(download_dir).mkdir(parents=True, exist_ok=True)

    options = Options()
    if config.headless:
        options.add_argument("--headless=new")

    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    logger.info("Chrome driver initialized, downloads -> %s", download_dir)
    return driver


def close_driver(driver: webdriver.Chrome):
    try:
        driver.quit()
        logger.info("Chrome driver closed")
    except Exception as e:
        logger.warning("Error closing driver: %s", e)
