from __future__ import annotations
import os
from typing import Dict, Tuple, Any, List
import pygame

from theme import (
    TOPBAR_H, STATUS_H, WIN_W, WIN_H,
    C_BG, C_PANEL, C_FRAME, C_PANEL_DARK, C_TEXT, C_TEXT_DIM,
    C_BTN, C_BTN_PRESSED, C_BTN_ACTIVE, C_BTN_DANGER, C_BTN_DANGER_PRS, C_BTN_BORDER
)

_hidden_set: set[str] = set()
_hidden_stack: List[str] = []

_deleted_set: set[str] = set()

_proj_first_index: int = 0

def px_rect(surf: pygame.Surface, r: pygame.Rect, fill, border, bw: int = 1):
    pygame.draw.rect(surf, fill, r)
    pygame.draw.rect(surf, border, r, bw)

def px_button(
    surf: pygame.Surface,
    r: pygame.Rect,
    *,
    active: bool = False,
    pressed: bool = False,
    danger: bool = False,
    hover: bool = False
):
    if danger:
        fill = C_BTN_DANGER_PRS if (pressed or hover) else C_BTN_DANGER
    else:
        if active:
            fill = C_BTN_ACTIVE
        elif (pressed or hover):
            fill = C_BTN_PRESSED
        else:
            fill = C_BTN
    px_rect(surf, r, fill, C_BTN_BORDER, 2)

def text(surf: pygame.Surface, s: str, pos: Tuple[int, int], col, f: pygame.font.Font):
    surf.blit(f.render(s, False, col), pos)

def trunc_text(s: str, fnt: pygame.font.Font, max_w: int) -> str:
    if fnt.size(s)[0] <= max_w:
        return s
    ell = "..."
    ell_w = fnt.size(ell)[0]
    out = []
    for ch in s:
        out.append(ch)
        if fnt.size("".join(out))[0] + ell_w > max_w:
            return "".join(out[:-1]) + ell
    return s

def draw_start_menu(
    screen: pygame.Surface,
    mouse_pos: Tuple[int, int],
    fonts: Dict[str, pygame.font.Font],
    recent_items: List[str],
    start_pressed: str | None,
    *,
    title_text: str = "Welcome!",
    uptime_s: float = 0.0,
    auto_hide_min: int = 30,
) -> Dict[str, Any]:

    global _proj_first_index

    mx, my = mouse_pos
    screen.fill(C_BG)
    text(screen, title_text, (24, 14), C_TEXT, fonts["title"])

    panel = pygame.Rect(16, TOPBAR_H + 12, WIN_W - 32, WIN_H - TOPBAR_H - STATUS_H - 24)
    px_rect(screen, panel, C_PANEL, C_FRAME, 2)

    full_list = [p for p in recent_items if p not in _deleted_set]

    left = pygame.Rect(panel.x + 12, panel.y + 12, panel.w // 2 - 24, panel.h - 24)
    px_rect(screen, left, C_PANEL_DARK, C_FRAME, 2)

    hide_left = uptime_s >= (auto_hide_min * 60)
    recents_rows: List[Dict[str, Any]] = []

    if hide_left:
        text(screen, f"Recents (hidden after {auto_hide_min} min)", (left.x + 12, left.y + 10), C_TEXT_DIM, fonts["hdr"])
        info = "Use the Projects list on the right to open or delete recent files."
        text(screen, trunc_text(info, fonts["base"], left.w - 24), (left.x + 12, left.y + 46), C_TEXT_DIM, fonts["base"])
    else:
        text(screen, "Recents", (left.x + 12, left.y + 10), C_TEXT, fonts["hdr"])

        # left rows: filter "hidden" (but NOT deleted)
        visible_recents = [p for p in full_list if p not in _hidden_set]

        row_h = 60
        hide_w = 64
        for i_visible, pth in enumerate(visible_recents[:12]):
            # index within the FULL list (engine opens by this)
            try:
                idx_full = full_list.index(pth)
            except ValueError:
                continue

            y = left.y + 40 + i_visible * row_h
            rr = pygame.Rect(left.x + 10, y, left.w - 20, row_h - 10)
            hide_r = pygame.Rect(rr.right - hide_w - 6, rr.y + 6, hide_w, rr.h - 12)

            pressed_row  = (start_pressed == f"recent:{i_visible}")
            pressed_hide = (start_pressed == f"recent_hide:{i_visible}")
            hover_row    = rr.collidepoint((mx, my))
            hover_hide   = hide_r.collidepoint((mx, my))

            # Row opens the recent project
            px_button(screen, rr, pressed=pressed_row, hover=hover_row)
            pygame.draw.rect(screen, C_FRAME, rr, 2)

            base = os.path.basename(pth)
            show_base = trunc_text(base, fonts["btn"], rr.w - hide_w - 28)
            show_dir  = trunc_text(os.path.dirname(pth), fonts["small"], rr.w - hide_w - 28)
            text(screen, show_base, (rr.x + 10, rr.y + 8), C_TEXT, fonts["btn"])
            text(screen, show_dir,  (rr.x + 10, rr.y + 32), C_TEXT_DIM, fonts["small"])

            # Hide button (UI-only: hides from left)
            px_button(screen, hide_r, pressed=pressed_hide, hover=hover_hide)
            hlabel = "Hide"
            tx = hide_r.centerx - fonts["small"].size(hlabel)[0] // 2
            ty = hide_r.centery - fonts["small"].get_height() // 2
            text(screen, hlabel, (tx, ty), C_TEXT, fonts["small"])

            recents_rows.append({"row": rr, "hide": hide_r, "path": pth, "index": idx_full})

    recents_for_engine = []
    offx, offy = -1000, -1000
    for idx_full, pth in enumerate(full_list):
        recents_for_engine.append((pygame.Rect(offx, offy, 10, 10), pth, idx_full))

    right = pygame.Rect(panel.centerx + 12, panel.y + 12, panel.w // 2 - 24, panel.h - 24)
    px_rect(screen, right, C_PANEL_DARK, C_FRAME, 2)
    text(screen, "Actions", (right.x + 12, right.y + 10), C_TEXT, fonts["hdr"])

    btn_h = 52
    b1 = pygame.Rect(right.x + 24, right.y + 60, right.w - 48, btn_h)
    b2 = pygame.Rect(right.x + 24, right.y + 60 + btn_h + 18, right.w - 48, btn_h)
    b3 = pygame.Rect(right.x + 24, right.y + 60 + 2 * (btn_h + 18), right.w - 48, btn_h)
    b4 = pygame.Rect(right.x + 24, right.y + 60 + 3 * (btn_h + 18), right.w - 48, btn_h)

    px_button(screen, b1, pressed=(start_pressed == "import"), hover=b1.collidepoint((mx, my)))
    text(screen, "Import Background (PNG)", (b1.x + 12, b1.y + 13), C_TEXT, fonts["btn"])

    px_button(screen, b2, pressed=(start_pressed == "open"), hover=b2.collidepoint((mx, my)))
    text(screen, "Open Project (.xzenp)", (b2.x + 12, b2.y + 13), C_TEXT, fonts["btn"])

    px_button(screen, b3, pressed=(start_pressed == "quit"), danger=True, hover=b3.collidepoint((mx, my)))
    text(screen, "Quit", (b3.x + 12, b3.y + 13), C_TEXT, fonts["btn"])

    px_button(screen, b4, pressed=(start_pressed == "unhide"), hover=b4.collidepoint((mx, my)))
    text(screen, "Unhide Last Hidden", (b4.x + 12, b4.y + 13), C_TEXT, fonts["btn"])

    proj_panel = pygame.Rect(right.x + 12, b4.bottom + 26, right.w - 24, right.bottom - (b4.bottom + 38))
    px_rect(screen, proj_panel, C_PANEL, C_FRAME, 2)
    text(screen, "Projects", (proj_panel.x + 10, proj_panel.y + 8), C_TEXT, fonts["hdr"])

    pager_h = 28
    prev_btn = pygame.Rect(proj_panel.right - 120, proj_panel.y + 6, 52, pager_h)
    next_btn = pygame.Rect(proj_panel.right - 62,  proj_panel.y + 6, 52, pager_h)
    px_button(screen, prev_btn, hover=prev_btn.collidepoint((mx, my)))
    px_button(screen, next_btn, hover=next_btn.collidepoint((mx, my)))
    text(screen, "Prev", (prev_btn.x + 10, prev_btn.y + 5), C_TEXT, fonts["small"])
    text(screen, "Next", (next_btn.x + 10, next_btn.y + 5), C_TEXT, fonts["small"])

    prow_h = 56
    prow_gap = 8
    projects_rows: List[Dict[str, Any]] = []
    max_rows = max(0, (proj_panel.h - 40) // (prow_h + prow_gap))
    if _proj_first_index < 0:
        _proj_first_index = 0
    if _proj_first_index > max(0, len(full_list) - max_rows):
        _proj_first_index = max(0, len(full_list) - max_rows)

    show_items = full_list[_proj_first_index : _proj_first_index + max_rows]

    for i_local, pth in enumerate(show_items):
        try:
            idx_full = full_list.index(pth)
        except ValueError:
            continue

        y = proj_panel.y + 36 + i_local * (prow_h + prow_gap)
        rr  = pygame.Rect(proj_panel.x + 8, y, proj_panel.w - 16, prow_h)
        del_w = 80
        del_r = pygame.Rect(rr.right - del_w - 6, rr.y + 6, del_w, rr.h - 12)

        pressed_row = (start_pressed == f"proj_open:{i_local}")
        pressed_del = (start_pressed == f"proj_del:{i_local}")
        hover_row   = rr.collidepoint((mx, my))
        hover_del   = del_r.collidepoint((mx, my))

        px_button(screen, rr, pressed=pressed_row, hover=hover_row)
        pygame.draw.rect(screen, C_FRAME, rr, 2)

        base = os.path.basename(pth)
        show_base = trunc_text(base, fonts["base"], rr.w - del_w - 28)
        show_dir  = trunc_text(os.path.dirname(pth), fonts["tiny"], rr.w - del_w - 28)
        text(screen, show_base, (rr.x + 10, rr.y + 8), C_TEXT, fonts["base"])
        text(screen, show_dir,  (rr.x + 10, rr.y + 30), C_TEXT_DIM, fonts["tiny"])

        px_button(screen, del_r, pressed=pressed_del, danger=True, hover=hover_del)
        label = "Delete"
        tx = del_r.centerx - fonts["small"].size(label)[0] // 2
        ty = del_r.centery - fonts["small"].get_height() // 2
        text(screen, label, (tx, ty), C_TEXT, fonts["small"])

        projects_rows.append({"row": rr, "del": del_r, "path": pth, "index": idx_full})

    return {

        "recents": recents_for_engine,
        "recents_rows": recents_rows,
        "projects": projects_rows,
        "btns": {
            "import": b1, "open": b2, "quit": b3, "unhide": b4,
            "proj_prev": prev_btn, "proj_next": next_btn
        },
    }

def handle_event(
    e: pygame.event.Event,
    mouse_pos: Tuple[int, int],
    hitmap: Dict[str, Any],
    start_pressed: str | None
) -> tuple[str | None, tuple[str, Any] | None]:

    global _proj_first_index, _hidden_set, _hidden_stack, _deleted_set

    mx, my = mouse_pos

    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
        if hitmap:

            if hitmap["btns"]["import"].collidepoint((mx, my)):
                return "import", None
            if hitmap["btns"]["open"].collidepoint((mx, my)):
                return "open", None
            if hitmap["btns"]["quit"].collidepoint((mx, my)):
                return "quit", None
            if hitmap["btns"]["unhide"].collidepoint((mx, my)):
                return "unhide", None
            if hitmap["btns"]["proj_prev"].collidepoint((mx, my)):
                return "proj_prev", None
            if hitmap["btns"]["proj_next"].collidepoint((mx, my)):
                return "proj_next", None

            for i, row in enumerate(hitmap.get("recents_rows", [])):
                if row["hide"].collidepoint((mx, my)):
                    return f"recent_hide:{i}", None
                if row["row"].collidepoint((mx, my)):
                    return f"recent:{i}", None

            for i, row in enumerate(hitmap.get("projects", [])):
                if row["del"].collidepoint((mx, my)):
                    return f"proj_del:{i}", None
                if row["row"].collidepoint((mx, my)):
                    return f"proj_open:{i}", None

    if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
        target = start_pressed
        if not target or not hitmap:
            return None, None

        if target == "import" and hitmap["btns"]["import"].collidepoint((mx, my)):
            return None, ("import", None)
        if target == "open" and hitmap["btns"]["open"].collidepoint((mx, my)):
            return None, ("open", None)
        if target == "quit" and hitmap["btns"]["quit"].collidepoint((mx, my)):
            return None, ("quit", None)
        if target == "unhide" and hitmap["btns"]["unhide"].collidepoint((mx, my)):

            if _hidden_stack:
                pth = _hidden_stack.pop()
                _hidden_set.discard(pth)
            return None, ("unhide_last", None)

        if target == "proj_prev" and hitmap["btns"]["proj_prev"].collidepoint((mx, my)):
            _proj_first_index = max(0, _proj_first_index - 1)
            return None, ("projects_page", {"first_index": _proj_first_index})
        if target == "proj_next" and hitmap["btns"]["proj_next"].collidepoint((mx, my)):
            _proj_first_index = _proj_first_index + 1
            return None, ("projects_page", {"first_index": _proj_first_index})

        if target.startswith("recent_hide:"):
            try:
                i = int(target.split(":")[1])
                row = hitmap["recents_rows"][i]
                if row["hide"].collidepoint((mx, my)):
                    p = row["path"]; idx_full = int(row["index"])
                    if p not in _hidden_set:
                        _hidden_set.add(p)
                        _hidden_stack.append(p)
                    return None, ("hide_recent", {"index": idx_full, "path": p})
            except Exception:
                pass
            return None, None

        if target.startswith("recent:"):
            try:
                i = int(target.split(":")[1])
                row = hitmap["recents_rows"][i]
                if row["row"].collidepoint((mx, my)):
                    idx_full = int(row["index"])
                    return None, ("recent", idx_full)
            except Exception:
                pass
            return None, None

        if target.startswith("proj_del:"):
            try:
                i = int(target.split(":")[1])
                row = hitmap["projects"][i]
                if row["del"].collidepoint((mx, my)):
                    p = row["path"]; idx_full = int(row["index"])
                    _deleted_set.add(p)
                    _hidden_set.discard(p)
                    try:
                        while p in _hidden_stack:
                            _hidden_stack.remove(p)
                    except Exception:
                        pass
                    return None, ("delete_recent", {"index": idx_full, "path": p})
            except Exception:
                pass
            return None, None

        if target.startswith("proj_open:"):
            try:
                i = int(target.split(":")[1])
                row = hitmap["projects"][i]
                if row["row"].collidepoint((mx, my)):
                    idx_full = int(row["index"])
                    return None, ("recent", idx_full)
            except Exception:
                pass
            return None, None

        return None, None

    return start_pressed, None
