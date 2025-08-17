from __future__ import annotations
import os, io, json, base64
from typing import Any, Dict, List, Optional, Tuple, Union

import pygame
import tkinter as tk
from tkinter import filedialog

from theme import (
    ENTRY_NEXT_BAKE_COLOR, ENTRY_BACK_BAKE_COLOR,
    DOOR_NEXT_BAKE_COLOR, DOOR_BACK_BAKE_COLOR,
)

BytesLike = Union[bytes, bytearray, memoryview]

def recents_file_path(app_dir: str = "Welcome") -> str:

    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    d = os.path.join(appdata, app_dir)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "recent.json")


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


def list_recent_projects(recents_path: Optional[str] = None, max_items: int = 12) -> List[str]:

    rp = recents_path or recents_file_path()
    data = _load_json(rp, {"projects": []})
    items = [p for p in data.get("projects", []) if isinstance(p, str)]
    items = [p for p in items if os.path.isfile(p)]
    return items[:max_items]


def remember_recent(path: str, recents_path: Optional[str] = None, max_items: int = 12) -> None:

    rp = recents_path or recents_file_path()
    data = _load_json(rp, {"projects": []})
    items = [p for p in data.get("projects", []) if isinstance(p, str)]
    if path in items:
        items.remove(path)
    items.insert(0, path)
    items = items[:max_items]
    _save_json(rp, {"projects": items})

def _recent_list() -> List[str]:
    return list_recent_projects()

def _remember_recent(path: str) -> None:
    remember_recent(path)

def _stamp_spawns_on_mask(
    base_surf: pygame.Surface,
    spawn_pos: Optional[Tuple[int, int]],
    entry_next_spawns: List[Tuple[int, int]],
    entry_back_spawns: List[Tuple[int, int]],
) -> pygame.Surface:

    out = base_surf.copy()
    w, h = out.get_width(), out.get_height()
    out.lock()
    try:
        if spawn_pos:
            x, y = int(spawn_pos[0]), int(spawn_pos[1])
            if 0 <= x < w and 0 <= y < h:
                out.set_at((x, y), (255, 0, 0))

        for (x, y) in entry_next_spawns:
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h:
                out.set_at((xi, yi), ENTRY_NEXT_BAKE_COLOR)

        for (x, y) in entry_back_spawns:
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h:
                out.set_at((xi, yi), ENTRY_BACK_BAKE_COLOR)
    finally:
        out.unlock()
    return out


def _bake_doors_fill(out_surf: pygame.Surface, doors: List[Dict[str, Any]]) -> pygame.Surface:

    if not doors:
        return out_surf
    for d in doors:
        if not d.get('visible', True):
            continue
        pts: List[Tuple[int, int]] = d.get('pts', [])
        if len(pts) >= 3:
            col = DOOR_NEXT_BAKE_COLOR if d.get('kind', 'next') == 'next' else DOOR_BACK_BAKE_COLOR
            pygame.draw.polygon(out_surf, col, pts)
    return out_surf


def bake_mask_surface(
    mask_world: pygame.Surface,
    spawn_pos: Optional[Tuple[int, int]],
    entry_next_spawns: List[Tuple[int, int]],
    entry_back_spawns: List[Tuple[int, int]],
    doors: List[Dict[str, Any]],
) -> pygame.Surface:

    out = _stamp_spawns_on_mask(mask_world, spawn_pos, entry_next_spawns, entry_back_spawns)
    out = _bake_doors_fill(out, doors)
    return out


def export_mask_png_dialog(
    mask_world: pygame.Surface,
    *,
    initial_dir_from_bg: Optional[str] = None,
    spawn_pos: Optional[Tuple[int, int]] = None,
    entry_next_spawns: Optional[List[Tuple[int, int]]] = None,
    entry_back_spawns: Optional[List[Tuple[int, int]]] = None,
    doors: Optional[List[Dict[str, Any]]] = None,
    default_filename: str = "mask.png",
) -> Optional[str]:

    try:
        init_dir = os.path.dirname(initial_dir_from_bg) if initial_dir_from_bg else os.path.expanduser("~")
    except Exception:
        init_dir = os.path.expanduser("~")

    root = tk.Tk(); root.withdraw()
    out_path = filedialog.asksaveasfilename(
        title="Export Mask PNG",
        defaultextension=".png",
        filetypes=[("PNG", "*.png")],
        initialdir=init_dir,
        initialfile=default_filename
    )
    root.destroy()

    if not out_path:
        print("🚫 Save canceled.")
        return None

    baked = bake_mask_surface(
        mask_world,
        spawn_pos=spawn_pos,
        entry_next_spawns=entry_next_spawns or [],
        entry_back_spawns=entry_back_spawns or [],
        doors=doors or [],
    )
    try:
        pygame.image.save(baked, out_path)
        print(f"✅ Saved mask -> {out_path}")
        print("   baked: walls=white, spawn=red, door►=green, door◄=blue, entry►=yellow, entry◄=magenta")
        return out_path
    except Exception as ex:
        print("💥 Failed to save mask:", ex)
        return None

def build_project_dict(
    *,
    bg_path_abs: Optional[str],
    world_size: Tuple[int, int],
    strokes: List[Dict[str, Any]],
    doors: List[Dict[str, Any]],
    brush_w: int,
    preview_alpha: int,
    grid_on: bool,
    grid_size: int,
    simplify_on: bool,
    sym_x: bool,
    sym_y: bool,
    spawn_pos: Optional[Tuple[int, int]],
    entry_next_spawns: List[Tuple[int, int]],
    entry_back_spawns: List[Tuple[int, int]],
    embed_bg_bytes_b64: Optional[str] = None,
) -> Dict[str, Any]:

    data = {
        "bg_path": bg_path_abs,
        "bg_rel": None,                 # filled in by save helper if path available
        "bg_embed_b64": embed_bg_bytes_b64,
        "world_size": [int(world_size[0]), int(world_size[1])],
        "strokes": strokes,
        "doors": doors,
        "brush_w": int(brush_w),
        "preview_alpha": int(preview_alpha),
        "grid_on": bool(grid_on),
        "grid_size": int(grid_size),
        "simplify_on": bool(simplify_on),
        "sym_x": bool(sym_x),
        "sym_y": bool(sym_y),
        "spawn_pos": list(spawn_pos) if (spawn_pos is not None) else None,
        "entry_next_spawns": entry_next_spawns,
        "entry_back_spawns": entry_back_spawns,
    }
    return data


def _maybe_embed_bg(bg_path_abs: Optional[str]) -> Tuple[Optional[str], Optional[str]]:

    if not bg_path_abs or not os.path.isfile(bg_path_abs):
        return (None, None)
    try:
        with open(bg_path_abs, "rb") as f:
            return (None, base64.b64encode(f.read()).decode("ascii"))
    except Exception:
        return (None, None)


def save_project_dialog(
    project_data: Dict[str, Any],
    *,
    current_project_path: Optional[str] = None,
    save_as: bool = False,
) -> Optional[str]:

    out_path: Optional[str] = current_project_path
    if not out_path or save_as:
        root = tk.Tk(); root.withdraw()
        chosen = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".xzenp",
            filetypes=[("Xzen Project", ".xzenp")]
        )
        root.destroy()
        if not chosen:
            return None
        out_path = chosen

    proj_dir = os.path.dirname(out_path)
    bg_path_abs = project_data.get("bg_path")

    bg_rel: Optional[str] = None
    if bg_path_abs:
        try:
            bg_rel = os.path.relpath(bg_path_abs, proj_dir)
        except Exception:
            bg_rel = None

    embed_b64 = project_data.get("bg_embed_b64")
    if embed_b64 is None:
        _, embed_b64 = _maybe_embed_bg(bg_path_abs)

    data = dict(project_data)
    data["bg_rel"] = bg_rel
    data["bg_embed_b64"] = embed_b64

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("💾 Project saved:", out_path)
        return out_path
    except Exception as ex:
        print("💥 Failed to save project:", ex)
        return None


def _decode_b64(s: str) -> bytes:
    return base64.b64decode(s)


def _try_read_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None


def _choose_bg_via_dialog() -> Optional[str]:

    root = tk.Tk(); root.withdraw()
    cand = filedialog.askopenfilename(
        title="Locate background PNG",
        filetypes=[("PNG", "*.png")]
    )
    root.destroy()
    return cand if (cand and os.path.isfile(cand)) else None


def load_project_file(
    project_path: str,
    *,
    allow_bg_prompt: bool = True,
) -> Tuple[Dict[str, Any], Optional[Tuple[str, Any]]]:

    with open(project_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ws = data.get("world_size", [1280, 720])
    w, h = int(ws[0]), int(ws[1])

    strokes: List[Dict[str, Any]] = data.get("strokes", [])
    default_loaded_w = int(data.get("brush_w", 3))
    for st in strokes:
        if 'w' not in st:
            st['w'] = default_loaded_w

    doors: List[Dict[str, Any]] = data.get("doors", [])
    for d in doors:
        if 'kind' not in d:
            d['kind'] = 'next'

    proj_norm: Dict[str, Any] = {
        "world_size": (w, h),
        "strokes": strokes,
        "doors": doors,
        "brush_w": int(data.get("brush_w", 3)),
        "preview_alpha": int(data.get("preview_alpha", 96)),
        "grid_on": bool(data.get("grid_on", False)),
        "grid_size": int(data.get("grid_size", 8)),
        "simplify_on": bool(data.get("simplify_on", False)),
        "sym_x": bool(data.get("sym_x", False)),
        "sym_y": bool(data.get("sym_y", False)),
        "spawn_pos": tuple(data.get("spawn_pos")) if data.get("spawn_pos") else None,
        "entry_next_spawns": [tuple(pp) for pp in data.get("entry_next_spawns", [])],
        "entry_back_spawns": [tuple(pp) for pp in data.get("entry_back_spawns", [])],
        "bg_path": data.get("bg_path") or None,
        "bg_rel": data.get("bg_rel") or None,
        "bg_embed_b64": data.get("bg_embed_b64") or None,
        "project_path": project_path,
    }

    proj_dir = os.path.dirname(project_path)
    abs_path: Optional[str] = proj_norm["bg_path"]
    rel_path: Optional[str] = proj_norm["bg_rel"]
    embed_b64: Optional[str] = proj_norm["bg_embed_b64"]

    candidates: List[str] = []
    if abs_path:
        candidates.append(abs_path)
    if rel_path:
        candidates.append(os.path.join(proj_dir, rel_path))
    if abs_path:
        candidates.append(os.path.join(proj_dir, os.path.basename(abs_path)))

    for c in candidates:
        if c and os.path.isfile(c):
            return proj_norm, ("path", c)

    if embed_b64:
        try:
            raw = _decode_b64(embed_b64)
            return proj_norm, ("bytes", raw)
        except Exception:
            pass

    if allow_bg_prompt:
        cand = _choose_bg_via_dialog()
        if cand:
            return proj_norm, ("path", cand)

    return proj_norm, None
