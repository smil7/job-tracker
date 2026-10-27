"""Write the API's OpenAPI schema to backend/openapi.json (used to generate frontend types)."""

import json
from pathlib import Path

from app.main import app

path = Path(__file__).resolve().parent.parent / "openapi.json"
path.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
print(f"Wrote {path}")
