import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any
import zoneinfo  # Python 3.9+ stdlib for tz-aware datetimes

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
LOCAL_FORMAT = "%Y-%m-%d_%H-%M-%S"  # Filenames: 2026-02-05_19-17-30
DATE_FOLDER_FORMAT = "%Y-%m-%d"     # Folders: 2026-02-05


def get_local_datetime(tz_name: str = "UTC") -> datetime:
    """Get tz-aware datetime for run_id/date_folder. Import from logger."""
    tz = zoneinfo.ZoneInfo(tz_name)
    return datetime.now(tz)


class JsonFormatter(logging.Formatter):
    """Render all log records as single-line JSON with LOCAL timestamps.
    
    Log CONTENT uses local time (user-friendly). XML/API data stays UTC per outline.md.
    """
    def __init__(self, tz_name: str = "America/Boise"):
        self.tz = zoneinfo.ZoneInfo(tz_name)
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        # LOCAL timestamp for log content (user timezone)
        local_dt = datetime.fromtimestamp(record.created, tz=self.tz)
        base: Dict[str, Any] = {
            "timestamp": local_dt.strftime(UTC_FORMAT),  # Still ISO8601 format
            "level": record.levelname,
            "module": record.name,
        }

        # Allow upstream to attach structured data via `extra`
        for key, value in record.__dict__.items():
            if key in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "levelno", "lineno", "msecs",
                "message", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info",
                "thread", "threadName",
            ):
                continue
            base[key] = value

        base["message"] = record.getMessage()
        return json.dumps(base, separators=(",", ":"), ensure_ascii=False)


def _make_rotating_handler(
    logfile: str,
    tz_name: str,  # ← ADD THIS PARAMETER
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        logfile,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    # Pass local timezone to formatter (MST for Nampa, ID)
    handler.setFormatter(JsonFormatter(tz_name))
    handler.setLevel(logging.DEBUG)
    return handler


def setup_logging(
    log_dir: str,
    run_id: str,
    tz_name: str,  # ← FIXED: Added tz_name parameter for RunManager
    log_level: str = "DEBUG",
) -> Dict[str, logging.Logger]:
    """
    Initialize structured logging for this run.
    
    run_id: Use LOCAL time format from RunManager (2026-02-05_19-08-30).
           Log FILENAMES: Local time (user timezone).
           Log CONTENT: Local timestamps. 
           XML/API data: UTC (no changes here).
           
    Returns dict of component loggers: processor, sports_api, xml_filter, generic.
    """
    os.makedirs(log_dir, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.DEBUG)

    # Root logger minimal config; attach handlers only to named loggers
    logging.basicConfig(level=logging.WARNING)

    def _build_logger(name: str, filename_suffix: str) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False

        # Avoid duplicate handlers if setup_logging called twice
        logger.handlers.clear()

        logfile = os.path.join(log_dir, f"{run_id}_{filename_suffix}.log")
        handler = _make_rotating_handler(logfile, tz_name)
        logger.addHandler(handler)
        return logger

    # Per-component log files (local-timed via run_id)
    processor_logger = _build_logger("processor", "processor")
    sports_api_logger = _build_logger("sports_api", "sports_api")
    xml_filter_logger = _build_logger("xml_filter", "xml_filter")
    main_logger = _build_logger("main", "main")

    # Common context hook (future Filters)
    for lg in (processor_logger, sports_api_logger, xml_filter_logger, main_logger):
        lg = lg  # placeholder

    return {
        "processor": processor_logger,
        "sports_api": sports_api_logger,
        "xml_filter": xml_filter_logger,
        "main": main_logger,
    }


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper: logger = get_logger("processor")"""
    return logging.getLogger(name)


# EXPLICIT PUBLIC API
__all__ = [
    "setup_logging",
    "get_logger", 
    "get_local_datetime",
    "UTC_FORMAT",
    "LOCAL_FORMAT", 
    "DATE_FOLDER_FORMAT",
]
