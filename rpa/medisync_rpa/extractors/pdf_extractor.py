"""PDF file utilities for per-order downloads.

Each order has its own PDF — no bulk splitting needed.
RPA downloads one PDF per order and names it with the order_id
to guarantee mapping integrity.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger("medisync.extractor.pdf")


def rename_to_order(source_path: str, order_id: str, output_dir: str) -> str:
    """
    Rename/move a downloaded PDF to include the order_id in the filename.
    Returns the new path.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    dest = output / f"order_{order_id}.pdf"
    shutil.move(source_path, dest)
    logger.info("Renamed PDF → %s", dest.name)
    return str(dest)
