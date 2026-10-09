"""Compatibility operator entry point for yes123 job capture."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acquisition.platforms.yes123.capture import main


if __name__ == "__main__":
    raise SystemExit(main())
