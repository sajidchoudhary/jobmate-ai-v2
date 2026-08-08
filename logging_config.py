# Shared logging setup: console + rotating file (logs/app.log). Call setup_logging()
# once at process startup, before any node code runs.
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "app.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    # Guards against duplicate handlers on Streamlit reruns, which re-execute
    # app.py's top level in the same process without re-importing this module.
    if _configured:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _configured = True
