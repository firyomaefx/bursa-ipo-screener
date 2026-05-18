"""
Streamlit Cloud entry point.
Redirects to the actual dashboard module.
"""
import sys
from pathlib import Path

# Ensure the bot directory is in path
BOT_DIR = Path(__file__).parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

# Import and run the dashboard
import dashboard  # noqa: F401
