from __future__ import annotations
from typing import Tuple
import pygame
from theme import (
    C_PANEL, C_FRAME, C_TEXT,
    C_BTN, C_BTN_PRESSED, C_BTN_ACTIVE, C_BTN_BORDER,
    C_BTN_DANGER, C_BTN_DANGER_PRS,
)

def px_rect(surf: pygame.Surface, r: pygame.Rect, fill, border, bw: int = 1) -> None:
    pygame.draw.rect(surf, fill, r)
    if bw > 0:
        pygame.draw.rect(surf, border, r, bw)

def px_button(
    surf: pygame.Surface,
    r: pygame.Rect,
    *,
    active: bool = False,
    pressed: bool = False,
    danger: bool = False
) -> None:
    if danger:
        fill = C_BTN_DANGER_PRS if pressed else C_BTN_DANGER
    else:
        if active:
            fill = C_BTN_ACTIVE
        elif pressed:
            fill = C_BTN_PRESSED
        else:
            fill = C_BTN
    px_rect(surf, r, fill, C_BTN_BORDER, 2)

def text(
    surf: pygame.Surface,
    s: str,
    pos: Tuple[int, int],
    col = C_TEXT,
    f: pygame.font.Font | None = None
) -> None:
    font = f or pygame.font.SysFont(None, 14)
    surf.blit(font.render(s, False, col), pos)

def text_center_in_rect(
    surf: pygame.Surface,
    s: str,
    r: pygame.Rect,
    col = C_TEXT,
    f: pygame.font.Font | None = None
) -> None:
    font = f or pygame.font.SysFont(None, 14)
    w, h = font.size(s)
    x = r.x + (r.w - w) // 2
    y = r.y + (r.h - h) // 2
    surf.blit(font.render(s, False, col), (x, y))

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
