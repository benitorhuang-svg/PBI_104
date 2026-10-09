"""Compatibility entry point for JobWant 104 category capture."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acquisition.platforms.jobwant_104.capture.capture_category_matrix import main


if __name__ == "__main__":
    raise SystemExit(main())
