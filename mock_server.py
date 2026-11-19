"""Backwards-compatible entry point. Prefer ``mockbox`` or ``python -m mockbox``."""

import sys

from mockbox.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
