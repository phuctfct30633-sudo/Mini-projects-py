import os
import random
import sys
import unicodedata

# Cho phép hiện khung gợi ý/ghép chữ của bộ gõ (IME) - phải đặt trước khi init pygame
os.environ.setdefault("SDL_IME_SHOW_UI", "1")

import pygame

# ----------------------------------------------------------------------------
# CẤU HÌNH
# ----------------------------------------------------------------------------
W, H = 2560, 1440          # độ phân giải 2K
FPS = 144

START_LIVES = 5
WORDS_PER_LEVEL = 10       # số từ gõ đúng để lên cấp
BASE_SPEED = 90            # px/giây ở cấp 1
SPEED_PER_LEVEL = 16       # tăng tốc mỗi cấp
BASE_SPAWN = 2.4           # giây giữa 2 lần sinh từ ở cấp 1
MIN_SPAWN = 0.7
MAX_INPUT_LEN = 40

BOX_W, BOX_H = 1000, 100
BOX_RECT = pygame.Rect((W - BOX_W) // 2, H - BOX_H - 60, BOX_W, BOX_H)
DEAD_Y = BOX_RECT.top - 50  # vạch đỏ: từ chạm vạch này là mất mạng

# Màu sắc
BG = (14, 17, 30)
WHITE = (235, 238, 245)
GREEN = (90, 230, 140)
RED = (240, 70, 80)
YELLOW = (255, 215, 90)
BLUE = (110, 170, 255)
GRAY = (120, 128, 150)
BOX_BG = (26, 32, 54)

# Từ vựng (chữ thường, có dấu)
WORDS = [
    "wordtest1"
]


def norm(s: str) -> str:
    """Chuẩn hoá Unicode (NFC) + chữ thường để so sánh tiếng Việt chính xác."""
    return unicodedata.normalize("NFC", s).strip().lower()


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Tìm font có hỗ trợ tiếng Việt. Có thể đặt file 'font.ttf' cạnh file này để ép dùng."""
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "font.ttf")
    if os.path.exists(local):
        return pygame.font.Font(local, size)
    for name in ("segoeui", "arial", "tahoma", "calibri", "dejavusans",
                 "notosans", "liberationsans", "freesans", "ubuntu"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)  # dự phòng (có thể thiếu dấu tiếng Việt)


# ----------------------------------------------------------------------------
# ĐỐI TƯỢNG TỪ RƠI
# ----------------------------------------------------------------------------
class FallingWord:
    def __init__(self, text: str, x: float, speed: float, font: pygame.font.Font):
        self.text = norm(text) if False else unicodedata.normalize("NFC", text)
        self.key = norm(text)
        self.x = x
        self.y = -60.0
        self.speed = speed
        self.font = font
        self.w, self.h = font.size(self.text)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def update(self, dt: float):
        self.y += self.speed * dt

    def draw(self, surf: pygame.Surface, typed_key: str):
        # nền mờ cho dễ đọc
        r = self.rect.inflate(36, 16)
        active = bool(typed_key) and self.key.startswith(typed_key)
        pygame.draw.rect(surf, (30, 38, 66), r, border_radius=14)
        pygame.draw.rect(surf, GREEN if active else (60, 72, 110), r, 3, border_radius=14)

        if active:
            n = len(typed_key)
            head = self.font.render(self.text[:n], True, GREEN)
            tail = self.font.render(self.text[n:], True, WHITE)
            surf.blit(head, (self.x, self.y))
            surf.blit(tail, (self.x + head.get_width(), self.y))
        else:
            surf.blit(self.font.render(self.text, True, WHITE), (self.x, self.y))


# ----------------------------------------------------------------------------
# GAME
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Typing Game Tiếng Việt")
        # SCALED: giữ độ phân giải logic 2560x1440 và tự co giãn theo màn hình thật
        flags = pygame.FULLSCREEN | pygame.SCALED
        self.screen = pygame.display.set_mode((W, H), flags)
        self.clock = pygame.time.Clock()

        self.font_word = load_font(54)
        self.font_input = load_font(58)
        self.font_hud = load_font(42)
        self.font_big = load_font(130, bold=True)
        self.font_mid = load_font(56)

        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(BOX_RECT)

        self.state = "menu"   # menu | play | pause | over
        self.reset()

    # ---- trạng thái ----
    def reset(self):
        self.words: list[FallingWord] = []
        self.text = ""          # chữ đã nhập
        self.composing = ""     # chữ đang ghép của bộ gõ (IME)
        self.score = 0
        self.lives = START_LIVES
        self.level = 1
        self.solved = 0
        self.spawn_timer = 1.0
        self.flash = 0.0        # hiệu ứng nhập sai
        self.combo = 0
        self.best_combo = 0

    def speed(self) -> float:
        return BASE_SPEED + (self.level - 1) * SPEED_PER_LEVEL

    def spawn_interval(self) -> float:
        return max(MIN_SPAWN, BASE_SPAWN - (self.level - 1) * 0.18)

    # ---- sinh từ ----
    def spawn_word(self):
        on_screen = {w.key for w in self.words}
        pool = [t for t in WORDS if norm(t) not in on_screen] or WORDS
        text = random.choice(pool)
        w, _ = self.font_word.size(text)
        x = random.randint(80, max(81, W - w - 80))
        # tránh chồng lên từ vừa sinh gần mép trên
        for _ in range(25):
            test = pygame.Rect(x, -60, w, 70).inflate(60, 0)
            if not any(test.colliderect(o.rect) for o in self.words if o.y < 140):
                break
            x = random.randint(80, max(81, W - w - 80))
        spd = self.speed() * random.uniform(0.85, 1.15)
        self.words.append(FallingWord(text, x, spd, self.font_word))

    # ---- xử lý nhập ----
    def submit(self):
        key = norm(self.text)
        self.text = ""
        if not key:
            return
        # chọn từ khớp đang ở thấp nhất (gần vạch đỏ nhất)
        matches = [w for w in self.words if w.key == key]
        if matches:
            target = max(matches, key=lambda w: w.y)
            self.words.remove(target)
            self.combo += 1
            self.best_combo = max(self.best_combo, self.combo)
            self.score += len(target.key) * 10 + (self.combo - 1) * 5
            self.solved += 1
            if self.solved % WORDS_PER_LEVEL == 0:
                self.level += 1
        else:
            self.combo = 0
            self.flash = 0.35

    def handle_event(self, e: pygame.event.Event):
        if e.type == pygame.QUIT:
            self.quit()

        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.quit()

        # --- menu / game over ---
        if self.state in ("menu", "over"):
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.reset()
                self.state = "play"
            return

        # --- tạm dừng ---
        if self.state == "pause":
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self.state = "play"
            return

        # --- đang chơi ---
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.submit()
            elif e.key == pygame.K_BACKSPACE:
                if not self.composing:
                    self.text = self.text[:-1]
            elif e.key == pygame.K_TAB:
                self.state = "pause"
        elif e.type == pygame.TEXTEDITING:
            self.composing = e.text          # chữ IME đang ghép (chưa chốt)
        elif e.type == pygame.TEXTINPUT:
            self.composing = ""
            if len(self.text) < MAX_INPUT_LEN:
                self.text = unicodedata.normalize("NFC", self.text + e.text)

    # ---- cập nhật ----
    def update(self, dt: float):
        if self.state != "play":
            return

        self.flash = max(0.0, self.flash - dt)

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_word()
            self.spawn_timer = self.spawn_interval()

        for w in self.words[:]:
            w.update(dt)
            if w.y + w.h >= DEAD_Y:
                self.words.remove(w)
                self.lives -= 1
                self.combo = 0
                self.flash = 0.35
                if self.lives <= 0:
                    self.state = "over"

    # ---- vẽ ----
    def draw_text_center(self, font, text, color, y):
        s = font.render(text, True, color)
        self.screen.blit(s, ((W - s.get_width()) // 2, y))

    def draw_hud(self):
        self.screen.blit(self.font_hud.render(f"Điểm: {self.score}", True, YELLOW), (60, 40))
        self.screen.blit(self.font_hud.render(f"Cấp độ: {self.level}", True, BLUE), (60, 100))
        lives = self.font_hud.render(f"Mạng: {self.lives}", True, RED if self.lives <= 2 else WHITE)
        self.screen.blit(lives, (W - lives.get_width() - 60, 40))
        if self.combo >= 2:
            c = self.font_hud.render(f"Combo x{self.combo}", True, GREEN)
            self.screen.blit(c, (W - c.get_width() - 60, 100))
        hint = self.font_hud.render("TAB: tạm dừng   ESC: thoát", True, GRAY)
        self.screen.blit(hint, ((W - hint.get_width()) // 2, 40))

    def draw_input_box(self):
        border = RED if self.flash > 0 else GREEN
        pygame.draw.rect(self.screen, BOX_BG, BOX_RECT, border_radius=20)
        pygame.draw.rect(self.screen, border, BOX_RECT, 4, border_radius=20)

        shown = self.text
        surf = self.font_input.render(shown, True, WHITE)
        x = BOX_RECT.x + 30
        y = BOX_RECT.centery - surf.get_height() // 2
        self.screen.blit(surf, (x, y))
        cx = x + surf.get_width()

        if self.composing:  # chữ IME đang ghép: gạch chân
            comp = self.font_input.render(self.composing, True, YELLOW)
            self.screen.blit(comp, (cx, y))
            pygame.draw.line(self.screen, YELLOW, (cx, y + comp.get_height()),
                             (cx + comp.get_width(), y + comp.get_height()), 3)
            cx += comp.get_width()

        if (pygame.time.get_ticks() // 500) % 2 == 0:   # con trỏ nhấp nháy
            pygame.draw.line(self.screen, WHITE, (cx + 4, y + 4), (cx + 4, y + surf.get_height() - 4), 3)

        if not self.text and not self.composing:
            ph = self.font_hud.render("Gõ từ rồi nhấn ENTER...", True, GRAY)
            self.screen.blit(ph, (x, BOX_RECT.centery - ph.get_height() // 2))

    def draw(self):
        self.screen.fill(BG)

        if self.state == "menu":
            self.draw_text_center(self.font_big, "NUKE BOME GAME", GREEN, 420)
            self.draw_text_center(self.font_mid, "Gỡ để phá hủy nó, chạm vạch -> OH MY PCCCCCCC", WHITE, 620)
            self.draw_text_center(self.font_mid, "Nhấn ENTER để bước vào đại ngục", YELLOW, 760)
            self.draw_text_center(self.font_hud, "Dell bật gõ Tiếng Việt -> YOU GAYYY", GRAY, 900)
            pygame.display.flip()
            return

        # vạch nguy hiểm
        pygame.draw.line(self.screen, RED, (0, DEAD_Y), (W, DEAD_Y), 4)

        typed_key = norm(self.text) if not self.composing else ""
        for w in self.words:
            w.draw(self.screen, typed_key)

        self.draw_hud()
        self.draw_input_box()

        if self.state == "pause":
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            self.screen.blit(overlay, (0, 0))
            self.draw_text_center(self.font_big, "TẠM DỪNG", YELLOW, 520)
            self.draw_text_center(self.font_mid, "Nhấn ENTER hoặc TAB để tiếp tục", WHITE, 700)

        if self.state == "over":
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 190))
            self.screen.blit(overlay, (0, 0))
            self.draw_text_center(self.font_big, "KẾT THÚC", RED, 380)
            self.draw_text_center(self.font_mid, f"Điểm: {self.score}   |   Cấp độ: {self.level}", YELLOW, 600)
            self.draw_text_center(self.font_mid, f"Từ đã gõ đúng: {self.solved}   |   Combo cao nhất: {self.best_combo}", WHITE, 690)
            self.draw_text_center(self.font_mid, "Nhấn ENTER để chơi lại", GREEN, 820)

        pygame.display.flip()

    # ---- vòng lặp ----
    def quit(self):
        pygame.quit()
        sys.exit()

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)  # tránh nhảy vọt khi lag
            for e in pygame.event.get():
                self.handle_event(e)
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()