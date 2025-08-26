import json
import sys
from pathlib import Path

# Ensure this script can import 'src.api.main' regardless of the CWD by
# injecting the APIBackend directory into sys.path dynamically.
# This makes it robust in CI or docker build contexts.
current_file = Path(__file__).resolve()
api_dir = current_file.parent
src_dir = api_dir.parent  # .../APIBackend/src
api_backend_root = src_dir.parent  # .../APIBackend

# Insert APIBackend root so 'src' is discoverable as a package
if str(api_backend_root) not in sys.path:
    sys.path.insert(0, str(api_backend_root))

from src.api.main import app  # noqa: E402

# Get the OpenAPI schema
openapi_schema = app.openapi()

# Write to file at APIBackend/interfaces/openapi.json
interfaces_dir = api_backend_root / "interfaces"
interfaces_dir.mkdir(parents=True, exist_ok=True)
output_path = interfaces_dir / "openapi.json"

with open(output_path, "w") as f:
    json.dump(openapi_schema, f, indent=2)
