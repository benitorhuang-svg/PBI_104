"""Compatibility entry point for the yes123 acquisition probe."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from acquisition.platforms.yes123.probe import main


if __name__ == "__main__":
    main()
