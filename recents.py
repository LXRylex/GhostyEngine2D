from __future__ import annotations
import os, json
from typing import List, Any

APP_SUBDIR = "Welcome"
RECENT_FILE_NAME = "recent.json"
MAX_RECENTS = 12

def _recents_path() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    d = os.path.join(appdata, APP_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, RECENT_FILE_NAME)

def _load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json(path: str, data: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def recent_list(max_items: int = MAX_RECENTS) -> List[str]:
    data = _load_json(_recents_path(), {"projects": []})
    items = [p for p in data.get("projects", []) if isinstance(p, str)]
    items = [p for p in items if os.path.isfile(p)]
    return items[:max_items]

def remember_recent(path: str, max_items: int = MAX_RECENTS) -> None:
    store_path = _recents_path()
    data = _load_json(store_path, {"projects": []})
    items = [p for p in data.get("projects", []) if isinstance(p, str)]

    if path in items:
        items.remove(path)
    items.insert(0, path)
    items = items[:max_items]

    _save_json(store_path, {"projects": items})
