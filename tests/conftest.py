import sys
import os

# Ensure backend package is importable when running pytest from repository root
ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_PATH = os.path.join(ROOT, "backend")
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)
