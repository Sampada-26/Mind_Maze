import math
import os
import random
import sys
from array import array
from dataclasses import dataclass

import pygame

# -----------------------------
# Config
# -----------------------------
WIDTH, HEIGHT = 1180, 780
FPS = 60
TOP_BAR_H = 84
BOTTOM_BAR_H = 96
PLAY_MARGIN = 24

BG_DEEP = (10, 10, 15)
BG_MID = (16, 20, 36)
PANEL_FILL = (14, 18, 28)
TEXT_COLOR = (232, 244, 255)

NEON_CYAN = (56, 238, 255)
NEON_MAGENTA = (255, 72, 214)
NEON_GREEN = (86, 255, 166)
NEON_RED = (255, 68, 92)
NEON_BLUE = (110, 154, 255)

STATE_START = "start"
STATE_PREVIEW = "preview"
STATE_PLAYING = "playing"
STATE_LEVEL_COMPLETE = "level_complete"
STATE_GAME_OVER = "game_over"


# -----------------------------
# Utility helpers
# -----------------------------
def clamp(value, lo, hi):
    return max(lo, min(value, hi))


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out_cubic(t):
    return 1.0 - (1.0 - t) ** 3


def pick_font(names, size, bold=False):
    for name in names:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.SysFont("consolas", size, bold=bold)


def draw_vertical_gradient(surface, top_color, bottom_color):
    width, height = surface.get_size()
    grad = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(lerp(top_color[0], bottom_color[0], t))
        g = int(lerp(top_color[1], bottom_color[1], t))
        b = int(lerp(top_color[2], bottom_color[2], t))
        pygame.draw.line(grad, (r, g, b, 255), (0, y), (width, y))
    surface.blit(grad, (0, 0))


def draw_glow_text(surface, text, font, pos, color, glow_color, center=False, glow_strength=1.0):
    text_surf = font.render(text, True, color)
    rect = text_surf.get_rect(center=pos) if center else text_surf.get_rect(topleft=pos)

    glow_offsets = [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (0, 0)]
    for ox, oy in glow_offsets:
        glow = font.render(text, True, glow_color)
        alpha = int((55 if (ox or oy) else 115) * glow_strength)
        glow.set_alpha(clamp(alpha, 0, 255))
        g_rect = glow.get_rect(center=rect.center)
        g_rect.x += ox
        g_rect.y += oy
        surface.blit(glow, g_rect)

    surface.blit(text_surf, rect)


def draw_glow_circle(surface, color, center, radius, glow_radius=22, layers=5):
    diameter = (radius + glow_radius) * 2
    glow = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    cx, cy = diameter // 2, diameter // 2

    for i in range(layers, 0, -1):
        r = radius + int(glow_radius * (i / layers))
        a = int(32 * (i / layers))
        pygame.draw.circle(glow, (*color, a), (cx, cy), r)

    pygame.draw.circle(glow, (*color, 245), (cx, cy), radius)
    surface.blit(glow, (center[0] - cx, center[1] - cy))


def draw_holo_panel(surface, rect, accent, pulse=0.0, fill_alpha=155):
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill((*PANEL_FILL, fill_alpha))
    surface.blit(panel, rect.topleft)

    glow_rect = rect.inflate(14 + int(pulse * 6), 14 + int(pulse * 6))
    glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(glow, (*accent, 42 + int(pulse * 16)), glow.get_rect(), border_radius=16)
    surface.blit(glow, glow_rect.topleft)

    pygame.draw.rect(surface, (*accent, 210), rect, width=2, border_radius=12)
    pygame.draw.rect(surface, (220, 246, 255, 30), rect.inflate(-8, -8), width=1, border_radius=10)


def create_tone(freq=440, duration=0.1, volume=0.35, sample_rate=44100, wave="sine"):
    n_samples = int(duration * sample_rate)
    amp = int(32767 * volume)
    buf = array("h")

    for i in range(n_samples):
        t = i / sample_rate
        phase = 2 * math.pi * freq * t
        if wave == "square":
            val = 1.0 if math.sin(phase) >= 0 else -1.0
        elif wave == "saw":
            frac = (freq * t) % 1.0
            val = 2.0 * frac - 1.0
        else:
            val = math.sin(phase)

        # Simple fade envelope to avoid clicks.
        env = 1.0
        edge = int(sample_rate * 0.01)
        if i < edge:
            env = i / max(1, edge)
        elif i > n_samples - edge:
            env = (n_samples - i) / max(1, edge)

        buf.append(int(amp * val * clamp(env, 0.0, 1.0)))

    return pygame.mixer.Sound(buffer=buf.tobytes())


# -----------------------------
# Maze generation
# -----------------------------
def generate_maze(rows, cols):
    """
    Generate a perfect maze with DFS backtracking.
    0 = path, 1 = wall
    """
    maze = [[1 for _ in range(cols)] for _ in range(rows)]
    stack = [(0, 0)]
    maze[0][0] = 0

    directions = [(2, 0), (-2, 0), (0, 2), (0, -2)]

    while stack:
        r, c = stack[-1]
        random.shuffle(directions)
        neighbors = []

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and maze[nr][nc] == 1:
                neighbors.append((nr, nc, r + dr // 2, c + dc // 2))

        if neighbors:
            nr, nc, wr, wc = random.choice(neighbors)
            maze[wr][wc] = 0
            maze[nr][nc] = 0
            stack.append((nr, nc))
        else:
            stack.pop()

    maze[rows - 1][cols - 1] = 0
    return maze


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    ttl: float
    size: float
    color: tuple


@dataclass
class TrailNode:
    x: float
    y: float
    life: float
    ttl: float
    radius: float
    color: tuple


class NeonButton:
    def __init__(self, center, size, label, font, accent):
        self.base_rect = pygame.Rect(0, 0, size[0], size[1])
        self.base_rect.center = center
        self.label = label
        self.font = font
        self.accent = accent
        self.hover_amount = 0.0
        self.press_amount = 0.0
        self.pressed_inside = False

    def current_rect(self):
        scale = 1.0 + 0.05 * self.hover_amount - 0.03 * self.press_amount
        w = int(self.base_rect.width * scale)
        h = int(self.base_rect.height * scale)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = self.base_rect.center
        return rect

    def update(self, dt, mouse_pos):
        hovered = self.current_rect().collidepoint(mouse_pos)
        target = 1.0 if hovered else 0.0
        self.hover_amount = lerp(self.hover_amount, target, clamp(dt * 12.0, 0.0, 1.0))
        self.press_amount = max(0.0, self.press_amount - dt * 8.0)

    def handle_event(self, event):
        rect = self.current_rect()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and rect.collidepoint(event.pos):
            self.pressed_inside = True
            self.press_amount = 1.0
            return False

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            clicked = self.pressed_inside and rect.collidepoint(event.pos)
            self.pressed_inside = False
            if clicked:
                self.press_amount = 0.75
            return clicked

        return False

    def draw(self, surface, time_s):
        rect = self.current_rect()
        pulse = 0.45 + 0.55 * math.sin(time_s * 3.0)

        glow_pad = int(10 + self.hover_amount * 12)
        glow_rect = rect.inflate(glow_pad * 2, glow_pad * 2)
        glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            glow,
            (*self.accent, int(36 + 38 * pulse + 42 * self.hover_amount)),
            glow.get_rect(),
            border_radius=16,
        )
        surface.blit(glow, glow_rect.topleft)

        body = pygame.Surface(rect.size, pygame.SRCALPHA)
        body.fill((12, 16, 28, 198))
        surface.blit(body, rect.topleft)

        border_col = (
            clamp(self.accent[0] + int(40 * self.hover_amount), 0, 255),
            clamp(self.accent[1] + int(40 * self.hover_amount), 0, 255),
            clamp(self.accent[2] + int(40 * self.hover_amount), 0, 255),
        )
        pygame.draw.rect(surface, border_col, rect, width=2, border_radius=12)
        pygame.draw.rect(surface, (220, 248, 255), rect.inflate(-8, -8), width=1, border_radius=10)

        draw_glow_text(
            surface,
            self.label,
            self.font,
            rect.center,
            TEXT_COLOR,
            self.accent,
            center=True,
            glow_strength=1.0 + 0.35 * self.hover_amount,
        )


class MindMazeGame:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Mind Maze")
        self.clock = pygame.time.Clock()
        self.rng = random.Random()

        # Fonts (Orbitron/Audiowide family first, then robust fallbacks)
        self.title_font = pick_font(["orbitron", "audiowide", "bankgothic", "eurostile", "consolas"], 88, bold=True)
        self.hero_font = pick_font(["orbitron", "audiowide", "bankgothic", "consolas"], 46, bold=True)
        self.ui_font = pick_font(["orbitron", "rajdhani", "audiowide", "consolas"], 28, bold=True)
        self.small_font = pick_font(["orbitron", "rajdhani", "consolas"], 21, bold=False)
        self.tiny_font = pick_font(["orbitron", "rajdhani", "consolas"], 18, bold=False)

        # Main menu logo
        self.logo_image = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
            if os.path.isfile(logo_path):
                logo = pygame.image.load(logo_path).convert_alpha()
                self.logo_image = pygame.transform.smoothscale(logo, (176, 176))
        except Exception:
            self.logo_image = None

        self.state = STATE_START
        self.state_age = 0.0

        # Fade transitions
        self.transition_phase = 0  # 0 idle, 1 fade-out, -1 fade-in
        self.transition_alpha = 0.0
        self.pending_state = None

        # Time / animation
        self.global_time = 0.0

        # Buttons
        self.start_btn = NeonButton((WIDTH // 2, HEIGHT // 2 + 102), (310, 74), "START GAME", self.ui_font, NEON_CYAN)
        self.exit_btn = NeonButton((WIDTH // 2, HEIGHT // 2 + 192), (310, 66), "EXIT", self.ui_font, NEON_MAGENTA)

        self.continue_btn = NeonButton((WIDTH // 2 + 120, HEIGHT // 2 + 178), (220, 64), "CONTINUE", self.ui_font, NEON_GREEN)
        self.complete_menu_btn = NeonButton((WIDTH // 2 - 128, HEIGHT // 2 + 178), (220, 64), "MENU", self.ui_font, NEON_CYAN)

        self.retry_btn = NeonButton((WIDTH // 2 - 128, HEIGHT // 2 + 160), (220, 64), "RETRY", self.ui_font, NEON_RED)
        self.over_menu_btn = NeonButton((WIDTH // 2 + 120, HEIGHT // 2 + 160), (220, 64), "MENU", self.ui_font, NEON_MAGENTA)

        # Backdrop particles
        self.bg_particles = []
        for _ in range(130):
            self.bg_particles.append(
                {
                    "x": self.rng.uniform(0, WIDTH),
                    "y": self.rng.uniform(0, HEIGHT),
                    "speed": self.rng.uniform(18, 78),
                    "depth": self.rng.uniform(0.35, 1.25),
                    "phase": self.rng.uniform(0, math.tau),
                }
            )

        # SFX (optional but recommended)
        self.snd_move = None
        self.snd_hit = None
        self.snd_win = None
        self.snd_ui = None
        self.snd_ambient = None
        self.init_sounds()

        # Gameplay values
        self.max_level = 12
        self.level = 1
        self.total_score = 0
        self.level_score = 0
        self.level_breakdown = {}

        # Runtime visuals
        self.particles = []
        self.trail = []
        self.trail_stamp_timer = 0.0

        self.red_flash = 0.0
        self.shake_timer = 0.0
        self.shake_duration = 0.25
        self.shake_power = 0.0
        self.maze_glitch_timer = 0.0
        self.game_over_glitch = 0.0

        self.round_resolved = False

        self.reset_level_data(new_level=True)

    # -----------------------------
    # Setup / reset
    # -----------------------------
    def init_sounds(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.snd_move = create_tone(freq=620, duration=0.04, volume=0.2, wave="sine")
            self.snd_hit = create_tone(freq=145, duration=0.18, volume=0.34, wave="square")
            self.snd_win = create_tone(freq=960, duration=0.16, volume=0.3, wave="sine")
            self.snd_ui = create_tone(freq=760, duration=0.05, volume=0.2, wave="sine")
            self.snd_ambient = create_tone(freq=96, duration=1.8, volume=0.07, wave="sine")
            self.snd_ambient.play(loops=-1)
        except pygame.error:
            self.snd_move = self.snd_hit = self.snd_win = self.snd_ui = self.snd_ambient = None

    def play_sound(self, snd, volume=1.0):
        if snd:
            snd.set_volume(clamp(volume, 0.0, 1.0))
            snd.play()

    def start_new_run(self):
        self.level = 1
        self.total_score = 0
        self.reset_level_data(new_level=True)

    def level_config(self, level):
        size = min(11 + (level - 1) * 2, 31)
        if size % 2 == 0:
            size += 1

        preview_time = clamp(4.9 - (level - 1) * 0.28, 1.8, 4.9)
        level_time = clamp(76 - (level - 1) * 3.6, 24, 76)
        hints = 2 if level <= 3 else (1 if level <= 8 else 0)
        focus_charges = 2 if level <= 4 else 1
        memory_decay = 0.10 + (level - 1) * 0.015
        return size, size, preview_time, level_time, hints, focus_charges, memory_decay

    def reset_level_data(self, new_level=False):
        rows, cols, preview_time, level_time, hints, focus_charges, memory_decay = self.level_config(self.level)

        self.rows = rows
        self.cols = cols
        self.preview_duration = preview_time
        self.level_duration = level_time
        self.hints_remaining = hints
        self.focus_charges = focus_charges
        self.memory_decay_rate = memory_decay

        self.preview_left = self.preview_duration
        self.level_timer = self.level_duration

        self.hint_reveal_timer = 0.0
        self.focus_timer = 0.0
        self.memory_stability = 1.0

        self.mistakes = 0
        self.round_resolved = False
        self.level_score = 0
        self.level_breakdown = {}

        self.maze = generate_maze(self.rows, self.cols)

        self.play_top = TOP_BAR_H + PLAY_MARGIN
        self.play_bottom = HEIGHT - BOTTOM_BAR_H - PLAY_MARGIN
        available_h = self.play_bottom - self.play_top
        available_w = WIDTH - PLAY_MARGIN * 2

        self.cell_size = min(available_w // self.cols, available_h // self.rows)
        self.grid_w = self.cell_size * self.cols
        self.grid_h = self.cell_size * self.rows
        self.grid_x = (WIDTH - self.grid_w) // 2
        self.grid_y = self.play_top + (available_h - self.grid_h) // 2

        self.start_cell = (0, 0)
        self.goal_cell = (self.rows - 1, self.cols - 1)

        self.player_row, self.player_col = self.start_cell
        self.target_cell = self.start_cell

        cx, cy = self.cell_center(*self.start_cell)
        self.player_px = float(cx)
        self.player_py = float(cy)
        self.move_from = (self.player_px, self.player_py)
        self.move_to = (self.player_px, self.player_py)
        self.move_progress = 1.0
        self.moving = False
        self.move_duration = 0.14

        self.trail.clear()
        self.particles.clear()
        self.trail_stamp_timer = 0.0

        self.red_flash = 0.0
        self.shake_timer = 0.0
        self.shake_power = 0.0
        self.maze_glitch_timer = 0.0
        self.game_over_glitch = 0.0

        if new_level:
            self.transition_alpha = 255
            self.transition_phase = -1

    # -----------------------------
    # State transitions
    # -----------------------------
    def set_state(self, new_state):
        self.state = new_state
        self.state_age = 0.0

    def transition_to(self, new_state):
        if self.pending_state == new_state:
            return
        if self.state == new_state:
            self.set_state(new_state)
            return

        self.pending_state = new_state
        self.transition_phase = 1
        self.transition_alpha = 0.0

    def update_transition(self, dt):
        speed = 520.0

        if self.transition_phase == 1:
            self.transition_alpha += speed * dt
            if self.transition_alpha >= 255:
                self.transition_alpha = 255
                self.transition_phase = -1
                if self.pending_state:
                    self.set_state(self.pending_state)
                    self.pending_state = None

        elif self.transition_phase == -1:
            self.transition_alpha -= speed * dt
            if self.transition_alpha <= 0:
                self.transition_alpha = 0
                self.transition_phase = 0

    # -----------------------------
    # Input / movement
    # -----------------------------
    def cell_center(self, row, col):
        x = self.grid_x + col * self.cell_size + self.cell_size // 2
        y = self.grid_y + row * self.cell_size + self.cell_size // 2
        return x, y

    def is_wall(self, row, col):
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return True
        return self.maze[row][col] == 1

    def spawn_particles(self, x, y, color, count, speed_lo=45, speed_hi=170, life_lo=0.2, life_hi=0.65, size_lo=2.0, size_hi=4.8):
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(speed_lo, speed_hi)
            ttl = self.rng.uniform(life_lo, life_hi)
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    life=ttl,
                    ttl=ttl,
                    size=self.rng.uniform(size_lo, size_hi),
                    color=color,
                )
            )

    def try_move(self, dr, dc):
        if self.moving or self.round_resolved:
            return

        nr = self.player_row + dr
        nc = self.player_col + dc

        if self.is_wall(nr, nc):
            self.mistakes += 1
            self.red_flash = 0.28
            self.shake_timer = self.shake_duration
            self.shake_power = 14
            self.maze_glitch_timer = max(self.maze_glitch_timer, 0.2)
            self.play_sound(self.snd_hit, volume=0.75)
            self.spawn_particles(self.player_px, self.player_py, NEON_RED, 22, speed_lo=70, speed_hi=230)

            # Reset to start for higher tension.
            self.player_row, self.player_col = self.start_cell
            self.target_cell = self.start_cell
            cx, cy = self.cell_center(*self.start_cell)
            self.player_px = float(cx)
            self.player_py = float(cy)
            self.move_from = (self.player_px, self.player_py)
            self.move_to = (self.player_px, self.player_py)
            self.move_progress = 1.0
            self.moving = False
            return

        self.target_cell = (nr, nc)
        self.moving = True
        self.move_progress = 0.0
        self.move_from = (self.player_px, self.player_py)
        self.move_to = self.cell_center(nr, nc)
        self.trail_stamp_timer = 0.0
        self.play_sound(self.snd_move, volume=0.45)

        # Movement burst
        self.spawn_particles(self.player_px, self.player_py, NEON_CYAN, 10, speed_lo=35, speed_hi=120, life_lo=0.14, life_hi=0.36)

    def activate_focus_mode(self):
        if self.focus_charges <= 0 or self.round_resolved:
            return
        self.focus_charges -= 1
        self.focus_timer = 1.85
        self.play_sound(self.snd_ui, volume=0.55)
        self.spawn_particles(self.player_px, self.player_py, NEON_GREEN, 20, speed_lo=45, speed_hi=180)

    def update_player_motion(self, dt):
        if not self.moving:
            return

        self.move_progress += dt / self.move_duration
        t = clamp(self.move_progress, 0.0, 1.0)
        et = ease_out_cubic(t)

        self.player_px = lerp(self.move_from[0], self.move_to[0], et)
        self.player_py = lerp(self.move_from[1], self.move_to[1], et)

        self.trail_stamp_timer -= dt
        if self.trail_stamp_timer <= 0:
            self.trail_stamp_timer = 0.035
            self.trail.append(
                TrailNode(
                    x=self.player_px,
                    y=self.player_py,
                    life=0.34,
                    ttl=0.34,
                    radius=max(2.0, self.cell_size * 0.13),
                    color=NEON_CYAN,
                )
            )

        if t >= 1.0:
            self.moving = False
            self.player_row, self.player_col = self.target_cell

    # -----------------------------
    # Screen handlers
    # -----------------------------
    def handle_start_events(self, event):
        if self.transition_phase == 1:
            return

        if self.start_btn.handle_event(event):
            self.play_sound(self.snd_ui, volume=0.65)
            self.start_new_run()
            self.transition_to(STATE_PREVIEW)
        elif self.exit_btn.handle_event(event):
            pygame.quit()
            sys.exit(0)

        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.play_sound(self.snd_ui, volume=0.65)
            self.start_new_run()
            self.transition_to(STATE_PREVIEW)

    def handle_gameplay_events(self, event):
        if event.type != pygame.KEYDOWN or self.round_resolved or self.transition_phase == 1:
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.try_move(-1, 0)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.try_move(1, 0)
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self.try_move(0, -1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.try_move(0, 1)
        elif event.key == pygame.K_h and self.hints_remaining > 0 and self.hint_reveal_timer <= 0:
            self.hints_remaining -= 1
            self.hint_reveal_timer = 1.45
            self.play_sound(self.snd_ui, volume=0.52)
        elif event.key in (pygame.K_f, pygame.K_SPACE):
            self.activate_focus_mode()

    def handle_complete_events(self, event):
        if self.transition_phase == 1:
            return

        if self.continue_btn.handle_event(event):
            self.play_sound(self.snd_ui, volume=0.65)
            if self.level < self.max_level:
                self.level += 1
                self.reset_level_data(new_level=True)
                self.transition_to(STATE_PREVIEW)
            else:
                self.transition_to(STATE_START)

        elif self.complete_menu_btn.handle_event(event):
            self.play_sound(self.snd_ui, volume=0.55)
            self.transition_to(STATE_START)

        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            if self.level < self.max_level:
                self.level += 1
                self.reset_level_data(new_level=True)
                self.transition_to(STATE_PREVIEW)
            else:
                self.transition_to(STATE_START)

    def handle_game_over_events(self, event):
        if self.transition_phase == 1:
            return

        if self.retry_btn.handle_event(event):
            self.play_sound(self.snd_ui, volume=0.65)
            self.reset_level_data(new_level=False)
            self.transition_to(STATE_PREVIEW)
        elif self.over_menu_btn.handle_event(event):
            self.play_sound(self.snd_ui, volume=0.55)
            self.transition_to(STATE_START)

        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.reset_level_data(new_level=False)
            self.transition_to(STATE_PREVIEW)

    # -----------------------------
    # Game update
    # -----------------------------
    def compute_level_score(self):
        base_score = 850 + self.level * 145
        time_bonus = int(self.level_timer * 22)
        focus_bonus = self.focus_charges * 85
        hint_bonus = self.hints_remaining * 55
        mistake_penalty = self.mistakes * 95

        level_score = max(120, base_score + time_bonus + focus_bonus + hint_bonus - mistake_penalty)
        self.level_breakdown = {
            "Base": base_score,
            "Time Bonus": time_bonus,
            "Focus Bonus": focus_bonus,
            "Hint Bonus": hint_bonus,
            "Mistake Penalty": -mistake_penalty,
            "Total": level_score,
        }
        self.level_score = level_score
        self.total_score += level_score

    def resolve_level_complete(self):
        if self.round_resolved:
            return
        self.round_resolved = True
        self.compute_level_score()
        self.play_sound(self.snd_win, volume=0.78)

        gx, gy = self.cell_center(*self.goal_cell)
        self.spawn_particles(gx, gy, NEON_GREEN, 70, speed_lo=50, speed_hi=245, life_lo=0.35, life_hi=0.9)
        self.transition_to(STATE_LEVEL_COMPLETE)

    def resolve_game_over(self):
        if self.round_resolved:
            return
        self.round_resolved = True
        self.game_over_glitch = 1.0
        self.red_flash = max(self.red_flash, 0.28)
        self.play_sound(self.snd_hit, volume=0.72)
        self.transition_to(STATE_GAME_OVER)

    def update_backdrop_particles(self, dt):
        for p in self.bg_particles:
            p["y"] += p["speed"] * dt * (0.65 + p["depth"])
            p["x"] += math.sin(self.global_time * 0.45 + p["phase"]) * dt * 16 * p["depth"]

            if p["y"] > HEIGHT + 4:
                p["y"] = -4
                p["x"] = self.rng.uniform(0, WIDTH)

            if p["x"] < -6:
                p["x"] = WIDTH + 6
            elif p["x"] > WIDTH + 6:
                p["x"] = -6

    def update_effects(self, dt):
        self.red_flash = max(0.0, self.red_flash - dt)
        self.shake_timer = max(0.0, self.shake_timer - dt)
        self.maze_glitch_timer = max(0.0, self.maze_glitch_timer - dt)
        self.game_over_glitch = max(0.0, self.game_over_glitch - dt)
        self.hint_reveal_timer = max(0.0, self.hint_reveal_timer - dt)
        self.focus_timer = max(0.0, self.focus_timer - dt)

        for particle in self.particles[:]:
            particle.life -= dt
            if particle.life <= 0:
                self.particles.remove(particle)
                continue
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vx *= 0.94
            particle.vy *= 0.94

        for node in self.trail[:]:
            node.life -= dt
            if node.life <= 0:
                self.trail.remove(node)

    def update(self, dt):
        self.global_time += dt
        self.state_age += dt

        mouse = pygame.mouse.get_pos()
        if self.state == STATE_START:
            self.start_btn.update(dt, mouse)
            self.exit_btn.update(dt, mouse)
        elif self.state == STATE_LEVEL_COMPLETE:
            self.continue_btn.update(dt, mouse)
            self.complete_menu_btn.update(dt, mouse)
        elif self.state == STATE_GAME_OVER:
            self.retry_btn.update(dt, mouse)
            self.over_menu_btn.update(dt, mouse)

        self.update_backdrop_particles(dt)
        self.update_effects(dt)

        if self.state == STATE_PREVIEW:
            self.preview_left -= dt
            if self.preview_left <= 0:
                self.preview_left = 0
                self.set_state(STATE_PLAYING)
                self.maze_glitch_timer = 0.34

        elif self.state == STATE_PLAYING:
            if not self.round_resolved:
                self.level_timer -= dt
                self.level_timer = max(0.0, self.level_timer)

                self.memory_stability -= self.memory_decay_rate * dt
                self.memory_stability = clamp(self.memory_stability, 0.08, 1.0)

                # Flicker/glitch bursts as memory gets weaker.
                if self.memory_stability < 0.58 and self.rng.random() < 0.02:
                    self.maze_glitch_timer = max(self.maze_glitch_timer, 0.12)
                if self.memory_stability < 0.32 and self.rng.random() < 0.04:
                    self.maze_glitch_timer = max(self.maze_glitch_timer, 0.17)

                self.update_player_motion(dt)

                if self.level_timer <= 0:
                    self.resolve_game_over()

                if (self.player_row, self.player_col) == self.goal_cell and not self.moving:
                    self.resolve_level_complete()

        self.update_transition(dt)

    # -----------------------------
    # Draw helpers
    # -----------------------------
    def get_shake_offset(self):
        if self.shake_timer <= 0:
            return 0, 0
        t = self.shake_timer / max(0.001, self.shake_duration)
        power = self.shake_power * t
        return int(self.rng.uniform(-power, power)), int(self.rng.uniform(-power, power))

    def draw_background(self, surface):
        draw_vertical_gradient(surface, BG_DEEP, BG_MID)

        # Tron-like moving grid plane.
        grid = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        horizon = int(HEIGHT * 0.33)

        for i in range(-16, 17):
            base_x = WIDTH // 2 + i * 68
            drift = math.sin(self.global_time * 0.8 + i * 0.65) * 24
            x1 = int(base_x + drift)
            x2 = int(base_x + drift + i * 26)
            pygame.draw.line(grid, (35, 110, 150, 58), (x1, horizon), (x2, HEIGHT), 1)

        scroll = (self.global_time * 120) % 52
        for i in range(1, 18):
            t = i / 18.0
            y = int(horizon + (t ** 1.85) * (HEIGHT - horizon) + scroll)
            if y > HEIGHT:
                y -= HEIGHT - horizon
            alpha = int(22 + 72 * (1 - t))
            pygame.draw.line(grid, (24, 140, 180, alpha), (0, y), (WIDTH, y), 1)

        pygame.draw.rect(grid, (255, 84, 220, 22), (0, 0, WIDTH, horizon), width=0)
        surface.blit(grid, (0, 0))

        # Floating ambient particles.
        for p in self.bg_particles:
            a = int(55 + p["depth"] * 80)
            color = (90, 212, 255, clamp(a, 20, 135)) if int(p["x"]) % 2 == 0 else (255, 85, 204, clamp(a, 20, 130))
            pygame.draw.circle(surface, color, (int(p["x"]), int(p["y"])), int(1 + p["depth"]))

        # Soft vignette.
        vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(6):
            pad = i * 28
            alpha = 16 + i * 5
            pygame.draw.rect(vignette, (0, 0, 0, alpha), (pad, pad, WIDTH - 2 * pad, HEIGHT - 2 * pad), width=26)
        surface.blit(vignette, (0, 0))

    def draw_particles(self, surface):
        for particle in self.particles:
            t = particle.life / max(0.001, particle.ttl)
            alpha = int(220 * t)
            radius = max(1, int(particle.size * (0.65 + t * 0.45)))
            pygame.draw.circle(surface, (*particle.color, alpha), (int(particle.x), int(particle.y)), radius)

    def draw_trail(self, surface):
        for node in self.trail:
            t = node.life / max(0.001, node.ttl)
            alpha = int(145 * t)
            radius = max(1, int(node.radius * t))
            pygame.draw.circle(surface, (*node.color, alpha), (int(node.x), int(node.y)), radius)

    def draw_hud(self, surface):
        pulse = 0.5 + 0.5 * math.sin(self.global_time * 2.0)

        top_rect = pygame.Rect(12, 10, WIDTH - 24, TOP_BAR_H - 14)
        draw_holo_panel(surface, top_rect, NEON_CYAN, pulse=pulse * 0.6, fill_alpha=145)

        seg_w = (top_rect.width - 24) // 3
        score_rect = pygame.Rect(top_rect.x + 8, top_rect.y + 8, seg_w, top_rect.height - 16)
        timer_rect = pygame.Rect(score_rect.right + 8, top_rect.y + 8, seg_w, top_rect.height - 16)
        level_rect = pygame.Rect(timer_rect.right + 8, top_rect.y + 8, seg_w, top_rect.height - 16)

        draw_holo_panel(surface, score_rect, NEON_CYAN, pulse=0.3 + pulse * 0.5, fill_alpha=120)
        draw_holo_panel(surface, timer_rect, NEON_MAGENTA, pulse=0.28 + pulse * 0.5, fill_alpha=120)
        draw_holo_panel(surface, level_rect, NEON_GREEN, pulse=0.22 + pulse * 0.5, fill_alpha=120)

        draw_glow_text(surface, "SCORE", self.tiny_font, (score_rect.centerx, score_rect.y + 14), (195, 230, 255), NEON_CYAN, center=True)
        draw_glow_text(surface, f"{self.total_score:,}", self.ui_font, (score_rect.centerx, score_rect.y + 38), TEXT_COLOR, NEON_CYAN, center=True)

        timer_value = self.preview_left if self.state == STATE_PREVIEW else self.level_timer
        timer_label = "MEMORY" if self.state == STATE_PREVIEW else "TIMER"
        draw_glow_text(surface, timer_label, self.tiny_font, (timer_rect.centerx, timer_rect.y + 14), (245, 205, 255), NEON_MAGENTA, center=True)
        draw_glow_text(surface, f"{timer_value:05.1f}s", self.ui_font, (timer_rect.centerx, timer_rect.y + 38), TEXT_COLOR, NEON_MAGENTA, center=True)

        draw_glow_text(surface, "LEVEL", self.tiny_font, (level_rect.centerx, level_rect.y + 14), (205, 255, 220), NEON_GREEN, center=True)
        draw_glow_text(surface, f"{self.level}/{self.max_level}", self.ui_font, (level_rect.centerx, level_rect.y + 38), TEXT_COLOR, NEON_GREEN, center=True)

        # Bottom status panel
        bottom_rect = pygame.Rect(12, HEIGHT - BOTTOM_BAR_H + 8, WIDTH - 24, BOTTOM_BAR_H - 16)
        draw_holo_panel(surface, bottom_rect, NEON_BLUE, pulse=0.4 + pulse * 0.6, fill_alpha=150)

        draw_glow_text(
            surface,
            f"HINTS: {self.hints_remaining} [H]   FOCUS: {self.focus_charges} [F/SPACE]",
            self.small_font,
            (bottom_rect.x + 18, bottom_rect.y + 15),
            (210, 230, 255),
            NEON_CYAN,
        )

        status = "MAZE STABLE" if self.memory_stability > 0.65 else ("PATTERN DECAYING" if self.memory_stability > 0.3 else "MEMORY CRITICAL")
        draw_glow_text(
            surface,
            status,
            self.small_font,
            (bottom_rect.right - 260, bottom_rect.y + 15),
            (240, 220, 255),
            NEON_MAGENTA,
        )

        # Memory Stability Bar
        bar_label_pos = (bottom_rect.centerx, bottom_rect.y + 16)
        draw_glow_text(surface, "MEMORY STABILITY", self.tiny_font, bar_label_pos, (225, 240, 255), NEON_BLUE, center=True)

        bar_rect = pygame.Rect(bottom_rect.centerx - 170, bottom_rect.y + 42, 340, 16)
        pygame.draw.rect(surface, (12, 16, 26), bar_rect, border_radius=8)
        pygame.draw.rect(surface, (105, 145, 200), bar_rect, width=1, border_radius=8)

        fill_w = int((bar_rect.width - 4) * self.memory_stability)
        if fill_w > 0:
            r = int(lerp(255, 85, self.memory_stability))
            g = int(lerp(60, 255, self.memory_stability))
            b = int(lerp(92, 182, self.memory_stability))
            fill_col = (r, g, b)
            fill_rect = pygame.Rect(bar_rect.x + 2, bar_rect.y + 2, fill_w, bar_rect.height - 4)
            pygame.draw.rect(surface, fill_col, fill_rect, border_radius=7)

        speed_text = f"Decay Rate: {self.memory_decay_rate:.2f}/s"
        draw_glow_text(surface, speed_text, self.tiny_font, (bar_rect.centerx, bar_rect.bottom + 6), (180, 205, 230), NEON_BLUE, center=True)

    def draw_maze(self, surface):
        panel_rect = pygame.Rect(self.grid_x - 14, self.grid_y - 14, self.grid_w + 28, self.grid_h + 28)
        pulse = 0.5 + 0.5 * math.sin(self.global_time * 2.6)
        draw_holo_panel(surface, panel_rect, NEON_CYAN, pulse=pulse * 0.7, fill_alpha=140)

        floor = pygame.Surface((self.grid_w, self.grid_h), pygame.SRCALPHA)
        floor.fill((11, 16, 27, 190))

        # Internal subtle grid
        step = max(12, self.cell_size // 2)
        grid_alpha = int(20 + 12 * pulse)
        for x in range(0, self.grid_w, step):
            pygame.draw.line(floor, (48, 95, 140, grid_alpha), (x, 0), (x, self.grid_h), 1)
        for y in range(0, self.grid_h, step):
            pygame.draw.line(floor, (48, 95, 140, grid_alpha), (0, y), (self.grid_w, y), 1)

        surface.blit(floor, (self.grid_x, self.grid_y))

        reveal_full = self.state == STATE_PREVIEW or self.hint_reveal_timer > 0 or self.focus_timer > 0

        wall_glow = pygame.Surface((self.grid_w, self.grid_h), pygame.SRCALPHA)
        wall_core = pygame.Surface((self.grid_w, self.grid_h), pygame.SRCALPHA)

        for r in range(self.rows):
            for c in range(self.cols):
                if self.maze[r][c] != 1:
                    continue

                vis = 1.0
                if self.state == STATE_PLAYING and not reveal_full:
                    dist = abs(r - self.player_row) + abs(c - self.player_col)
                    falloff = clamp(1.10 - dist * 0.14, 0.05, 1.0)
                    vis = self.memory_stability * falloff

                    # Hide distant walls as memory collapses.
                    if self.memory_stability < 0.72 and dist > int(3 + self.memory_stability * 5):
                        vis *= 0.22
                    if self.memory_stability < 0.28 and self.rng.random() < 0.38:
                        continue

                if self.maze_glitch_timer > 0 and self.state == STATE_PLAYING and not reveal_full:
                    flick = 0.6 + 0.4 * math.sin(self.global_time * 80 + r * 4.3 + c * 5.1)
                    vis *= flick
                    if self.rng.random() < 0.04 * (1 + self.maze_glitch_timer * 4):
                        continue

                if vis < 0.06:
                    continue

                x = c * self.cell_size
                y = r * self.cell_size
                rect = pygame.Rect(x, y, self.cell_size, self.cell_size)
                rounded = max(2, self.cell_size // 6)

                col = NEON_CYAN if (r + c) % 2 == 0 else NEON_MAGENTA
                glow_a = int(20 + 60 * vis)
                core_a = int(28 + 115 * vis)
                edge_a = int(120 + 120 * vis)

                pygame.draw.rect(wall_glow, (*col, glow_a), rect.inflate(8, 8), border_radius=rounded + 2)
                pygame.draw.rect(wall_core, (*col, core_a), rect, border_radius=rounded)
                pygame.draw.rect(wall_core, (220, 250, 255, edge_a), rect, width=1, border_radius=rounded)

        surface.blit(wall_glow, (self.grid_x, self.grid_y))
        surface.blit(wall_core, (self.grid_x, self.grid_y))

        # Flicker/glitch streaks when maze visibility drops.
        if self.maze_glitch_timer > 0 and self.state == STATE_PLAYING and not reveal_full:
            glitch = pygame.Surface((self.grid_w, self.grid_h), pygame.SRCALPHA)
            lines = 8 + int(self.maze_glitch_timer * 22)
            for _ in range(lines):
                yy = self.rng.randint(0, self.grid_h - 2)
                xx = self.rng.randint(0, max(1, self.grid_w - 120))
                ww = self.rng.randint(40, 220)
                color = (255, 72, 214, self.rng.randint(30, 85)) if self.rng.random() < 0.5 else (56, 238, 255, self.rng.randint(30, 85))
                pygame.draw.rect(glitch, color, (xx, yy, ww, 2))
            surface.blit(glitch, (self.grid_x, self.grid_y))

    def draw_goal(self, surface):
        gx, gy = self.cell_center(*self.goal_cell)
        pulse = 0.5 + 0.5 * math.sin(self.global_time * 5.5)

        core_r = max(6, int(self.cell_size * (0.19 + 0.08 * pulse)))
        glow_r = int(self.cell_size * (0.56 + 0.22 * pulse))

        draw_glow_circle(surface, NEON_GREEN, (gx, gy), core_r, glow_radius=glow_r, layers=6)

        ring_r = core_r + int(self.cell_size * 0.46)
        pygame.draw.circle(surface, (*NEON_GREEN, 120), (gx, gy), ring_r, width=2)
        pygame.draw.circle(surface, (*NEON_CYAN, 70), (gx, gy), ring_r + 7, width=1)

    def draw_player(self, surface):
        px, py = int(self.player_px), int(self.player_py)
        radius = max(6, int(self.cell_size * 0.2))
        draw_glow_circle(surface, NEON_CYAN, (px, py), radius, glow_radius=int(self.cell_size * 0.48), layers=6)
        pygame.draw.circle(surface, (244, 255, 255), (px, py), max(2, radius // 2))

    def draw_gameplay_base(self, surface):
        self.draw_background(surface)
        self.draw_hud(surface)
        self.draw_maze(surface)
        self.draw_goal(surface)
        self.draw_trail(surface)
        self.draw_particles(surface)
        self.draw_player(surface)

        if self.state == STATE_PREVIEW:
            msg = f"MEMORIZE THE MAZE  {self.preview_left:0.1f}s"
            draw_glow_text(surface, msg, self.ui_font, (WIDTH // 2, TOP_BAR_H + 20), TEXT_COLOR, NEON_MAGENTA, center=True)

        if self.focus_timer > 0:
            alpha = int(145 * (self.focus_timer / 1.85))
            msg = pygame.Surface((WIDTH, 42), pygame.SRCALPHA)
            msg.fill((25, 120, 92, alpha // 3))
            surface.blit(msg, (0, HEIGHT - BOTTOM_BAR_H - 42))
            draw_glow_text(
                surface,
                "FOCUS MODE ACTIVE: MAZE RECONSTRUCTED",
                self.small_font,
                (WIDTH // 2, HEIGHT - BOTTOM_BAR_H - 20),
                TEXT_COLOR,
                NEON_GREEN,
                center=True,
            )

        if self.red_flash > 0:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = int(165 * (self.red_flash / 0.28))
            overlay.fill((255, 42, 54, clamp(alpha, 0, 165)))
            surface.blit(overlay, (0, 0))

    def draw_start_screen(self, surface):
        self.draw_background(surface)

        pulse = 0.52 + 0.48 * math.sin(self.global_time * 2.2)
        float_y = int(math.sin(self.global_time * 1.7) * 6)

        # Draw main menu logo above the title when available
        if self.logo_image:
            logo_rect = self.logo_image.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 258 + float_y))
            surface.blit(self.logo_image, logo_rect)
            title_y = HEIGHT // 2 - 102 + float_y
            subtitle_y = HEIGHT // 2 - 42 + float_y
        else:
            title_y = HEIGHT // 2 - 170 + float_y
            subtitle_y = HEIGHT // 2 - 100 + float_y

        draw_glow_text(
            surface,
            "MIND MAZE",
            self.title_font,
            (WIDTH // 2, title_y),
            TEXT_COLOR,
            NEON_CYAN,
            center=True,
            glow_strength=1.0 + 0.35 * pulse,
        )

        draw_glow_text(
            surface,
            "MEMORIZE. ADAPT. ESCAPE.",
            self.small_font,
            (WIDTH // 2, subtitle_y),
            (210, 226, 246),
            NEON_MAGENTA,
            center=True,
        )

        panel = pygame.Rect(WIDTH // 2 - 290, HEIGHT // 2 - 26, 580, 122)
        draw_holo_panel(surface, panel, NEON_MAGENTA, pulse=0.25 + pulse * 0.5, fill_alpha=110)

        controls = "ARROWS/WASD: Move    H: Hint Scan    F/SPACE: Focus Mode"
        draw_glow_text(surface, controls, self.tiny_font, (panel.centerx, panel.y + 31), (220, 235, 255), NEON_CYAN, center=True)
        draw_glow_text(surface, "Avoid neon walls. Reach the energy core before time collapses.", self.tiny_font, (panel.centerx, panel.y + 68), (235, 215, 250), NEON_MAGENTA, center=True)

        self.start_btn.draw(surface, self.global_time)
        self.exit_btn.draw(surface, self.global_time)

    def draw_level_complete_screen(self, surface):
        self.draw_gameplay_base(surface)

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 10, 14, 165))
        surface.blit(overlay, (0, 0))

        pulse = 0.5 + 0.5 * math.sin(self.global_time * 4.2)
        panel = pygame.Rect(WIDTH // 2 - 330, HEIGHT // 2 - 210, 660, 420)
        draw_holo_panel(surface, panel, NEON_GREEN, pulse=0.35 + pulse * 0.55, fill_alpha=180)

        # Success burst rings
        center = (panel.centerx, panel.y + 52)
        pygame.draw.circle(surface, (*NEON_GREEN, 115), center, 32 + int(pulse * 9), width=2)
        pygame.draw.circle(surface, (*NEON_CYAN, 80), center, 46 + int(pulse * 12), width=1)

        draw_glow_text(surface, "LEVEL COMPLETE", self.hero_font, (panel.centerx, panel.y + 54), TEXT_COLOR, NEON_GREEN, center=True)
        draw_glow_text(surface, f"Level Score: {self.level_score:,}", self.ui_font, (panel.centerx, panel.y + 104), (220, 255, 230), NEON_GREEN, center=True)

        left_x = panel.x + 70
        y = panel.y + 148
        for key in ["Base", "Time Bonus", "Focus Bonus", "Hint Bonus", "Mistake Penalty", "Total"]:
            value = self.level_breakdown.get(key, 0)
            value_text = f"{value:+,}" if key != "Total" else f"{value:,}"
            col = (210, 235, 255) if value >= 0 else (255, 170, 182)
            glow = NEON_CYAN if value >= 0 else NEON_RED
            draw_glow_text(surface, key, self.small_font, (left_x, y), (225, 235, 250), NEON_CYAN)
            draw_glow_text(surface, value_text, self.small_font, (panel.right - 88, y), col, glow, center=True)
            y += 34

        draw_glow_text(surface, f"Total Score: {self.total_score:,}", self.ui_font, (panel.centerx, panel.bottom - 78), TEXT_COLOR, NEON_MAGENTA, center=True)

        self.complete_menu_btn.draw(surface, self.global_time)
        self.continue_btn.draw(surface, self.global_time)

    def draw_game_over_screen(self, surface):
        self.draw_gameplay_base(surface)

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 0, 0, 188))
        surface.blit(overlay, (0, 0))

        # Red glitch strips
        glitch_strength = clamp(self.game_over_glitch, 0.0, 1.0)
        strips = 16 + int(glitch_strength * 34)
        for _ in range(strips):
            y = self.rng.randint(0, HEIGHT - 3)
            h = self.rng.randint(1, 3)
            x_off = self.rng.randint(-40, 40)
            color = (255, 55, 72, self.rng.randint(30, 115))
            strip = pygame.Surface((WIDTH, h), pygame.SRCALPHA)
            strip.fill(color)
            surface.blit(strip, (x_off, y))

        panel = pygame.Rect(WIDTH // 2 - 330, HEIGHT // 2 - 190, 660, 390)
        pulse = 0.5 + 0.5 * math.sin(self.global_time * 5.4)
        draw_holo_panel(surface, panel, NEON_RED, pulse=0.38 + pulse * 0.6, fill_alpha=190)

        draw_glow_text(surface, "SYSTEM FAILURE", self.hero_font, (panel.centerx, panel.y + 64), TEXT_COLOR, NEON_RED, center=True)
        draw_glow_text(
            surface,
            f"Maze integrity lost at Level {self.level}",
            self.small_font,
            (panel.centerx, panel.y + 110),
            (255, 210, 220),
            NEON_RED,
            center=True,
        )

        draw_glow_text(surface, f"Score: {self.total_score:,}", self.ui_font, (panel.centerx, panel.y + 168), (242, 235, 255), NEON_MAGENTA, center=True)
        draw_glow_text(surface, f"Mistakes: {self.mistakes}", self.small_font, (panel.centerx, panel.y + 206), (255, 186, 202), NEON_RED, center=True)

        self.retry_btn.draw(surface, self.global_time)
        self.over_menu_btn.draw(surface, self.global_time)

    def draw(self):
        frame = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        if self.state == STATE_START:
            self.draw_start_screen(frame)

        elif self.state in (STATE_PREVIEW, STATE_PLAYING):
            self.draw_gameplay_base(frame)

        elif self.state == STATE_LEVEL_COMPLETE:
            self.draw_level_complete_screen(frame)

        elif self.state == STATE_GAME_OVER:
            self.draw_game_over_screen(frame)

        if self.state in (STATE_PREVIEW, STATE_PLAYING, STATE_LEVEL_COMPLETE, STATE_GAME_OVER):
            shake_x, shake_y = self.get_shake_offset()
        else:
            shake_x, shake_y = 0, 0

        self.screen.fill((0, 0, 0))
        self.screen.blit(frame, (shake_x, shake_y))

        if self.transition_alpha > 0:
            fade = pygame.Surface((WIDTH, HEIGHT))
            fade.fill((0, 0, 0))
            fade.set_alpha(int(self.transition_alpha))
            self.screen.blit(fade, (0, 0))

    # -----------------------------
    # Main loop
    # -----------------------------
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.state == STATE_START:
                        pygame.quit()
                        sys.exit(0)
                    self.transition_to(STATE_START)

                if self.state == STATE_START:
                    self.handle_start_events(event)
                elif self.state in (STATE_PREVIEW, STATE_PLAYING):
                    self.handle_gameplay_events(event)
                elif self.state == STATE_LEVEL_COMPLETE:
                    self.handle_complete_events(event)
                elif self.state == STATE_GAME_OVER:
                    self.handle_game_over_events(event)

            self.update(dt)
            self.draw()
            pygame.display.flip()


if __name__ == "__main__":
    MindMazeGame().run()
