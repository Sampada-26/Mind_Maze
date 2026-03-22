import math
import random
import sys
from array import array

import pygame

# -----------------------------
# Config
# -----------------------------
WIDTH, HEIGHT = 1000, 760
FPS = 60
TOP_BAR_H = 60
BOTTOM_BAR_H = 52
PLAY_MARGIN = 20

BG_COLOR = (10, 10, 16)
TEXT_COLOR = (220, 240, 255)
NEON_BLUE = (80, 180, 255)
NEON_PURPLE = (170, 90, 255)
NEON_RED = (255, 70, 90)
NEON_GREEN = (85, 255, 145)
PANEL_COLOR = (18, 18, 30)

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


def draw_glow_circle(surface, color, center, radius, glow_radius=20, layers=4):
    """Draw a neon-like glowing circle using alpha layers."""
    glow_surface = pygame.Surface((radius * 2 + glow_radius * 2, radius * 2 + glow_radius * 2), pygame.SRCALPHA)
    gx, gy = glow_surface.get_size()
    c = (gx // 2, gy // 2)

    for i in range(layers, 0, -1):
        r = radius + int(glow_radius * (i / layers))
        a = int(35 * (i / layers))
        pygame.draw.circle(glow_surface, (*color, a), c, r)

    pygame.draw.circle(glow_surface, (*color, 255), c, radius)
    surface.blit(glow_surface, (center[0] - gx // 2, center[1] - gy // 2), special_flags=pygame.BLEND_ALPHA_SDL2)


def draw_glow_text(surface, text, font, pos, color, glow_color, center=False):
    """Render text with subtle glow for neon UI."""
    text_surf = font.render(text, True, color)
    rect = text_surf.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos

    for ox, oy, alpha in [(-2, 0, 55), (2, 0, 55), (0, -2, 55), (0, 2, 55), (0, 0, 85)]:
        glow = font.render(text, True, glow_color)
        glow.set_alpha(alpha)
        g_rect = glow.get_rect(center=rect.center)
        g_rect.x += ox
        g_rect.y += oy
        surface.blit(glow, g_rect)

    surface.blit(text_surf, rect)


def lerp(a, b, t):
    return a + (b - a) * t


def create_tone(freq=440, duration=0.1, volume=0.35, sample_rate=44100):
    """Generate a simple sine-wave tone as pygame Sound without external assets."""
    n_samples = int(duration * sample_rate)
    buf = array("h")
    amp = int(32767 * volume)
    for i in range(n_samples):
        t = i / sample_rate
        s = int(amp * math.sin(2 * math.pi * freq * t))
        buf.append(s)
    return pygame.mixer.Sound(buffer=buf.tobytes())


# -----------------------------
# Maze generation
# -----------------------------
def generate_maze(rows, cols):
    """
    Generate a perfect maze with DFS backtracking.
    0 = path, 1 = wall

    Uses odd dimensions; starts from top-left (0,0) and guarantees a path to bottom-right.
    """
    maze = [[1 for _ in range(cols)] for _ in range(rows)]

    # Carve from (0,0) across "cell" positions stepping by 2.
    stack = [(0, 0)]
    maze[0][0] = 0

    directions = [(2, 0), (-2, 0), (0, 2), (0, -2)]

    while stack:
        r, c = stack[-1]
        neighbors = []
        random.shuffle(directions)

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


class Button:
    def __init__(self, rect, label, font):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font

    def draw(self, surface, mouse_pos):
        hover = self.rect.collidepoint(mouse_pos)
        base = NEON_PURPLE if hover else NEON_BLUE

        # Glow border
        glow_rect = self.rect.inflate(14, 14)
        glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow, (*base, 70 if hover else 40), glow.get_rect(), border_radius=14)
        surface.blit(glow, glow_rect.topleft)

        pygame.draw.rect(surface, PANEL_COLOR, self.rect, border_radius=10)
        pygame.draw.rect(surface, base, self.rect, width=2, border_radius=10)
        draw_glow_text(surface, self.label, self.font, self.rect.center, TEXT_COLOR, base, center=True)

    def clicked(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)


class MindMazeGame:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 1, 256)
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Mind Maze")
        self.clock = pygame.time.Clock()

        # Fonts
        self.title_font = pygame.font.SysFont("consolas", 72, bold=True)
        self.big_font = pygame.font.SysFont("consolas", 40, bold=True)
        self.ui_font = pygame.font.SysFont("consolas", 28, bold=True)
        self.small_font = pygame.font.SysFont("consolas", 20)

        # Sounds (graceful fallback if audio unavailable)
        self.snd_move = None
        self.snd_hit = None
        self.snd_win = None
        self.init_sounds()

        self.state = STATE_START

        # Start screen buttons
        self.start_btn = Button((WIDTH // 2 - 150, HEIGHT // 2 + 30, 300, 64), "START GAME", self.ui_font)
        self.exit_btn = Button((WIDTH // 2 - 150, HEIGHT // 2 + 120, 300, 64), "EXIT", self.ui_font)

        # Game variables initialized per level
        self.level = 1
        self.max_level = 12
        self.reset_level_data(new_level=True)

    def init_sounds(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.snd_move = create_tone(600, 0.035, 0.17)
            self.snd_hit = create_tone(180, 0.18, 0.34)
            self.snd_win = create_tone(900, 0.13, 0.27)
        except pygame.error:
            # Audio not available in environment; gameplay still works.
            self.snd_move = self.snd_hit = self.snd_win = None

    def play_sound(self, snd):
        if snd:
            snd.play()

    def level_config(self, level):
        # Odd dimensions keep DFS carving consistent.
        base = 11
        size = min(base + (level - 1) * 2, 31)
        preview_time = clamp(5.0 - (level - 1) * 0.35, 2.0, 5.0)
        level_time = clamp(70 - (level - 1) * 4, 24, 70)
        hints = 2 if level <= 3 else (1 if level <= 7 else 0)
        fog_radius = clamp(5 - (level // 4), 2, 5)
        return size, size, preview_time, level_time, hints, fog_radius

    def reset_level_data(self, new_level=False):
        rows, cols, preview_time, level_time, hints, fog_radius = self.level_config(self.level)

        self.rows = rows
        self.cols = cols
        self.preview_duration = preview_time
        self.level_duration = level_time
        self.hints_remaining = hints
        self.fog_radius = fog_radius

        self.maze = generate_maze(self.rows, self.cols)

        # Layout for maze area
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
        self.prev_safe_cell = self.start_cell
        self.target_cell = self.start_cell

        cx, cy = self.cell_center(self.player_row, self.player_col)
        self.player_px = float(cx)
        self.player_py = float(cy)
        self.move_from = (self.player_px, self.player_py)
        self.move_to = (self.player_px, self.player_py)
        self.move_progress = 1.0
        self.moving = False
        self.move_duration = 0.12

        self.preview_left = self.preview_duration
        self.level_timer = self.level_duration

        self.level_start_ticks = pygame.time.get_ticks()
        self.mistakes = 0

        self.flash_red = 0.0
        self.hint_reveal_timer = 0.0

        # Transition alpha (fade in)
        self.fade_alpha = 180 if new_level else 0

    def cell_center(self, r, c):
        x = self.grid_x + c * self.cell_size + self.cell_size // 2
        y = self.grid_y + r * self.cell_size + self.cell_size // 2
        return x, y

    def is_wall(self, r, c):
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return True
        return self.maze[r][c] == 1

    def try_move(self, dr, dc):
        if self.moving:
            return

        nr = self.player_row + dr
        nc = self.player_col + dc

        if self.is_wall(nr, nc):
            self.mistakes += 1
            self.flash_red = 0.25
            self.play_sound(self.snd_hit)

            # Reset to start for higher tension.
            self.player_row, self.player_col = self.start_cell
            self.target_cell = self.start_cell
            cx, cy = self.cell_center(self.player_row, self.player_col)
            self.player_px = float(cx)
            self.player_py = float(cy)
            self.move_from = (self.player_px, self.player_py)
            self.move_to = (self.player_px, self.player_py)
            self.move_progress = 1.0
            self.moving = False
            return

        self.prev_safe_cell = (self.player_row, self.player_col)
        self.target_cell = (nr, nc)
        self.moving = True
        self.move_progress = 0.0
        self.move_from = (self.player_px, self.player_py)
        self.move_to = self.cell_center(nr, nc)
        self.play_sound(self.snd_move)

    def update_player_motion(self, dt):
        if not self.moving:
            return

        self.move_progress += dt / self.move_duration
        t = clamp(self.move_progress, 0.0, 1.0)

        # Ease-out for smoother motion
        et = 1 - (1 - t) * (1 - t)

        self.player_px = lerp(self.move_from[0], self.move_to[0], et)
        self.player_py = lerp(self.move_from[1], self.move_to[1], et)

        if t >= 1.0:
            self.moving = False
            self.player_row, self.player_col = self.target_cell

    def draw_background(self):
        self.screen.fill(BG_COLOR)

        # Subtle cyber gradient bands
        grad = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(HEIGHT):
            alpha = int(18 + 18 * math.sin(y * 0.009 + pygame.time.get_ticks() * 0.001))
            color = (16, 20, 34, clamp(alpha, 10, 45))
            pygame.draw.line(grad, color, (0, y), (WIDTH, y))
        self.screen.blit(grad, (0, 0))

    def draw_ui_bars(self):
        pygame.draw.rect(self.screen, PANEL_COLOR, (0, 0, WIDTH, TOP_BAR_H))
        pygame.draw.line(self.screen, NEON_BLUE, (0, TOP_BAR_H - 1), (WIDTH, TOP_BAR_H - 1), 1)

        pygame.draw.rect(self.screen, PANEL_COLOR, (0, HEIGHT - BOTTOM_BAR_H, WIDTH, BOTTOM_BAR_H))
        pygame.draw.line(self.screen, NEON_PURPLE, (0, HEIGHT - BOTTOM_BAR_H), (WIDTH, HEIGHT - BOTTOM_BAR_H), 1)

        draw_glow_text(
            self.screen,
            f"LEVEL {self.level}",
            self.ui_font,
            (20, 14),
            TEXT_COLOR,
            NEON_BLUE,
        )

        if self.state in (STATE_PREVIEW, STATE_PLAYING):
            time_label = "PREVIEW" if self.state == STATE_PREVIEW else "TIME"
            timer_value = self.preview_left if self.state == STATE_PREVIEW else self.level_timer
            draw_glow_text(
                self.screen,
                f"{time_label}: {max(0, timer_value):04.1f}s",
                self.ui_font,
                (WIDTH - 300, 14),
                TEXT_COLOR,
                NEON_PURPLE,
            )

        draw_glow_text(
            self.screen,
            f"MISTAKES: {self.mistakes}",
            self.small_font,
            (20, HEIGHT - BOTTOM_BAR_H + 15),
            (205, 220, 245),
            NEON_BLUE,
        )

        hint_text = f"HINTS: {self.hints_remaining}   (press H)"
        draw_glow_text(
            self.screen,
            hint_text,
            self.small_font,
            (WIDTH - 280, HEIGHT - BOTTOM_BAR_H + 15),
            (205, 220, 245),
            NEON_PURPLE,
        )

    def draw_maze(self, ghost=False, reveal_full=False):
        # Grid panel
        panel_rect = pygame.Rect(self.grid_x - 10, self.grid_y - 10, self.grid_w + 20, self.grid_h + 20)
        pygame.draw.rect(self.screen, (14, 14, 22), panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, (60, 85, 125), panel_rect, width=1, border_radius=8)

        wall_alpha = 210 if not ghost else 60
        wall_color = (*NEON_BLUE, wall_alpha)
        wall_color2 = (*NEON_PURPLE, wall_alpha)

        wall_surface = pygame.Surface((self.grid_w, self.grid_h), pygame.SRCALPHA)

        px, py = self.player_row, self.player_col
        for r in range(self.rows):
            for c in range(self.cols):
                if self.maze[r][c] != 1:
                    continue

                if self.state == STATE_PLAYING and not reveal_full:
                    # Optional fog: hide far walls for extra challenge.
                    dist = abs(r - px) + abs(c - py)
                    if dist > self.fog_radius:
                        continue

                x = c * self.cell_size
                y = r * self.cell_size
                rect = pygame.Rect(x, y, self.cell_size, self.cell_size)
                color = wall_color if (r + c) % 2 == 0 else wall_color2
                pygame.draw.rect(wall_surface, color, rect)

                # Thin bright edge to keep cyber look readable
                edge_alpha = 180 if not ghost else 85
                edge_color = (140, 220, 255, edge_alpha)
                pygame.draw.rect(wall_surface, edge_color, rect, width=1)

        self.screen.blit(wall_surface, (self.grid_x, self.grid_y))

    def draw_goal(self):
        gx, gy = self.cell_center(*self.goal_cell)
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.005)
        radius = int(self.cell_size * (0.24 + 0.08 * pulse))
        glow = int(self.cell_size * (0.40 + 0.15 * pulse))
        draw_glow_circle(self.screen, NEON_GREEN, (gx, gy), radius, glow_radius=glow, layers=5)

    def draw_player(self):
        radius = max(6, int(self.cell_size * 0.22))
        glow = int(self.cell_size * 0.35)
        draw_glow_circle(self.screen, NEON_RED, (int(self.player_px), int(self.player_py)), radius, glow_radius=glow, layers=5)

    def draw_start_screen(self, mouse_pos):
        self.draw_background()

        draw_glow_text(
            self.screen,
            "MIND MAZE",
            self.title_font,
            (WIDTH // 2, HEIGHT // 2 - 120),
            TEXT_COLOR,
            NEON_BLUE,
            center=True,
        )
        draw_glow_text(
            self.screen,
            "MEMORIZE. NAVIGATE. SURVIVE.",
            self.small_font,
            (WIDTH // 2, HEIGHT // 2 - 60),
            (190, 208, 235),
            NEON_PURPLE,
            center=True,
        )

        self.start_btn.draw(self.screen, mouse_pos)
        self.exit_btn.draw(self.screen, mouse_pos)

    def draw_overlay_message(self, title, subtitle, btn_a, btn_b=None):
        self.draw_background()

        panel = pygame.Rect(WIDTH // 2 - 260, HEIGHT // 2 - 170, 520, 340)
        pygame.draw.rect(self.screen, (16, 16, 28), panel, border_radius=12)
        pygame.draw.rect(self.screen, (75, 115, 160), panel, width=2, border_radius=12)

        draw_glow_text(self.screen, title, self.big_font, (WIDTH // 2, panel.y + 70), TEXT_COLOR, NEON_BLUE, center=True)
        draw_glow_text(self.screen, subtitle, self.small_font, (WIDTH // 2, panel.y + 120), (200, 220, 245), NEON_PURPLE, center=True)

        bx = WIDTH // 2 - 160
        by = panel.y + 200
        a_btn = Button((bx, by, 140, 54), btn_a, self.small_font)
        a_btn.draw(self.screen, pygame.mouse.get_pos())

        b_btn = None
        if btn_b:
            b_btn = Button((bx + 180, by, 140, 54), btn_b, self.small_font)
            b_btn.draw(self.screen, pygame.mouse.get_pos())

        return a_btn, b_btn

    def handle_start_events(self, event):
        if self.start_btn.clicked(event):
            self.level = 1
            self.reset_level_data(new_level=True)
            self.state = STATE_PREVIEW
        elif self.exit_btn.clicked(event):
            pygame.quit()
            sys.exit(0)

    def handle_playing_input(self, event):
        if event.type != pygame.KEYDOWN:
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
            self.hint_reveal_timer = 1.3

    def handle_overlay_events(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        mx, my = event.pos
        if self.state == STATE_LEVEL_COMPLETE:
            retry_rect = pygame.Rect(WIDTH // 2 - 160, HEIGHT // 2 + 30, 140, 54)
            next_rect = pygame.Rect(WIDTH // 2 + 20, HEIGHT // 2 + 30, 140, 54)

            if retry_rect.collidepoint((mx, my)):
                self.reset_level_data(new_level=False)
                self.state = STATE_PREVIEW
            elif next_rect.collidepoint((mx, my)):
                self.level = min(self.level + 1, self.max_level)
                self.reset_level_data(new_level=True)
                self.state = STATE_PREVIEW

        elif self.state == STATE_GAME_OVER:
            retry_rect = pygame.Rect(WIDTH // 2 - 160, HEIGHT // 2 + 30, 140, 54)
            exit_rect = pygame.Rect(WIDTH // 2 + 20, HEIGHT // 2 + 30, 140, 54)
            if retry_rect.collidepoint((mx, my)):
                self.reset_level_data(new_level=False)
                self.state = STATE_PREVIEW
            elif exit_rect.collidepoint((mx, my)):
                self.state = STATE_START

    def update(self, dt):
        if self.state == STATE_PREVIEW:
            self.preview_left -= dt
            if self.preview_left <= 0:
                self.preview_left = 0
                self.state = STATE_PLAYING

        elif self.state == STATE_PLAYING:
            self.level_timer -= dt
            if self.level_timer <= 0:
                self.level_timer = 0
                self.state = STATE_GAME_OVER

            if self.hint_reveal_timer > 0:
                self.hint_reveal_timer -= dt

            if self.flash_red > 0:
                self.flash_red -= dt

            self.update_player_motion(dt)

            if (self.player_row, self.player_col) == self.goal_cell and not self.moving:
                self.play_sound(self.snd_win)
                self.state = STATE_LEVEL_COMPLETE

        # fade in transition
        if self.fade_alpha > 0:
            self.fade_alpha = max(0, self.fade_alpha - 240 * dt)

    def draw_gameplay(self):
        self.draw_background()
        self.draw_ui_bars()

        reveal_full = self.state == STATE_PREVIEW or self.hint_reveal_timer > 0
        ghost = self.state == STATE_PLAYING and not reveal_full
        self.draw_maze(ghost=ghost, reveal_full=reveal_full)

        self.draw_goal()
        self.draw_player()

        # Collision flash effect
        if self.flash_red > 0:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = int(130 * (self.flash_red / 0.25))
            overlay.fill((255, 40, 40, clamp(alpha, 0, 130)))
            self.screen.blit(overlay, (0, 0))

        if self.state == STATE_PREVIEW:
            draw_glow_text(
                self.screen,
                f"MEMORIZE THE MAZE: {max(0, self.preview_left):.1f}s",
                self.ui_font,
                (WIDTH // 2, TOP_BAR_H + 18),
                TEXT_COLOR,
                NEON_PURPLE,
                center=True,
            )

    def draw(self):
        if self.state == STATE_START:
            self.draw_start_screen(pygame.mouse.get_pos())

        elif self.state in (STATE_PREVIEW, STATE_PLAYING):
            self.draw_gameplay()

        elif self.state == STATE_LEVEL_COMPLETE:
            # Keep background gameplay context visible behind summary.
            self.draw_gameplay()
            elapsed = self.level_duration - self.level_timer
            subtitle = f"Time: {elapsed:.1f}s   Mistakes: {self.mistakes}"
            self.draw_overlay_message("LEVEL COMPLETE", subtitle, "RETRY", "NEXT")

        elif self.state == STATE_GAME_OVER:
            self.draw_gameplay()
            subtitle = f"Time up. Mistakes: {self.mistakes}"
            self.draw_overlay_message("GAME OVER", subtitle, "RETRY", "MENU")

        if self.fade_alpha > 0:
            fade = pygame.Surface((WIDTH, HEIGHT))
            fade.fill((0, 0, 0))
            fade.set_alpha(int(self.fade_alpha))
            self.screen.blit(fade, (0, 0))

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

                if self.state == STATE_START:
                    self.handle_start_events(event)
                elif self.state in (STATE_PREVIEW, STATE_PLAYING):
                    self.handle_playing_input(event)
                elif self.state in (STATE_LEVEL_COMPLETE, STATE_GAME_OVER):
                    self.handle_overlay_events(event)

            self.update(dt)
            self.draw()
            pygame.display.flip()


if __name__ == "__main__":
    MindMazeGame().run()
