import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# A subprocess run of the CLI inherits this environment: its stdout stays the plain contract.
os.environ.pop("FORCE_COLOR", None)
