import json
from pathlib import Path

base = Path(__file__).parents[1] / "custom_components" / "syr_connect" / "translations"
files = list(base.glob('*.json'))

def load(path):
    return json.loads(path.read_text(encoding='utf8'))

de = load(base / 'de.json')

def collect_keys(obj, prefix=''):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_prefix = f"{prefix}.{k}" if prefix else k
            keys.add(new_prefix)
            keys |= collect_keys(v, new_prefix)
    return keys

base_keys = collect_keys(de)

results = {}
for f in files:
    if f.name == 'de.json':
        continue
    data = load(f)
    keys = collect_keys(data)
    missing = sorted(list(base_keys - keys))
    results[f.name] = missing

print(json.dumps(results, indent=2, ensure_ascii=False))
