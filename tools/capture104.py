"""Compatibility entry point for a single JobWant 104 capture."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acquisition.platforms.jobwant_104.capture.capture104 import main


if __name__ == "__main__":
    main()
