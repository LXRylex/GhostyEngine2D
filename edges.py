from __future__ import annotations
from typing import Any, cast
import pygame
import numpy as np
from theme import C_FRAME, clamp

def compute_edges_surface(bg: pygame.Surface) -> pygame.Surface:
    arr = cast(Any, pygame.surfarray.pixels3d(bg)).copy()
    w, h = bg.get_width(), bg.get_height()
    edges = pygame.Surface((w, h), flags=0, depth=32).convert_alpha()

    px = cast(Any, pygame.surfarray.pixels_alpha(edges))
    px[:] = 0
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            gx = abs(int(arr[x + 1, y].mean()) - int(arr[x - 1, y].mean()))
            gy = abs(int(arr[x, y + 1].mean()) - int(arr[x, y - 1].mean()))
            g = clamp(gx + gy, 0, 255)
            px[x, y] = g
    del px

    rgb = cast(Any, pygame.surfarray.pixels3d(edges))
    rgb[:, :, 0] = C_FRAME[0]
    rgb[:, :, 1] = C_FRAME[1]
    rgb[:, :, 2] = C_FRAME[2]
    edges.set_alpha(90)
    return edges
