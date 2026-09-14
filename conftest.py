"""Let pytest import adapters/triage/digest/settings from the repository root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
