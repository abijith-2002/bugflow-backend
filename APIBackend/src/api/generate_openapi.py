import json
import os

from src.api.main import app

# Generate the OpenAPI schema from the running app
openapi_schema = app.openapi()

# Ensure tags are present for better grouping in docs
if "tags" not in openapi_schema:
    openapi_schema["tags"] = [
        {"name": "Health", "description": "Service health and diagnostics"},
        {"name": "Auth", "description": "User authentication endpoints using Supabase"},
    ]

# Write to interfaces/openapi.json
output_dir = "interfaces"
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "openapi.json")

with open(output_path, "w") as f:
    json.dump(openapi_schema, f, indent=2)
