"""Entry point for job category crosswalk coverage audit."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acquisition.platforms.yes123.crosswalk_audit import main

if __name__ == "__main__":
    raise SystemExit(main())
