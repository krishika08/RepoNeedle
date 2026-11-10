"""
Execution wrapper for `python -m reponeedle.mcp`.
"""

import sys
from reponeedle.mcp.server import main

if __name__ == "__main__":
    sys.exit(main())
