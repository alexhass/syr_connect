"""List the translation keys of de.json that are missing in the other translation files."""

import json
from pathlib import Path
from typing import Any

base = Path(__file__).parents[1] / "custom_components" / "syr_connect" / "translations"
files = list(base.glob("*.json"))


def load(path: Path) -> Any:
    """Load a translation file."""
    return json.loads(path.read_text(encoding="utf8"))


de = load(base / "de.json")


def collect_keys(obj: Any, prefix: str = "") -> set[str]:
    """Return the dotted paths of all keys in a nested translation dict."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_prefix = f"{prefix}.{k}" if prefix else k
            keys.add(new_prefix)
            keys |= collect_keys(v, new_prefix)
    return keys


base_keys = collect_keys(de)

results = {}
for f in files:
    if f.name == "de.json":
        continue
    data = load(f)
    keys = collect_keys(data)
    missing = sorted(base_keys - keys)
    results[f.name] = missing

print(json.dumps(results, indent=2, ensure_ascii=False))
