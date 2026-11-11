# GLOBAL COMMIT: 21
# OWNER: Nijhum
# COMMIT MESSAGE: Add renderer typography and horror background
# REPOSITORY DESTINATION: zombiehood/ui.py
# Cumulative snapshot: replace destination contents with this file.
# Partial stage; follow GLOBAL_SERIAL.md before running.

"""Rendering, HUD and menus matching the exact ZombieHood HTML/SVG UI."""
import math
import os
import random
import pygame
from game import Phase

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CREEPSTER = os.path.join(_BASE_DIR, "Creepster-Regular.ttf")
_PIXEL     = os.path.join(_BASE_DIR, "PressStart2P-Regular.ttf")

W, H = 1720, 960

INK   = (225, 232, 225)
DIM   = (155, 187, 187)     # #9bb in HTML
RED   = (224, 38, 43)       # #e0262b in HTML
GOLD  = (255, 210, 63)      # #ffd23f in HTML
GREEN = (110, 255, 140)

# Colors matching the HTML stylesheet
BG_DARK      = (11, 15, 20)        # #0b0f14
PANEL_BG     = (16, 24, 38)        # #101826
PANEL_BORDER = (47, 66, 88)        # #2f4258
BOARD_BORDER = (47, 106, 79)       # #2f6a4f
TILE_A       = (28, 54, 56)        # rgba(28,54,56,.7)
TILE_B       = (25, 48, 51)        # rgba(25,48,51,.7)
TILE_ZOMBIE  = (107, 26, 29)       # rgba(107,26,29,.85)
OUTLINE_Z    = (176, 42, 46)       # #b02a2e


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Renderer:
    def __init__(self, screen, cfg):
        self.screen, self.cfg = screen, cfg
        self.board_w = W - 560
        self.board_h = H - 160
        self.cell = self.board_w / max(cfg.rows, cfg.cols)
        self.BX = (W - self.board_w) // 2
        self.BY = 168
        self.fonts = {}
        self.buttons = []
        self.menu_mode = "main"        # "main", "select_difficulty", "select_human"
        self.chosen_mode = "ai"        # "ai" or "human"
        self.chosen_diff = getattr(cfg, "difficulty", "hard")  # "easy", "medium", "hard"
        self.bg_static = self._make_static_background()

        # Animated bats: (x, y, speed, scale, phase)
        self.bats = [
            [-120.0, 150.0, 58.0, 1.0, 0.0],
            [-60.0,  90.0,  44.0, 1.4, 2.5],
            [-200.0, 180.0, 36.0, 0.8, 5.0],
        ]

        # Continuous marching zombies across bottom without stops or jerks
        # [x_pos, direction, scale, speed_pixels_per_sec]
        self.marcher_data = [
            [   0.0,  1, 1.30, 32.0],
            [ 200.0,  1, 0.90, 26.0],
            [ 420.0,  1, 1.55, 36.0],
            [ 640.0,  1, 1.10, 29.0],
            [ 860.0,  1, 1.40, 34.0],
            [ 100.0, -1, 1.30, 31.0],
            [ 320.0, -1, 0.90, 25.0],
            [ 540.0, -1, 1.55, 37.0],
            [ 760.0, -1, 1.10, 28.0],
            [ 980.0, -1, 1.40, 33.0],
        ]
        self._last_tick = pygame.time.get_ticks()

    # ------------------------------------------------------------ fonts & text
    def font(self, size, bold=True, title=False, pixel=False):
        key = (size, bold, title, pixel)
        if key not in self.fonts:
            if title:
                if os.path.exists(_CREEPSTER):
                    try:
                        self.fonts[key] = pygame.font.Font(_CREEPSTER, size)
                    except Exception:
                        self.fonts[key] = pygame.font.SysFont("chiller,copperplategothic,georgia", size)
                else:
                    self.fonts[key] = pygame.font.SysFont("chiller,copperplategothic,georgia", size)
            elif pixel:
                if os.path.exists(_PIXEL):
                    try:
                        self.fonts[key] = pygame.font.Font(_PIXEL, size)
                    except Exception:
                        self.fonts[key] = pygame.font.SysFont("consolas,couriernew", size, bold=bold)
                else:
                    self.fonts[key] = pygame.font.SysFont("consolas,couriernew", size, bold=bold)
            else:
                self.fonts[key] = pygame.font.SysFont("segoeuiemoji,segoeui,trebuchetms,arial,dejavusans", size, bold=bold)
        return self.fonts[key]

    def text(self, s, size, color, pos, anchor="topleft", bold=True, title=False, pixel=False, surf=None):
        img = self.font(size, bold=bold, title=title, pixel=pixel).render(str(s), True, color)
        r = img.get_rect(**{anchor: pos})
        (surf or self.screen).blit(img, r)
        return r

    def panel(self, rect, bg=PANEL_BG, border=PANEL_BORDER, width=3, radius=8):
        pygame.draw.rect(self.screen, bg, rect, border_radius=radius)
        if width:
            pygame.draw.rect(self.screen, border, rect, width, border_radius=radius)

    def set_config(self, cfg):
        self.cfg = cfg
        self.chosen_diff = getattr(cfg, "difficulty", "hard")
        self.board_w = W - 560
        self.board_h = H - 160
        self.cell = self.board_w / max(cfg.rows, cfg.cols)
        self.BX = (W - self.board_w) // 2

    def cell_rect(self, pos):
        return pygame.Rect(self.BX + pos[1] * self.cell,
                           self.BY + pos[0] * self.cell,
                           self.cell, self.cell)

    # ------------------------------------------------------------ background drawing
    def _make_static_background(self):
        s = pygame.Surface((W, H))

        # 1. Sky gradient: #0a0510 (0%) -> #2a0a14 (60%) -> #0b0f0d (100%)
        c_top = (10, 5, 16)
        c_mid = (42, 10, 20)
        c_bot = (11, 15, 13)
        h_mid = int(H * 0.6)
        for y in range(H):
            if y < h_mid:
                col = lerp(c_top, c_mid, y / max(1, h_mid))
            else:
                col = lerp(c_mid, c_bot, (y - h_mid) / max(1, H - h_mid))
            s.fill(col, (0, y, W, 1))

        # 2. Ambient radial tints:
        # Greenish #1f4a3a55 at (20%, 30%)
        glow_g = pygame.Surface((400, 400), pygame.SRCALPHA)
        for r in range(200, 0, -10):
            pygame.draw.circle(glow_g, (31, 74, 58, int(22 * (1 - r / 200))), (200, 200), r)
        s.blit(glow_g, (int(W * 0.2) - 200, int(H * 0.3) - 200))

        # Purplish #3a1f5a66 at (80%, 80%)
        glow_p = pygame.Surface((500, 500), pygame.SRCALPHA)
        for r in range(250, 0, -10):
            pygame.draw.circle(glow_p, (58, 31, 90, int(26 * (1 - r / 250))), (250, 250), r)
        s.blit(glow_p, (int(W * 0.8) - 250, int(H * 0.8) - 250))

        # 3. Blood Moon: cx=int(W*0.775)=775, cy=110
        mx, my = int(W * 0.775), 110
        moon_glow = pygame.Surface((340, 340), pygame.SRCALPHA)
        for r in range(170, 0, -6):
            pygame.draw.circle(moon_glow, (255, 42, 42, int(60 * (1 - r / 170))), (170, 170), r)
        s.blit(moon_glow, (mx - 170, my - 170))
        pygame.draw.circle(s, (196, 22, 28), (mx, my), 52)          # #c4161c
        pygame.draw.circle(s, (142, 15, 20), (mx - 16, my - 13), 10)  # crater
        pygame.draw.circle(s, (142, 15, 20), (mx + 17, my + 15), 7)   # crater

        # 4. Bare dead trees (matching SVG paths scaled to canvas)
        tree_col = (4, 6, 10)
        # Left tree
        pygame.draw.line(s, tree_col, (80, H), (80, H - 320), 13)
        for (y1, x2, y2) in ((H - 200, 25, H - 290),
                             (H - 250, 150, H - 360),
                             (H - 320, 55, H - 410),
                             (H - 260, 12, H - 350)):
            pygame.draw.line(s, tree_col, (80, y1), (x2, y2), 7)
        pygame.draw.line(s, tree_col, (150, H - 360), (185, H - 410), 6)

        # Right tree
        rx = W - 80
        pygame.draw.line(s, tree_col, (rx, H), (rx, H - 350), 13)
        for (y1, x2, y2) in ((H - 210, rx + 55, H - 305),
                             (H - 265, rx - 75, H - 375),
                             (H - 330, rx + 25, H - 435),
                             (H - 275, rx + 70, H - 360)):
            pygame.draw.line(s, tree_col, (rx, y1), (x2, y2), 7)
        pygame.draw.line(s, tree_col, (rx - 75, H - 375), (rx - 110, H - 420), 6)

        # 5. Tombstones & Crypts along bottom (#06090c)
        tomb_col = (6, 9, 12)
        tombs = [
            (0, H - 75, 110, 75, 0),
            (145, H - 55, 55, 55, 24),
            (210, H - 42, 40, 42, 18),
            (W - 250, H - 65, 60, 65, 26),
            (W - 190, H - 35, 42, 35, 16),
            (W - 130, H - 50, 130, 50, 0),
        ]
        for (tx, ty, tw, th, tr) in tombs:
            if tr > 0:
                pygame.draw.rect(s, tomb_col, (tx, ty, tw, th),
                                 border_top_left_radius=tr, border_top_right_radius=tr)
            else:
                pygame.draw.rect(s, tomb_col, (tx, ty, tw, th))

        # 6. Spider webs in top corners (stroke #cfd6dc with opacity .4)
        web_s = pygame.Surface((W, 250), pygame.SRCALPHA)
        web_col = (207, 214, 220, 100)
        # Left web
        strands_l = [(180, 180), (130, 230), (230, 120), (70, 240), (240, 50)]
        for ex, ey in strands_l:
            pygame.draw.line(web_s, web_col, (0, 0), (ex, ey), 1)
        for r in (50, 100, 150, 200):
            pts = [(int(ex * r / 200), int(ey * r / 200)) for ex, ey in strands_l]
            for i in range(len(pts) - 1):
                pygame.draw.line(web_s, web_col, pts[i], pts[i + 1], 1)

        # Right web
        strands_r = [(W - ex, ey) for ex, ey in strands_l]
        for ex, ey in strands_r:
            pygame.draw.line(web_s, web_col, (W, 0), (ex, ey), 1)
        for r in (50, 100, 150, 200):
            pts = [(int(W - ex * r / 200), int(ey * r / 200)) for ex, ey in strands_l]
            for i in range(len(pts) - 1):
                pygame.draw.line(web_s, web_col, pts[i], pts[i + 1], 1)
        s.blit(web_s, (0, 0))

        # 7. Blood drips from ceiling (#8a0c12)
        pygame.draw.line(s, (138, 12, 18), (0, 2), (W, 2), 6)
        drips = [
            (75, 45), (180, 26), (290, 58), (410, 32),
            (530, 52), (680, 35), (820, 48), (920, 28)
        ]
        for dx, dh in drips:
            pygame.draw.line(s, (138, 12, 18), (dx, 2), (dx, dh), 5)
            pygame.draw.circle(s, (138, 12, 18), (dx, dh + 2), 3)

        # 8. Hanging Spider on thread at x=55
        pygame.draw.line(s, (170, 170, 170), (55, 0), (55, 125), 1)
        pygame.draw.circle(s, (10, 10, 10), (55, 129), 6)
        pygame.draw.circle(s, (68, 68, 68), (55, 129), 6, 1)
        for lx, ly in [(-8, -4), (-9, 2), (8, -4), (9, 2)]:
            pygame.draw.line(s, (68, 68, 68), (55, 129), (55 + lx, 129 + ly), 1)

        # 9. Vignette shadow along outer edges
        vig = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.rect(vig, (0, 0, 0, 90), (0, 0, W, H), width=24)
        s.blit(vig, (0, 0))

        return s

    def _draw_hanging_skull(self, x, y_pivot, rope_len, scale, t):
        """Swinging skull on rope matching the HTML SVG exactly."""
        angle = math.sin(t / 650.0 + x) * 0.07
        rope_end_x = x + math.sin(angle) * rope_len
        rope_end_y = y_pivot + math.cos(angle) * rope_len
        pygame.draw.line(self.screen, (34, 34, 34), (x, y_pivot), (rope_end_x, rope_end_y), 2)

        cx, cy = int(rope_end_x), int(rope_end_y)
        rx = int(22 * scale)
        ry = int(25 * scale)

        # Cranium (#d9d6c0)
        cranium = pygame.Rect(cx - rx, cy - ry, rx * 2, ry * 2)
        pygame.draw.ellipse(self.screen, (217, 214, 192), cranium)

        # Jaw (#d9d6c0)
        jw, jh = int(24 * scale), int(14 * scale)
        jaw = pygame.Rect(cx - jw // 2, cy + int(14 * scale), jw, jh)
        pygame.draw.rect(self.screen, (217, 214, 192), jaw, border_radius=3)

        # Eye sockets (#050505) with red glowing pupils (#ff3333)
        er = int(6 * scale)
        for ex in (-int(8 * scale), int(8 * scale)):
            pygame.draw.circle(self.screen, (5, 5, 5), (cx + ex, cy - int(2 * scale)), er)
            pygame.draw.circle(self.screen, (255, 51, 51), (cx + ex, cy - int(1 * scale)), max(2, int(2 * scale)))

        # Nose cavity
        nw = int(3 * scale)
        pygame.draw.polygon(self.screen, (5, 5, 5), [
            (cx, cy + int(6 * scale)),
            (cx - nw, cy + int(12 * scale)),
            (cx + nw, cy + int(12 * scale)),
        ])

        # Teeth lines
        for tx in range(-int(8 * scale), int(9 * scale), max(3, int(4 * scale))):
            pygame.draw.line(self.screen, (85, 85, 85),
                             (cx + tx, cy + int(18 * scale)),
                             (cx + tx, cy + int(24 * scale)), 1)

    def _draw_glowing_eyes(self, t):
        """Blinking red evil eyes in background."""
        blink = (int(t / 100) % 55) in (51, 52)
        if blink:
            return
        eye_pairs = [
            (35, 290, 48, 290),
            (W - 45, 275, W - 32, 275),
            (130, H - 75, 142, H - 75),
        ]
        for (x1, y1, x2, y2) in eye_pairs:
            pygame.draw.ellipse(self.screen, (255, 32, 32), (x1 - 3, y1 - 2, 7, 4))
            pygame.draw.ellipse(self.screen, (255, 32, 32), (x2 - 3, y2 - 2, 7, 4))

    def _draw_marching_zombies(self, t):
        """Continuous smooth marching zombies along bottom without stops or jerks."""
        now = t
        dt = min(0.04, max(0.001, (now - self._last_tick) / 1000.0))
        self._last_tick = now

        for m in self.marcher_data:
            x, d, scale, spd = m
            x += d * spd * dt
            if d > 0 and x > W + 90:
                x = -90.0
            elif d < 0 and x < -90:
                x = W + 90.0
            m[0] = x

            bob = int(math.sin(t / 380.0 + x * 0.08) * 2.2)
            y = H - 12 + bob
            self._draw_zombie_silhouette(int(x), y, scale, d)

    def _draw_zombie_silhouette(self, x, y, scale, direction):
        body_col   = (11, 19, 13)       # #0b130d
        stroke_col = (60, 122, 63)      # #3c7a3f
        k = scale

        # Head
        hy = int(y - 62 * k)
        pygame.draw.circle(self.screen, body_col, (x, hy), int(8 * k))
        pygame.draw.circle(self.screen, stroke_col, (x, hy), int(8 * k), 1)

        # Glowing red eye
        ex = x + direction * int(3 * k)
        pygame.draw.circle(self.screen, (255, 42, 42), (ex, hy - int(1 * k)), max(1, int(1.5 * k)))

        # Torso
        torso = [
            (x - int(7 * k), hy + int(8 * k)),
            (x + int(7 * k), hy + int(8 * k)),
            (x + int(9 * k), hy + int(38 * k)),
            (x - int(9 * k), hy + int(38 * k)),
        ]
        pygame.draw.polygon(self.screen, body_col, torso)
        pygame.draw.polygon(self.screen, stroke_col, torso, 1)

        # Arms reaching forward
        arm1_end = (x + direction * int(28 * k), hy + int(14 * k))
        arm2_end = (x + direction * int(25 * k), hy + int(22 * k))
        pygame.draw.line(self.screen, body_col, (x, hy + int(12 * k)), arm1_end, max(2, int(4 * k)))
        pygame.draw.line(self.screen, stroke_col, (x, hy + int(12 * k)), arm1_end, 1)
        pygame.draw.line(self.screen, body_col, (x, hy + int(18 * k)), arm2_end, max(2, int(4 * k)))
        pygame.draw.line(self.screen, stroke_col, (x, hy + int(18 * k)), arm2_end, 1)

        # Legs
        leg1_end = (x - int(5 * k), y)
        leg2_end = (x + int(7 * k), y)
        pygame.draw.line(self.screen, body_col, (x - int(4 * k), hy + int(38 * k)), leg1_end, max(2, int(4 * k)))
        pygame.draw.line(self.screen, body_col, (x + int(4 * k), hy + int(38 * k)), leg2_end, max(2, int(4 * k)))

    # ------------------------------------------------------------ sprites matching HTML SVG








    # ------------------------------------------------------------ main board





    # ------------------------------------------------------------ Header & Cards matching HTML








    # ------------------------------------------------------------ main draw loop
