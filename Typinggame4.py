# -*- coding: utf-8 -*-
"""
TYPING GAME TIẾNG VIỆT - Phiên bản 0.3
  + Nút "Thêm từ mới" ngay trong menu (ghi thẳng vào words.txt) và ô "?" hướng dẫn cách gõ từ trong file
  + Nạp từ vựng từ file words.txt
  + Hệ thống thành tựu (lưu vào achievements.json)
  + Âm thanh (tự tạo bằng code, có thể thay bằng file trong thư mục sounds/)
  + Hiệu ứng nổ tung bằng các quả cầu nhiều màu khi phá chữ
"""

import array
import colorsys
import json
import math
import os
import random
import sys
import unicodedata

# Cho phép hiện khung gợi ý/ghép chữ của bộ gõ (IME) - phải đặt trước khi init pygame
os.environ.setdefault("SDL_IME_SHOW_UI", "1")

import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------
# CẤU HÌNH
# ----------------------------------------------------------------------------
W, H = 2560, 1440          # độ phân giải 2K
FPS = 144

START_LIVES = 5
WORDS_PER_LEVEL = 10      # số từ gõ đúng để lên cấp
BASE_SPEED = 90            # px/giây ở cấp 1
SPEED_PER_LEVEL = 16       # tăng tốc mỗi cấp
BASE_SPAWN = 2.4           # giây giữa 2 lần sinh từ ở cấp 1
MIN_SPAWN = 0.7
MAX_INPUT_LEN = 40

BOX_W, BOX_H = 1000, 100
BOX_RECT = pygame.Rect((W - BOX_W) // 2, H - BOX_H - 60, BOX_W, BOX_H)
DEAD_Y = BOX_RECT.top - 50  # vạch đỏ: từ chạm vạch này là mất mạng

# File dữ liệu
WORDS_FILE = "words.txt"            # mỗi dòng 1 từ/cụm từ (UTF-8). Dòng bắt đầu bằng # là ghi chú
SAVE_FILE = "achievements.json"     # lưu thành tựu đã mở khóa
SOUND_DIR = "sounds"                # (tuỳ chọn) đặt file .wav/.ogg để thay âm thanh mặc định

# Màu sắc
BG = (14, 17, 30)
WHITE = (235, 238, 245)
GREEN = (90, 230, 140)
RED = (240, 70, 80)
YELLOW = (255, 215, 90)
BLUE = (110, 170, 255)
GRAY = (120, 128, 150)
BOX_BG = (26, 32, 54)

# Từ vựng dự phòng khi chưa có words.txt
DEFAULT_WORDS = [
    "wordtest1"
]

# Danh sách thành tựu
ACHIEVEMENTS = [
    {"id": "lv1", "name": "Bước vào đại ngục", "desc": "Bắt đầu chơi - Cấp 1", "level": 1},
    {"id": "lv2", "name": "Khởi động xong", "desc": "Đạt cấp 2", "level": 2},
    {"id": "lv5", "name": "Ngón tay thần tốc", "desc": "Đạt cấp 5", "level": 5},
    {"id": "lv10", "name": "Cao thủ bàn phím", "desc": "Đạt cấp 10", "level": 10},
    {"id": "lv20", "name": "Huyền thoại gõ phím", "desc": "Đạt cấp 20", "level": 20},
    {"id": "first_death", "name": "Lần đầu nếm mùi", "desc": "Thua lần đầu tiên"},
    {"id": "flawless30", "name": "Bất khả xâm phạm", "desc": "Vượt qua cấp 30 mà không mất mạng nào"},
]
ACH_BY_ID = {a["id"]: a for a in ACHIEVEMENTS}
TOAST_TIME = 4.0

# Nút & khung trên menu / màn hình thêm từ
ADD_BTN = pygame.Rect((W - 630) // 2, 1190, 520, 90)       # nút "Thêm từ mới"
HELP_BTN = pygame.Rect(ADD_BTN.right + 20, 1190, 90, 90)    # ô "?" kế bên
BACK_BTN = pygame.Rect(60, H - 140, 380, 80)                # nút quay lại ở màn hình thêm từ
ADD_BOX = pygame.Rect((W - 1400) // 2, 520, 1400, 110)     # ô nhập từ mới

# Nội dung ô "?" - lưu ý cách gõ từ trong file text
HELP_TITLE = f"CÁCH GÕ TỪ TRONG FILE {WORDS_FILE}"
HELP_LINES = [
    "• Mỗi dòng là MỘT từ hoặc MỘT cụm từ (được phép có dấu cách).",
    "• Gõ tiếng Việt có dấu và lưu file ở định dạng UTF-8.",
    "• Dòng bắt đầu bằng # là ghi chú, game sẽ bỏ qua.",
    f"• Tối đa {MAX_INPUT_LEN} ký tự mỗi dòng, không phân biệt chữ hoa/thường.",
    "• Từ trùng nhau chỉ được tính một lần.",
    "• Sửa xong hãy lưu file, từ mới tự nạp lại ở ván kế tiếp.",
]
HELP_EXAMPLE = ["# Các từ về gia đình", "xin chào", "học một biết mười"]


# ----------------------------------------------------------------------------
# TIỆN ÍCH
# ----------------------------------------------------------------------------
def norm(s: str) -> str:
    """Chuẩn hoá Unicode (NFC) + chữ thường để so sánh tiếng Việt chính xác."""
    return unicodedata.normalize("NFC", s).strip().lower()


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Tìm font có hỗ trợ tiếng Việt. Có thể đặt file 'font.ttf' cạnh file này để ép dùng."""
    local = os.path.join(BASE_DIR, "font.ttf")
    if os.path.exists(local):
        return pygame.font.Font(local, size)
    for name in ("segoeui", "arial", "tahoma", "calibri", "dejavusans",
                 "notosans", "liberationsans", "freesans", "ubuntu"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)  # dự phòng (có thể thiếu dấu tiếng Việt)


def fade(color, t: float):
    """Pha màu `color` với màu nền: t=1 giữ nguyên, t=0 hoà vào nền."""
    t = max(0.0, min(1.0, t))
    return tuple(int(b + (c - b) * t) for b, c in zip(BG, color))


def rainbow_color():
    h = random.random()
    r, g, b = colorsys.hsv_to_rgb(h, random.uniform(0.6, 0.9), 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def fire_color():
    return random.choice([(255, 90, 60), (255, 140, 40), (255, 200, 70), (240, 60, 80)])


def lighten(color, amount=0.55):
    return tuple(int(c + (255 - c) * amount) for c in color)


# ----------------------------------------------------------------------------
# TỪ VỰNG TỪ FILE
# ----------------------------------------------------------------------------
def load_words() -> list:
    """Đọc words.txt (mỗi dòng 1 từ/cụm từ). Tự tạo file mẫu nếu chưa có."""
    path = os.path.join(BASE_DIR, WORDS_FILE)
    words = []
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Mỗi dòng là 1 từ hoặc cụm từ. Dòng bắt đầu bằng # là ghi chú.\n")
                f.write("# Lưu file ở định dạng UTF-8. Thêm/sửa từ rồi bắt đầu ván mới là có hiệu lực.\n")
                for w in DEFAULT_WORDS:
                    f.write(w + "\n")
        except OSError:
            pass
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                line = unicodedata.normalize("NFC", line)
                if len(line) > MAX_INPUT_LEN:
                    print(f"[words] Bỏ qua (dài quá {MAX_INPUT_LEN} ký tự): {line}")
                    continue
                words.append(line)
    except OSError:
        pass
    # bỏ trùng, giữ thứ tự
    seen, unique = set(), []
    for w in words:
        k = norm(w)
        if k not in seen:
            seen.add(k)
            unique.append(w)
    return unique or DEFAULT_WORDS[:]


def add_word_to_file(raw: str):
    """Thêm 1 từ vào cuối words.txt. Trả về (thành công, thông báo, từ đã chuẩn hoá)."""
    word = unicodedata.normalize("NFC", " ".join(raw.split()))
    if not word:
        return False, "Hãy gõ một từ trước khi nhấn ENTER", word
    if word.startswith("#"):
        return False, "Từ không được bắt đầu bằng dấu #", word
    if len(word) > MAX_INPUT_LEN:
        return False, f"Quá dài (tối đa {MAX_INPUT_LEN} ký tự)", word
    existing = {norm(w) for w in load_words()}      # đồng thời tạo file mẫu nếu chưa có
    if norm(word) in existing:
        return False, f"Từ đã có trong danh sách: {word}", word
    path = os.path.join(BASE_DIR, WORDS_FILE)
    try:
        needs_newline = False
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, "rb") as f:
                f.seek(-1, os.SEEK_END)
                needs_newline = f.read(1) not in (b"\n", b"\r")
        with open(path, "a", encoding="utf-8") as f:
            if needs_newline:
                f.write("\n")
            f.write(word + "\n")
    except OSError:
        return False, f"Không ghi được vào {WORDS_FILE}", word
    return True, f"Đã thêm: {word}", word


# ----------------------------------------------------------------------------
# LƯU THÀNH TỰU
# ----------------------------------------------------------------------------
def load_unlocked() -> set:
    try:
        with open(os.path.join(BASE_DIR, SAVE_FILE), "r", encoding="utf-8") as f:
            data = json.load(f)
        return {i for i in data.get("unlocked", []) if i in ACH_BY_ID}
    except (OSError, ValueError, AttributeError):
        return set()


def save_unlocked(unlocked: set):
    try:
        with open(os.path.join(BASE_DIR, SAVE_FILE), "w", encoding="utf-8") as f:
            json.dump({"unlocked": sorted(unlocked)}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ----------------------------------------------------------------------------
# ÂM THANH (tự tổng hợp, không cần file ngoài)
# ----------------------------------------------------------------------------
class SoundBank:
    def __init__(self):
        self.enabled = False
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 1, 512)
            self.freq, fmt, self.ch = pygame.mixer.get_init()
            if fmt != -16:
                raise RuntimeError("định dạng âm thanh không hỗ trợ")
            pygame.mixer.set_num_channels(32)
            self.enabled = True
        except Exception as ex:  # không có thiết bị âm thanh -> chơi im lặng
            print("[sound] Tắt âm thanh:", ex)
            return
        self._build()

    # --- các khối dựng sóng ---
    def _wave(self, freq, dur, vol=0.5, decay=6.0, freq_end=None, shape="sine"):
        n = int(self.freq * dur)
        out, phase = [], 0.0
        attack = max(1, int(0.004 * self.freq))
        for i in range(n):
            t = i / n
            f = freq if freq_end is None else freq + (freq_end - freq) * t
            phase += math.tau * f / self.freq
            s = math.sin(phase)
            if shape == "square":
                s = 0.6 if s >= 0 else -0.6
            out.append(s * math.exp(-decay * t) * min(1.0, i / attack) * vol)
        return out

    def _noise(self, dur, vol=0.4, decay=8.0):
        n = int(self.freq * dur)
        return [random.uniform(-1, 1) * math.exp(-decay * i / n) * vol for i in range(n)]

    def _mix(self, parts):
        length = max(int(off * self.freq) + len(s) for off, s in parts)
        buf = [0.0] * length
        for off, s in parts:
            o = int(off * self.freq)
            for i, v in enumerate(s):
                buf[o + i] += v
        return buf

    def _to_sound(self, samples, volume=1.0):
        data = array.array("h")
        for v in samples:
            iv = int(max(-1.0, min(1.0, v)) * 32767)
            for _ in range(self.ch):
                data.append(iv)
        snd = pygame.mixer.Sound(buffer=data.tobytes())
        snd.set_volume(volume)
        return snd

    def _external(self, name):
        for ext in (".wav", ".ogg"):
            path = os.path.join(BASE_DIR, SOUND_DIR, name + ext)
            if os.path.exists(path):
                try:
                    return pygame.mixer.Sound(path)
                except pygame.error:
                    pass
        return None

    # --- tạo toàn bộ hiệu ứng ---
    def _build(self):
        w, nz, mix = self._wave, self._noise, self._mix
        builders = {
            # gõ phím: 3 biến thể cao độ khác nhau cho đỡ nhàm
            "type": [lambda p=p: mix([(0, w(p, 0.05, 0.35, 8)), (0, nz(0.015, 0.25, 10))])
                     for p in (720, 800, 900)],
            "back": [lambda: mix([(0, w(430, 0.05, 0.3, 8)), (0, nz(0.012, 0.15, 10))])],
            "wrong": [lambda: w(170, 0.22, 0.45, 4, freq_end=105, shape="square")],
            # phá chữ thành công: tiếng nổ + tiếng lấp lánh
            "destroy": [lambda: mix([
                (0, w(260, 0.40, 0.65, 5, freq_end=45)),
                (0, nz(0.30, 0.45, 7)),
                (0.02, w(988, 0.18, 0.22, 6)),
                (0.07, w(1319, 0.18, 0.22, 6)),
                (0.12, w(1760, 0.22, 0.22, 6)),
            ])],
            "lose": [lambda: mix([(0, w(130, 0.45, 0.7, 4, freq_end=40)), (0, nz(0.3, 0.4, 6))])],
            "levelup": [lambda: mix([(i * 0.09, w(f, 0.18, 0.35, 5))
                                     for i, f in enumerate((523, 659, 784, 1047))])],
            "achievement": [lambda: mix([
                (0.00, w(784, 0.45, 0.30, 3)), (0.00, w(1568, 0.45, 0.10, 3)),
                (0.14, w(1175, 0.55, 0.30, 3)), (0.14, w(2350, 0.55, 0.10, 3)),
                (0.28, w(1568, 0.80, 0.30, 2.5)), (0.28, w(3136, 0.80, 0.10, 2.5)),
            ])],
        }
        for name, makers in builders.items():
            ext = self._external(name)
            if ext:
                self.sounds[name] = [ext]
            else:
                self.sounds[name] = [self._to_sound(m(), 0.8) for m in makers]

    def play(self, name):
        if self.enabled and name in self.sounds:
            random.choice(self.sounds[name]).play()


# ----------------------------------------------------------------------------
# HIỆU ỨNG NỔ
# ----------------------------------------------------------------------------
class Particle:
    """Một quả cầu nhỏ bắn ra khi chữ bị phá."""
    __slots__ = ("x", "y", "vx", "vy", "radius", "color", "shine", "life", "max_life")

    def __init__(self, x, y, color):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(250, 1000) * random.choice((0.5, 1.0, 1.0))
        self.x, self.y = x, y
        self.vx = math.cos(ang) * spd
        self.vy = math.sin(ang) * spd - 160
        self.radius = random.uniform(6, 19)
        self.color = color
        self.shine = lighten(color)
        self.life = self.max_life = random.uniform(0.7, 1.4)

    def update(self, dt):
        self.vy += 900 * dt                 # trọng lực
        k = max(0.0, 1.0 - 1.8 * dt)        # lực cản
        self.vx *= k
        self.vy *= k
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

    def draw(self, surf):
        t = max(0.0, self.life / self.max_life)
        r = max(1, int(self.radius * (0.3 + 0.7 * t)))
        pos = (int(self.x), int(self.y))
        pygame.draw.circle(surf, fade(self.color, t ** 0.6), pos, r)
        if r > 4:  # đốm sáng tạo cảm giác hình cầu
            pygame.draw.circle(surf, fade(self.shine, t ** 0.6),
                               (pos[0] - int(r * 0.3), pos[1] - int(r * 0.3)), max(1, r // 3))


class Ring:
    """Vòng sóng xung kích lan ra từ tâm vụ nổ."""

    def __init__(self, x, y, color):
        self.x, self.y, self.color = x, y, color
        self.life = self.max_life = 0.5
        self.max_r = 230

    def update(self, dt):
        self.life -= dt

    def draw(self, surf):
        t = max(0.0, self.life / self.max_life)
        r = int(30 + (1 - t) * self.max_r)
        pygame.draw.circle(surf, fade(self.color, t), (int(self.x), int(self.y)), r, max(1, int(10 * t)))


# ----------------------------------------------------------------------------
# ĐỐI TƯỢNG TỪ RƠI
# ----------------------------------------------------------------------------
class FallingWord:
    def __init__(self, text: str, x: float, speed: float, font: pygame.font.Font):
        self.text = unicodedata.normalize("NFC", text)
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
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Typing Game Tiếng Việt")
        # SCALED: giữ độ phân giải logic 2560x1440 và tự co giãn theo màn hình thật
        flags = pygame.FULLSCREEN | pygame.SCALED
        self.screen = pygame.display.set_mode((W, H), flags)
        self.clock = pygame.time.Clock()

        self.font_word = load_font(54)
        self.font_input = load_font(58)
        self.font_hud = load_font(42)
        self.font_small = load_font(32)
        self.font_big = load_font(130, bold=True)
        self.font_mid = load_font(56)

        # Bộ gõ (IME) chỉ được bật ở màn hình cần nhập chữ (đang chơi / thêm từ). Ở menu, tạm dừng,
        # kết thúc, thành tựu thì tắt để phím tắt (A, T, ...) nhận đúng khi đang dùng bàn phím tiếng Việt.
        self._ti_on = True        # pygame mặc định bật sẵn
        self._ti_state = None

        self.sounds = SoundBank()
        self.word_list = load_words()
        self.unlocked = load_unlocked()
        self.toast_queue = []
        self.toast_current = None
        self.toast_timer = 0.0

        # màn hình thêm từ + ô "?"
        self.help_open = False
        self.add_text = ""
        self.add_composing = ""
        self.add_msg = ""
        self.add_msg_ok = True
        self.added_recent = []

        self.state = "menu"   # menu | play | pause | over | achievements | addword
        self.prev_state = "menu"
        self.reset()
        self.sync_text_input()

    # ---- trạng thái ----
    def reset(self):
        self.words: list[FallingWord] = []
        self.particles: list[Particle] = []
        self.rings: list[Ring] = []
        self.text = ""          # chữ đã nhập
        self.composing = ""     # chữ đang ghép của bộ gõ (IME)
        self.score = 0
        self.lives = START_LIVES
        self.hearts_lost = 0
        self.level = 1
        self.solved = 0
        self.spawn_timer = 1.0
        self.flash = 0.0        # hiệu ứng nhập sai
        self.combo = 0
        self.best_combo = 0

    def start_game(self):
        self.reset()
        self.word_list = load_words()      # nạp lại words.txt mỗi ván mới
        self.help_open = False
        self.state = "play"
        self.check_level_achievements()

    def speed(self) -> float:
        return BASE_SPEED + (self.level - 1) * SPEED_PER_LEVEL

    def spawn_interval(self) -> float:
        return max(MIN_SPAWN, BASE_SPAWN - (self.level - 1) * 0.18)

    # ---- thành tựu ----
    def unlock(self, aid: str):
        if aid in self.unlocked or aid not in ACH_BY_ID:
            return
        self.unlocked.add(aid)
        save_unlocked(self.unlocked)
        self.toast_queue.append(aid)

    def check_level_achievements(self):
        for a in ACHIEVEMENTS:
            lv = a.get("level")
            if lv and self.level >= lv:
                self.unlock(a["id"])
        # vượt qua cấp 30 (tức là lên cấp 31) mà chưa mất mạng nào
        if self.level > 30 and self.hearts_lost == 0:
            self.unlock("flawless30")

    def update_toast(self, dt: float):
        if self.toast_current is None and self.toast_queue:
            self.toast_current = self.toast_queue.pop(0)
            self.toast_timer = TOAST_TIME
            self.sounds.play("achievement")
        if self.toast_current is not None:
            self.toast_timer -= dt
            if self.toast_timer <= 0:
                self.toast_current = None

    # ---- hiệu ứng nổ ----
    def explode(self, word: FallingWord, red: bool = False):
        cx, cy = word.rect.center
        count = min(90, 30 + len(word.text) * 5)
        if red:
            count //= 2
        for _ in range(count):
            x = random.uniform(word.x, word.x + word.w)
            y = random.uniform(word.y, word.y + word.h)
            self.particles.append(Particle(x, y, fire_color() if red else rainbow_color()))
        self.rings.append(Ring(cx, cy, RED if red else YELLOW))
        if len(self.particles) > 900:
            del self.particles[:len(self.particles) - 900]

    def update_fx(self, dt: float):
        for p in self.particles:
            p.update(dt)
        for r in self.rings:
            r.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        self.rings = [r for r in self.rings if r.life > 0]

    # ---- sinh từ ----
    def spawn_word(self):
        on_screen = {w.key for w in self.words}
        pool = [t for t in self.word_list if norm(t) not in on_screen] or self.word_list
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
            self.explode(target)
            self.sounds.play("destroy")
            self.combo += 1
            self.best_combo = max(self.best_combo, self.combo)
            self.score += len(target.key) * 10 + (self.combo - 1) * 5
            self.solved += 1
            if self.solved % WORDS_PER_LEVEL == 0:
                self.level += 1
                self.sounds.play("levelup")
                self.check_level_achievements()
        else:
            self.combo = 0
            self.flash = 0.35
            self.sounds.play("wrong")

    def handle_event(self, e: pygame.event.Event):
        if e.type == pygame.QUIT:
            self.quit()

        # --- bảng thành tựu ---
        if self.state == "achievements":
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN,
                                                      pygame.K_KP_ENTER, pygame.K_a):
                self.state = self.prev_state
            return

        # --- màn hình thêm từ ---
        if self.state == "addword":
            self.handle_addword_event(e)
            return

        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.state == "menu" and self.help_open:
                self.help_open = False      # ESC đầu tiên chỉ đóng bảng hướng dẫn
                return
            self.quit()

        # --- menu / game over ---
        if self.state in ("menu", "over"):
            if self.state == "menu":
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if ADD_BTN.collidepoint(e.pos):
                        self.open_add_screen()
                        return
                    elif HELP_BTN.collidepoint(e.pos):
                        self.help_open = not self.help_open
                    else:
                        self.help_open = False
                elif e.type == pygame.KEYUP and e.key == pygame.K_t:
                    # dùng KEYUP để chữ "t" vừa bấm không lọt vào ô nhập của màn hình thêm từ
                    self.open_add_screen()
                    return
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F1:
                    self.help_open = not self.help_open
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.start_game()
                elif e.key == pygame.K_a:
                    self.prev_state = self.state
                    self.state = "achievements"
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
                if not self.composing and self.text:
                    self.text = self.text[:-1]
                    self.sounds.play("back")
            elif e.key == pygame.K_TAB:
                self.state = "pause"
        elif e.type == pygame.TEXTEDITING:
            self.composing = e.text          # chữ IME đang ghép (chưa chốt)
            if e.text:
                self.sounds.play("type")
        elif e.type == pygame.TEXTINPUT:
            self.composing = ""
            if len(self.text) < MAX_INPUT_LEN:
                self.text = unicodedata.normalize("NFC", self.text + e.text)
                self.sounds.play("type")

    # ---- bật/tắt bộ gõ theo màn hình ----
    def sync_text_input(self):
        """Bật IME khi đang chơi / thêm từ; tắt ở mọi màn hình còn lại.

        Khi IME của bàn phím tiếng Việt (Telex/VNI) đang bật, phím bấm bị IME giữ lại và game không
        nhận được KEYDOWN của phím A, T... Tắt text input ở menu giúp phím tắt hoạt động bình thường.
        """
        want = self.state in ("play", "addword")
        if want:
            if not self._ti_on:
                pygame.key.start_text_input()
                self._ti_on = True
            if self._ti_state != self.state:   # đổi màn hình -> chuyển khung gợi ý IME về đúng ô nhập
                pygame.key.set_text_input_rect(ADD_BOX if self.state == "addword" else BOX_RECT)
        elif self._ti_on:
            pygame.key.stop_text_input()
            self._ti_on = False
            self.composing = ""
            self.add_composing = ""
        self._ti_state = self.state

    # ---- màn hình thêm từ ----
    def open_add_screen(self):
        self.help_open = False
        self.add_text = ""
        self.add_composing = ""
        self.add_msg = ""
        self.state = "addword"

    def close_add_screen(self):
        self.add_composing = ""
        self.state = "menu"

    def submit_new_word(self):
        ok, msg, word = add_word_to_file(self.add_text)
        self.add_msg, self.add_msg_ok = msg, ok
        if ok:
            self.add_text = ""
            self.word_list = load_words()
            self.added_recent.insert(0, word)
            del self.added_recent[8:]
            self.sounds.play("levelup")
        else:
            self.sounds.play("wrong")

    def handle_addword_event(self, e: pygame.event.Event):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.close_add_screen()
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.submit_new_word()
            elif e.key == pygame.K_BACKSPACE:
                if not self.add_composing and self.add_text:
                    self.add_text = self.add_text[:-1]
                    self.sounds.play("back")
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if BACK_BTN.collidepoint(e.pos):
                self.close_add_screen()
        elif e.type == pygame.TEXTEDITING:
            self.add_composing = e.text
            if e.text:
                self.sounds.play("type")
        elif e.type == pygame.TEXTINPUT:
            self.add_composing = ""
            if len(self.add_text) < MAX_INPUT_LEN:
                self.add_text = unicodedata.normalize("NFC", self.add_text + e.text)
                self.sounds.play("type")

    # ---- cập nhật ----
    def update(self, dt: float):
        self.update_toast(dt)
        if self.state in ("play", "over"):
            self.update_fx(dt)
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
                self.explode(w, red=True)
                self.sounds.play("lose")
                self.lives -= 1
                self.hearts_lost += 1
                self.combo = 0
                self.flash = 0.35
                if self.lives <= 0:
                    self.state = "over"
                    self.unlock("first_death")

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
        self.draw_text_box(BOX_RECT, self.text, self.composing,
                           RED if self.flash > 0 else GREEN, "Gõ từ rồi nhấn ENTER...")

    def draw_text_box(self, rect, text, composing, border, placeholder):
        pygame.draw.rect(self.screen, BOX_BG, rect, border_radius=20)
        pygame.draw.rect(self.screen, border, rect, 4, border_radius=20)

        surf = self.font_input.render(text, True, WHITE)
        x = rect.x + 30
        y = rect.centery - surf.get_height() // 2
        self.screen.blit(surf, (x, y))
        cx = x + surf.get_width()

        if composing:  # chữ IME đang ghép: gạch chân
            comp = self.font_input.render(composing, True, YELLOW)
            self.screen.blit(comp, (cx, y))
            pygame.draw.line(self.screen, YELLOW, (cx, y + comp.get_height()),
                             (cx + comp.get_width(), y + comp.get_height()), 3)
            cx += comp.get_width()

        if (pygame.time.get_ticks() // 500) % 2 == 0:   # con trỏ nhấp nháy
            pygame.draw.line(self.screen, WHITE, (cx + 4, y + 4), (cx + 4, y + surf.get_height() - 4), 3)

        if not text and not composing:
            ph = self.font_hud.render(placeholder, True, GRAY)
            self.screen.blit(ph, (x, rect.centery - ph.get_height() // 2))

    def draw_fx(self):
        for r in self.rings:
            r.draw(self.screen)
        for p in self.particles:
            p.draw(self.screen)

    def draw_toast(self):
        if self.toast_current is None:
            return
        a = ACH_BY_ID[self.toast_current]
        elapsed = TOAST_TIME - self.toast_timer
        # trượt xuống khi xuất hiện, trượt lên khi biến mất
        p = min(1.0, elapsed / 0.4, self.toast_timer / 0.4)
        p = max(0.0, p)
        p = 1 - (1 - p) ** 3
        pw, ph = 1000, 170
        x = (W - pw) // 2
        y = int(-ph + p * (ph + 110))
        rect = pygame.Rect(x, y, pw, ph)
        pygame.draw.rect(self.screen, (40, 34, 12), rect, border_radius=22)
        pygame.draw.rect(self.screen, YELLOW, rect, 4, border_radius=22)
        # huy hiệu hình tròn có ngôi sao
        cx, cy = x + 85, y + ph // 2
        pygame.draw.circle(self.screen, YELLOW, (cx, cy), 46)
        star = []
        for i in range(10):
            r = 34 if i % 2 == 0 else 15
            ang = -math.pi / 2 + i * math.pi / 5
            star.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        pygame.draw.polygon(self.screen, (40, 34, 12), star)
        self.screen.blit(self.font_small.render("THÀNH TỰU MỞ KHÓA!", True, YELLOW), (x + 170, y + 10))
        self.screen.blit(self.font_hud.render(a["name"], True, WHITE), (x + 170, y + 54))
        self.screen.blit(self.font_small.render(a["desc"], True, GRAY), (x + 170, y + 114))

    def draw_achievements(self):
        total = len(ACHIEVEMENTS)
        got = sum(1 for a in ACHIEVEMENTS if a["id"] in self.unlocked)
        self.draw_text_center(self.font_big, "THÀNH TỰU", YELLOW, 60)
        self.draw_text_center(self.font_hud, f"Đã mở khóa {got}/{total}", WHITE, 230)
        pw, ph = 1500, 120
        x = (W - pw) // 2
        for i, a in enumerate(ACHIEVEMENTS):
            y = 310 + i * (ph + 18)
            ok = a["id"] in self.unlocked
            rect = pygame.Rect(x, y, pw, ph)
            pygame.draw.rect(self.screen, (34, 42, 74) if ok else (22, 27, 46), rect, border_radius=18)
            pygame.draw.rect(self.screen, YELLOW if ok else (50, 58, 86), rect, 3, border_radius=18)
            cx, cy = x + 70, y + ph // 2
            pygame.draw.circle(self.screen, YELLOW if ok else (50, 58, 86), (cx, cy), 36)
            if ok:
                pygame.draw.lines(self.screen, BG, False,
                                  [(cx - 16, cy + 2), (cx - 4, cy + 14), (cx + 18, cy - 12)], 8)
            self.screen.blit(self.font_hud.render(a["name"], True, WHITE if ok else GRAY), (x + 140, y + 8))
            self.screen.blit(self.font_small.render(a["desc"], True, YELLOW if ok else GRAY), (x + 140, y + 70))
        self.draw_text_center(self.font_hud, "Nhấn ENTER hoặc ESC để quay lại", GRAY, 1340)

    def draw_button(self, rect, label, font, hover, accent=GREEN):
        pygame.draw.rect(self.screen, (44, 56, 96) if hover else BOX_BG, rect, border_radius=20)
        pygame.draw.rect(self.screen, accent, rect, 5 if hover else 3, border_radius=20)
        s = font.render(label, True, WHITE)
        self.screen.blit(s, s.get_rect(center=rect.center))

    def draw_help_panel(self):
        """Bảng lưu ý cách gõ từ trong file text (hiện khi rê chuột/bấm vào ô ?)."""
        pw = 1200
        ph = (24 + 57 + 14 + len(HELP_LINES) * 48 + 12 + 46
              + len(HELP_EXAMPLE) * 46 + 24 + 28)
        x = (W - pw) // 2
        y = ADD_BTN.top - 20 - ph
        rect = pygame.Rect(x, y, pw, ph)
        pygame.draw.rect(self.screen, (20, 26, 48), rect, border_radius=24)
        pygame.draw.rect(self.screen, YELLOW, rect, 4, border_radius=24)

        cy = y + 24
        self.screen.blit(self.font_hud.render(HELP_TITLE, True, YELLOW), (x + 40, cy))
        cy += 57 + 14
        for line in HELP_LINES:
            self.screen.blit(self.font_small.render(line, True, WHITE), (x + 40, cy))
            cy += 48
        cy += 12
        self.screen.blit(self.font_small.render("Ví dụ nội dung file:", True, GRAY), (x + 40, cy))
        cy += 46
        box = pygame.Rect(x + 40, cy, pw - 80, len(HELP_EXAMPLE) * 46 + 24)
        pygame.draw.rect(self.screen, (10, 13, 26), box, border_radius=14)
        pygame.draw.rect(self.screen, (60, 72, 110), box, 2, border_radius=14)
        for i, line in enumerate(HELP_EXAMPLE):
            color = GRAY if line.startswith("#") else GREEN
            self.screen.blit(self.font_small.render(line, True, color), (box.x + 24, box.y + 12 + i * 46))

    def draw_addword(self):
        mouse = pygame.mouse.get_pos()
        self.draw_text_center(self.font_big, "THÊM TỪ MỚI", GREEN, 90)
        self.draw_text_center(self.font_hud, f"Hiện có {len(self.word_list)} từ trong {WORDS_FILE}", WHITE, 290)
        self.draw_text_center(self.font_small, "Gõ từ hoặc cụm từ tiếng Việt có dấu, rồi nhấn ENTER để lưu vào file.", GRAY, 370)
        self.draw_text_center(self.font_small, f"Mỗi lần ENTER thêm một dòng mới (tối đa {MAX_INPUT_LEN} ký tự, từ trùng sẽ bị bỏ qua).", GRAY, 420)
        self.draw_text_box(ADD_BOX, self.add_text, self.add_composing, GREEN,
                           "Gõ từ hoặc cụm từ mới rồi nhấn ENTER...")
        if self.add_msg:
            self.draw_text_center(self.font_hud, self.add_msg, GREEN if self.add_msg_ok else RED, ADD_BOX.bottom + 30)
        if self.added_recent:
            y = ADD_BOX.bottom + 130
            self.draw_text_center(self.font_hud, "Vừa thêm:", YELLOW, y)
            y += 70
            for w in self.added_recent:
                self.draw_text_center(self.font_small, w, WHITE, y)
                y += 46
        self.draw_button(BACK_BTN, "Quay lại (ESC)", self.font_small, BACK_BTN.collidepoint(mouse), BLUE)

    def draw(self):
        self.screen.fill(BG)

        if self.state == "menu":
            self.draw_text_center(self.font_big, "NUKE BOME GAME", GREEN, 420)
            self.draw_text_center(self.font_mid, "Gõ để phá hủy nó, chạm vạch -> OH MY PCCCCCCC", WHITE, 620)
            self.draw_text_center(self.font_mid, "Nhấn ENTER để bước vào đại ngục", YELLOW, 760)
            self.draw_text_center(self.font_hud, "Không bật gõ Tiếng Việt -> YOU'RE LOSER", GRAY, 900)
            got = sum(1 for a in ACHIEVEMENTS if a["id"] in self.unlocked)
            self.draw_text_center(self.font_hud, f"Nhấn A để xem thành tựu ({got}/{len(ACHIEVEMENTS)})", WHITE, 1010)
            self.draw_text_center(self.font_small, f"Đã nạp {len(self.word_list)} từ từ {WORDS_FILE}", GRAY, 1090)
            mouse = pygame.mouse.get_pos()
            self.draw_button(ADD_BTN, "+ Thêm từ mới  [T]", self.font_hud, ADD_BTN.collidepoint(mouse))
            hover_help = HELP_BTN.collidepoint(mouse)
            self.draw_button(HELP_BTN, "?", self.font_mid, hover_help or self.help_open, YELLOW)
            if self.help_open or hover_help:
                self.draw_help_panel()
            self.draw_toast()
            pygame.display.flip()
            return

        if self.state == "addword":
            self.draw_addword()
            self.draw_toast()
            pygame.display.flip()
            return

        if self.state == "achievements":
            self.draw_achievements()
            pygame.display.flip()
            return

        # vạch nguy hiểm
        pygame.draw.line(self.screen, RED, (0, DEAD_Y), (W, DEAD_Y), 4)

        typed_key = norm(self.text) if not self.composing else ""
        for w in self.words:
            w.draw(self.screen, typed_key)

        self.draw_fx()
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
            self.draw_fx()
            self.draw_text_center(self.font_big, "KẾT THÚC", RED, 380)
            self.draw_text_center(self.font_mid, f"Điểm: {self.score}   |   Cấp độ: {self.level}", YELLOW, 600)
            self.draw_text_center(self.font_mid, f"Từ đã gõ đúng: {self.solved}   |   Combo cao nhất: {self.best_combo}", WHITE, 690)
            self.draw_text_center(self.font_mid, "Nhấn ENTER để chơi lại", GREEN, 820)
            self.draw_text_center(self.font_hud, "Nhấn A để xem thành tựu", GRAY, 930)

        self.draw_toast()
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
            self.sync_text_input()
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()
