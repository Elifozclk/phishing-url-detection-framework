from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
required = ["README.md", "requirements.txt", "notebooks", "src", "configs", "results", "docs"]
missing = [item for item in required if not (ROOT / item).exists()]
for notebook in ROOT.glob("notebooks/**/*.ipynb"):
    json.loads(notebook.read_text(encoding="utf-8"))
if missing:
    raise SystemExit(f"Missing required paths: {missing}")
print("Repository structure and notebook JSON files are valid.")
