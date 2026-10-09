"""Compatibility entry point for importing verified 104 captures."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acquisition.platforms.jobwant_104.persistence.sync import main


if __name__ == "__main__":
    raise SystemExit(main())
