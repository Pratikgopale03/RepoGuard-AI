"""Launcher for Free view (3-token Pro variant for testing)."""

import os
import sys

# Ensure the RepoGuardAI directory is on the path so that the local app.py is found.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force low-limit variant in this process.
os.environ["PLANS_VARIANT"] = "3"
os.environ["STREAMLIT_ANALYSIS_URL"] = "http://localhost:8516/?view=analysis"

from app import main


if __name__ == "__main__":
    main()
