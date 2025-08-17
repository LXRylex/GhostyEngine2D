import os, sys, json, copy, io, base64, subprocess
from typing import List, Dict, Tuple, Any, Optional, Union, cast

import pygame
import tkinter as tk
from tkinter import filedialog, messagebox
from theme import (
    LEFTBAR_W, RIGHTBAR_W, TOPBAR_H, TABS_H, STATUS_H, WIN_W, WIN_H,
    C_BG, C_PANEL, C_FRAME, C_TEXT, C_TEXT_DIM,
    MASK_DRAW_COLOR, MASK_ERASE_COLOR, LINE_WIDTH_DEFAULT, DOUBLE_CLICK_MS,
    ENTRY_NEXT_BAKE_COLOR, ENTRY_BACK_BAKE_COLOR,
    DOOR_NEXT_OVERLAY_OUTLINE, DOOR_BACK_OVERLAY_OUTLINE,
    DOOR_NEXT_BAKE_COLOR, DOOR_BACK_BAKE_COLOR,
    SPAWN_COLOR, SPAWN_BORDER, SPAWN_SIZE,
    ENTRY_NEXT_OVERLAY, ENTRY_BACK_OVERLAY, ENTRY_MARK_SIZE,
    C_CHECKER_A, C_CHECKER_B,
    clamp,
)

from ui_widgets import px_rect, px_button, text, trunc_text
from ui_panels import (
    draw_topbar, draw_tabs_bar, draw_status,
    draw_left_toolbar, draw_right_panel,
)

from start_menu import draw_start_menu, handle_event as startmenu_handle

WORLD_W, WORLD_H = 1280, 720

WIDTH_MIN = 1
WIDTH_MAX = 150

def _discover_resources_root() -> Optional[str]:
    bases = []
    base_mei = getattr(sys, "_MEIPASS", None)
    if base_mei:
        bases.append(base_mei)
    here = os.path.dirname(os.path.abspath(__file__))
    bases += [here, os.getcwd()]
    cur = here
    for _ in range(5):
        bases.append(cur)
        nxt = os.path.dirname(cur)
        if nxt == cur:
            break
        cur = nxt
    seen = set()
    for b in bases:
        if not b or b in seen:
            continue
        seen.add(b)
        p = os.path.join(b, "resources")
        if os.path.isdir(p):
            return p
    try:
        for name in os.listdir(here):
            if name.lower() == "resources":
                p = os.path.join(here, name)
                if os.path.isdir(p):
                    return p
    except Exception:
        pass
    return None

_RES_ROOT = _discover_resources_root()

def resource_path(*parts: str) -> str:
    if _RES_ROOT:
        return os.path.join(_RES_ROOT, *parts)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)

pygame.init()
pygame.display.set_caption("Ghosty Engine 2D (v3.7)")

def _load_icon():
    p = resource_path("icons", "app_icon.ico")
    if os.path.isfile(p):
        try:
            icon = pygame.image.load(p)
            pygame.display.set_icon(icon)
        except Exception:
            pass

_load_icon()

screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.DOUBLEBUF)
clock  = pygame.time.Clock()
app_start_ms = pygame.time.get_ticks()

def _require_font_path() -> str:
    p = resource_path("fonts", "font-default.ttf")
    if os.path.isfile(p):
        print(f"[font] using: {p}")
        return p
    try:
        root = tk.Tk(); root.withdraw()
        chosen = filedialog.askopenfilename(
            title="Locate font-default.ttf",
            filetypes=[("TrueType Font", "*.ttf")]
        )
        root.destroy()
        if chosen and os.path.isfile(chosen):
            print(f"[font] using (manual): {chosen}")
            return chosen
    except Exception:
        pass
    raise FileNotFoundError(
    )

_FONT_PATH = _require_font_path()

def _mkfont(size: int) -> pygame.font.Font:
    return pygame.font.Font(_FONT_PATH, size)

font_title     = _mkfont(22)
font_btn       = _mkfont(18)
font_layer_hdr = _mkfont(18)
font_layer     = _mkfont(17)
font_base      = _mkfont(16)
font_small     = _mkfont(14)
font_tiny      = _mkfont(12)
font_mono      = _mkfont(14)

FONTS = {
    "title": font_title,
    "btn":   font_btn,
    "hdr":   font_layer_hdr,
    "layer": font_layer,
    "base":  font_base,
    "small": font_small,
    "tiny":  font_tiny,
    "mono":  font_mono,
}

BytesLike = Union[bytes, bytearray, memoryview]

def set_world_size(w: int, h: int):
    global WORLD_W, WORLD_H, mask_world, _last_zoom, _scaled_mask_dirty
    WORLD_W, WORLD_H = int(w), int(h)
    mask_world = pygame.Surface((WORLD_W, WORLD_H)).convert()
    mask_world.fill(MASK_ERASE_COLOR)
    _last_zoom = -1.0
    _scaled_mask_dirty = True

def _place_image_onto_canvas(img: pygame.Surface, canvas_wh: Tuple[int,int]) -> pygame.Surface:
    cw, ch = canvas_wh
    iw, ih = img.get_size()
    canvas = pygame.Surface((cw, ch)).convert()
    canvas.fill((255, 255, 255))
    x = max(0, (cw - iw) // 2)
    y = max(0, (ch - ih) // 2)
    src = pygame.Rect(0, 0, min(iw, cw), min(ih, ch))
    canvas.blit(img, (x, y), area=src)
    return canvas

def _sanitize_name(s: str) -> str:
    bad = {">", "<", "◄", "►"}
    return "".join(ch for ch in s if ch not in bad).strip()

# ---- Orthogonalization helpers (fix for disconnected auto-straight) ----
def _dedupe_consecutive(pts: List[Tuple[int,int]]) -> List[Tuple[int,int]]:
    out: List[Tuple[int,int]] = []
    last = None
    for p in pts:
        if p != last:
            out.append(p)
            last = p
    return out

def orthogonalize_pts(pts: List[Tuple[int,int]]) -> List[Tuple[int,int]]:
    if not pts:
        return []
    out: List[Tuple[int,int]] = [(int(pts[0][0]), int(pts[0][1]))]
    last_dir: Optional[str] = None  # 'h' or 'v'
    for i in range(1, len(pts)):
        x1, y1 = out[-1]
        x2, y2 = int(pts[i][0]), int(pts[i][1])
        if x1 == x2 or y1 == y2:
            out.append((x2, y2))
            last_dir = 'h' if y1 == y2 else 'v'
            continue
        cand_h = (x2, y1) 
        cand_v = (x1, y2) 
        if last_dir == 'h':
            out.append(cand_h); out.append((x2, y2)); last_dir = 'v'
        elif last_dir == 'v':
            out.append(cand_v); out.append((x2, y2)); last_dir = 'h'
        else:
            if abs(x2 - x1) >= abs(y2 - y1):
                out.append(cand_h); out.append((x2, y2)); last_dir = 'v'
            else:
                out.append(cand_v); out.append((x2, y2)); last_dir = 'h'
    return _dedupe_consecutive(out)

def _recents_path():
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    d = os.path.join(appdata, "Welcome")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "recent.json")

RECENT_FILE = _recents_path()
MAX_RECENTS = 12

def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _recent_list():
    data = _load_json(RECENT_FILE, {"projects": []})
    items = [p for p in data.get("projects", []) if isinstance(p, str)]
    items = [p for p in items if os.path.isfile(p)]
    return items[:MAX_RECENTS]

def _remember_recent(path):
    data = _load_json(RECENT_FILE, {"projects": []})
    items = [p for p in data.get("projects", []) if isinstance(p, str)]
    if path in items:
        items.remove(path)
    items.insert(0, path)
    items = items[:MAX_RECENTS]
    _save_json(RECENT_FILE, {"projects": items})

def _remove_recent(path):
    data = _load_json(RECENT_FILE, {"projects": []})
    items = [p for p in data.get("projects", []) if isinstance(p, str)]
    if path in items:
        items.remove(path)
    _save_json(RECENT_FILE, {"projects": items})

hidden_recent_stack: List[str] = []
hidden_recent_set:   set[str]  = set()

def snapshot_state():
    return copy.deepcopy((
        strokes, doors, sel_kind, sel_idx, brush_w, preview_alpha,
        grid_on, grid_size, simplify_on, sym_x, sym_y, spawn_pos, zoom, ox, oy,
        entry_next_spawns, entry_back_spawns
    ))

def restore_state(snap):
    global strokes, doors, sel_kind, sel_idx, brush_w, preview_alpha
    global grid_on, grid_size, simplify_on, sym_x, sym_y, spawn_pos, zoom, ox, oy
    global entry_next_spawns, entry_back_spawns, _scaled_mask_dirty, _last_zoom
    (strokes, doors, sel_kind, sel_idx, brush_w, preview_alpha,
     grid_on, grid_size, simplify_on, sym_x, sym_y, spawn_pos, zoom, ox, oy,
     entry_next_spawns, entry_back_spawns) = copy.deepcopy(snap)
    _scaled_mask_dirty = True
    _last_zoom = -1.0
    update_mask()

def make_tab_dict(name: str, bg_path: Optional[str], bg_surface: Optional[pygame.Surface]):
    return {
        "name": name,
        "bg_path": bg_path,
        "bg_surface": bg_surface,
        "state": snapshot_state(),
        "project_path": None,
        "dirty": False
    }

def mark_dirty():
    if tabs:
        tabs[active_tab]["dirty"] = True

def mark_clean():
    if tabs:
        tabs[active_tab]["dirty"] = False

tabs: List[Dict[str, Any]] = []
active_tab: int = 0

BG_PATH: Optional[str] = None
bg_world: Optional[pygame.Surface] = None
mask_world = pygame.Surface((WORLD_W, WORLD_H)).convert(); mask_world.fill(MASK_ERASE_COLOR)

edges_overlay: Optional[pygame.Surface] = None
show_edges = False

strokes: List[Dict[str, Any]] = []
points: List[Tuple[int,int]] = []

doors: List[Dict[str, Any]] = []
door_points: List[Tuple[int,int]] = []

entry_next_spawns: List[Tuple[int,int]] = []
entry_back_spawns: List[Tuple[int,int]] = []

sel_kind: Optional[str] = None
sel_idx: Optional[int]  = None

undo_stack: List[Any] = []
redo_stack: List[Any] = []

VIEW = pygame.Rect(
    LEFTBAR_W, TOPBAR_H + TABS_H,
    WIN_W - LEFTBAR_W - RIGHTBAR_W,
    WIN_H - TOPBAR_H - TABS_H - STATUS_H
)
zoom = 1.0
ox, oy = (VIEW.x + (VIEW.w - WORLD_W)//2), (VIEW.y + (VIEW.h - WORLD_H)//2)
last_click_time = 0

TOOL_BRUSH = "brush"; TOOL_LINE = "line"; TOOL_MOVE = "move"; TOOL_HAND = "hand"; TOOL_SPAWN = "spawn"
TOOL_DOOR_NEXT = "door_next"; TOOL_DOOR_BACK = "door_back"
TOOL_ENTRY_NEXT = "entry_spawn_next"; TOOL_ENTRY_BACK = "entry_spawn_back"
tool = TOOL_BRUSH
create_tool = TOOL_BRUSH
mode = "create"

dragging = False
drag_started = False
last_mouse = (0, 0)
space_pan = False
mmb_pan   = False

drag_anchor_world: Optional[Tuple[float, float]] = None
drag_orig_pts_cache: List[Tuple[int,int]] = []

brush_w = LINE_WIDTH_DEFAULT
grid_on = False; grid_size = 8
preview_alpha = 96
simplify_on = False
sym_x = False; sym_y = False

renaming = False; rename_buf = ""

history_show = False
help_show    = False

spawn_pos: Optional[Tuple[int,int]] = None

toolbar_pressed: Optional[str] = None
topbar_pressed: Optional[str]   = None
tab_pressed: Optional[int]      = None
tab_close_pressed: Optional[int]= None

thickness_dragging: bool = False

file_menu_open: bool = False
file_menu_items: List[Tuple[str, str]] = []  
file_menu_item_rects: List[pygame.Rect] = []
file_menu_rect: Optional[pygame.Rect] = None

_last_zoom = -1.0
_cached_bg: Optional[pygame.Surface] = None
_cached_mask: Optional[pygame.Surface] = None
_cached_edges: Optional[pygame.Surface] = None
_scaled_mask_dirty = True

def _assets_bat_files() -> List[Tuple[str, str]]:
    """Scan likely 'assets' folders for .bat files; return (display, full_path)."""
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [
        os.path.join(here, "assets"),
        os.path.join(os.getcwd(), "assets"),
        resource_path("assets"),
    ]
    seen = set()
    out: List[Tuple[str,str]] = []
    for d in dirs:
        if not d or not os.path.isdir(d) or d in seen:
            continue
        seen.add(d)
        try:
            for name in os.listdir(d):
                if name.lower().endswith(".bat"):
                    disp = os.path.splitext(name)[0]
                    out.append((disp, os.path.join(d, name)))
        except Exception:
            pass
    uniq: List[Tuple[str,str]] = []
    used = set()
    for disp, full in out:
        key = (disp, os.path.normpath(full))
        if key in used:
            continue
        used.add(key)
        uniq.append((disp, full))
    return uniq

def _run_bat(full_path: str):
    try:
        if sys.platform.startswith("win"):
            os.startfile(full_path)
        else:
            subprocess.Popen([full_path], shell=True)
        print(f"[File] Launched: {full_path}")
    except Exception as ex:
        print(f"[File] Failed to run: {full_path} — {ex}")

def update_mask():
    global _scaled_mask_dirty
    mask_world.fill(MASK_ERASE_COLOR)
    for st in strokes:
        if not st.get('visible', True):
            continue
        draw_stroke_on(mask_world, st, MASK_DRAW_COLOR)
    _scaled_mask_dirty = True

def _draw_axis_rect_segment_world(surf, col, w, a: Tuple[int,int], b: Tuple[int,int]):
    x1, y1 = a; x2, y2 = b
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) >= abs(dy):
        x0, x1b = (x2, x1) if x2 < x1 else (x1, x2)
        rect = pygame.Rect(x0, int(y1 - w//2), (x1b - x0) + 1, w)
    else:
        y0, y1b = (y2, y1) if y2 < y1 else (y1, y2)
        rect = pygame.Rect(int(x1 - w//2), y0, w, (y1b - y0) + 1)
    pygame.draw.rect(surf, col, rect)

def draw_stroke_on(surf, st, col):
    pts = [(int(x), int(y)) for (x, y) in st['pts']]
    w = max(WIDTH_MIN, int(st.get('w', brush_w)))
    if st['mode'] == 'poly':
        for a, b in zip(pts, pts[1:]):
            pygame.draw.line(surf, col, a, b, w)
    elif st['mode'] == 'straight_poly':
        o = orthogonalize_pts(pts)
        if len(o) == 1:
            pygame.draw.rect(surf, col, pygame.Rect(o[0][0] - w//2, o[0][1] - w//2, w, w))
            return
        for a, b in zip(o, o[1:]):
            _draw_axis_rect_segment_world(surf, col, w, a, b)
        for (jx, jy) in o:
            pygame.draw.rect(surf, col, pygame.Rect(int(jx - w//2), int(jy - w//2), w, w))

def stroke_bounds(st):
    xs=[p[0] for p in st['pts']]; ys=[p[1] for p in st['pts']]
    if not xs:
        return pygame.Rect(0,0,0,0)
    w = max(WIDTH_MIN, int(st.get('w', brush_w)))
    return pygame.Rect(min(xs)-w, min(ys)-w, max(xs)-min(xs)+2*w, max(ys)-min(ys)+2*w)

def door_bounds(d):
    xs=[p[0] for p in d['pts']]; ys=[p[1] for p in d['pts']]
    if not xs:
        return pygame.Rect(0,0,0,0)
    return pygame.Rect(min(xs)-4, min(ys)-4, max(xs)-min(xs)+8, max(ys)-min(ys)+8)

def hit_test_strokes(world_pos):
    for i in reversed(range(len(strokes))):
        if not strokes[i].get('visible', True):
            continue
        if stroke_bounds(strokes[i]).inflate(6,6).collidepoint(world_pos):
            return i
    return None

def hit_test_doors(world_pos):
    for i in reversed(range(len(doors))):
        if not doors[i].get('visible', True):
            continue
        if door_bounds(doors[i]).inflate(6,6).collidepoint(world_pos):
            return i
    return None

def commit_points(mode_kind, pts):
    if len(pts) < 1:
        return
    s = {
        'mode': mode_kind, 'pts': pts, 'visible': True,
        'locked': False, 'name': f"Stroke {len(strokes):02d}",
        'w': int(brush_w)
    }
    strokes.append(s); update_mask(); mark_dirty()

def commit_door_points(pts, kind: str):
    if len(pts) < 3:
        return
    d = {
        'pts': [(int(x),int(y)) for (x,y) in pts],
        'visible': True,
        'locked': False,
        'name': f"Door {len(doors):02d}",
        'kind': 'next' if kind!='back' else 'back',
        'w': int(brush_w)
    }
    doors.append(d); mark_dirty()

def symmetry_mirror_pts(pts):
    out=[]
    if sym_x:
        cx = WORLD_W//2
        out += [(2*cx - x, y) for (x,y) in pts]
    if sym_y:
        cy = WORLD_H//2
        out += [(x, 2*cy - y) for (x,y) in pts]
    return out

def push_undo():
    undo_stack.append(snapshot_state())
    if len(undo_stack) > 128:
        undo_stack.pop(0)
    redo_stack.clear(); mark_dirty()

def do_undo():
    if not undo_stack:
        return
    snap = undo_stack.pop()
    redo_stack.append(snapshot_state())
    restore_state(snap); mark_dirty()

def do_redo():
    if not redo_stack:
        return
    snap = redo_stack.pop()
    undo_stack.append(snapshot_state())
    restore_state(snap); mark_dirty()

def load_background(src: Union[str, pygame.Surface, BytesLike], *, keep_world: bool = False):
    global BG_PATH, bg_world, _cached_bg, _cached_edges, _last_zoom

    if isinstance(src, (bytes, bytearray, memoryview)):
        BG_PATH = None
        surf = pygame.image.load(io.BytesIO(bytes(src))).convert()
    elif isinstance(src, str):
        BG_PATH = src
        surf = pygame.image.load(src).convert()
    elif isinstance(src, pygame.Surface):
        BG_PATH = None
        surf = src.convert()
    else:
        raise TypeError(f"load_background: unsupported type {type(src).__name__}")

    if keep_world:
        bg_world = _place_image_onto_canvas(surf, (WORLD_W, WORLD_H))
    else:
        iw, ih = surf.get_size()
        set_world_size(iw, ih)
        bg_world = surf

    _cached_bg = None; _cached_edges = None; _last_zoom = -1.0

def compute_edges_surface(bg):
    arr = cast(Any, pygame.surfarray.pixels3d(bg)).copy()
    w,h = bg.get_width(), bg.get_height()
    edges = pygame.Surface((w,h), flags=0, depth=32).convert_alpha()
    px = cast(Any, pygame.surfarray.pixels_alpha(edges)); px[:] = 0
    for y in range(1,h-1):
        for x in range(1,w-1):
            gx = abs(int(arr[x+1,y].mean()) - int(arr[x-1,y].mean()))
            gy = abs(int(arr[x,y+1].mean()) - int(arr[x,y-1].mean()))
            g  = clamp(gx+gy,0,255)
            px[x,y] = g
    del px
    cast(Any, pygame.surfarray.pixels3d(edges))[:,:,:] = (C_FRAME[0], C_FRAME[1], C_FRAME[2])
    edges.set_alpha(90)
    return edges

def _mask_with_spawns_pixels(base_surf: pygame.Surface, spawn, entries_next, entries_back):
    out = base_surf.copy(); out.lock()
    if spawn:
        x, y = map(int, spawn)
        if 0 <= x < out.get_width() and 0 <= y < out.get_height():
            out.set_at((x, y), (255, 0, 0))
    for (x,y) in entries_next:
        xi, yi = int(x), int(y)
        if 0 <= xi < out.get_width() and 0 <= yi < out.get_height():
            out.set_at((xi, yi), ENTRY_NEXT_BAKE_COLOR)
    for (x,y) in entries_back:
        xi, yi = int(x), int(y)
        if 0 <= xi < out.get_width() and 0 <= yi < out.get_height():
            out.set_at((xi, yi), ENTRY_BACK_BAKE_COLOR)
    out.unlock()
    return out

def _bake_doors_fill(out_surf: pygame.Surface):
    for d in doors:
        if not d.get('visible', True):
            continue
        if len(d['pts']) >= 3:
            col = DOOR_NEXT_BAKE_COLOR if d.get('kind','next')=='next' else DOOR_BACK_BAKE_COLOR
            pygame.draw.polygon(out_surf, col, d['pts'])
    return out_surf

def save_mask_png():
    try:
        init_dir = os.path.dirname(BG_PATH) if BG_PATH else os.path.expanduser("~")
    except Exception:
        init_dir = os.path.expanduser("~")
    root = tk.Tk(); root.withdraw()
    out = filedialog.asksaveasfilename(
        title="Export Mask PNG",
        defaultextension=".png",
        filetypes=[("PNG", "*.png")],
        initialdir=init_dir,
        initialfile="mask.png"
    )
    root.destroy()
    if not out:
        print("🚫 Save canceled.")
        return
    out_surf = _mask_with_spawns_pixels(mask_world, spawn_pos, entry_next_spawns, entry_back_spawns)
    out_surf = _bake_doors_fill(out_surf)
    try:
        pygame.image.save(out_surf, out)
        print(f"✅ Saved mask -> {out}")
        print("   baked: walls=white, spawn=red, door=green/blue, entry=yellow/magenta")
    except Exception as ex:
        print("💥 Failed to save mask:", ex)

def save_project(save_as: bool=False):
    if not tabs:
        print("No tab to save.")
        return False
    cur = tabs[active_tab]
    p = cur.get("project_path")
    if not p or save_as:
        root = tk.Tk(); root.withdraw()
        out = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".xzenp",
            filetypes=[("Xzen Project",".xzenp")]
        )
        root.destroy()
        if not out:
            return False
        p = out

    bg_path_abs = BG_PATH if BG_PATH and os.path.isfile(BG_PATH) else None
    bg_rel = None
    bg_embed_b64 = None
    if bg_path_abs:
        try:
            bg_rel = os.path.relpath(bg_path_abs, os.path.dirname(p))
        except Exception:
            bg_rel = None
        try:
            with open(bg_path_abs, "rb") as f:
                bg_embed_b64 = base64.b64encode(f.read()).decode("ascii")
        except Exception:
            bg_embed_b64 = None

    data = {
        "bg_path": bg_path_abs,
        "bg_rel": bg_rel,
        "bg_embed_b64": bg_embed_b64,
        "world_size": [WORLD_W, WORLD_H],
        "strokes": strokes, "doors": doors,
        "brush_w": brush_w, "preview_alpha": preview_alpha,
        "grid_on": grid_on, "grid_size": grid_size,
        "simplify_on": simplify_on, "sym_x": sym_x, "sym_y": sym_y,
        "spawn_pos": list(spawn_pos) if spawn_pos is not None else None,
        "entry_next_spawns": entry_next_spawns,
        "entry_back_spawns": entry_back_spawns,
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    tabs[active_tab]["project_path"] = p
    _remember_recent(p); mark_clean()
    print("💾 Project saved:", p)
    return True

def _load_project_from_path(p: str):
    global strokes, doors, brush_w, preview_alpha, grid_on, grid_size
    global simplify_on, sym_x, sym_y, sel_kind, sel_idx, spawn_pos
    global entry_next_spawns, entry_back_spawns

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    ws = data.get("world_size", [WORLD_W, WORLD_H])
    set_world_size(int(ws[0]), int(ws[1]))

    proj_dir = os.path.dirname(p)
    abs_path = data.get("bg_path")
    rel_path = data.get("bg_rel")
    embed_b64 = data.get("bg_embed_b64")

    loaded_bg = False
    candidates = []
    if abs_path: candidates.append(abs_path)
    if rel_path: candidates.append(os.path.join(proj_dir, rel_path))
    if abs_path:
        candidates.append(os.path.join(proj_dir, os.path.basename(abs_path)))

    for cand in candidates:
        try:
            if cand and os.path.isfile(cand):
                load_background(cand, keep_world=True)
                loaded_bg = True
                break
        except Exception as ex:
            print("bg load fail:", cand, ex)

    if not loaded_bg and embed_b64:
        try:
            raw = base64.b64decode(embed_b64)
            load_background(raw, keep_world=True)
            loaded_bg = True
        except Exception as ex:
            print("embedded bg decode fail:", ex)

    if not loaded_bg:
        root = tk.Tk(); root.withdraw()
        cand = filedialog.askopenfilename(title="Locate background PNG", filetypes=[("PNG","*.png")])
        root.destroy()
        if cand and os.path.isfile(cand):
            load_background(cand, keep_world=True)
            loaded_bg = True
        else:
            print("⚠️ Project loaded without background image.")

    strokes[:] = data.get("strokes", [])
    default_loaded_w = int(data.get("brush_w", LINE_WIDTH_DEFAULT))
    for st in strokes:
        if 'w' not in st:
            st['w'] = default_loaded_w

    doors[:]   = data.get("doors", [])
    for d in doors:
        if 'kind' not in d:
            d['kind'] = 'next'
        if 'w' not in d:
            d['w'] = default_loaded_w
    brush_w = int(clamp(int(data.get("brush_w", LINE_WIDTH_DEFAULT)), WIDTH_MIN, WIDTH_MAX))
    preview_alpha = data.get("preview_alpha", 96)
    grid_on  = data.get("grid_on", False); grid_size = data.get("grid_size", 8)
    simplify_on = data.get("simplify_on", False)
    sym_x = data.get("sym_x", False); sym_y = data.get("sym_y", False)

    sp = data.get("spawn_pos")
    spawn_pos = tuple(sp) if sp else None
    entry_next_spawns[:] = [tuple(pp) for pp in data.get("entry_next_spawns", [])]
    entry_back_spawns[:] = [tuple(pp) for pp in data.get("entry_back_spawns", [])]

    sel_kind, sel_idx = None, None
    _remember_recent(p)
    update_mask()
    print("📂 Project loaded:", p)

def load_project_into_current():
    root = tk.Tk(); root.withdraw()
    p = filedialog.askopenfilename(title="Load Project", filetypes=[("Xzen Project",".xzenp")])
    root.destroy()
    if not p:
        return False
    _load_project_from_path(p)
    if tabs:
        tabs[active_tab]["project_path"] = p
        tabs[active_tab]["name"] = os.path.basename(p)
    fit_and_center(); mark_clean(); return True

def clear_all():
    strokes.clear(); doors.clear()
    entry_next_spawns.clear(); entry_back_spawns.clear()
    global spawn_pos, _scaled_mask_dirty
    spawn_pos=None
    update_mask(); _scaled_mask_dirty = True; mark_dirty()

def reorder_layer(delta):
    global sel_idx, sel_kind
    if sel_kind != "stroke":
        return
    if sel_idx is None or not strokes:
        return
    j = clamp(sel_idx+delta, 0, len(strokes)-1)
    if j == sel_idx:
        return
    strokes[sel_idx], strokes[j] = strokes[j], strokes[sel_idx]
    sel_idx = j; update_mask(); mark_dirty()

# ---------- COORD + ZOOM ----------
def world_to_screen(x: float, y: float) -> Tuple[int,int]:
    return (int(VIEW.x + ox + x*zoom), int(VIEW.y + oy + y*zoom))

def screen_to_world(sx: float, sy: float) -> Tuple[float,float]:
    return ((sx - VIEW.x - ox)/zoom, (sy - VIEW.y - oy)/zoom)

def zoom_to(factor, anchor_screen=None):
    global zoom, ox, oy
    factor = clamp(factor, 0.5, 6.0)
    if anchor_screen is None:
        anchor_screen=(VIEW.centerx, VIEW.centery)
    ax_old, ay_old = anchor_screen
    wx,wy = screen_to_world(ax_old, ay_old)
    zoom = factor
    sx,sy = world_to_screen(wx,wy)
    ox += (ax_old - sx); oy += (ay_old - sy)

def fit_to_view():
    zw=(VIEW.w-8)/WORLD_W; zh=(VIEW.h-8)/WORLD_H
    zoom_to(min(zw,zh), VIEW.center)

def fit_and_center():
    global zoom, ox, oy
    w, h = WORLD_W, WORLD_H
    factor = clamp(min((VIEW.w - 8) / w, (VIEW.h - 8) / h), 0.5, 6.0)
    zoom = factor
    ox = int(VIEW.centerx - VIEW.x - (w * zoom) / 2)
    oy = int(VIEW.centery - VIEW.y - (h * zoom) / 2)

# ---------- TABS ----------
def tabs_save_current():
    if not tabs:
        return
    t = tabs[active_tab]
    t["state"] = snapshot_state()
    t["bg_path"] = BG_PATH
    t["bg_surface"] = bg_world

def tabs_load(i:int):
    global active_tab, BG_PATH, bg_world, _last_zoom, _cached_bg, _cached_edges
    active_tab = i
    t = tabs[i]
    BG_PATH = t.get("bg_path")
    bg_world = t.get("bg_surface")
    restore_state(t.get("state"))
    _cached_bg = None; _cached_edges = None; _last_zoom = -1.0
    fit_and_center()

def tab_new_from_png():
    root = tk.Tk(); root.withdraw()
    path = filedialog.askopenfilename(title="Select background PNG", filetypes=[("PNG","*.png")])
    root.destroy()
    if not path:
        return
    tabs_save_current()
    load_background(path, keep_world=False)
    clear_all()
    fit_and_center()
    name = os.path.basename(path)
    tabs.append(make_tab_dict(name, path, bg_world))
    tabs_load(len(tabs)-1)
    mark_clean()

def tab_open_project():
    root = tk.Tk(); root.withdraw()
    p = filedialog.askopenfilename(title="Open Project (.xzenp)", filetypes=[("Xzen Project",".xzenp")])
    root.destroy()
    if not p:
        return
    tabs_save_current()
    _load_project_from_path(p)
    fit_and_center()
    name = os.path.basename(p)
    t = make_tab_dict(name, BG_PATH, bg_world)
    t["project_path"] = p
    t["dirty"] = False
    tabs.append(t)
    tabs_load(len(tabs)-1)
    mark_clean()

def maybe_save_before_close(i:int) -> bool:
    t = tabs[i]
    if not t.get("dirty"):
        return True
    root = tk.Tk(); root.withdraw()
    name = t.get("name","Untitled")
    ans = messagebox.askyesnocancel("Save project?", f"Save changes to '{name}' before closing?")
    root.destroy()
    if ans is None:
        return False
    if ans:
        if i == active_tab:
            return save_project(save_as=not bool(t.get("project_path")))
        else:
            tabs_save_current()
            cur = active_tab
            tabs_load(i)
            ok = save_project(save_as=not bool(t.get("project_path")))
            tabs_load(cur)
            return ok
    return True

def close_tab(i:int):
    global active_tab, BG_PATH, bg_world
    if not (0 <= i < len(tabs)):
        return
    if not maybe_save_before_close(i):
        return
    tabs.pop(i)
    if not tabs:
        BG_PATH = None; bg_world = None
        clear_all(); fit_and_center()
    else:
        active_tab = max(0, min(active_tab, len(tabs)-1))
        tabs_load(active_tab)

# ---------- VIEW DRAW ----------
def px_tooltip(s, anchor_rect):
    pad_x = 14; pad_y = 10
    min_w = 240; min_h = 40
    txt_w, txt_h = font_small.size(s)
    w = max(min_w, txt_w + pad_x*2)
    h = max(min_h, txt_h + pad_y*2)
    x = min(anchor_rect.right + 12, WIN_W - w - 8)
    y = max(TOPBAR_H + 8, min(anchor_rect.y, WIN_H - STATUS_H - h - 8))
    rr = pygame.Rect(x, y, w, h)
    px_rect(screen, rr, (250, 250, 252), C_FRAME, 2)
    text(screen, s, (rr.x + pad_x, rr.y + pad_y), C_TEXT, font_small)

def _draw_axis_rect_segment_screen(ax: int, ay: int, bx: int, by: int, w: int, col: Tuple[int,int,int]):
    if abs(bx - ax) >= abs(by - ay):  # horizontal
        x0, x1b = (bx, ax) if bx < ax else (ax, bx)
        rect = pygame.Rect(x0, int(ay - w//2), (x1b - x0) + 1, w)
    else:  # vertical
        y0, y1b = (by, ay) if by < ay else (ay, by)
        rect = pygame.Rect(int(ax - w//2), y0, w, (y1b - y0) + 1)
    pygame.draw.rect(screen, col, rect)

def draw_viewport():
    global _last_zoom, _cached_bg, _cached_mask, _cached_edges, _scaled_mask_dirty
    px_rect(screen, VIEW, C_PANEL, C_FRAME)
    clip_old = screen.get_clip(); screen.set_clip(VIEW)

    # checker
    tile=16
    for yy in range(VIEW.y, VIEW.bottom, tile):
        for xx in range(VIEW.x, VIEW.right, tile):
            c = C_CHECKER_A if ((xx//tile + yy//tile) % 2 == 0) else C_CHECKER_B
            pygame.draw.rect(screen, c, pygame.Rect(xx,yy,tile,tile))

    if bg_world is not None:
        if _last_zoom != zoom:
            target_size = (int(WORLD_W*zoom), int(WORLD_H*zoom))
            _cached_bg = pygame.transform.scale(bg_world, target_size)
            if edges_overlay is not None:
                _cached_edges = pygame.transform.scale(edges_overlay, target_size)
            _cached_mask = pygame.transform.scale(mask_world, target_size)
            _last_zoom = zoom
            _scaled_mask_dirty = False
        elif _scaled_mask_dirty:
            target_size = (int(WORLD_W*zoom), int(WORLD_H*zoom))
            _cached_mask = pygame.transform.scale(mask_world, target_size)
            _scaled_mask_dirty = False

        if _cached_bg is not None:
            screen.blit(_cached_bg, (VIEW.x+ox, VIEW.y+oy))
        if _cached_mask is not None:
            m = _cached_mask.copy(); m.set_alpha(preview_alpha); screen.blit(m, (VIEW.x+ox, VIEW.y+oy))
        if show_edges and _cached_edges is not None:
            screen.blit(_cached_edges, (VIEW.x+ox, VIEW.y+oy))

    # translucent grid overlay
    if grid_on:
        step = max(4, int(grid_size * zoom))
        grid_surf = pygame.Surface((VIEW.w, VIEW.h), pygame.SRCALPHA)
        gcol = (0, 0, 0, 60)
        offx = int((VIEW.x + int(ox)) % step)
        offy = int((VIEW.y + int(oy)) % step)
        for x in range(offx, VIEW.w, step):
            pygame.draw.line(grid_surf, gcol, (x, 0), (x, VIEW.h), 1)
        for y in range(offy, VIEW.h, step):
            pygame.draw.line(grid_surf, gcol, (0, y), (VIEW.w, y), 1)
        screen.blit(grid_surf, (VIEW.x, VIEW.y))

    if mode == "create":
        prev_w = max(1, int(round(brush_w * zoom)))

        if create_tool in (TOOL_BRUSH, TOOL_LINE) and points:
            col = (0, 140, 90)
            pts = points[:]
            mx, my = pygame.mouse.get_pos()
            wx, wy = screen_to_world(mx, my)

            if pygame.key.get_mods() & pygame.KMOD_SHIFT and pts:
                ax, ay = pts[-1]
                if abs(wx - ax) > abs(wy - ay):
                    wy = ay
                else:
                    wx = ax

            if grid_on:
                wx = round(wx / grid_size) * grid_size
                wy = round(wy / grid_size) * grid_size

            pts2 = pts + [(int(wx), int(wy))]

            if create_tool == TOOL_LINE:
                ortho = orthogonalize_pts(pts2)
                if len(ortho) == 1:
                    ax, ay = world_to_screen(*ortho[0])
                    pygame.draw.rect(screen, col, pygame.Rect(int(ax - prev_w//2), int(ay - prev_w//2), prev_w, prev_w))
                else:
                    for (x1,y1),(x2,y2) in zip(ortho, ortho[1:]):
                        ax, ay = world_to_screen(x1, y1)
                        bx, by = world_to_screen(x2, y2)
                        _draw_axis_rect_segment_screen(ax, ay, bx, by, prev_w, col)
                    for (jx, jy) in ortho:
                        sx, sy = world_to_screen(jx, jy)
                        pygame.draw.rect(screen, col, pygame.Rect(int(sx - prev_w//2), int(sy - prev_w//2), prev_w, prev_w))
            else:
                for a, b in zip(pts2, pts2[1:]):
                    ax, ay = world_to_screen(*a)
                    bx, by = world_to_screen(*b)
                    pygame.draw.line(screen, col, (ax, ay), (bx, by), prev_w)

        if create_tool in (TOOL_DOOR_NEXT, TOOL_DOOR_BACK) and door_points:
            col = DOOR_NEXT_OVERLAY_OUTLINE if create_tool==TOOL_DOOR_NEXT else DOOR_BACK_OVERLAY_OUTLINE
            mx, my = pygame.mouse.get_pos()
            wx, wy = screen_to_world(mx, my)

            if pygame.key.get_mods() & pygame.KMOD_SHIFT and door_points:
                ax, ay = door_points[-1]
                if abs(wx - ax) > abs(wy - ay):
                    wy = ay
                else:
                    wx = ax

            if grid_on:
                wx = round(wx / grid_size) * grid_size
                wy = round(wy / grid_size) * grid_size

            pts2 = door_points + [(int(wx), int(wy))]
            for a, b in zip(pts2, pts2[1:]):
                ax, ay = world_to_screen(*a)
                bx, by = world_to_screen(*b)
                pygame.draw.line(screen, col, (ax, ay), (bx, by), prev_w)
            for (jx, jy) in pts2:
                sx, sy = world_to_screen(jx, jy)
                pygame.draw.circle(screen, col, (sx, sy), max(1, prev_w//2))

    if sel_kind=="stroke" and sel_idx is not None and 0<=sel_idx<len(strokes):
        b = stroke_bounds(strokes[sel_idx])
        tl=world_to_screen(b.left,b.top); br=world_to_screen(b.right,b.bottom)
        pygame.draw.rect(screen, (120,110,170), pygame.Rect(tl,(br[0]-tl[0], br[1]-tl[1])), 1)
    if sel_kind=="door" and sel_idx is not None and 0<=sel_idx<len(doors):
        b = door_bounds(doors[sel_idx])
        tl=world_to_screen(b.left,b.top); br=world_to_screen(b.right,b.bottom)
        pygame.draw.rect(screen, (200,160,40), pygame.Rect(tl,(br[0]-tl[0], br[1]-tl[1])), 1)

    if doors:
        for d in doors:
            if not d.get('visible', True):
                continue
            pts = d['pts']; kind = d.get('kind','next')
            w_scr = max(1, int(round(d.get('w', brush_w) * zoom)))
            if len(pts) >= 2:
                outline = DOOR_NEXT_OVERLAY_OUTLINE if kind=='next' else DOOR_BACK_OVERLAY_OUTLINE
                for a,b in zip(pts, pts[1:]):
                    ax,ay = world_to_screen(*a); bx,by = world_to_screen(*b)
                    pygame.draw.line(screen, outline, (ax,ay), (bx,by), w_scr)
                if len(pts) >= 3:
                    ax,ay = world_to_screen(*pts[-1]); bx,by = world_to_screen(*pts[0])
                    pygame.draw.line(screen, outline, (ax,ay), (bx,by), w_scr)
                for (jx,jy) in pts:
                    sx,sy = world_to_screen(jx,jy)
                    pygame.draw.circle(screen, outline, (sx,sy), max(1, w_scr//2))

    if spawn_pos is not None:
        sx, sy = world_to_screen(spawn_pos[0], spawn_pos[1])
        sz = max(2, int(SPAWN_SIZE * zoom))
        rect = pygame.Rect(sx - sz//2, sy - sz//2, sz, sz)
        pygame.draw.rect(screen, SPAWN_COLOR, rect); pygame.draw.rect(screen, SPAWN_BORDER, rect, 1)

    for x,y in entry_next_spawns:
        sx, sy = world_to_screen(x,y)
        sz = max(2, int(ENTRY_MARK_SIZE * zoom))
        r = pygame.Rect(sx - sz//2, sy - sz//2, sz, sz)
        pygame.draw.rect(screen, ENTRY_NEXT_OVERLAY, r, 0); pygame.draw.rect(screen, C_FRAME, r, 1)
    for x,y in entry_back_spawns:
        sx, sy = world_to_screen(x,y)
        sz = max(2, int(ENTRY_MARK_SIZE * zoom))
        r = pygame.Rect(sx - sz//2, sy - sz//2, sz, sz)
        pygame.draw.rect(screen, ENTRY_BACK_OVERLAY, r, 0); pygame.draw.rect(screen, C_FRAME, r, 1)

    mx,my=pygame.mouse.get_pos(); wx,wy=screen_to_world(mx,my)
    if bg_world is not None and 0<=wx<WORLD_W and 0<=wy<WORLD_H:
        c = bg_world.get_at((clamp(int(wx),0,WORLD_W-1), clamp(int(wy),0,WORLD_H-1)))
    else:
        c = (0,0,0)
    swatch = pygame.Rect(VIEW.right-54, VIEW.y+10, 44, 18)
    px_rect(screen, swatch, c, C_FRAME)
    text(screen, f"{c[0]},{c[1]},{c[2]}", (VIEW.right-130, VIEW.y+10), C_TEXT_DIM, font_small)
    screen.set_clip(clip_old)

PHASE = "start"   # "start" | "editor"
start_pressed: Optional[str]   = None

def main():
    global tool, create_tool, mode, dragging, drag_started, last_mouse, sel_kind, sel_idx, ox, oy, last_click_time
    global space_pan, mmb_pan, brush_w, grid_on, preview_alpha, simplify_on, sym_x, sym_y, renaming, rename_buf
    global history_show, help_show, zoom, show_edges, spawn_pos, points, door_points
    global entry_next_spawns, entry_back_spawns, edges_overlay, _cached_edges, _last_zoom, PHASE
    global toolbar_pressed, start_pressed, bg_world, BG_PATH, topbar_pressed, tab_pressed, tab_close_pressed
    global tabs, active_tab
    global drag_anchor_world, drag_orig_pts_cache
    global thickness_dragging
    global file_menu_open, file_menu_items, file_menu_item_rects, file_menu_rect
    global hidden_recent_stack, hidden_recent_set

    fit_to_view()
    running=True
    cached_start_hit: Optional[Dict[str, Any]] = None

    topbar_hit_cache: Optional[Dict[str, pygame.Rect]] = None

    def slider_set_from_mouse(mx: int):
        global brush_w
        if not topbar_hit_cache or "thickness_track" not in topbar_hit_cache:
            return
        tr = topbar_hit_cache["thickness_track"]
        if tr.w <= 0:
            return
        t = (mx - tr.x) / float(tr.w)
        t = max(0.0, min(1.0, t))
        new_w = int(round(WIDTH_MIN + t * (WIDTH_MAX - WIDTH_MIN)))
        new_w = int(clamp(new_w, WIDTH_MIN, WIDTH_MAX))
        if new_w != brush_w:
            brush_w = new_w
            update_mask()
            mark_dirty()

    while running:
        _dt = clock.tick(120)
        mx,my = pygame.mouse.get_pos()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                can_quit = True
                for i in range(len(tabs)-1, -1, -1):
                    if not maybe_save_before_close(i):
                        can_quit = False; break
                if can_quit:
                    running=False

            if PHASE == "start":
                if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    start_pressed, action = startmenu_handle(e, (mx, my), cached_start_hit or {}, start_pressed)
                    if action:
                        kind, payload = action
                        if kind == "import":
                            tab_new_from_png(); PHASE = "editor"
                        elif kind == "open":
                            tab_open_project(); PHASE = "editor"
                        elif kind == "quit":
                            running = False
                        elif kind == "recent":
                            try:
                                idx = int(payload)
                            except Exception:
                                idx = None
                            if idx is not None:
                                try:
                                    recs_drawn = (cached_start_hit or {}).get("recents", [])
                                    pth = None
                                    if 0 <= idx < len(recs_drawn):
                                        item = recs_drawn[idx]
                                        if isinstance(item, dict):
                                            pth = item.get("path")
                                        elif isinstance(item, (list, tuple)):
                                            if len(item) >= 2:
                                                pth = item[1]
                                    if pth:
                                        tabs_save_current()
                                        _load_project_from_path(pth)
                                        name=os.path.basename(pth)
                                        t = make_tab_dict(name, BG_PATH, bg_world)
                                        t["project_path"]=pth
                                        tabs.append(t); tabs_load(len(tabs)-1); PHASE="editor"; mark_clean()
                                    else:
                                        print("Failed to open recent: could not resolve path from hitmap")
                                except Exception as ex:
                                    print("Failed to open recent:", ex)
                        elif kind == "hide_recent":
                            if payload and isinstance(payload, dict):
                                pth = payload.get("path")
                                if pth and pth not in hidden_recent_set:
                                    hidden_recent_set.add(pth)
                                    hidden_recent_stack.append(pth)
                        elif kind == "unhide_last":
                            if hidden_recent_stack:
                                pth = hidden_recent_stack.pop()
                                if pth in hidden_recent_set:
                                    hidden_recent_set.remove(pth)
                        elif kind == "delete_recent":
                            if payload and isinstance(payload, dict):
                                pth = payload.get("path")
                                if pth:
                                    _remove_recent(pth)
                                    if pth in hidden_recent_set:
                                        hidden_recent_set.remove(pth)
                                    try:
                                        while pth in hidden_recent_stack:
                                            hidden_recent_stack.remove(pth)
                                    except Exception:
                                        pass

                screen.fill(C_BG)
                all_recents = _recent_list()
                visible_for_now = [p for p in all_recents if p not in hidden_recent_set]
                uptime_s = (pygame.time.get_ticks() - app_start_ms)/1000.0
                cached_start_hit = draw_start_menu(
                    screen, (mx, my), FONTS, visible_for_now, start_pressed,
                    title_text="Welcome!", uptime_s=uptime_s, auto_hide_min=30
                )
                pygame.display.flip()
                continue

            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                space_pan=True
            if e.type == pygame.KEYUP   and e.key == pygame.K_SPACE:
                space_pan=False; dragging=False; drag_started=False

            if e.type == pygame.MOUSEWHEEL and VIEW.collidepoint((mx,my)):
                if pygame.key.get_mods() & pygame.KMOD_ALT:
                    preview_alpha = clamp(preview_alpha + (10 if e.y>0 else -10), 10, 255)
                else:
                    if e.y>0: zoom_to(zoom*1.1,(mx,my))
                    elif e.y<0: zoom_to(zoom/1.1,(mx,my))

            if e.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                if (mods & pygame.KMOD_CTRL) and e.key == pygame.K_n: tab_new_from_png()
                if (mods & pygame.KMOD_CTRL) and (mods & pygame.KMOD_SHIFT) and e.key == pygame.K_o: tab_open_project()

                if e.key == pygame.K_PAGEUP:   mode="edit";  tool=TOOL_MOVE
                if e.key == pygame.K_PAGEDOWN: mode="create"; tool=create_tool
                if e.key == pygame.K_b: create_tool=TOOL_BRUSH; mode="create"; tool=create_tool; points.clear(); door_points.clear()
                if e.key == pygame.K_l: create_tool=TOOL_LINE;  mode="create"; tool=create_tool; points.clear(); door_points.clear()
                if e.key == pygame.K_o: create_tool=TOOL_DOOR_NEXT;  mode="create"; tool=create_tool; points.clear(); door_points.clear()
                if e.key == pygame.K_u: create_tool=TOOL_DOOR_BACK;  mode="create"; tool=create_tool; points.clear(); door_points.clear()
                if e.key == pygame.K_y: mode="edit"; tool=TOOL_ENTRY_NEXT
                if e.key == pygame.K_m: mode="edit"; tool=TOOL_ENTRY_BACK
                if e.key == pygame.K_p: mode="edit"; tool=TOOL_SPAWN
                if e.key == pygame.K_h: mode="edit"; tool=TOOL_HAND

                if e.key == pygame.K_1: zoom_to(0.75,(mx,my))
                if e.key == pygame.K_2: zoom_to(1.0,(mx,my))
                if e.key == pygame.K_3: zoom_to(2.0,(mx,my))
                if e.key == pygame.K_LEFTBRACKET:  brush_w = clamp(brush_w-1, WIDTH_MIN, WIDTH_MAX); update_mask(); mark_dirty()
                if e.key == pygame.K_RIGHTBRACKET: brush_w = clamp(brush_w+1, WIDTH_MIN, WIDTH_MAX); update_mask(); mark_dirty()
                if e.key == pygame.K_MINUS: preview_alpha = clamp(preview_alpha-10, 10, 255); mark_dirty()
                if e.key == pygame.K_EQUALS: preview_alpha = clamp(preview_alpha+10, 10, 255); mark_dirty()
                if e.key == pygame.K_g: grid_on = not grid_on; mark_dirty()
                if e.key == pygame.K_x: sym_x = not sym_x; mark_dirty()
                if e.key == pygame.K_t: sym_y = not sym_y; mark_dirty()
                if e.key == pygame.K_s: simplify_on = not simplify_on; mark_dirty()
                if e.key == pygame.K_e:
                    show_edges = not show_edges
                    if show_edges and edges_overlay is None and bg_world is not None:
                        edges_overlay = compute_edges_surface(bg_world)
                        _cached_edges = None; _last_zoom = -1.0

                if e.key == pygame.K_UP and not (mods & pygame.KMOD_CTRL):
                    all_count = len(strokes) + len(doors)
                    if all_count:
                        if sel_kind is None or sel_idx is None:
                            sel_kind, sel_idx = ("stroke", 0) if len(strokes)>0 else ("door", 0)
                        else:
                            si = cast(int, sel_idx)
                            flat_index = (si if sel_kind=="stroke" else len(strokes)+si) - 1
                            if flat_index < 0: flat_index = all_count-1
                            if flat_index < len(strokes): sel_kind, sel_idx = "stroke", flat_index
                            else: sel_kind, sel_idx = "door", flat_index - len(strokes)
                if e.key == pygame.K_DOWN and not (mods & pygame.KMOD_CTRL):
                    all_count = len(strokes) + len(doors)
                    if all_count:
                        if sel_kind is None or sel_idx is None:
                            sel_kind, sel_idx = ("stroke", 0) if len(strokes)>0 else ("door", 0)
                        else:
                            si = cast(int, sel_idx)
                            flat_index = (si if sel_kind=="stroke" else len(strokes)+si) + 1
                            if flat_index >= all_count: flat_index = 0
                            if flat_index < len(strokes): sel_kind, sel_idx = "stroke", flat_index
                            else: sel_kind, sel_idx = "door", flat_index - len(strokes)

                if (mods & pygame.KMOD_CTRL) and e.key == pygame.K_UP: reorder_layer(-1)
                if (mods & pygame.KMOD_CTRL) and e.key == pygame.K_DOWN: reorder_layer(+1)

                if e.key == pygame.K_l and sel_kind is not None and sel_idx is not None and not renaming:
                    if sel_kind=="stroke":
                        strokes[cast(int, sel_idx)]['locked'] = not strokes[cast(int, sel_idx)].get('locked', False); update_mask(); mark_dirty()
                    else:
                        doors[cast(int, sel_idx)]['locked'] = not doors[cast(int, sel_idx)].get('locked', False); mark_dirty()
                if e.key == pygame.K_F2 and sel_kind is not None and sel_idx is not None:
                    renaming = True
                    if sel_kind=="stroke": rename_buf = strokes[cast(int, sel_idx)].get('name',"")
                    else: rename_buf = doors[cast(int, sel_idx)].get('name',"")

                if renaming:
                    if e.key == pygame.K_RETURN and sel_kind is not None and sel_idx is not None:
                        if sel_kind=="stroke": strokes[cast(int, sel_idx)]['name']=_sanitize_name(rename_buf)
                        else: doors[cast(int, sel_idx)]['name']=_sanitize_name(rename_buf)
                        renaming=False; mark_dirty()
                    elif e.key == pygame.K_ESCAPE: renaming=False
                    elif e.key == pygame.K_BACKSPACE: rename_buf = rename_buf[:-1]
                    else:
                        ch = e.unicode
                        if ch.isprintable(): rename_buf += ch

                if e.key == pygame.K_DELETE and sel_kind is not None and sel_idx is not None:
                    push_undo()
                    if sel_kind=="stroke":
                        idx = cast(int, sel_idx)
                        strokes.pop(idx); update_mask()
                        if not strokes and doors: sel_kind, sel_idx = "door", 0
                        elif strokes: sel_idx = clamp(idx, 0, len(strokes)-1)
                        else: sel_kind, sel_idx = None, None
                    else:
                        idx = cast(int, sel_idx)
                        doors.pop(idx)
                        if doors: sel_idx = clamp(idx, 0, len(doors)-1)
                        elif strokes: sel_kind, sel_idx = "stroke", 0
                        else: sel_kind, sel_idx = None, None

                if e.key == pygame.K_d and not (mods & pygame.KMOD_CTRL) and sel_kind is not None and sel_idx is not None:
                    push_undo()
                    if sel_kind=="stroke":
                        idx = cast(int, sel_idx)
                        strokes.append(copy.deepcopy(strokes[idx])); sel_idx=len(strokes)-1; update_mask()
                    else:
                        idx = cast(int, sel_idx)
                        doors.append(copy.deepcopy(doors[idx])); sel_idx=len(doors)-1

                if (mods & pygame.KMOD_CTRL) and e.key == pygame.K_BACKSPACE:
                    push_undo(); clear_all()
                if (mods & pygame.KMOD_CTRL) and (mods & pygame.KMOD_SHIFT) and e.key == pygame.K_s:
                    save_project(save_as=True)
                if (mods & pygame.KMOD_CTRL) and e.key == pygame.K_o:
                    load_project_into_current()
                if (mods & pygame.KMOD_CTRL) and e.key == pygame.K_s:
                    save_mask_png()

                if e.key in (pygame.K_RETURN,):
                    if mode=="create":
                        if create_tool==TOOL_BRUSH and len(points)>=2:
                            push_undo(); pts=points[:] + symmetry_mirror_pts(points)
                            commit_points('poly', pts); points.clear()
                        elif create_tool==TOOL_LINE and len(points)>=2:
                            push_undo()
                            base = orthogonalize_pts(points[:])
                            pts = base + symmetry_mirror_pts(base)
                            commit_points('straight_poly', pts); points.clear()
                        elif create_tool in (TOOL_DOOR_NEXT, TOOL_DOOR_BACK) and len(door_points)>=3:
                            push_undo()
                            pts = door_points[:] + symmetry_mirror_pts(door_points)
                            kind = 'next' if create_tool==TOOL_DOOR_NEXT else 'back'
                            commit_door_points(pts, kind); door_points.clear()

                if e.key == pygame.K_ESCAPE and mode=="create" and create_tool in (TOOL_DOOR_NEXT, TOOL_DOOR_BACK):
                    door_points.clear()

                if e.key == pygame.K_F9: history_show = not history_show
                if e.key == pygame.K_F1: help_show = not help_show
                if (mods & pygame.KMOD_CTRL) and e.key == pygame.K_z: do_undo()
                if (mods & pygame.KMOD_CTRL) and e.key == pygame.K_y: do_redo()

            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button==1:
                    if topbar_hit_cache:
                        file_btn = topbar_hit_cache.get("file")
                        if file_btn and file_btn.collidepoint((mx,my)):
                            file_menu_open = not file_menu_open
                            file_menu_items = _assets_bat_files() if file_menu_open else []
                            file_menu_item_rects = []
                            file_menu_rect = None
                        elif topbar_hit_cache.get("save") and topbar_hit_cache["save"].collidepoint((mx,my)):
                            topbar_pressed="save"
                        elif topbar_hit_cache.get("new") and topbar_hit_cache["new"].collidepoint((mx,my)):
                            topbar_pressed="new"
                        elif topbar_hit_cache.get("open") and topbar_hit_cache["open"].collidepoint((mx,my)):
                            topbar_pressed="open"

                        if (topbar_hit_cache.get("thickness_knob") and topbar_hit_cache["thickness_knob"].collidepoint((mx,my))) or \
                           (topbar_hit_cache.get("thickness_track") and topbar_hit_cache["thickness_track"].collidepoint((mx,my))):
                            thickness_dragging = True
                            slider_set_from_mouse(mx)

                    if file_menu_open:
                        btn = topbar_hit_cache.get("file") if topbar_hit_cache else None
                        inside_btn = (btn and btn.collidepoint((mx,my)))
                        inside_menu = (file_menu_rect and file_menu_rect.collidepoint((mx,my)))
                        if not inside_btn and not inside_menu:
                            file_menu_open = False
                            file_menu_items = []
                            file_menu_item_rects = []
                            file_menu_rect = None

                if e.button in (1,2) and tabs:
                    _, rects, closes = draw_tabs_bar(screen, FONTS, tabs, active_tab, pressed=tab_pressed)
                    for i,r in enumerate(rects):
                        if r.collidepoint((mx,my)):
                            if e.button==1: tab_pressed=i
                            else: close_tab(i)
                            break
                    for i,cx in enumerate(closes):
                        if cx.collidepoint((mx,my)):
                            tab_close_pressed=i; break

                btns,_=draw_left_toolbar(screen, FONTS, (mx,my), tool, pressed=toolbar_pressed)
                for key, rect, _ in btns:
                    if rect.collidepoint((mx,my)) and e.button==1:
                        toolbar_pressed = key

                if VIEW.collidepoint((mx,my)):
                    wx,wy = screen_to_world(mx,my)
                    if grid_on:
                        wx = round(wx / grid_size) * grid_size
                        wy = round(wy / grid_size) * grid_size
                    now = pygame.time.get_ticks()
                    dbl=(now-last_click_time)<=DOUBLE_CLICK_MS; last_click_time=now

                    if (space_pan and e.button==1) or e.button==2:
                        dragging=True; mmb_pan = (e.button==2); last_mouse=(mx,my); drag_started=False

                    elif tool==TOOL_SPAWN and e.button in (1,3,2):
                        if e.button==1:
                            push_undo(); globals()['spawn_pos'] = (int(wx), int(wy))
                        else:
                            push_undo(); globals()['spawn_pos'] = None

                    elif tool==TOOL_ENTRY_NEXT:
                        if e.button==1:
                            push_undo(); entry_next_spawns.append((int(wx),int(wy)))
                        elif e.button in (3,2):
                            if entry_next_spawns:
                                sx,sy=int(wx),int(wy)
                                idx=min(range(len(entry_next_spawns)),
                                        key=lambda i:(entry_next_spawns[i][0]-sx)**2+(entry_next_spawns[i][1]-sy)**2)
                                if (entry_next_spawns[idx][0]-sx)**2+(entry_next_spawns[idx][1]-sy)**2 <= 36:
                                    push_undo(); entry_next_spawns.pop(idx)
                    elif tool==TOOL_ENTRY_BACK:
                        if e.button==1:
                            push_undo(); entry_back_spawns.append((int(wx),int(wy)))
                        elif e.button in (3,2):
                            if entry_back_spawns:
                                sx,sy=int(wx),int(wy)
                                idx=min(range(len(entry_back_spawns)),
                                        key=lambda i:(entry_back_spawns[i][0]-sx)**2+(entry_back_spawns[i][1]-sy)**2)
                                if (entry_back_spawns[idx][0]-sx)**2+(entry_back_spawns[idx][1]-sy)**2 <= 36:
                                    push_undo(); entry_back_spawns.pop(idx)

                    elif mode=="create" and create_tool==TOOL_BRUSH and e.button==1:
                        if pygame.key.get_mods() & pygame.KMOD_SHIFT and points:
                            ax,ay=points[-1]
                            if abs(wx-ax)>abs(wy-ay): wy=ay
                            else: wx=ax
                        if dbl and len(points)>=2:
                            push_undo(); pts=points[:] + symmetry_mirror_pts(points)
                            commit_points('poly', pts); points.clear()
                        else:
                            points.append((int(wx),int(wy)))

                    elif mode=="create" and create_tool==TOOL_LINE and e.button==1:
                        if dbl and len(points)>=2:
                            push_undo()
                            base = orthogonalize_pts(points[:])
                            pts = base + symmetry_mirror_pts(base)
                            commit_points('straight_poly', pts)
                            points.clear()
                        else:
                            points.append((int(wx),int(wy)))

                    elif mode=="create" and create_tool in (TOOL_DOOR_NEXT, TOOL_DOOR_BACK):
                        if e.button == 1:
                            if pygame.key.get_mods() & pygame.KMOD_SHIFT and door_points:
                                ax, ay = door_points[-1]
                                if abs(wx-ax) > abs(wy-ay): wy = ay
                                else: wx = ax
                            if dbl and len(door_points) >= 3:
                                push_undo()
                                pts = door_points[:] + symmetry_mirror_pts(door_points)
                                kind = 'next' if create_tool==TOOL_DOOR_NEXT else 'back'
                                commit_door_points(pts, kind)
                                door_points.clear()
                            else:
                                door_points.append((int(wx), int(wy)))
                        elif e.button == 3:
                            if door_points:
                                door_points.pop()

                    elif tool==TOOL_MOVE and e.button==1:
                        didx = hit_test_doors((wx,wy))
                        sidx = hit_test_strokes((wx,wy))
                        if didx is not None and (not doors[didx].get('locked',False)):
                            sel_kind, sel_idx = "door", didx
                            dragging=True; drag_started=False
                            drag_anchor_world=(wx,wy)
                            drag_orig_pts_cache = doors[didx]['pts'][:]
                        elif sidx is not None and (not strokes[sidx].get('locked',False)):
                            sel_kind, sel_idx = "stroke", sidx
                            dragging=True; drag_started=False
                            drag_anchor_world=(wx,wy)
                            drag_orig_pts_cache = strokes[sidx]['pts'][:]

                rows_local = draw_right_panel(screen, FONTS, strokes, doors,
                                              {"kind": sel_kind, "idx": sel_idx}, renaming, rename_buf)
                for kind, i, rr, eye, lkr in rows_local:
                    if rr.collidepoint((mx,my)) and e.button==1:
                        sel_kind, sel_idx = kind, i
                    if eye.collidepoint((mx,my)) and e.button==1:
                        if kind=="stroke":
                            strokes[i]['visible']=not strokes[i].get('visible',True); update_mask(); mark_dirty()
                        else:
                            doors[i]['visible']=not doors[i].get('visible',True); mark_dirty()
                    if lkr.collidepoint((mx,my)) and e.button==1:
                        if kind=="stroke":
                            strokes[i]['locked']=not strokes[i].get('locked',False); mark_dirty()
                        else:
                            doors[i]['locked']=not doors[i].get('locked',False); mark_dirty()

            if e.type == pygame.MOUSEBUTTONUP:
                if e.button==1:
                    target = topbar_pressed; topbar_pressed=None
                    if target and topbar_hit_cache and topbar_hit_cache.get(target) and topbar_hit_cache[target].collidepoint((mx,my)):
                        if target=="save":
                            save_project()
                        elif target=="new":
                            tab_new_from_png()
                        elif target=="open":
                            tab_open_project()

                    thickness_dragging = False

                    if file_menu_open and file_menu_rect:
                        mxu, myu = mx, my
                        if file_menu_rect.collidepoint((mxu, myu)):
                            for (rr, item) in zip(file_menu_item_rects, file_menu_items):
                                if rr.collidepoint((mxu, myu)):
                                    _run_bat(item[1])
                                    break

                    if tabs:
                        _bar, rects, close_rects = draw_tabs_bar(screen, FONTS, tabs, active_tab, pressed=tab_pressed)
                        if tab_pressed is not None:
                            i = tab_pressed; tab_pressed=None
                            if 0<=i<len(rects) and rects[i].collidepoint((mx,my)):
                                tabs_save_current(); tabs_load(i)
                        if tab_close_pressed is not None:
                            i = tab_close_pressed; tab_close_pressed=None
                            if 0<=i<len(close_rects) and close_rects[i].collidepoint((mx,my)):
                                close_tab(i)

                    if toolbar_pressed is not None:
                        key_up = toolbar_pressed; toolbar_pressed=None
                        btns,_=draw_left_toolbar(screen, FONTS, (mx,my), tool)
                        clicked_inside = None
                        for key, rect, _ in btns:
                            if key==key_up and rect.collidepoint((mx,my)):
                                clicked_inside = key; break
                        if clicked_inside is not None:
                            key = clicked_inside
                            if key in (TOOL_BRUSH,TOOL_LINE,TOOL_DOOR_NEXT,TOOL_DOOR_BACK):
                                create_tool=key; mode="create"; tool=create_tool
                                points.clear(); door_points.clear()
                            elif key==TOOL_MOVE: mode="edit"; tool=TOOL_MOVE
                            elif key==TOOL_HAND: mode="edit"; tool=TOOL_HAND
                            elif key==TOOL_SPAWN: mode="edit"; tool=TOOL_SPAWN
                            elif key==TOOL_ENTRY_NEXT: mode="edit"; tool=TOOL_ENTRY_NEXT
                            elif key==TOOL_ENTRY_BACK: mode="edit"; tool=TOOL_ENTRY_BACK
                            elif key=="fit": fit_and_center()
                            elif key=="clear":
                                push_undo(); clear_all()
                            elif key=="del" and sel_kind is not None and sel_idx is not None:
                                push_undo()
                                if sel_kind=="stroke":
                                    idx = cast(int, sel_idx)
                                    strokes.pop(idx); update_mask()
                                    if not strokes and doors: sel_kind, sel_idx = "door", 0
                                    elif strokes: sel_idx = clamp(idx, 0, len(strokes)-1)
                                    else: sel_kind, sel_idx = None, None
                                else:
                                    idx = cast(int, sel_idx)
                                    doors.pop(idx)
                                    if doors: sel_idx = clamp(idx, 0, len(doors)-1)
                                    elif strokes: sel_kind, sel_idx = "stroke", 0
                                    else: sel_kind, sel_idx = None, None
                            elif key=="dup" and sel_kind is not None and sel_idx is not None:
                                push_undo()
                                if sel_kind=="stroke":
                                    idx = cast(int, sel_idx)
                                    strokes.append(copy.deepcopy(strokes[idx])); sel_idx=len(strokes)-1; update_mask()
                                else:
                                    idx = cast(int, sel_idx)
                                    doors.append(copy.deepcopy(doors[idx])); sel_idx=len(doors)-1

                if e.button == 2:
                    mmb_pan = False
                dragging=False; drag_started=False
                drag_anchor_world=None; drag_orig_pts_cache=[]

            if e.type == pygame.MOUSEMOTION:
                if thickness_dragging:
                    slider_set_from_mouse(e.pos[0])
                if dragging:
                    if (tool==TOOL_HAND) or space_pan or mmb_pan:
                        ox += (e.pos[0]-last_mouse[0]); oy += (e.pos[1]-last_mouse[1]); last_mouse=e.pos
                    elif tool==TOOL_MOVE and sel_kind is not None and sel_idx is not None and drag_anchor_world is not None:
                        wx,wy = screen_to_world(e.pos[0], e.pos[1])
                        dx = wx - drag_anchor_world[0]
                        dy = wy - drag_anchor_world[1]
                        if not drag_started:
                            push_undo(); drag_started=True
                        if sel_kind=="stroke" and not strokes[cast(int, sel_idx)].get('locked',False):
                            st = strokes[cast(int, sel_idx)]
                            st['pts']=[(int(round(x+dx)), int(round(y+dy))) for (x,y) in drag_orig_pts_cache]
                            update_mask()
                        elif sel_kind=="door" and not doors[cast(int, sel_idx)].get('locked',False):
                            d=doors[cast(int, sel_idx)]
                            d['pts']=[(int(round(x+dx)), int(round(y+dy))) for (x,y) in drag_orig_pts_cache]

        if PHASE == "start":
            continue

        screen.fill(C_BG)

        topbar_hit_cache = draw_topbar(screen, FONTS, pressed=topbar_pressed, thickness=int(brush_w))

        _bar, _tab_rects, _tab_closes = draw_tabs_bar(screen, FONTS, tabs, active_tab, pressed=tab_pressed)

        btns, hovered = draw_left_toolbar(screen, FONTS, (mx,my), tool, pressed=toolbar_pressed)
        _rows = draw_right_panel(screen, FONTS, strokes, doors,
                                 {"kind": sel_kind, "idx": sel_idx}, renaming, rename_buf)

        draw_viewport()

        file_menu_rect = None
        file_menu_item_rects = []
        if file_menu_open and topbar_hit_cache and topbar_hit_cache.get("file"):
            anchor = topbar_hit_cache["file"]
            f = FONTS["btn"]
            pad_x = 12
            row_h = 26
            max_w = 140
            for disp, _full in file_menu_items:
                max_w = max(max_w, f.size(disp)[0] + pad_x*2)

            menu_h = 4 + len(file_menu_items)*row_h + 4
            file_menu_rect = pygame.Rect(anchor.x, anchor.bottom + 2, max_w, menu_h)

            px_rect(screen, file_menu_rect, (250, 250, 253), C_FRAME, 2)

            y = file_menu_rect.y + 4
            mx_now, my_now = pygame.mouse.get_pos()
            for disp, _full in file_menu_items:
                rr = pygame.Rect(file_menu_rect.x + 2, y, file_menu_rect.w - 4, row_h)
                hovered_row = rr.collidepoint((mx_now, my_now))
                if hovered_row:
                    pygame.draw.rect(screen, (232, 236, 244), rr)
                text(screen, disp, (rr.x + pad_x, rr.y + 4), C_TEXT, f)
                file_menu_item_rects.append(rr)
                y += row_h

        if hovered:
            px_tooltip(hovered[0], hovered[1])

        info = {
            "mode": mode, "tool": tool, "brush_w": int(brush_w), "zoom": zoom,
            "grid_on": grid_on, "sym_x": sym_x, "sym_y": sym_y,
            "spawn_pos": spawn_pos,
            "n_door_next": sum(1 for d in doors if d.get('kind','next')=='next'),
            "n_door_back": sum(1 for d in doors if d.get('kind','next')=='back'),
            "n_entry_next": len(entry_next_spawns),
            "n_entry_back": len(entry_back_spawns),
        }
        wx,wy = screen_to_world(mx,my)
        msg = f"{int(wx)}, {int(wy)}"
        if mode=="create":
            if create_tool in (TOOL_BRUSH, TOOL_LINE) and points: msg += f"  pts:{len(points)}"
            if create_tool in (TOOL_DOOR_NEXT, TOOL_DOOR_BACK) and door_points: msg += f"  door_pts:{len(door_points)}"
        draw_status(screen, FONTS, msg, info)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print("💥 Error:", ex)
        pygame.quit(); sys.exit(1)
