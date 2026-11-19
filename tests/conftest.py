"""pytest configuration: make the repository root (pam_player, pam_trace,
the ``pam`` package) and the test helpers importable."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (HERE, HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
