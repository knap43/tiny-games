#!/usr/bin/env python3
"""LITANY - a tiny dark-fantasy typing game.

Shades creep in from every side, each carrying a word: type it to banish them.
The first letter picks the nearest matching word · BACKSPACE lets go of it
ESC pause · F11 fullscreen/window (--windowed starts in a window)
"""
import array
import math
import os
import random
import sys

import pygame

W, H = 400, 225
CX, CY = W // 2, H // 2 + 6
RING = 22                      # the ritual circle: a shade that reaches it snuffs a candle
BLACK = (8, 6, 7)
BONE = (222, 210, 186)
BLOOD = (176, 22, 30)
KEY = (255, 0, 255)
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
TAU = math.tau

# ------------------------------------------------------------------ font (3x5)
FONT = {
    'A': '010101111101101', 'B': '110101110101110', 'C': '011100100100011',
    'D': '110101101101110', 'E': '111100110100111', 'F': '111100110100100',
    'G': '011100101101011', 'H': '101101111101101', 'I': '111010010010111',
    'J': '001001001101010', 'K': '101101110101101', 'L': '100100100100111',
    'M': '101111111101101', 'N': '110101101101101', 'O': '010101101101010',
    'P': '110101110100100', 'Q': '010101101110011', 'R': '110101110101101',
    'S': '011100010001110', 'T': '111010010010010', 'U': '101101101101111',
    'V': '101101101101010', 'W': '101101101111101', 'X': '101101010101101',
    'Y': '101101010010010', 'Z': '111001010100111', '0': '111101101101111',
    '1': '010110010010111', '2': '110001010100111', '3': '110001010001110',
    '4': '101101111001001', '5': '111100110001110', '6': '011100111101111',
    '7': '111001010010010', '8': '111101111101111', '9': '111101111001110',
    '.': '000000000000010', ',': '000000000010100', ':': '000010000010000',
    '/': '001001010100100', '-': '000000111000000', '+': '000010111010000',
    '%': '101001010100101', '!': '010010010000010', '?': '110001010000010',
    '[': '110100100100110', ']': '011001001001011', "'": '010010000000000',
    '>': '100010001010100', '<': '001010100010001', ' ': '000000000000000',
}
_tcache = {}


def text_surf(s, scale=1, color=BONE):
    key = (s, scale, color)
    surf = _tcache.get(key)
    if surf is None:
        if len(_tcache) > 3000:
            _tcache.clear()
        s2 = s.upper()
        w = max(1, len(s2) * 4 - 1)
        surf = pygame.Surface((w, 5), pygame.SRCALPHA)
        for i, ch in enumerate(s2):
            for j, c in enumerate(FONT.get(ch, FONT['?'])):
                if c == '1':
                    surf.set_at((i * 4 + j % 3, j // 3), color)
        if scale > 1:
            surf = pygame.transform.scale(surf, (w * scale, 5 * scale))
        _tcache[key] = surf
    return surf


def draw_text(dst, s, x, y, scale=1, align='l', color=BONE, outline=True):
    t = text_surf(s, scale, color)
    if align == 'c':
        x -= t.get_width() // 2
    elif align == 'r':
        x -= t.get_width()
    if outline:
        o = text_surf(s, scale, BLACK)
        for dx, dy in DIRS:
            dst.blit(o, (x + dx, y + dy))
    dst.blit(t, (x, y))


# ------------------------------------------------------------------ sound
class Sfx:
    SPECS = {  # dur, f0, f1, noise, vol, wave
        'key': (0.035, 900, 700, 0.3, 0.07, 'sq'),
        'miss': (0.06, 140, 110, 0.2, 0.08, 'sq'),
        'banish': (0.25, 600, 120, 0.5, 0.16, 'sq'),
        'hurt': (0.5, 200, 40, 0.6, 0.35, 'sq'),
        'toll': (1.2, 110, 108, 0.0, 0.3, 'sin'),
        'ward': (0.6, 900, 80, 0.3, 0.25, 'sq'),
        'elder': (1.0, 70, 50, 0.5, 0.25, 'sq'),
        'lock': (0.05, 1200, 1500, 0.0, 0.05, 'sin'),
        'candle': (0.4, 300, 800, 0.0, 0.12, 'sin'),
    }

    def __init__(self):
        self.ok = False
        self.s = {}
        try:
            pygame.mixer.init(22050, -16, 1, 512)
            freq, _, ch = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(16)
        except Exception:
            return
        for name, spec in self.SPECS.items():
            self.s[name] = self.make(freq, ch, *spec)
        self.ok = True

    @staticmethod
    def make(sr, ch, dur, f0, f1, noise, vol, wave):
        n = int(sr * dur)
        buf = array.array('h')
        ph = 0.0
        rnd = random.random
        for i in range(n):
            t = i / n
            ph += (f0 + (f1 - f0) * t) / sr
            v = (1.0 if (ph % 1.0) < 0.5 else -1.0) if wave == 'sq' else math.sin(ph * TAU)
            if noise:
                v = v * (1 - noise) + (rnd() * 2 - 1) * noise
            s = int(v * (1 - t) ** 2 * vol * 32767)
            for _ in range(ch):
                buf.append(s)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        if self.ok:
            self.s[name].play()


# ------------------------------------------------------------------ words
WORDS = sorted(set("""
ash bone rot hex owl yew oak ink urn vow sin dusk moth crow wolf mist fog veil gate tomb dirt
worm salt iron gold rust rune oath fang claw horn wing bell hymn pyre soot wax wick lamp moon
star void dead dread doom fear fell grim gore hush keen knell lich lore maw mire murk night
pale pall pray reap rift ruin rite sage seer shade shrine shroud skull smoke snake spell spire
stain still stone storm sword thorn throne tithe toll tower vigil voice wail waste weep whisper
wight witch wraith wyrm altar amber angel ashen beast black blade blood bloom brand briar
candle carrion cellar chain chalice chapel charm choir cinder cloak coffin corpse coven crypt
curse dagger demon devil ember exile famine feast fever flesh forge frost ghost ghoul glyph
grave grief haunt heart heresy hollow hunger idol jackal kneel lantern leech maggot marrow
martyr mercy mortal mourn nettle omen orphan ossuary pagan penance phantom plague poison prayer
prophet psalm raven relic rosary sabbath sacred saint scythe serpent shadow shepherd silence
sorrow specter spider spirit tallow tempest torment torch unholy vampire venom vessel vulture
warden widow willow winter wither wormwood zealot abyss acolyte apostle banshee basilisk
belfry bishop bramble brimstone catacomb cathedral cauldron censer chimera cloister conjure
covenant crucible darkness deathbed devour eclipse effigy eldritch embalm enchant eternal
exorcism forsaken funeral gallows gargoyle gloaming graveyard grimoire harbinger hellfire
heretic hexagram incense infernal midnight miserere monastery moonlight nightfall nightmare
oblivion obsidian penitent pestilence pilgrim purgatory reliquary requiem revenant sacrament
sacrifice sanctuary scripture seraphim sepulcher sorcerer spectral starless sunless twilight
underworld unhallowed vespers wanderer wasteland witchcraft quill quiet query quench quarry
quiver jinx joust jester jewel judge yearn yoke young yonder zephyr zenith xylem axe vex
bog cog dim elk fen gnaw hag imp jaw kin lye nag ode pyx rue sty tar vat wan
""".split()))
LONG = ['lamentation', 'malediction', 'necromancer', 'excommunicate', 'resurrection',
        'abomination', 'desecration', 'inquisition', 'damnation', 'everlasting',
        'sepulchral', 'transfiguration', 'benediction', 'incantation', 'hallowed ground',
        'unconsecrated', 'phantasmagoria', 'thaumaturgy', 'apparition', 'flagellant']


# ------------------------------------------------------------------ graphics
def make_figure():
    """The kneeling, hooded reciter."""
    s = pygame.Surface((13, 15), pygame.SRCALPHA)
    pygame.draw.polygon(s, BONE, [(6, 0), (10, 4), (12, 14), (0, 14), (2, 4)])
    pygame.draw.ellipse(s, BLACK, (4, 2, 5, 5))
    s.set_at((5, 4), BLOOD)
    s.set_at((7, 4), BLOOD)
    s.fill(BLACK, (6, 8, 1, 6))
    s.fill(BLOOD, (4, 9, 5, 2))             # the open book
    s.fill(BONE, (6, 9, 1, 2))
    return s


def make_shades():
    frames = []
    for f in range(4):
        s = pygame.Surface((11, 13), pygame.SRCALPHA)
        pygame.draw.circle(s, BONE, (5, 4), 4, 1)
        tail = [(1, 5), (1, 9), (3, 12 - f % 2), (5, 9 + f % 2), (7, 12 - (f + 1) % 2),
                (9, 9), (9, 5)]
        pygame.draw.lines(s, BONE, False, tail)
        frames.append(s)
    big = []
    for f in frames:
        b = pygame.transform.scale(f, (22, 26))
        big.append(b)
    return frames, big


# ------------------------------------------------------------------ game
class Shade:
    def __init__(self, word, x, y, frames, kind='shade'):
        self.word, self.x, self.y, self.kind = word, x, y, kind
        self.typed = 0
        self.spd = (math.hypot(x - CX, y - CY) - RING) / frames
        self.t = random.randint(0, 99)
        self.kb = 0.0
        self.flash = 0
        self.dead = False
        self.r = 10 if kind == 'elder' else 5


class Game:
    def __init__(self):
        pygame.init()
        flags = pygame.SCALED
        if '--windowed' not in sys.argv:
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode((W, H), flags)
        except pygame.error:  # no fullscreen available: fall back to a window
            self.screen = pygame.display.set_mode((W, H), pygame.SCALED)
        pygame.display.set_caption('LITANY')
        pygame.mouse.set_visible(False)
        pygame.key.set_repeat()
        self.clock = pygame.time.Clock()
        self.sfx = Sfx()
        self.figure = make_figure()
        self.shade_img, self.elder_img = make_shades()
        self.dim = pygame.Surface((W, H))
        self.dim.fill(KEY)
        self.dim.set_colorkey(KEY)
        for y in range(0, H, 2):
            for x in range(0, W, 2):
                self.dim.set_at((x, y), BLACK)
                self.dim.set_at((x + 1, y + 1), BLACK)
        self.specks = [(random.randrange(W), random.randrange(H)) for _ in range(70)]
        self.best_file = os.path.join(os.environ.get('XDG_DATA_HOME') or
                                      os.path.expanduser('~/.local/share'), 'litany', 'best')
        self.best = 0
        try:
            with open(self.best_file) as f:
                self.best = int(f.read().strip() or 0)
        except (OSError, ValueError):
            pass
        self.state = 'title'
        self.t = 0
        self.new_run()
        self.state = 'title'

    def new_run(self):
        self.state = 'play'
        self.shades, self.sparks, self.particles, self.rings, self.texts = [], [], [], [], []
        self.target = None
        self.wave = 0
        self.queue = []
        self.spawn_t = 0
        self.candles = 3
        self.score = self.combo = self.best_combo = 0
        self.keys = self.correct = 0
        self.play_frames = 0
        self.shake = 0.0
        self.banner, self.banner_t = '', 0
        self.wave_gap = 0
        self.dead_t = 0
        self.next_wave()

    # ---------------------------------------------------------- waves
    def next_wave(self):
        self.wave += 1
        w = self.wave
        lo = min(7, 3 + w // 4)
        hi = min(12, 4 + w // 2)
        n = 5 + w * 2
        self.queue = [('shade', (lo, hi)) for _ in range(n)]
        if w >= 2:
            for _ in range(1 + (w >= 8)):
                self.queue.insert(random.randrange(len(self.queue)), ('ward', (4, 7)))
        if w % 5 == 0:
            self.queue.insert(len(self.queue) // 2, ('elder', None))
            self.banner = 'AN ELDER SHADE COMES'
            self.sfx.play('elder')
        else:
            self.banner = f'WAVE {w}'
            self.sfx.play('toll')
        self.banner_t = 120
        self.spawn_t = 90

    def pick_word(self, lo, hi):
        used = {s.word[0] for s in self.shades if not s.dead}
        on = {s.word for s in self.shades}
        pool = [x for x in WORDS if lo <= len(x) <= hi and x not in on]
        fresh = [x for x in pool if x[0] not in used]
        return random.choice(fresh or pool)

    def spawn(self, kind, rng):
        w = self.wave
        if kind == 'elder':
            used = {s.word[0] for s in self.shades if not s.dead}
            choices = [x for x in LONG if x[0] not in used] or LONG
            word = random.choice(choices)
        else:
            word = self.pick_word(*rng)
        a = random.uniform(0, TAU)
        x = CX + math.cos(a) * (W / 2 + 10)
        y = CY + math.sin(a) * (H / 2 + 10)
        # travel time: shorter each wave, longer for longer words
        frames = max(360, 1250 - w * 65) + 35 * max(0, len(word) - 4)
        if kind == 'elder':
            frames *= 1.6
        self.shades.append(Shade(word, x, y, frames, kind))

    # ---------------------------------------------------------- typing
    def type_char(self, ch):
        self.keys += 1
        tgt = self.target
        if tgt is None or tgt.dead:
            cands = [s for s in self.shades if not s.dead and s.word[0] == ch]
            if not cands:
                self.miss()
                return
            tgt = min(cands, key=lambda s: math.hypot(s.x - CX, s.y - CY))
            self.target = tgt
            self.sfx.play('lock')
        if tgt.word[tgt.typed] == ch:
            tgt.typed += 1
            # spaces in elder phrases are typed through automatically
            while tgt.typed < len(tgt.word) and tgt.word[tgt.typed] == ' ':
                tgt.typed += 1
            self.correct += 1
            self.combo += 1
            self.best_combo = max(self.best_combo, self.combo)
            self.score += self.mult()
            tgt.kb += 2.5 if tgt.kind != 'elder' else 1.0
            tgt.flash = 4
            self.sparks.append([CX, CY - 6, tgt, 0])
            self.sfx.play('key')
            if tgt.typed >= len(tgt.word):
                self.banish(tgt)
        else:
            self.miss()

    def mult(self):
        return 1 + min(9, self.combo // 15)

    def miss(self):
        self.combo = 0
        self.sfx.play('miss')
        self.shake = max(self.shake, 1.5)

    def banish(self, s, chain=False):
        s.dead = True
        if self.target is s:
            self.target = None
        bonus = len(s.word) * self.mult() * (5 if s.kind == 'elder' else 1)
        self.score += bonus
        self.burst(s.x, s.y, 14 if s.kind != 'elder' else 50, 2.5, 26, BONE)
        self.burst(s.x, s.y, 6, 1.5, 20, BLOOD)
        self.texts.append([s.x, s.y - 12, f'+{bonus}', 40])
        if chain:
            return
        self.sfx.play('banish')
        if s.kind == 'ward':
            self.sfx.play('ward')
            self.rings.append([0, 120])
            for o in self.shades:
                if not o.dead:
                    d = math.hypot(o.x - CX, o.y - CY)
                    if d < 120 and o.kind != 'elder':
                        self.banish(o, True)
                    else:
                        o.kb += 30
        elif s.kind == 'elder':
            self.shake = 6
            self.sfx.play('elder')

    def burst(self, x, y, n, spd, life, color):
        for _ in range(n):
            a = random.uniform(0, TAU)
            v = random.uniform(0.3, 1) * spd
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v,
                                   random.randint(life // 2, life), color])

    # ---------------------------------------------------------- update
    def update(self):
        self.t += 1
        self.play_frames += 1
        if self.queue:
            self.spawn_t -= 1
            alive = sum(1 for s in self.shades if not s.dead)
            if self.spawn_t <= 0 and alive < 4 + self.wave:
                kind, rng = self.queue.pop(0)
                self.spawn(kind, rng)
                self.spawn_t = max(40, 160 - self.wave * 10) + random.randint(-15, 15)
        elif not any(not s.dead for s in self.shades):
            self.wave_gap += 1
            if self.wave_gap > 80:
                self.wave_gap = 0
                if self.wave % 3 == 0 and self.candles < 3:
                    self.candles += 1
                    self.sfx.play('candle')
                    self.texts.append([CX, CY - 30, 'A CANDLE RELIT', 60])
                self.next_wave()
        for s in self.shades:
            if s.dead:
                continue
            s.t += 1
            if s.flash:
                s.flash -= 1
            dx, dy = CX - s.x, CY - s.y
            d = math.hypot(dx, dy) or 0.01
            ux, uy = dx / d, dy / d
            wob = math.sin(s.t * 0.05) * 0.25
            s.x += ux * s.spd - uy * wob - ux * s.kb
            s.y += uy * s.spd + ux * wob - uy * s.kb
            s.kb *= 0.8
            if d < RING + s.r:
                self.hit(s)
        self.shades = [s for s in self.shades if not s.dead]
        for sp in self.sparks:
            sp[3] += 1
        self.sparks = [sp for sp in self.sparks if sp[3] < 7]
        for q in self.particles:
            q[0] += q[2]
            q[1] += q[3]
            q[2] *= 0.92
            q[3] *= 0.92
            q[4] -= 1
        self.particles = [q for q in self.particles if q[4] > 0][-500:]
        for r in self.rings:
            r[0] += 1
        self.rings = [r for r in self.rings if r[0] < 30]
        for t in self.texts:
            t[1] -= 0.4
            t[3] -= 1
        self.texts = [t for t in self.texts if t[3] > 0]
        self.shake = max(0.0, self.shake - 0.3)
        if self.banner_t:
            self.banner_t -= 1

    def hit(self, s):
        s.dead = True
        if self.target is s:
            self.target = None
        self.candles -= 1
        self.combo = 0
        self.shake = 8
        self.sfx.play('hurt')
        self.burst(CX, CY, 30, 3, 30, BLOOD)
        for o in self.shades:          # a moment's mercy: the rest recoil
            if not o.dead and math.hypot(o.x - CX, o.y - CY) < 90:
                o.kb += 12
        if self.candles <= 0:
            self.state = 'dead'
            self.dead_t = 0
            self.sfx.play('toll')
            if self.score > self.best:
                self.best = self.score
                try:
                    os.makedirs(os.path.dirname(self.best_file), exist_ok=True)
                    with open(self.best_file, 'w') as f:
                        f.write(str(self.best))
                except OSError:
                    pass

    def wpm(self):
        mins = self.play_frames / 3600
        return int(self.correct / 5 / mins) if mins > 0.05 else 0

    def accuracy(self):
        return int(100 * self.correct / self.keys) if self.keys else 100

    # ---------------------------------------------------------- drawing
    def draw_circle(self, s, ox, oy):
        t = self.t
        cx, cy = CX + ox, CY + oy
        n = 36
        for i in range(n):                         # a slowly turning ring of runes
            a = i * TAU / n + t * 0.004
            x, y = cx + math.cos(a) * RING, cy + math.sin(a) * RING * 0.8
            if i % 3 == 0:
                s.fill(BLOOD, (int(x) - 1, int(y) - 1, 2, 2))
            else:
                s.set_at((int(x), int(y)), BONE)
        for i in range(12):
            a = -i * TAU / 12 - t * 0.006
            x, y = cx + math.cos(a) * (RING - 6), cy + math.sin(a) * (RING - 6) * 0.8
            s.set_at((int(x), int(y)), BLOOD)
        s.blit(self.figure, (cx - 6, cy - 12))
        for i in range(3):                         # candles: your remaining wards
            a = -math.pi / 2 + (i - 1) * 2.2
            x = int(cx + math.cos(a) * (RING + 2))
            y = int(cy + math.sin(a) * (RING + 2) * 0.8)
            s.fill(BONE, (x - 1, y - 2, 3, 5))
            if i < self.candles:
                fl = (t // 6 + i) % 3
                pygame.draw.polygon(s, BLOOD, [(x - 1, y - 3), (x + 2, y - 3),
                                               (x + (fl - 1) // 2, y - 7 - fl % 2)])
                s.set_at((x, y - 4), BONE)
            elif t % 40 < 30:
                s.set_at((x + (t // 10) % 2, y - 5), BONE)
                s.set_at((x, y - 7), BONE)

    def draw_word(self, s, sh, ox, oy):
        word = sh.word.upper()
        w = len(word) * 4 - 1
        x = int(sh.x + ox) - w // 2
        y = int(sh.y + oy) - (20 if sh.kind == 'elder' else 14)
        x = max(2, min(W - w - 2, x))
        y = max(2, min(H - 8, y))
        locked = sh is self.target
        rest_col = BLOOD if sh.kind == 'ward' else BONE
        if locked:
            s.fill(BLACK, (x - 3, y - 2, w + 6, 9))
            pygame.draw.rect(s, BLOOD, (x - 3, y - 2, w + 6, 9), 1)
        typed = word[:sh.typed]
        if typed:
            draw_text(s, typed, x, y, 1, 'l', BLOOD if sh.kind != 'ward' else BONE, not locked)
        draw_text(s, word[sh.typed:], x + len(typed) * 4, y, 1, 'l', rest_col, not locked)

    def draw_play(self):
        s = self.screen
        s.fill(BLACK)
        ox = oy = 0
        if self.shake > 0:
            ox = int(random.uniform(-self.shake, self.shake))
            oy = int(random.uniform(-self.shake, self.shake))
        for x, y in self.specks:
            s.set_at((x, y), BONE)
        for r in self.rings:
            rad = int(10 + r[0] * 4)
            pygame.draw.circle(s, BONE if r[0] < 4 else BLOOD, (CX + ox, CY + oy), rad, 2)
        self.draw_circle(s, ox, oy)
        for sh in self.shades:
            img = (self.elder_img if sh.kind == 'elder' else self.shade_img)[(sh.t // 10) % 4]
            x, y = int(sh.x + ox), int(sh.y + oy)
            s.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2))
            eye = BONE if sh.flash else BLOOD
            e = 2 if sh.kind == 'elder' else 1
            s.fill(eye, (x - 2 * e, y - 3 * e + (e - 1), e, e))
            s.fill(eye, (x + 1 * e, y - 3 * e + (e - 1), e, e))
            if sh.kind == 'ward' and self.t % 20 < 14:
                pygame.draw.circle(s, BLOOD, (x, y), 8, 1)
        for sp in self.sparks:
            tgt = sp[2]
            f = sp[3] / 6
            x = CX + (tgt.x - CX) * f + ox
            y = CY - 6 + (tgt.y - CY + 6) * f + oy
            x0 = CX + (tgt.x - CX) * max(0, f - 0.25) + ox
            y0 = CY - 6 + (tgt.y - CY + 6) * max(0, f - 0.25) + oy
            pygame.draw.line(s, BLOOD, (x0, y0), (x, y), 2)
            s.set_at((int(x), int(y)), BONE)
        for q in self.particles:
            s.set_at((int(q[0] + ox), int(q[1] + oy)), q[5])
        for sh in sorted(self.shades, key=lambda sh: sh is self.target):
            self.draw_word(s, sh, ox, oy)
        for x, y, txt, life in self.texts:
            if life > 10 or self.t % 2:
                draw_text(s, txt, int(x), int(y), 1, 'c', BLOOD)
        # hud
        draw_text(s, f'SCORE {self.score}', 4, 4)
        if self.mult() > 1:
            draw_text(s, f'X{self.mult()}', 4, 12, 1, 'l', BLOOD)
        draw_text(s, f'WAVE {self.wave}', W - 4, 4, 1, 'r', BLOOD)
        draw_text(s, f'{self.wpm()} WPM   {self.accuracy()}%', W - 4, H - 9, 1, 'r')
        if self.combo >= 5:
            draw_text(s, f'COMBO {self.combo}', 4, H - 9, 1, 'l', BLOOD if self.combo >= 15 else BONE)
        if self.banner_t and (self.banner_t > 20 or self.t % 2):
            draw_text(s, self.banner, W // 2, 40, 3 if len(self.banner) < 12 else 2, 'c', BLOOD)

    def draw_title(self):
        s = self.screen
        s.fill(BLACK)
        for x, y in self.specks:
            s.set_at((x, y), BONE)
        self.t += 1
        draw_text(s, 'LITANY', W // 2, 26, 6, 'c')
        draw_text(s, 'SPEAK THE WORDS. KEEP THE CANDLES LIT.', W // 2, 62, 1, 'c', BLOOD)
        lines = ['SHADES CREEP IN FROM EVERY SIDE, EACH CARRYING A WORD.',
                 'TYPE A WORD TO BANISH ITS SHADE. YOUR FIRST LETTER',
                 'PICKS THE NEAREST WORD; BACKSPACE LETS GO OF IT.',
                 'BLOOD-RED WORDS ARE WARDS: THEY BANISH ALL SHADES NEAR YOU.',
                 'A SHADE THAT REACHES THE CIRCLE SNUFFS A CANDLE.']
        for i, l in enumerate(lines):
            draw_text(s, l, W // 2, 80 + i * 9, 1, 'c')
        if (self.t // 30) % 2:
            draw_text(s, 'ENTER TO BEGIN', W // 2, 140, 2, 'c', BLOOD)
        draw_text(s, 'ESC PAUSE    F11 FULLSCREEN', W // 2, 170, 1, 'c')
        if self.best:
            draw_text(s, f'BEST {self.best}', W // 2, 195, 1, 'c')

    def draw(self):
        s = self.screen
        if self.state == 'title':
            self.draw_title()
            return
        self.draw_play()
        if self.state == 'pause':
            s.blit(self.dim, (0, 0))
            draw_text(s, 'PAUSED', W // 2, 70, 3, 'c')
            draw_text(s, 'ESC  RESUME     ENTER  GIVE UP', W // 2, 100, 1, 'c')
        elif self.state == 'dead':
            self.dead_t += 1
            s.blit(self.dim, (0, 0))
            draw_text(s, 'THE LAST CANDLE GUTTERS', W // 2, 50, 2, 'c', BLOOD)
            draw_text(s, f'SCORE {self.score}', W // 2, 75, 3, 'c')
            draw_text(s, f'WAVE {self.wave}   {self.wpm()} WPM   {self.accuracy()}% ACCURATE   '
                         f'BEST COMBO {self.best_combo}', W // 2, 102, 1, 'c')
            draw_text(s, f'BEST {self.best}', W // 2, 114, 1, 'c')
            if self.dead_t > 60:
                draw_text(s, 'ENTER TO RECITE AGAIN', W // 2, 145, 2, 'c', BLOOD)

    # ---------------------------------------------------------- input / loop
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if ev.type != pygame.KEYDOWN:
            return
        key = ev.key
        if key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
        st = self.state
        enter = key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        if st == 'title':
            if enter:
                self.new_run()
            elif key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
        elif st == 'play':
            if key == pygame.K_ESCAPE:
                self.state = 'pause'
            elif key == pygame.K_BACKSPACE:
                self.target = None
            else:
                ch = ev.unicode.lower() if ev.unicode else ''
                if len(ch) == 1 and 'a' <= ch <= 'z':
                    self.type_char(ch)
        elif st == 'pause':
            if key == pygame.K_ESCAPE:
                self.state = 'play'
            elif enter:
                self.candles = 1
                self.hit(Shade('x', CX, CY, 1))
        elif st == 'dead':
            if self.dead_t > 60 and enter:
                self.new_run()
            elif key == pygame.K_ESCAPE:
                self.state = 'title'

    def run(self):
        while True:
            for ev in pygame.event.get():
                self.handle(ev)
            if self.state == 'play':
                self.update()
            elif self.state == 'dead':
                self.t += 1
            self.draw()
            pygame.display.flip()
            self.clock.tick(60)


if __name__ == '__main__':
    Game().run()
