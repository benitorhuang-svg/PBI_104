"""Operator entry point for batch acquisition of the full yes123 catalog."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acquisition.platforms.yes123.runner import main


if __name__ == "__main__":
    raise SystemExit(main())
