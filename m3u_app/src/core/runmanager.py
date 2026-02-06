# src/core/runmanager.py
import os
import shutil
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict

from .config_loader import ConfigLoader, ConfigError
from .logger import (
    setup_logging, get_local_datetime,
    LOCAL_FORMAT, DATE_FOLDER_FORMAT
)


@dataclass
class RunContext:
    """Immutable per-run context shared across modules."""
    run_id: str
    date_folder: str
    log_dir: str              # /opt/m3uapp/logs/2026-02-05/2026-02-05_19-27-30
    diagnostics_dir: str      # /opt/m3uapp/logs/2026-02-05/2026-02-05_19-27-30/diagnostics
    config_loader: ConfigLoader  # Pass loader instance, access via dot notation
    loggers: Dict[str, object]   # processor, sports_api, xml_filter, main


class RunManager:
    """
    Handles per-run initialization exactly per outline spec:
    - Load configs via ConfigLoader.load_all() (single call)
    - Create timestamped log folder: logs/YYYY-MM-DD/YYYY-MM-DD_HH-MM-SS/
    - Create diagnostics/ subfolder  
    - Setup structured JSON logging with run_id prefix + config-driven timezone
    - Cleanup old runs if settings.cleanup_on_startup
    - Atomic 'current' symlink update
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.config_loader = ConfigLoader(base_dir)
        self.context: RunContext | None = None

    def initialize(self) -> RunContext:
        # 1. Load ALL configs (creates missing, fails if hard configs auto-created)
        self.config_loader.load_all()  # Void return, populates self.config_loader.*

        # 2. Access config via loader instance (dot notation works post-load_all)
        config = self.config_loader  # Alias for readability
        tz_name = config.settings.timezone        # NEW: "America/Boise"
        log_level = config.settings.log_level
        log_retention_days = config.settings.log_retention_days
        cleanup_on_startup = config.settings.cleanup_on_startup
        base_log_dir = config.paths.log_dir

        # 3. Generate LOCAL run ID/date via logger.py (config-driven timezone)
        run_dt = get_local_datetime(tz_name)      # Uses config.settings.timezone
        run_id = run_dt.strftime(LOCAL_FORMAT)    # "%Y-%m-%d_%H-%M-%S"
        date_folder = run_dt.strftime(DATE_FOLDER_FORMAT)  # "%Y-%m-%d"

        # 4. Create exact log dir structure per logger.py spec
        run_root = os.path.join(base_log_dir, date_folder, run_id)
        diagnostics_dir = os.path.join(run_root, "diagnostics")
        os.makedirs(diagnostics_dir, exist_ok=True)

        # 5. Setup logging BEFORE cleanup/symlink (config-driven timezone)
        loggers = setup_logging(
            log_dir=run_root,
            run_id=run_id,
            tz_name=tz_name,      # REQUIRED by logger.py
            log_level=log_level,
        )

        main_logger = loggers["main"]
        main_logger.info(
            "Run initialized",
            extra={
                "step": "run_init",
                "run_id": run_id,
                "date_folder": date_folder,
                "log_dir": run_root,
                "base_log_dir": base_log_dir,
                "timezone": tz_name,
            },
        )

        # 6. Cleanup old runs if enabled (AFTER logging setup)
        if cleanup_on_startup:
            self._cleanup_old_runs(base_log_dir, log_retention_days, main_logger)

        # 7. Atomic symlink update (AFTER logging setup)
        self._update_current_symlink(base_log_dir, run_root, main_logger)

        # 8. Create immutable context with config_loader instance
        self.context = RunContext(
            run_id=run_id,
            date_folder=date_folder,
            log_dir=run_root,
            diagnostics_dir=diagnostics_dir,
            config_loader=self.config_loader,
            loggers=loggers,
        )
        return self.context

    def _cleanup_old_runs(self, base_logdir: str, retention_days: int, logger) -> None:
        """Delete date folders older than retention_days per outline."""
        cutoff = get_local_datetime().date() - timedelta(days=retention_days)
        try:
            for name in os.listdir(base_logdir):
                date_path = os.path.join(base_logdir, name)
                if not os.path.isdir(date_path):
                    continue
                try:
                    folder_date = datetime.strptime(name, DATE_FOLDER_FORMAT).date()
                except ValueError:
                    continue  # Skip non-date folders
                if folder_date < cutoff:
                    shutil.rmtree(date_path, ignore_errors=True)
                    logger.info(
                        "Old log folder removed",
                        extra={"step": "log_cleanup", "folder": date_path},
                    )
        except FileNotFoundError:
            pass  # First run, log dir didn't exist yet

    def _update_current_symlink(self, base_logdir: str, run_root: str, logger) -> None:
        """Atomic symlink update: tmp → rename per outline."""
        current_link = os.path.join(base_logdir, "current")
        tmp_link = current_link + ".tmp"
        
        try:
            # Atomic: create temp → rename
            if os.path.lexists(tmp_link):
                os.remove(tmp_link)
            os.symlink(run_root, tmp_link)
            os.replace(tmp_link, current_link)
            logger.info(
                "Current symlink updated", 
                extra={"step": "symlink_update", "target": run_root}
            )
        except OSError as e:
            logger.warning(
                "Symlink update failed",
                extra={"step": "symlink_update", "target": run_root, "error": str(e)}
            )
