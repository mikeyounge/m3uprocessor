# src/orchestrator.py
import sys
import os

from .core.runmanager import RunManager, ConfigError


def main() -> int:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manager = RunManager(base_dir)

    try:
        ctx = manager.initialize()
    except ConfigError as e:
        # Hard-fail: configloader already logged critical and created templates
        print(f"Config error, exiting: {e}", file=sys.stderr)
        return 1

    main_logger = ctx.loggers["main"]
    main_logger.info(
        "Orchestrator startup complete",
        extra={"step": "startup", "run_id": ctx.run_id},
    )

    # For now just exit after initialization
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
