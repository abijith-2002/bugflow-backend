import sys
import os

# Add parent directory to path to import from app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app.main import app

# Re-export the app instance for uvicorn
__all__ = ["app"]
