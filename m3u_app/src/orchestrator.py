# src/orchestrator.py - Updated with Phase 1 core modules
"""
Main cron entrypoint. Initializes RunManager + core modules.
Phase 2+ business logic to be added here.
"""
import sys
import os
from pathlib import Path
from datetime import datetime

from .core.runmanager import RunManager, RunContext, ConfigError
from .core.diagnostic_collector import DiagnosticCollector
from .core.lineup_manager import SportsLineupManager
from .core.sports_lookups import build_sports_lookups
from .core.entities import SportsLookups


def main() -> int:
    base_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    manager = RunManager(base_dir)

    try:
        ctx = manager.initialize()
    except ConfigError as e:
        print(f"Config error, exiting: {e}", file=sys.stderr)
        return 1

    main_logger = ctx.loggers["main"]
    main_logger.info(
        "Orchestrator startup complete - Phase 1 core ready",
        extra={"step": "startup", "run_id": ctx.run_id},
    )
    
    # ===== PHASE 1 CORE MODULES INITIALIZED =====
    diagnostics = DiagnosticCollector(
        base_dir=Path(ctx.config.paths.log_dir) / ctx.date_folder,
        run_id=ctx.run_id
    )
    
    # Build immutable lookups from sports_config.json
    lookups: SportsLookups = build_sports_lookups(ctx.config.sports_config)
    
    # League managers dict (populated during M3U processing)
    managers = {}  # league_key → SportsLineupManager
    
    main_logger.info(
        "Core modules initialized",
        extra={
            "step": "core_init",
            "leagues": list(lookups.leagues.keys()),
            "total_teams": len(lookups.team_index),
            "diagnostics": "ready"
        }
    )
    
    # ===== PHASE 2+ BUSINESS LOGIC HERE =====
    # for provider in ctx.config.m3u_sources:
    #     process_provider(provider, ctx, diagnostics, lookups, managers)
    # 
    # diagnostics.dump_all()
    
    main_logger.info(
        "Orchestrator shutdown - Phase 1 test complete", 
        extra={"step": "shutdown"}
    )
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
