
"""FSKU executable CLI runner."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fsku.cli.main import app

if __name__ == "__main__":
    app()
