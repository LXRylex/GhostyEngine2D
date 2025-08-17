from typing import Final

# ---------- Geometry ----------
LEFTBAR_W: Final[int] = 72
RIGHTBAR_W: Final[int] = 270
TOPBAR_H: Final[int]   = 36
TABS_H: Final[int]     = 28
STATUS_H: Final[int]   = 24

# Window baseline (editor canvas target width is 1024 in the middle)
WIN_W: Final[int] = LEFTBAR_W + 1024 + RIGHTBAR_W
WIN_H: Final[int] = TOPBAR_H + TABS_H + 720 + STATUS_H

# ---------- Theme Colors ----------
C_BG         = (248, 248, 250)
C_PANEL      = (238, 238, 242)
C_PANEL_DARK = (224, 224, 230)
C_FRAME      = (24, 24, 28)
C_FRAME_DIM  = (120, 120, 130)
C_TEXT       = (20, 20, 24)
C_TEXT_DIM   = (95, 95, 110)
C_OK         = (18, 150, 90)
C_WARN       = (200, 70, 70)

# Tooltips / overlays
C_TOOLTIP_BG = (250, 250, 252)

# Checkerboard background
C_CHECKER_A  = (235, 235, 240)
C_CHECKER_B  = (228, 228, 234)

# ---------- Buttons ----------
C_BTN            = C_PANEL
C_BTN_PRESSED    = (210, 210, 215)
C_BTN_ACTIVE     = (210, 205, 240)
C_BTN_BORDER     = C_FRAME
C_BTN_DANGER     = (255, 230, 230)
C_BTN_DANGER_PRS = (255, 200, 200)

# ---------- Mask / Draw Params ----------
MASK_DRAW_COLOR     = (255, 255, 255)
MASK_ERASE_COLOR    = (0, 0, 0)
LINE_WIDTH_DEFAULT  = 3
DOUBLE_CLICK_MS     = 400

# ---------- Spawn & Entry Overlays ----------
SPAWN_COLOR = (240, 60, 60)
SPAWN_BORDER = (30, 20, 24)
SPAWN_SIZE = 10

ENTRY_NEXT_OVERLAY = (255, 220, 100)
ENTRY_BACK_OVERLAY = (255, 120, 255)
ENTRY_MARK_SIZE = 8
ENTRY_NEXT_BAKE_COLOR = (255, 255, 0)   # yellow
ENTRY_BACK_BAKE_COLOR = (255, 0, 255)   # magenta

# ---------- Door Overlays ----------
DOOR_NEXT_OVERLAY_OUTLINE = (0, 140, 70)
DOOR_NEXT_OVERLAY_NODE    = (0, 160, 90)
DOOR_BACK_OVERLAY_OUTLINE = (0, 70, 160)
DOOR_BACK_OVERLAY_NODE    = (0, 90, 190)
DOOR_NODE_R_BASE          = 2

# Door fill colors in baked mask
DOOR_NEXT_BAKE_COLOR = (0, 255, 0)   # green
DOOR_BACK_BAKE_COLOR = (0, 0, 255)   # blue

# ---------- Utilities ----------
def clamp(v, lo, hi):
    """Clamp numeric value v into the inclusive range [lo, hi]."""
    return max(lo, min(hi, v))
