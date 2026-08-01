import sys
from pathlib import Path


def pytest_sessionstart(session):
    """
    Ensure project root is on sys.path so that `import app...` works in tests.
    """
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

