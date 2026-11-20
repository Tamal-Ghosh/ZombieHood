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
DIALOG_W, DIALOG_H = 1000, 660

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
        self.board_w = W - 80
        self.board_h = H - 90
        self.cell = min(88, self.board_w / max(cfg.rows, cfg.cols))
        self.BX = (W - self.board_w) // 2
        self.BY = 115
        self.board_zoom = 1.0
        self.board_pan = [0.0, 0.0]
        self.board_drag = None
        self.zombie_bounds = []
        self.agent_images = {}
        self.agent_frames = {}
        self.agent_directions = {}
        self.agent_cache = {}
        self.agent_steps = {}
        self.agent_step_state = None
        self._load_agent_sprites()
        self.face_images = []
        self.face_cache = {}
        self.face_assignments = {}
        self.face_state = None
        self._load_zombie_faces()
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
        self.board_w = W - 80
        self.board_h = H - 90
        self.cell = min(88, self.board_w / max(cfg.rows, cfg.cols))
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
    def sprite_soldier(self, rect, color, is_female=False, dead=False):
        """Soldier avatar sprite matching soldier(c, girl) in HTML."""
        cx, cy, u = rect.centerx, rect.centery, rect.width
        if dead:
            # Gravestone
            gw, gh = int(u * 0.52), int(u * 0.6)
            gr = pygame.Rect(cx - gw // 2, cy - gh // 2, gw, gh)
            pygame.draw.rect(self.screen, (120, 125, 130), gr,
                             border_top_left_radius=gw // 2, border_top_right_radius=gw // 2)
            self.text("RIP", int(u * 0.18), (30, 35, 40), (cx, cy), "center")
            return

        # Girl hair on back
        if is_female:
            hair_rect = pygame.Rect(cx + int(0.18 * u), cy - int(0.08 * u), int(0.24 * u), int(0.44 * u))
            pygame.draw.ellipse(self.screen, (107, 58, 26), hair_rect)

        # Face circle (#e8b48a)
        face_r = int(0.31 * u)
        pygame.draw.circle(self.screen, (232, 180, 138), (cx, int(cy + 0.05 * u)), face_r)
        pygame.draw.circle(self.screen, (34, 34, 34), (cx, int(cy + 0.05 * u)), face_r, 2)

        # Helmet (#5a6b3a)
        pts = [(cx + math.cos(math.pi + i * math.pi / 12) * 0.34 * u,
                cy - 0.02 * u + math.sin(math.pi + i * math.pi / 12) * 0.34 * u) for i in range(13)]
        pygame.draw.polygon(self.screen, (90, 107, 58), pts)
        pygame.draw.polygon(self.screen, (34, 34, 34), pts, 2)

        # Helmet band (#3d4a26) and colored headband (color)
        band_y = cy - int(0.08 * u)
        pygame.draw.rect(self.screen, (61, 74, 38), (cx - int(0.33 * u), band_y, int(0.66 * u), int(0.09 * u)))
        pygame.draw.rect(self.screen, color, (cx - int(0.31 * u), band_y + 1, int(0.62 * u), int(0.06 * u)))

        # Eyes (#222)
        for ex in (-int(0.12 * u), int(0.12 * u)):
            pygame.draw.circle(self.screen, (34, 34, 34), (cx + ex, int(cy + 0.14 * u)), max(2, int(0.04 * u)))

        # Mouth (#7a2a1a)
        pygame.draw.line(self.screen, (122, 42, 26),
                         (cx - int(0.08 * u), int(cy + 0.24 * u)),
                         (cx + int(0.08 * u), int(cy + 0.24 * u)), 2)

        # Girl hair clip (#ff7bb5)
        if is_female:
            pygame.draw.circle(self.screen, (255, 123, 181), (cx + int(0.24 * u), cy - int(0.04 * u)), 4)
            pygame.draw.circle(self.screen, (34, 34, 34), (cx + int(0.24 * u), cy - int(0.04 * u)), 4, 1)

    def _load_agent_sprites(self):
        try:
            sheet = pygame.image.load(os.path.join(_BASE_DIR,"assets","agent_survivors_upright.png")).convert_alpha()
            # Source photo order differs from the match's Tamal/Progga/Nijhum order.
            for i,name in enumerate(("Nijhum","Progga","Tamal")):
                left = round(sheet.get_width()*i/3)
                right = round(sheet.get_width()*(i+1)/3)
                sprite = sheet.subsurface((left,0,right-left,sheet.get_height())).copy()
                bounds = sprite.get_bounding_rect(min_alpha=20)
                self.agent_images[name] = sprite.subsurface(bounds).copy()
        except (pygame.error,OSError):
            self.agent_images = {}

        try:
            sheet = pygame.image.load(os.path.join(_BASE_DIR,"assets","agent_walk_frames.png")).convert_alpha()
            for row,name in enumerate(("Nijhum","Progga","Tamal")):
                frames = []
                top,bottom = round(sheet.get_height()*row/3),round(sheet.get_height()*(row+1)/3)
                for col in range(4):
                    left,right = round(sheet.get_width()*col/4),round(sheet.get_width()*(col+1)/4)
                    frame = sheet.subsurface((left,top,right-left,bottom-top)).copy()
                    frames.append(frame.subsurface(frame.get_bounding_rect(min_alpha=20)).copy())
                width = max(f.get_width() for f in frames)
                height = max(f.get_height() for f in frames)
                aligned = []
                for frame in frames:
                    canvas = pygame.Surface((width,height),pygame.SRCALPHA)
                    canvas.blit(frame,frame.get_rect(midbottom=(width//2,height)))
                    aligned.append(canvas)
                self.agent_frames[name] = aligned
        except (pygame.error,OSError):
            self.agent_frames = {}

        for name in ("Nijhum","Progga","Tamal"):
            try:
                sheet = pygame.image.load(os.path.join(_BASE_DIR,"assets",f"agent_directions_{name.lower()}.png")).convert_alpha()
                rows = {}
                for row,direction in enumerate(("RIGHT","DOWN","UP","LEFT")):
                    frames = []
                    top,bottom = round(sheet.get_height()*row/4),round(sheet.get_height()*(row+1)/4)
                    for col in range(4):
                        left,right = round(sheet.get_width()*col/4),round(sheet.get_width()*(col+1)/4)
                        frame = sheet.subsurface((left,top,right-left,bottom-top)).copy()
                        components = pygame.mask.from_surface(frame,100).connected_components(20)
                        # Select the central character, excluding detached generation artifacts.
                        component = max(components,key=lambda m:m.count()/(1+abs(m.get_bounding_rects()[0].centerx-frame.get_width()/2)/frame.get_width()*4))
                        bounds = component.get_bounding_rects()[0]
                        frames.append(frame.subsurface(bounds).copy())
                    rows[direction] = frames
                # One scale and root across the whole turn/walk sheet.
                width = max(f.get_width() for frames in rows.values() for f in frames)
                height = max(f.get_height() for frames in rows.values() for f in frames)
                for direction,frames in rows.items():
                    aligned = []
                    for frame in frames:
                        canvas = pygame.Surface((width,height),pygame.SRCALPHA)
                        canvas.blit(frame,frame.get_rect(midbottom=(width//2,height)))
                        aligned.append(canvas)
                    rows[direction] = aligned
                self.agent_directions[name] = rows
            except (pygame.error,OSError,ValueError):
                continue

    def draw_agent_sprite(self, survivor, rect, portrait=False, t=None):
        source = self.agent_images.get(survivor.name)
        if source is None:
            return False
        frame_index = -1
        facing = getattr(survivor,"facing","RIGHT")
        feet = rect.midbottom
        if not portrait:
            frame_index = 1
            step = self.agent_steps.get(survivor.name)
            if step is None:
                step = dict(pos=survivor.pos,origin=survivor.pos,started=None,leg=0)
                self.agent_steps[survivor.name] = step
            if step["pos"] != survivor.pos:
                step.update(origin=step["pos"],pos=survivor.pos,started=t,leg=2 if step["leg"]==0 else 0)
            if t is not None and step["started"] is not None:
                progress = max(0,min(1,(t-step["started"])/360))
                if progress < 1:
                    # Exactly one footfall per cell: passing, one extended leg, passing.
                    frame_index = step["leg"] if .2 <= progress < .8 else 1
                    start = self.board_point(step["origin"][0]+.5,step["origin"][1]+.5,4)
                    feet = (round(start[0]+(feet[0]-start[0])*progress),
                            round(start[1]+(feet[1]-start[1])*progress-math.sin(progress*math.pi)*2))
            if survivor.reached_goal:
                # Show the original front-facing portrait pose upon reaching the exit.
                frame_index = -1
                facing = "goal_front"
                source = self.agent_images[survivor.name]
                feet = rect.midbottom
            elif survivor.name in self.agent_directions:
                source = self.agent_directions[survivor.name][facing][frame_index]
            elif survivor.name in self.agent_frames:
                source = self.agent_frames[survivor.name][frame_index]
        key = (survivor.name,rect.width,rect.height,portrait,frame_index,facing if not portrait else "portrait")
        if key not in self.agent_cache:
            if portrait:
                head = source.subsurface((0,0,source.get_width(),round(source.get_height()*.34)))
                scale = min(rect.width/head.get_width(),rect.height/head.get_height())
                image = pygame.transform.smoothscale(head,(max(1,round(head.get_width()*scale)),max(1,round(head.get_height()*scale))))
            else:
                scale = min(rect.width/source.get_width(),rect.height/source.get_height())
                image = pygame.transform.smoothscale(source,(max(1,round(source.get_width()*scale)),max(1,round(source.get_height()*scale))))
            self.agent_cache[key] = image
        image = self.agent_cache[key]
        self.screen.blit(image,image.get_rect(center=rect.center) if portrait else image.get_rect(midbottom=feet))
        return True

    def _load_zombie_faces(self):
        sheet_path = os.path.join(_BASE_DIR, "assets", "zombie_fullbody.png")
        try:
            sheet = pygame.image.load(sheet_path).convert_alpha()
            for i in range(5):
                left = round(i * sheet.get_width() / 5)
                right = round((i + 1) * sheet.get_width() / 5)
                sprite = sheet.subsurface((left, 0, right-left, sheet.get_height())).copy()
                bounds = sprite.get_bounding_rect(min_alpha=20)
                self.face_images.append(sprite.subsurface(bounds).copy())
        except (pygame.error, OSError):
            self.face_images = []

    def _assign_zombie_faces(self, state):
        if self.face_state is state:
            return
        self.face_state = state
        self.face_assignments = {}
        if not self.face_images:
            return
        rng = random.Random(state.seed if hasattr(state, "seed") else None)
        bag = []
        for zombie in state.zombies:
            if not bag:
                bag = list(range(len(self.face_images)))
                rng.shuffle(bag)
            self.face_assignments[zombie.id] = bag.pop()

    def _draw_zombie_body(self, pos, size, zombie_id, t=0):
        index = self.face_assignments[zombie_id]
        height = max(52, round(size * 2.5))
        source = self.face_images[index]
        width = round(source.get_width()*height/source.get_height())
        phase = int((t/110+zombie_id*2.3)%24)
        key = ("whole",index,width,height,phase)
        if key not in self.face_cache:
            # One intact image: no cut seams at the neck, shoulders or hands.
            # Oversample before rotation so facial features do not blur repeatedly.
            quality = 3
            sprite = pygame.transform.smoothscale(source,(width*quality,height*quality))
            sprite.fill((24,24,16,0),special_flags=pygame.BLEND_RGB_ADD)
            sway = math.sin(phase*math.tau/24)
            support_x = round(-width*.20 if sway>=0 else width*.20)
            pivot = (width*quality//2+support_x*quality,height*quality-2*quality)
            canvas = pygame.Surface((height*quality*3,height*quality*3),pygame.SRCALPHA)
            center = canvas.get_width()//2
            canvas.blit(sprite,(center-pivot[0],center-pivot[1]))
            rotated = pygame.transform.rotozoom(canvas,sway*10,1)
            # Downsample once, after rotation, preserving the original complete silhouette.
            frame = pygame.transform.smoothscale(rotated,
                         (round(rotated.get_width()/quality),round(rotated.get_height()/quality)))
            bounds = frame.get_bounding_rect(min_alpha=1)
            image = frame.subsurface(bounds).copy()
            anchor = (frame.get_width()//2-bounds.x-support_x,
                      frame.get_height()//2-bounds.y+2)
            self.face_cache[key] = (image,anchor)
        image,anchor = self.face_cache[key]
        x,y = self.board_point(pos[0]+.5,pos[1]+.5,4)
        self.screen.blit(image,(x-anchor[0],y-anchor[1]))
        self.zombie_bounds.append(pygame.Rect(x-width//2,y-height,width,height))

    def sprite_zombie(self, rect, zombie_id=None):
        """Zombie head sprite matching the detailed HTML SVG."""
        cx, cy, u = rect.centerx, rect.centery, rect.width
        r = int(0.36 * u)

        # Green head (#7fb85a, outline #1b3410)
        pygame.draw.circle(self.screen, (127, 184, 90), (cx, cy), r)
        pygame.draw.circle(self.screen, (27, 52, 16), (cx, cy), r, 2)

        # Exposed skull / brain fragment (#e4dcb4)
        pygame.draw.arc(self.screen, (228, 220, 180),
                        (cx - int(r * 0.1), cy - int(r * 0.95), int(r * 1.1), int(r * 0.9)),
                        0.2, 1.5, 4)

        # Decaying patch (#5c8f3e)
        pygame.draw.circle(self.screen, (92, 143, 62), (cx - int(r * 0.35), cy - int(r * 0.35)), int(r * 0.32))

        # Big eyes with dark sockets (#2f5420), black pupil, red glowing dot (#ff2d2d)
        for ex in (-int(0.14 * u), int(0.14 * u)):
            ey = cy - int(0.04 * u)
            pygame.draw.circle(self.screen, (47, 84, 32), (cx + ex, ey), int(0.12 * u))
            pygame.draw.circle(self.screen, (10, 10, 10), (cx + ex, ey), int(0.08 * u))
            pygame.draw.circle(self.screen, (255, 45, 45), (cx + ex + 1, ey), 2)

        # Gaping bloody mouth (#2a0808) with teeth (#ece6c0)
        mouth = [
            (cx - int(0.20 * u), cy + int(0.14 * u)),
            (cx - int(0.12 * u), cy + int(0.22 * u)),
            (cx, cy + int(0.25 * u)),
            (cx + int(0.12 * u), cy + int(0.22 * u)),
            (cx + int(0.20 * u), cy + int(0.14 * u)),
            (cx + int(0.10 * u), cy + int(0.32 * u)),
            (cx - int(0.10 * u), cy + int(0.32 * u)),
        ]
        pygame.draw.polygon(self.screen, (42, 8, 8), mouth)
        pygame.draw.polygon(self.screen, (27, 52, 16), mouth, 1)

        # Teeth lines
        for tx in (-int(0.09 * u), 0, int(0.09 * u)):
            pygame.draw.line(self.screen, (236, 230, 192),
                             (cx + tx, cy + int(0.15 * u)),
                             (cx + tx, cy + int(0.22 * u)), 2)

        # Blood cuts (#b01e24)
        pygame.draw.line(self.screen, (176, 30, 36),
                         (cx + int(0.24 * u), cy + int(0.08 * u)),
                         (cx + int(0.28 * u), cy + int(0.26 * u)), 2)

    def sprite_coin(self, rect, value):
        """Gold coin sprite matching coin(v) in HTML."""
        cx, cy, u = rect.centerx, rect.centery, rect.width
        r_outer = int(0.42 * u)
        r_inner = int(0.32 * u)

        # Outer rim #f2a900, border #8a5200
        pygame.draw.circle(self.screen, (242, 169, 0), (cx, cy), r_outer)
        pygame.draw.circle(self.screen, (138, 82, 0), (cx, cy), r_outer, 2)

        # Inner gold circle #ffd23f, border #c98500
        pygame.draw.circle(self.screen, GOLD, (cx, cy), r_inner)
        pygame.draw.circle(self.screen, (201, 133, 0), (cx, cy), r_inner, 1)

        # White shine arc #fff3b0
        pygame.draw.arc(self.screen, (255, 243, 176),
                        (cx - r_inner + 2, cy - r_inner + 2, (r_inner - 2) * 2, (r_inner - 2) * 2),
                        math.pi * 0.45, math.pi * 0.95, 2)

        # Value text in #6a3b00
        font_sz = int(u * 0.29) if value >= 10 else int(u * 0.35)
        self.text(value, font_sz, (106, 59, 0), (cx, cy), "center", bold=True)

    def sprite_heart(self, rect, fill_col=(255, 38, 62), outline_col=(160, 18, 30), shine=True):
        """Crisp, high-contrast heart icon with curved lobes and clean perimeter."""
        cx, cy = rect.center
        sz = rect.width
        r = max(2, int(sz * 0.28))
        top_y = cy - int(sz * 0.12)
        tip_y = cy + int(sz * 0.46)
        col = fill_col if shine else (24, 34, 46)
        border_col = outline_col if shine else (90, 115, 145)

        # Solid fill
        pygame.draw.circle(self.screen, col, (cx - r, top_y), r)
        pygame.draw.circle(self.screen, col, (cx + r, top_y), r)
        pts = [(cx - int(r * 1.95), top_y + int(r * 0.2)),
               (cx + int(r * 1.95), top_y + int(r * 0.2)),
               (cx, tip_y)]
        pygame.draw.polygon(self.screen, col, pts)

        # Clean outer perimeter (no interior cross lines)
        pygame.draw.arc(self.screen, border_col, (cx - 2 * r, top_y - r, 2 * r, 2 * r), 0, math.pi, 1)
        pygame.draw.arc(self.screen, border_col, (cx, top_y - r, 2 * r, 2 * r), 0, math.pi, 1)
        pygame.draw.line(self.screen, border_col, pts[0], (cx, tip_y), 1)
        pygame.draw.line(self.screen, border_col, pts[1], (cx, tip_y), 1)

        # Crisp shine highlight arc
        if shine:
            pygame.draw.arc(self.screen, (255, 235, 245),
                            (cx - r - 2, top_y - r, r * 2, r * 2),
                            math.pi * 0.25, math.pi * 0.85, 2)

    def sprite_heart_pickup(self, rect):
        """Crisp, vibrant, high-contrast Heart pickup on the grid."""
        cx, cy, u = rect.centerx, rect.centery, rect.width

        # 1. Soft glowing red aura
        aura = pygame.Surface((u, u), pygame.SRCALPHA)
        pygame.draw.circle(aura, (255, 45, 65, 55), (u // 2, u // 2), int(u * 0.44))
        self.screen.blit(aura, rect.topleft)

        # 2. Heart geometry: width ~68% of tile, height ~60%
        hw = int(u * 0.68)
        hh = int(u * 0.62)
        top_y = cy - hh // 2
        bot_y = cy + hh // 2
        hr = hw // 4
        c1 = (cx - hr, top_y + hr)
        c2 = (cx + hr, top_y + hr)

        # White outer border for strong contrast on dark tiles
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            pygame.draw.circle(self.screen, (255, 255, 255), (c1[0] + dx, c1[1] + dy), hr + 1)
            pygame.draw.circle(self.screen, (255, 255, 255), (c2[0] + dx, c2[1] + dy), hr + 1)
            pygame.draw.polygon(self.screen, (255, 255, 255), [
                (cx - hw // 2 - 1 + dx, top_y + hr + dy),
                (cx + hw // 2 + 1 + dx, top_y + hr + dy),
                (cx + dx, bot_y + 1 + dy)
            ])

        # Vibrant ruby red heart body
        body_col = (255, 25, 55)
        pygame.draw.circle(self.screen, body_col, c1, hr + 1)
        pygame.draw.circle(self.screen, body_col, c2, hr + 1)
        pygame.draw.polygon(self.screen, body_col, [
            (cx - hw // 2, top_y + hr),
            (cx + hw // 2, top_y + hr),
            (cx, bot_y)
        ])

        # Glossy highlight shine
        pygame.draw.arc(self.screen, (255, 215, 225),
                        (c1[0] - hr + 1, c1[1] - hr + 1, hr * 2 - 2, hr * 2 - 2),
                        0.7, 2.7, 2)

        # Crisp white '+' in center
        pw = max(2, int(u * 0.08))
        pl = max(6, int(u * 0.26))
        pygame.draw.rect(self.screen, (255, 255, 255), (cx - pw // 2, cy - pl // 2 + 1, pw, pl))
        pygame.draw.rect(self.screen, (255, 255, 255), (cx - pl // 2, cy - pw // 2 + 1, pl, pw))

    def draw_iron_frame(self, rect):
        """Riveted metallic border matching .cell.lockd in HTML."""
        # Frame outer
        pygame.draw.rect(self.screen, (169, 179, 186), rect, 3)
        pygame.draw.rect(self.screen, (57, 64, 70), rect.inflate(-4, -4), 1)
        # 4 Corner rivets (#d5dce1)
        for rx, ry in [(rect.left + 3, rect.top + 3),
                       (rect.right - 4, rect.top + 3),
                       (rect.left + 3, rect.bottom - 4),
                       (rect.right - 4, rect.bottom - 4)]:
            pygame.draw.circle(self.screen, (213, 220, 225), (rx, ry), 2)

    def sprite_steel_box(self, rect):
        """Heavy industrial steel box / cargo crate for blocked cells."""
        r = rect.inflate(-2, -2)
        pygame.draw.rect(self.screen, (22, 28, 35), r, border_radius=4)

        inner = r.inflate(-2, -2)
        pygame.draw.rect(self.screen, (72, 84, 98), inner, border_radius=3)

        # 3D Beveled steel edge lighting
        pygame.draw.line(self.screen, (150, 168, 185), inner.topleft, inner.topright, 2)
        pygame.draw.line(self.screen, (150, 168, 185), inner.topleft, inner.bottomleft, 2)
        pygame.draw.line(self.screen, (38, 45, 54), inner.bottomleft, inner.bottomright, 2)
        pygame.draw.line(self.screen, (38, 45, 54), inner.topright, inner.bottomright, 2)

        plate = inner.inflate(-6, -6)
        if plate.width > 4 and plate.height > 4:
            pygame.draw.rect(self.screen, (58, 68, 80), plate, border_radius=2)
            pygame.draw.rect(self.screen, (35, 42, 50), plate, 1, border_radius=2)

            # Reinforced diagonal steel X-brace
            pygame.draw.line(self.screen, (35, 42, 50), plate.topleft, plate.bottomright, 2)
            pygame.draw.line(self.screen, (105, 122, 140), (plate.left + 1, plate.top), (plate.right, plate.bottom - 1), 1)
            pygame.draw.line(self.screen, (35, 42, 50), plate.topright, plate.bottomleft, 2)
            pygame.draw.line(self.screen, (105, 122, 140), (plate.right - 1, plate.top), (plate.left, plate.bottom - 1), 1)

            # Central steel bolt / hub
            cx, cy = plate.center
            pygame.draw.circle(self.screen, (35, 42, 50), (cx, cy), 4)
            pygame.draw.circle(self.screen, (130, 148, 166), (cx, cy), 3)
            pygame.draw.circle(self.screen, (200, 215, 230), (cx - 1, cy - 1), 1)

        # Four heavy steel corner rivets / bolts
        for rx, ry in [(r.left + 4, r.top + 4),
                       (r.right - 5, r.top + 4),
                       (r.left + 4, r.bottom - 5),
                       (r.right - 5, r.bottom - 5)]:
            pygame.draw.circle(self.screen, (28, 35, 42), (rx, ry), 2)
            pygame.draw.circle(self.screen, (185, 200, 215), (rx, ry), 1)

    def sprite_goal(self, rect, unlocked_survivors, t):
        """Goal cell matching lock SVG in HTML with unlocked initials."""
        unlocked = len(unlocked_survivors) > 0
        pulse = 0.5 + 0.5 * math.sin(t / 250.0)

        # Border color & glow
        col = (90, 235, 120) if unlocked else (255, 138, 31)
        glow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow, (*col, int(45 + 55 * pulse)), glow.get_rect(), border_radius=6)
        self.screen.blit(glow, rect.topleft)

        cx, cy, u = rect.centerx, rect.centery, rect.width

        if unlocked:
            # Open portal border
            pygame.draw.rect(self.screen, col, rect, 3, border_radius=6)

            # Padlock (Open shackle)
            shackle_rect = pygame.Rect(cx - int(0.12 * u), cy - int(0.32 * u), int(0.24 * u), int(0.24 * u))
            pygame.draw.arc(self.screen, (34, 34, 34), shackle_rect, 0, math.pi, 3)
            # Padlock body (#ffa733)
            body = pygame.Rect(cx - int(0.22 * u), cy - int(0.10 * u), int(0.44 * u), int(0.30 * u))
            pygame.draw.rect(self.screen, (120, 230, 130), body, border_radius=3)
            pygame.draw.rect(self.screen, (34, 34, 34), body, 2, border_radius=3)

            # Draw initials of unlocked survivors on the goal
            n = len(unlocked_survivors)
            font_sz = 16 if n == 1 else (13 if n == 2 else 11)
            spacing = rect.width // (n + 1)
            for i, sv in enumerate(unlocked_survivors):
                lx = rect.left + spacing * (i + 1)
                ly = rect.centery + int(0.12 * u)
                pill = pygame.Rect(0, 0, font_sz + 4, font_sz + 4)
                pill.center = (lx, ly)
                pygame.draw.rect(self.screen, (10, 20, 25), pill, border_radius=3)
                pygame.draw.rect(self.screen, sv.color, pill, 1, border_radius=3)
                self.text(sv.name[0], font_sz, sv.color, (lx, ly), "center", bold=True)
        else:
            # Locked state: iron frame + diagonal cross (#aaa) + orange lock
            self.draw_iron_frame(rect)
            pygame.draw.line(self.screen, (170, 170, 170), rect.topleft, rect.bottomright, 3)
            pygame.draw.line(self.screen, (170, 170, 170), rect.topright, rect.bottomleft, 3)

            # Closed padlock
            shackle_rect = pygame.Rect(cx - int(0.15 * u), cy - int(0.30 * u), int(0.30 * u), int(0.26 * u))
            pygame.draw.arc(self.screen, (34, 34, 34), shackle_rect, 0, math.pi, 4)
            pygame.draw.line(self.screen, (34, 34, 34), shackle_rect.midleft, (shackle_rect.left, cy - int(0.08 * u)), 4)
            pygame.draw.line(self.screen, (34, 34, 34), shackle_rect.midright, (shackle_rect.right, cy - int(0.08 * u)), 4)

            body = pygame.Rect(cx - int(0.24 * u), cy - int(0.08 * u), int(0.48 * u), int(0.32 * u))
            pygame.draw.rect(self.screen, (255, 167, 51), body, border_radius=3)
            pygame.draw.rect(self.screen, (34, 34, 34), body, 2, border_radius=3)
            pygame.draw.circle(self.screen, (34, 34, 34), body.center, 3)

    # ------------------------------------------------------------ main board
    def pickup_rect(self, pos, size):
        return self.piece_rect(pos, size, 3)

    def board_point(self, row, col, height=0):
        """Orthographic 3D projection, shared by tiles, pieces and effects."""
        sx = self.board_w / (self.cfg.rows + self.cfg.cols)
        sy = (self.board_h - 100) / (self.cfg.rows + self.cfg.cols)
        left = self.BX + self.cfg.rows * sx
        px = left + (col-row)*sx
        py = self.BY+40+(row+col)*sy
        cx, cy = W/2, self.BY+40+(self.board_h-100)/2
        return (round(cx+(px-cx)*self.board_zoom+self.board_pan[0]),
                round(cy+(py-cy)*self.board_zoom+self.board_pan[1]-height))

    def tile_polygon(self, pos, height=0, inset=0.035):
        r, c = pos
        return [self.board_point(r + dr, c + dc, height)
                for dr, dc in ((inset, inset), (inset, 1-inset),
                               (1-inset, 1-inset), (1-inset, inset))]

    def board_block(self, pos, height, color, base=0, inset=0.035):
        top = self.tile_polygon(pos, height, inset)
        bottom = self.tile_polygon(pos, base, inset)
        for edge, shade in ((1, 0.48), (2, 0.68)):
            face = [top[edge], top[(edge+1) % 4],
                    bottom[(edge+1) % 4], bottom[edge]]
            pygame.draw.polygon(self.screen, lerp((0, 0, 0), color, shade), face)
            pygame.draw.polygon(self.screen, (12, 22, 24), face, 1)
        pygame.draw.polygon(self.screen, color, top)
        pygame.draw.polygon(self.screen, (65, 94, 87), top, 1)
        return top

    def piece_rect(self, pos, size=None, height=0):
        size = size or max(18, int(self.cell * 0.48))
        x, y = self.board_point(pos[0]+0.5, pos[1]+0.5, height)
        return pygame.Rect(x-size//2, y-size, size, size)

    def draw_board(self, game, t):
        self.zombie_bounds = []
        st = game.state
        if self.agent_step_state is not st:
            self.agent_step_state = st
            self.agent_steps = {}
        # Thick board plinth with two shaded faces and a cast shadow.
        corners = [self.board_point(r, c) for r, c in
                   ((0, 0), (0, self.cfg.cols),
                    (self.cfg.rows, self.cfg.cols), (self.cfg.rows, 0))]
        pygame.draw.polygon(self.screen, (6, 9, 13),
                            [(x+9, y+25) for x, y in corners])
        for edge, color in ((1, (16, 35, 32)), (2, (26, 51, 43))):
            a, b = corners[edge], corners[(edge+1) % 4]
            pygame.draw.polygon(self.screen, color,
                                [a, b, (b[0], b[1]+18), (a[0], a[1]+18)])
        pygame.draw.polygon(self.screen, (17, 31, 29), corners)
        pygame.draw.polygon(self.screen, BOARD_BORDER, corners, 3)

        # Paint ground first so a front tile never covers a standing piece.
        self._assign_zombie_faces(st)
        zombies = {z.pos: z for z in st.zombies if z.alive}
        agent_tiles = {sv.pos: sv.color for sv in st.survivors if sv.alive}
        for r in range(self.cfg.rows):
            for c in range(self.cfg.cols):
                pos = (r, c)
                col = TILE_A if (r+c) % 2 == 0 else TILE_B
                if pos in zombies:
                    col = TILE_ZOMBIE
                elif pos in st.buried_cells:
                    col = (45, 29, 35)
                elif pos in agent_tiles:
                    col = agent_tiles[pos]
                self.board_block(pos, 3, col)
                border = ((74, 163, 255) if pos in st.blue_cells else
                          (255, 123, 181) if pos in st.pink_cells else None)
                if border:
                    pygame.draw.polygon(self.screen, border,
                                        self.tile_polygon(pos, 4, 0.08), 2)

        unlocked = [sv for sv in st.survivors if sv.alive and st.goal_unlocked_for(sv)]
        # Back-to-front painter order for raised objects on the ground plane.
        survivors = {}
        for sv in st.survivors:
            survivors.setdefault(sv.pos, []).append(sv)
        positions = (set(st.obstacles) | set(st.coins) | set(st.hearts)
                     | set(zombies) | set(st.buried_cells) | set(survivors) | {st.goal})
        for pos in sorted(positions, key=lambda p: (sum(p), p[0])):
            x, y = self.board_point(pos[0]+0.5, pos[1]+0.5, 4)
            size = max(18, int(self.cell * 0.48))
            if pos in st.obstacles:
                top = self.board_block(pos, self.cell*0.38, (92, 112, 123), base=3, inset=0.12)
                pygame.draw.line(self.screen, (166, 183, 183), top[0], top[2], 2)
                pygame.draw.line(self.screen, (40, 55, 64), top[1], top[3], 2)
            if pos in st.coins:
                self.sprite_coin(self.pickup_rect(pos, size), st.coins[pos])
            if pos in st.hearts:
                self.sprite_heart_pickup(self.pickup_rect(pos, size))
            if pos == st.goal:
                color = (90, 235, 120) if unlocked else (255, 138, 31)
                pygame.draw.polygon(self.screen, color, self.tile_polygon(pos, 5, 0.08), 2)
                self.sprite_goal(self.piece_rect(pos, size, 5), unlocked, t)
            if pos in st.buried_cells and pos not in survivors:
                self.sprite_soldier(self.piece_rect(pos, size, 4), DIM, dead=True)
            pieces = [(None, True)] if pos in zombies else []
            pieces += [(sv, False) for sv in survivors.get(pos, [])]
            for sv, zombie in pieces:
                color = (127, 184, 90) if zombie else sv.color
                pygame.draw.ellipse(self.screen, (9, 17, 19), (x-size//2, y-4, size, 9))
                if sv and not sv.alive:
                    self.sprite_soldier(self.piece_rect(pos, size, 4), color, dead=True)
                    continue
                if zombie and zombies[pos].id in self.face_assignments:
                    self._draw_zombie_body(pos, size, zombies[pos].id, t)
                    continue
                if sv and sv.alive:
                    agent_rect = pygame.Rect(0,0,round(size*1.5),round(size*2.35))
                    agent_rect.midbottom = (x,y)
                    if self.draw_agent_sprite(sv,agent_rect,t=t if game.phase == Phase.PLAYING else None):
                        if sv.reached_goal:
                            self.text("WINNER!",11,GOLD,(x,agent_rect.top-8),"center")
                        continue
                # Pawn body and shaded base anchor the original avatars in space.
                pygame.draw.ellipse(self.screen, lerp((0, 0, 0), color, 0.4),
                                    (x-size//3, y-6, size*2//3, 9))
                pygame.draw.polygon(self.screen, lerp((0, 0, 0), color, 0.65),
                                    [(x-size//4, y-5), (x-size//5, y-size),
                                     (x+size//5, y-size), (x+size//4, y-5)])
                rect = self.piece_rect(pos, size, size*0.45)
                if zombie:
                    self.sprite_zombie(rect, zombies[pos].id)
                else:
                    self.sprite_soldier(rect, color, is_female=sv.female)
                    self.text(sv.name[0], 10, color, (x+size//2, y-5), "bottomleft")
                    if sv.reached_goal:
                        self.text("WINNER!", 11, GOLD, (x, rect.top-8), "center")

        for fx in game.effects:
            k = 1.0 - fx["ttl"] / fx["total"]
            if fx["kind"] in ("shot", "bite"):
                a = self.board_point(fx["src"][0]+0.5, fx["src"][1]+0.5, 20)
                b = self.board_point(fx["dst"][0]+0.5, fx["dst"][1]+0.5, 20)
                pygame.draw.line(self.screen, (255, 180, 170) if fx["kind"] == "bite" else (255, 255, 200), a, b, 4)
                pygame.draw.line(self.screen, fx["color"], a, b, 2)
                pygame.draw.circle(self.screen, (255, 120, 60), b, int(6+14*k), 2)
            else:
                x, y = self.board_point(fx["pos"][0]+0.5, fx["pos"][1]+0.5, 30+16*k)
                self.text(fx["text"], 14, fx["color"], (x, y), "center")

    # ------------------------------------------------------------ Header & Cards matching HTML
    def draw_header(self, game):
        """Top banner matching .title and .motto in HTML."""
        cx = W // 2

        # Title Box
        title_w, title_h = 520, 82
        title_box = pygame.Rect(cx - title_w // 2, 6, title_w, title_h)
        self.panel(title_box, bg=PANEL_BG, border=PANEL_BORDER, width=3, radius=8)

        # Title Text with 3D drop shadow
        self.text("ZombieHood", 64, (90, 13, 16), (cx + 2, title_box.centery + 2), "center", title=True)
        self.text("ZombieHood", 64, RED, (cx, title_box.centery), "center", title=True)

        # Motto
        self.text("THE LAST ALIVE", 22, (0, 0, 0), (cx + 1, 103), "center", title=True)
        self.text("THE LAST ALIVE", 22, (214, 220, 207), (cx, 102), "center", title=True)

        # Top-right tiny match info strip
        if game.state:
            st = game.state
            diff_label = getattr(self.cfg, "difficulty", "hard").upper()
            mode = "AI Battle" if game.human_idx is None else "Control: %s" % st.survivors[game.human_idx].name
            self.text("R%d/%d | %s (%dx%d) | %s | %dms" % (st.round + 1, self.cfg.max_rounds, diff_label, self.cfg.rows, self.cfg.cols, mode, game.delay_ms),
                      15, DIM, (W - 16, 10), "topright", bold=False)

    def draw_cards(self, game, t):
        ranked = sorted(game.state.survivors, key=lambda sv: (-sv.score, -sv.lives))
        ranks = {sv.idx: 1 + sum(other.score > sv.score for other in ranked) for sv in ranked}
        for i, sv in enumerate(game.state.survivors):
            card_positions = {"Tamal": (16,120), "Progga": (16,226), "Nijhum": (242,120)}
            card_x, card_y = card_positions.get(sv.name,(16,120+i*106))
            rect = pygame.Rect(card_x,card_y,214,100)
            active = game.state.turn == sv.idx and sv.alive
            self.panel(rect, border=sv.color if active else PANEL_BORDER, width=3 if active else 2)
            portrait_rect = pygame.Rect(rect.x+5,rect.y+7,48,48)
            if not self.draw_agent_sprite(sv,portrait_rect,portrait=True):
                self.sprite_soldier(portrait_rect,sv.color,is_female=sv.female,dead=not sv.alive)
            self.text(sv.name, 22, sv.color, (rect.x + 60, rect.y + 8))
            self.text("#%d" % ranks[sv.idx], 20, GOLD, (rect.right-10,rect.y+10), "topright")
            if sv.idx == game.human_idx:
                self.text("YOU",11,GREEN,(rect.x+28,rect.y+52),"center")
            for h in range(sv.max_lives):
                self.sprite_heart(pygame.Rect(rect.x + 60 + h * 22, rect.y + 36, 19, 19), shine=h < sv.lives)
            self.text("Score %d   Kills %d" % (sv.score, sv.kills), 17, GOLD, (rect.x + 12, rect.y + 60))
            status = "DEAD" if not sv.alive else ("ESCAPED" if sv.reached_goal else ("READY" if game.state.goal_unlocked_for(sv) else "LOCKED"))
            self.text("Coins %d/%d" % (sv.coins, self.cfg.coins_to_kill), 16, INK, (rect.x + 12, rect.y + 83))
            self.text(status, 14, GREEN if status == "READY" else sv.color, (rect.right - 10, rect.y + 84), "topright")

    def button(self, label, action, rect, border_color=None, font_size=17):
        mouse = getattr(self, "mouse_pos", pygame.mouse.get_pos())
        hover = rect.collidepoint(mouse)
        bg = (35, 50, 72) if hover else PANEL_BG
        border = (120, 160, 210) if hover else (border_color or PANEL_BORDER)
        pygame.draw.rect(self.screen, bg, rect, border_radius=6)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=6)
        self.text(label, font_size, INK, rect.center, "center", bold=True)
        self.buttons.append((rect, action))

    def draw_bottom_bar(self, game):
        x = W - 246
        self.panel(pygame.Rect(x, 130, 230, 255), width=2)
        self.text("EVENT LOG", 24, GOLD, (x+12,142), title=True)
        y = 178
        for line,color in reversed(game.log[-3:]):
            wrapped = ""
            for word in str(line).split():
                candidate = (wrapped+" "+word).strip()
                if self.font(14).size(candidate)[0] > 204 and wrapped:
                    if y <= 357:
                        self.text(wrapped,14,color,(x+12,y))
                    y += 19
                    wrapped = word
                else:
                    wrapped = candidate
            if y <= 357:
                self.text(wrapped,14,color,(x+12,y))
            y += 27
        self.text("MATCH CONTROLS",24,GOLD,(x+10,710),title=True)
        labels = [("Resume [P]" if game.phase == Phase.PAUSED else "Pause [P]", "pause"),
                  ("Restart [R]", "restart"), ("New Map [N]", "new"), ("Menu [M]", "menu")]
        for i,(label,action) in enumerate(labels):
            self.button(label,action,pygame.Rect(x,745+i*43,230,35))
        if game.human_idx is not None:
            human = game.state.survivors[game.human_idx]
            your_turn = game.state.turn == game.human_idx and human.alive
            if not human.alive:
                heading = "YOU DIED - Watching remaining AIs"
            elif game.goal_delay_ms > 0:
                heading = "Goal reached - match ending"
            else:
                heading = "YOUR TURN - "+human.name if your_turn else "AI TURN - "+game.state.survivors[game.state.turn].name
            self.panel(pygame.Rect(16,H-131,440,65),border=GREEN if your_turn else PANEL_BORDER,width=2)
            self.text(heading,20,GREEN if your_turn else INK,(28,H-122))
            self.text(game.flash or ("WASD / Arrows: move | Space: attack | Z: wait" if your_turn else "Please wait for your turn"),16,
                      (255,140,120) if game.flash else DIM,(28,H-94))
        self.text("WASD: move   Space: shoot",13,DIM,(16,H-55))
        self.text("Z: wait   F11: fullscreen",13,DIM,(16,H-33))

    def dim(self, a=180):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, a))
        self.screen.blit(s, (0, 0))

    def draw_menu(self):
        self.dim(200)
        box_w, box_h = DIALOG_W, DIALOG_H
        box = pygame.Rect((W - box_w) // 2, (H - box_h) // 2, box_w, box_h)
        self.panel(box, bg=PANEL_BG, border=PANEL_BORDER, width=3, radius=10)

        cx = box.centerx
        # Horror title using Creepster
        self.text("ZombieHood", 78, (90, 13, 16), (cx + 3, box.y + 58), "center", title=True)
        self.text("ZombieHood", 78, RED, (cx, box.y + 56), "center", title=True)

        if self.menu_mode == "select_difficulty":
            self.text("SELECT DIFFICULTY", 30, (214, 220, 207), (cx, box.y + 122), "center", title=True)
            subtitle = "AI VS AI BATTLEFIELD SELECTION" if self.chosen_mode == "ai" else "CHOOSE YOUR SURVIVAL CHALLENGE"
            self.text(subtitle, 22, GOLD, (cx, box.y + 174), "center", title=True)

            diff_opts = [
                ("🟢 Easy    - 10x10 Grid • 3 Lives • 10 Coins to Kill  [1]", "diff_easy", GREEN),
                ("🟡 Medium  - 12x12 Grid • 2 Lives • 15 Coins to Kill  [2]", "diff_medium", GOLD),
                ("🔴 Hard    - 15x15 Grid • 1 Life  • 20 Coins to Kill  [3]", "diff_hard", (255, 95, 95)),
            ]
            for i, (lab, act, col) in enumerate(diff_opts):
                r = pygame.Rect(cx - 430, box.y + 224 + i * 82, 860, 64)
                self.button(lab, act, r, border_color=col, font_size=25)

            self.button("<- Back to Mode Select  [B]", "menu_main", pygame.Rect(cx - 250, box.y + 514, 500, 58), font_size=24)
            self.text("Keys: 1 Easy   2 Medium   3 Hard   |   B / Backspace: Back",
                      18, DIM, (cx, box.bottom - 30), "center", bold=False)

        elif self.menu_mode == "select_human":
            self.text("SELECT YOUR SURVIVOR", 30, (214, 220, 207), (cx, box.y + 122), "center", title=True)
            grid_sz = 10 if self.chosen_diff == "easy" else (12 if self.chosen_diff == "medium" else 15)
            self.text("DIFFICULTY: %s (%dx%d) • TAKE CONTROL OF A SURVIVOR" % (self.chosen_diff.upper(), grid_sz, grid_sz),
                      22, GOLD, (cx, box.y + 174), "center", title=True)

            survivors_info = [
                ("Play as Tamal   (MCTS Agent)   [1]", "h0", (74, 163, 255)),
                ("Play as Progga  (Fuzzy Logic)  [2]", "h1", (255, 123, 181)),
                ("Play as Nijhum  (A* Search)    [3]", "h2", (255, 184, 74)),
            ]
            for i, (lab, act, col) in enumerate(survivors_info):
                r = pygame.Rect(cx - 430, box.y + 224 + i * 82, 860, 64)
                self.button(lab, act, r, border_color=col, font_size=25)

            self.button("<- Back to Difficulty Select  [B]", "menu_diff", pygame.Rect(cx - 250, box.y + 514, 500, 58), font_size=24)
            self.text("Keys: 1 Tamal   2 Progga   3 Nijhum   |   B / Backspace: Back",
                      18, DIM, (cx, box.bottom - 30), "center", bold=False)

        else:
            self.text("THE LAST ALIVE", 30, (214, 220, 207), (cx, box.y + 122), "center", title=True)

            # Enhanced, large, clear horror-style rules text
            lines = [
                ("3 DIFFICULTIES: EASY (10X10), MEDIUM (12X12), HARD (15X15)", GOLD),
                ("GATHER REQUIRED COINS TO SHOOT ZOMBIES & UNLOCK GOAL", (255, 185, 80)),
                ("ENTERING ADJACENT ZOMBIE CELL LOSES ALL COINS & 1 LIFE!", (255, 110, 110)),
                ("KILL AT LEAST 1 ZOMBIE TO UNLOCK THE EXIT GOAL!", GREEN),
            ]
            for i, (ln, col) in enumerate(lines):
                self.text(ln, 24, col, (cx, box.y + 182 + i * 40), "center")

            # 2 Main Modes
            opts = [
                ("AI vs AI  (Watch Battle)  [SPACE]", "choose_diff_ai"),
                ("AI vs Human  (Play Survivor)  [ENTER]", "choose_diff_human"),
            ]
            for i, (lab, act) in enumerate(opts):
                self.button(lab, act, pygame.Rect(cx - 350, box.y + 378 + i * 84, 700, 64), font_size=26)

            self.text("Select Mode with mouse or SPACE (AI vs AI) / ENTER (AI vs Human)  |  ESC: Window mode",
                      18, DIM, (cx, box.bottom - 30), "center", bold=False)

    def draw_pause(self):
        self.dim(170)
        box = pygame.Rect((W-DIALOG_W)//2,(H-DIALOG_H)//2,DIALOG_W,DIALOG_H)
        self.panel(box,bg=PANEL_BG,border=PANEL_BORDER,width=3,radius=10)
        self.text("PAUSED",78,INK,(box.centerx,box.centery-45),"center",title=True)
        self.text("Press P to resume",26,DIM,(box.centerx,box.centery+35),"center")

    def draw_over(self, game):
        self.dim(190)
        o = game.outcome
        box_w, box_h = DIALOG_W, DIALOG_H
        box = pygame.Rect((W - box_w) // 2, (H - box_h) // 2, box_w, box_h)
        col = RED if o["title"] == "DEFEAT" else (GOLD if "DRAW" in o["title"] else GREEN)
        self.panel(box, bg=PANEL_BG, border=col, width=3, radius=10)

        cx = box.centerx
        # Horror title for Game Over / Defeat
        self.text(o["title"], 68, col, (cx, box.y + 52), "center", title=True)

        words, line = o["detail"].split(), ""
        y = box.y + 112
        for w in words:
            if self.font(22, bold=False).size(line + w)[0] > box.width - 50:
                self.text(line, 22, INK, (cx, y), "center", bold=False)
                line, y = "", y + 30
            line += w + " "
        self.text(line, 22, INK, (cx, y), "center", bold=False)

        self.text("FINAL STANDINGS", 22, DIM, (box.x + 36, y + 44), bold=True)
        for i, sv in enumerate(o["ranking"]):
            tag = "escaped" if sv.reached_goal else ("dead" if not sv.alive else "alive")
            self.text("%d. %-7s %4d pts   coins %-2d   kills %d   (%s)" % (
                i + 1, sv.name, sv.score, sv.coins, sv.kills, tag),
                24, sv.color, (box.x + 36, y + 84 + i * 44), bold=True)

        for i, (lab, act) in enumerate([("Restart [R]", "restart"), ("New Map [N]", "new"), ("Menu [M]", "menu")]):
            self.button(lab, act, pygame.Rect(box.x + 36 + i * 316, box.bottom - 90, 296, 62), font_size=23)

    # ------------------------------------------------------------ main draw loop
    def draw(self, game):
        if game.cfg is not self.cfg:
            self.set_config(game.cfg)
        t = pygame.time.get_ticks()
        self.buttons = []

        # 1. Static atmospheric background
        self.screen.blit(self.bg_static, (0, 0))

        # 2. Dynamic background elements from HTML
        self._draw_glowing_eyes(t)
        self._draw_hanging_skull(90, 0, 120, 1.0, t)
        self._draw_hanging_skull(W - 85, 0, 95, 0.8, t)
        self._draw_marching_zombies(t)

        # 3. Game screens
        if game.state is None:
            self.draw_menu()
            return

        self.draw_board(game, t)
        self.draw_header(game)
        self.draw_cards(game, t)
        self.draw_bottom_bar(game)

        if game.phase == Phase.MENU:
            self.draw_menu()
        elif game.phase == Phase.PAUSED:
            self.draw_pause()
        elif game.phase == Phase.OVER:
            self.draw_over(game)
