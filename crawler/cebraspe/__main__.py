"""Compat shim — a CLI virou ``python -m crawler``; este alias segue valendo."""
import sys

from crawler.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
