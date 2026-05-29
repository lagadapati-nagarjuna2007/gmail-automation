"""
app/logger.py  –  Logging configuration
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(level)

    file_h = RotatingFileHandler(
        LOG_DIR / "agent.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_h.setFormatter(fmt)
    file_h.setLevel(level)

    error_h = RotatingFileHandler(
        LOG_DIR / "errors.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_h.setFormatter(fmt)
    error_h.setLevel(logging.ERROR)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_h)
    root.addHandler(error_h)

    # Silence noisy libs
    for noisy in ("httpx", "httpcore", "urllib3", "googleapiclient", "google"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
