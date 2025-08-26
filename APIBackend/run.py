#!/usr/bin/env python3
"""
PUBLIC_INTERFACE
Entrypoint script to run the BugFlow FastAPI backend locally.

Usage:
    python run.py
This script:
- Loads .env if present (without failing if missing).
- Ensures APIBackend root is on sys.path so 'src' package imports resolve.
- Starts Uvicorn on 0.0.0.0:3001.

Environment variables:
- SUPABASE_URL (required for auth endpoints)
- SUPABASE_ANON_KEY (required for auth endpoints)
- FRONTEND_ORIGIN (optional; defaults to "*")
- SITE_URL (optional; used for signup email redirect)
"""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except Exception:
    # dotenv is optional; ignore if not installed
    pass

# Ensure APIBackend root is on sys.path so 'src' is a package
api_backend_root = Path(__file__).parent.resolve()
if str(api_backend_root) not in sys.path:
    sys.path.insert(0, str(api_backend_root))

import uvicorn  # noqa: E402

def main() -> None:
    """Start Uvicorn server for the FastAPI app."""
    uvicorn.run(
        "src.api.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "3001")),
        reload=os.getenv("RELOAD", "true").lower() == "true",
    )

if __name__ == "__main__":
    main()
