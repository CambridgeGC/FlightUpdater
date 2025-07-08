"""
Copy this file to config.py (which is .gitignored) and fill in
the real values.  DO NOT commit config.py.

You can also leave these as empty strings and set environment
variables instead – see the bottom of the file.
"""

import os

BASE_URL = os.getenv("CGC_LIVE_BASE_URL", "https://admin.zweef.app/club/cgc2")
API_TOKEN =  os.getenv("CGC_LIVE_API_TOKEN",  "YOUR_TOKEN")
AEROLOG_PATH = os.getenv("CGC_LIVE_AEROLOG_PATH",  "PATH")
