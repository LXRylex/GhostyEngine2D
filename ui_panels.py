from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import pygame

from theme import (
    LEFTBAR_W, RIGHTBAR_W, TOPBAR_H, TABS_H, STATUS_H, WIN_W, WIN_H,
    C_PANEL, C_PANEL_DARK, C_FRAME, C_FRAME_DIM,
    C_TEXT, C_TEXT_DIM, C_OK, C_WARN,
)
from ui_widgets import px_rect, px_button, text, trunc_text, text_center_in_rect

def _font(fonts: Dict[str, pygame.font.Font], key: str, fallback_key: str = "base") -> pygame.font.Font:
    f = fonts.get(key) or fonts.get(fallback_key)
    return f if f is not None else pygame.font.SysFont(None, 16)

def draw_topbar(
    screen: pygame.Surface,
    fonts: Dict[str, pygame.font.Font],
    *,
    pressed: Optional[str] = None,
    thickness: Optional[int] = None,
    geo: Optional[Dict] = None,
):
    f_btn   = _font(fonts, "btn")
    f_small = _font(fonts, "small")

    x = 10
    h = TOPBAR_H - 12
    gap = 8

    file_r = pygame.Rect(x, 6, 70, h); x = file_r.right + gap
    save_r = pygame.Rect(x, 6, 72, h); x = save_r.right + gap
    new_r  = pygame.Rect(x, 6, 64, h); x = new_r.right + gap
    open_r = pygame.Rect(x, 6, 68, h); x = open_r.right + gap

    px_button(screen, file_r, pressed=(pressed == "file"))
    text_center_in_rect(screen, "File", file_r, C_TEXT, f_btn)

    px_button(screen, save_r, active=True, pressed=(pressed == "save"))
    text_center_in_rect(screen, "Save", save_r, C_OK, f_btn)

    px_button(screen, new_r, pressed=(pressed == "new"))
    text_center_in_rect(screen, "New", new_r, C_TEXT, f_btn)

    px_button(screen, open_r, pressed=(pressed == "open"))
    text_center_in_rect(screen, "Open", open_r, C_TEXT, f_btn)

    hit = {"file": file_r, "save": save_r, "new": new_r, "open": open_r}
    if thickness is not None:
        track_w = 180
        track_h = 10
        track = pygame.Rect(
            WIN_W - RIGHTBAR_W - track_w - 20,
            6 + (h - track_h) // 2,
            track_w, track_h
        )
        label = f"W:{int(thickness)}"
        text(screen, label, (track.x - f_small.size(label)[0] - 8, track.y - 6), C_TEXT_DIM, f_small)

        pygame.draw.rect(screen, (220, 223, 230), track, border_radius=5)

        t = max(0.0, min(1.0, (float(thickness) - 1.0) / 149.0))
        kx = int(track.x + t * track.w)
        knob = pygame.Rect(kx - 5, track.centery - 8, 10, 16)
        pygame.draw.rect(screen, (160, 165, 175), knob, border_radius=3)

        hit["thickness_track"] = track
        hit["thickness_knob"]  = knob

    return hit

def draw_tabs_bar(
    screen: pygame.Surface,
    fonts: Dict[str, pygame.font.Font],
    tabs: List[Dict],
    active_tab: int,
    *,
    pressed: Optional[int] = None,
) -> Tuple[pygame.Rect, List[pygame.Rect], List[pygame.Rect]]:
    f_base  = _font(fonts, "base")
    f_small = _font(fonts, "small")

    bar = pygame.Rect(LEFTBAR_W, TOPBAR_H, WIN_W - LEFTBAR_W, TABS_H)
    px_rect(screen, bar, C_PANEL, C_FRAME)

    x = bar.x + 8
    max_w = bar.w - 16
    tab_h = TABS_H - 6
    tab_min_w = 120
    total = max(1, len(tabs))
    w_each = max(tab_min_w, min(240, (max_w - 8 * total) // total))

    rects: List[pygame.Rect] = []
    close_rects: List[pygame.Rect] = []

    for i, t in enumerate(tabs):
        r = pygame.Rect(x, bar.y + 3, w_each, tab_h)
        px_button(screen, r, active=(i == active_tab), pressed=(pressed == i))

        name = str(t.get("name", "Untitled"))
        if t.get("dirty"):
            name = "*" + name

        label_w_avail = r.w - 24 - 10
        name_show = trunc_text(name, f_base, label_w_avail)

        label_area = pygame.Rect(r.x + 6, r.y + 2, r.w - 24 - 12, r.h - 4)
        text_center_in_rect(screen, name_show, label_area, C_TEXT, f_base)

        cx = pygame.Rect(r.right - 20, r.y + 5, 14, 14)
        px_rect(screen, cx, C_PANEL, C_FRAME)
        text_center_in_rect(screen, "x", cx, C_WARN, f_small)

        rects.append(r)
        close_rects.append(cx)
        x += w_each + 8

    return bar, rects, close_rects

def draw_status(
    screen: pygame.Surface,
    fonts: Dict[str, pygame.font.Font],
    left_msg: str,
    info: Dict,
) -> None:
    f_small = _font(fonts, "small")

    r = pygame.Rect(0, WIN_H - STATUS_H, WIN_W, STATUS_H)
    px_rect(screen, r, C_PANEL, C_FRAME)

    mode     = info.get("mode", "")
    tool     = info.get("tool", "")
    brush_w  = int(info.get("brush_w", 0))
    zoom_pct = int(round(100 * float(info.get("zoom", 1.0))))
    grid_on  = bool(info.get("grid_on", False))
    sym_x    = bool(info.get("sym_x", False))
    sym_y    = bool(info.get("sym_y", False))
    spawn    = info.get("spawn_pos", None)

    n_next   = int(info.get("n_door_next", 0))
    n_back   = int(info.get("n_door_back", 0))
    n_en     = int(info.get("n_entry_next", 0))
    n_eb     = int(info.get("n_entry_back", 0))

    right = (
        f"Mode:{mode}  Tool:{tool}  W:{brush_w}px  Zoom:{zoom_pct}%  "
        f"Grid:{'on' if grid_on else 'off'}  SymX:{sym_x} SymY:{sym_y}"
    )
    if spawn:
        try:
            sx, sy = int(spawn[0]), int(spawn[1])
            right += f"  Spawn:{sx},{sy}"
        except Exception:
            pass
    right += f"  Doors►:{n_next}  ◄:{n_back}   Entry►:{n_en}  ◄:{n_eb}"

    text(screen, left_msg, (8, WIN_H - STATUS_H + 3), C_TEXT_DIM, f_small)
    text(screen, right, (WIN_W - 780, WIN_H - STATUS_H + 3), C_TEXT_DIM, f_small)

def draw_left_toolbar(
    screen: pygame.Surface,
    fonts: Dict[str, pygame.font.Font],
    mouse_pos: Tuple[int, int],
    tool: str,
    *,
    pressed: Optional[str] = None,
):
    f_tiny = _font(fonts, "tiny")

    r = pygame.Rect(0, TOPBAR_H + TABS_H, LEFTBAR_W, WIN_H - TOPBAR_H - TABS_H - STATUS_H)
    px_rect(screen, r, C_PANEL_DARK, C_FRAME)

    btns = []
    size = 30
    gap  = 6
    inner_w = LEFTBAR_W - 12
    cols = max(1, (inner_w + gap) // (size + gap))
    start_x = 6
    start_y = r.y + 10

    items = [
        ("brush", "B", "Brush (Create)"),
        ("line",  "L", "Line (Create)"),
        ("door_next", "O", "Door► (Next)"),
        ("door_back", "U", "Door◄ (Back)"),
        ("move", "Mv", "Move (Edit)"),
        ("hand", "H", "Hand pan"),
        ("spawn", "P", "Spawn marker"),
        ("entry_spawn_next", "Y", "Entry► (yellow)"),
        ("entry_spawn_back", "M", "Entry◄ (magenta)"),
        ("dup", "Dup", "Duplicate selected"),
        ("del", "Del", "Delete selected"),
        ("clear", "Clr", "Clear all"),
        ("fit", "Fit", "Fit & center"),
    ]

    hovered = None
    mx, my = mouse_pos

    for idx, (key, label, tip) in enumerate(items):
        col_idx = idx % cols
        row_idx = idx // cols
        b = pygame.Rect(
            start_x + col_idx * (size + gap),
            start_y + row_idx * (size + gap),
            size, size
        )
        px_button(screen, b, active=(key == tool), pressed=(pressed == key))
        text_center_in_rect(screen, label, b, C_TEXT, f_tiny)
        btns.append((key, b, tip))
        if b.collidepoint((mx, my)):
            hovered = (tip, b)

    return btns, hovered

def draw_right_panel(
    screen: pygame.Surface,
    fonts: Dict[str, pygame.font.Font],
    strokes: List[Dict],
    doors: List[Dict],
    selection: Dict[str, int | str | None],
    renaming: bool,
    rename_buf: str,
):
    f_hdr   = _font(fonts, "hdr")
    f_layer = _font(fonts, "layer", "base")

    r = pygame.Rect(WIN_W - RIGHTBAR_W, TOPBAR_H + TABS_H, RIGHTBAR_W, WIN_H - TOPBAR_H - TABS_H - STATUS_H)
    px_rect(screen, r, C_PANEL_DARK, C_FRAME)

    text(screen, "Layers  (F2 rename · L lock · Eye)", (r.x + 12, r.y + 8), C_TEXT_DIM, f_hdr)

    list_r = pygame.Rect(r.x + 10, r.y + 36, r.w - 20, r.h - 46)
    px_rect(screen, list_r, C_PANEL, C_FRAME)

    rows = []
    row_h = 40
    header_h = f_hdr.get_height()
    header_gap = 10

    sel_kind = selection.get("kind")
    sel_idx  = selection.get("idx")

    yoff = list_r.y
    text(screen, "Walls", (list_r.x + 8, yoff), C_TEXT_DIM, f_hdr)
    yoff += header_h + header_gap

    for i, st in enumerate(strokes):
        y = yoff + i * row_h
        if y > list_r.bottom - row_h:
            break
        rr = pygame.Rect(list_r.x + 6, y, list_r.w - 12, row_h - 6)
        is_selected = (sel_kind == "stroke" and sel_idx == i)
        px_rect(screen, rr, (245, 245, 248) if is_selected else (240, 240, 244), C_FRAME)

        eye = pygame.Rect(rr.x + 8, rr.y + 8, 20, 20)
        px_rect(screen, eye, C_PANEL_DARK if st.get('visible', True) else (230, 230, 235), C_FRAME)
        pygame.draw.circle(screen, (C_FRAME if st.get('visible', True) else C_FRAME_DIM), eye.center, 6, 2)

        lock_r = pygame.Rect(eye.right + 8, rr.y + 9, 16, 16)
        px_rect(screen, lock_r, C_PANEL, C_FRAME)
        if st.get('locked', False):
            pygame.draw.line(screen, C_WARN, (lock_r.left + 2, lock_r.top + 2), (lock_r.right - 2, lock_r.bottom - 2), 2)
            pygame.draw.line(screen, C_WARN, (lock_r.left + 2, lock_r.bottom - 2), (lock_r.right - 2, lock_r.top + 2), 2)

        name_max_w = rr.right - (lock_r.right + 12) - 10
        nm = st.get('name', f"Stroke {i:02d}") or ""
        nm = trunc_text(nm, f_layer, name_max_w)
        label_col = C_TEXT
        if not st.get('visible', True):
            label_col = C_TEXT_DIM
        if st.get('locked', False):
            label_col = C_WARN

        if renaming and sel_kind == "stroke" and sel_idx == i:
            edit_r = pygame.Rect(lock_r.right + 12, rr.y + 8, name_max_w, 22)
            px_rect(screen, edit_r, (252, 252, 255), C_FRAME)
            show = trunc_text(rename_buf, f_layer, name_max_w - 8)
            text(screen, show, (edit_r.x + 4, edit_r.y + 2), C_TEXT, f_layer)
        else:
            text(screen, nm, (lock_r.right + 12, rr.y + 8), label_col, f_layer)

        rows.append(("stroke", i, rr, eye, lock_r))

    yoff += len(strokes) * row_h + header_gap * 2

    text(screen, "Doors", (list_r.x + 8, yoff), C_TEXT_DIM, f_hdr)
    yoff += header_h + header_gap

    for i, d in enumerate(doors):
        y = yoff + i * row_h
        if y > list_r.bottom - row_h:
            break
        rr = pygame.Rect(list_r.x + 6, y, list_r.w - 12, row_h - 6)
        is_selected = (sel_kind == "door" and sel_idx == i)
        px_rect(screen, rr, (245, 248, 252) if is_selected else (240, 242, 246), C_FRAME)

        eye = pygame.Rect(rr.x + 8, rr.y + 8, 20, 20)
        px_rect(screen, eye, C_PANEL_DARK if d.get('visible', True) else (230, 230, 235), C_FRAME)
        pygame.draw.circle(screen, (C_FRAME if d.get('visible', True) else C_FRAME_DIM), eye.center, 6, 2)

        lock_r = pygame.Rect(eye.right + 8, rr.y + 9, 16, 16)
        px_rect(screen, lock_r, C_PANEL, C_FRAME)
        if d.get('locked', False):
            pygame.draw.line(screen, C_WARN, (lock_r.left + 2, lock_r.top + 2), (lock_r.right - 2, lock_r.bottom - 2), 2)
            pygame.draw.line(screen, C_WARN, (lock_r.left + 2, d.get('locked', False) and lock_r.bottom - 2 or lock_r.bottom - 2), (lock_r.right - 2, lock_r.top + 2), 2)

        kind = d.get('kind', 'next')
        tag  = "►" if kind == 'next' else "◄"
        nm   = f"{tag} " + (d.get('name', f"Door {i:02d}") or "")
        name_max_w = rr.right - (lock_r.right + 12) - 10
        nm = trunc_text(nm, f_layer, name_max_w)
        label_col = (0, 120, 70) if kind == 'next' else (0, 70, 140)
        if not d.get('visible', True):
            label_col = C_TEXT_DIM
        if d.get('locked', False):
            label_col = C_WARN

        if renaming and sel_kind == "door" and sel_idx == i:
            edit_r = pygame.Rect(lock_r.right + 12, rr.y + 8, name_max_w, 22)
            px_rect(screen, edit_r, (252, 252, 255), C_FRAME)
            show = trunc_text(rename_buf, f_layer, name_max_w - 8)
            text(screen, show, (edit_r.x + 4, edit_r.y + 2), C_TEXT, f_layer)
        else:
            text(screen, nm, (lock_r.right + 12, rr.y + 8), label_col, f_layer)

        rows.append(("door", i, rr, eye, lock_r))

    return rows
