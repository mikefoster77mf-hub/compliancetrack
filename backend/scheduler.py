"""Background scheduler for email reminders.

Runs check_and_send() once per day. Starts when the FastAPI app starts
via a lifespan event. Uses a simple threading.Timer loop for MVP.
"""

import threading
import time
import logging
from datetime import datetime

from reminders import check_and_send

logger = logging.getLogger("scheduler")


def _run_once():
    """Execute one reminder check cycle and schedule the next."""
    logger.info("Scheduler: starting reminder check")
    start = time.time()
    try:
        check_and_send()
        logger.info(f"Scheduler: reminder check completed in {time.time() - start:.1f}s")
    except Exception as e:
        logger.error(f"Scheduler: reminder check failed: {e}")

    # Schedule next run ~24 hours from now
    # Use 23.5 hours to avoid exact-hour alignment drift
    next_run = 23.5 * 60 * 60  # seconds
    logger.info(f"Scheduler: next run in {next_run / 3600:.1f} hours")
    threading.Timer(next_run, _run_once).start()


def start_scheduler():
    """Start the daily reminder scheduler (non-blocking).

    Called from FastAPI lifespan on_startup.
    """
    logger.info("Scheduler: starting background reminder scheduler")
    t = threading.Timer(30, _run_once)  # first run after 30 seconds (let app warm up)
    t.daemon = True
    t.start()
    logger.info("Scheduler: background thread started")
