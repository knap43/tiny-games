#!/usr/bin/env python3
"""CENOTAPH - a tiny dark-fantasy turn-based tactical roguelike.

Moving is attacking: step between two tiles next to a foe to STAB it; step straight at a foe
two tiles away to LUNGE (spear in hand). 1 LEAP · 2 THROW SPEAR · 3 BASH (or click / right click)
WASD/arrows + Q E Z C diagonals (or numpad) move · SPACE wait · ESC pause · F11 fullscreen
"""
import array
import math
import os
import random
import sys
from collections import deque

import pygame

W, H = 400, 225
GW, GH, TS = 15, 11, 16
GX, GY = 6, 22                 # grid origin on screen
PX = GX + GW * TS + 8          # side panel
BLACK = (8, 6, 7)
BONE = (222, 210, 186)
BLOOD = (176, 22, 30)
KEY = (255, 0, 255)
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
DIR8 = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
TAU = math.tau
FLOOR, WALL, CHASM, STAIRS = 0, 1, 2, 3
LAST_DEPTH = 12

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
    '[': '110100100100110', ']': '011001001001011', '(': '010100100100010',
    ')': '010001001001010', "'": '010010000000000', '>': '100010001010100',
    '<': '001010100010001', ' ': '000000000000000',
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


def wrap(s, width):
    lines, cur = [], ''
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + ' ' + word).strip()
    if cur:
        lines.append(cur)
    return lines


def cheb(ax, ay, bx, by):
    return max(abs(ax - bx), abs(ay - by))


def sign(v):
    return (v > 0) - (v < 0)


# ------------------------------------------------------------------ sound
class Sfx:
    SPECS = {  # dur, f0, f1, noise, vol, wave
        'step': (0.05, 200, 150, 0.7, 0.05, 'sq'),
        'stab': (0.1, 500, 150, 0.8, 0.14, 'sq'),
        'kill': (0.2, 260, 50, 0.6, 0.2, 'sq'),
        'hurt': (0.3, 300, 60, 0.45, 0.32, 'sq'),
        'leap': (0.2, 200, 600, 0.4, 0.1, 'sq'),
        'throw': (0.12, 900, 300, 0.5, 0.12, 'sq'),
        'bash': (0.18, 120, 50, 0.7, 0.25, 'sq'),
        'fall': (0.6, 500, 60, 0.2, 0.15, 'sin'),
        'arrow': (0.08, 1100, 400, 0.5, 0.1, 'sq'),
        'hex': (0.25, 300, 1200, 0.2, 0.12, 'sin'),
        'boom': (0.45, 110, 25, 0.85, 0.35, 'sq'),
        'fuse': (0.1, 1500, 1800, 0.6, 0.05, 'sq'),
        'stairs': (0.9, 90, 400, 0.1, 0.25, 'sin'),
        'boon': (0.4, 300, 900, 0.0, 0.15, 'sin'),
        'pickup': (0.1, 500, 1000, 0.0, 0.12, 'sin'),
        'no': (0.06, 160, 140, 0.0, 0.1, 'sq'),
        'toll': (1.2, 110, 108, 0.0, 0.3, 'sin'),
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


# ------------------------------------------------------------------ data
ENEMIES = {
    'ghoul': dict(name='GHOUL', hp=1, depth=1, weight=10,
                  desc='STRIKES ANY TILE NEXT TO IT.'),
    'archer': dict(name='BONE ARCHER', hp=1, depth=2, weight=6,
                   desc='SHOOTS ALONG ROWS, COLUMNS AND DIAGONALS, 2 TO 5 TILES AWAY. '
                        'CANNOT SHOOT POINT-BLANK.'),
    'cultist': dict(name='CULTIST', hp=1, depth=4, weight=4,
                    desc='HEXES ALONG ROWS AND COLUMNS, UP TO 7 TILES. RESTS A TURN AFTER.'),
    'bomber': dict(name='GRAVE-ROBBER', hp=1, depth=6, weight=3,
                   desc='LOBS A BOMB AT YOU FROM 2-4 TILES. IT BURSTS NEXT TURN, 3X3, '
                        'HURTING ANYONE CAUGHT.'),
    'revenant': dict(name='REVENANT', hp=2, depth=8, weight=3,
                     desc='TAKES TWO WOUNDS. STRIKES ANY TILE NEXT TO IT. '
                          'MOVES ONLY EVERY OTHER TURN.'),
}

BOONS = {
    'VIGOR': 'ONE MORE HEART, AND HEAL ONE',
    'MEND': 'HEAL EVERY WOUND',
    'FAR LEAP': 'LEAP UP TO 3 TILES',
    'QUICK LEAP': 'LEAP RECOVERS A TURN SOONER',
    'SHIELD WALL': 'BASH RECOVERS A TURN SOONER',
    'HEAVY SHIELD': 'BASH SHOVES FOES 2 TILES',
    'LONG ARM': 'THROW THE SPEAR 2 TILES FARTHER',
    'BONE SPEAR': 'A THROWN SPEAR FLIES BACK TO YOUR HAND',
    'BLOODLUST': 'KILL 3 OR MORE IN ONE TURN TO HEAL ONE',
    'SHOCKWAVE': 'LANDING A LEAP STUNS EVERY FOE NEXT TO YOU',
}

ABILITY_KEYS = {pygame.K_1: 'leap', pygame.K_2: 'throw', pygame.K_3: 'bash'}
MOVE_KEYS = {
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0), pygame.K_KP6: (1, 0),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_KP4: (-1, 0),
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_KP8: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1), pygame.K_KP2: (0, 1), pygame.K_x: (0, 1),
    pygame.K_q: (-1, -1), pygame.K_KP7: (-1, -1), pygame.K_e: (1, -1), pygame.K_KP9: (1, -1),
    pygame.K_z: (-1, 1), pygame.K_KP1: (-1, 1), pygame.K_c: (1, 1), pygame.K_KP3: (1, 1),
}


# ------------------------------------------------------------------ graphics
def make_sprites():
    def surf():
        return pygame.Surface((14, 15), pygame.SRCALPHA)

    def knight(spear):
        s = surf()
        pygame.draw.polygon(s, BONE, [(4, 7), (10, 7), (11, 14), (3, 14)])
        s.fill(BLACK, (5, 11, 4, 1))
        pygame.draw.rect(s, BONE, (4, 1, 6, 6), border_radius=2)
        s.fill(BLACK, (5, 3, 4, 1))
        s.set_at((7, 5), BLACK)
        for px, py in ((6, 0), (5, 0), (4, 0), (3, 1), (2, 2)):
            s.set_at((px, py), BLOOD)
        pygame.draw.rect(s, BLOOD, (0, 7, 4, 6), border_radius=1)    # shield
        s.set_at((1, 9), BONE)
        if spear:
            pygame.draw.line(s, BONE, (12, 14), (12, 2))
            pygame.draw.polygon(s, BONE, [(11, 2), (13, 2), (12, 0)])
            s.set_at((12, 4), BLOOD)
        return s

    def ghoul():
        s = surf()
        pygame.draw.circle(s, BONE, (8, 4), 3, 1)
        pygame.draw.polygon(s, BONE, [(4, 6), (10, 6), (11, 13), (3, 13)], 1)
        pygame.draw.line(s, BONE, (10, 8), (13, 11))
        pygame.draw.line(s, BONE, (4, 8), (2, 12))
        return s

    def archer():
        s = surf()
        pygame.draw.circle(s, BONE, (6, 3), 3, 1)
        pygame.draw.line(s, BONE, (6, 6), (6, 12))
        for y in (8, 10):
            pygame.draw.line(s, BONE, (4, y), (8, y))
        pygame.draw.line(s, BONE, (4, 13), (8, 13))
        pygame.draw.arc(s, BONE, (8, 2, 5, 11), -math.pi / 2, math.pi / 2)
        pygame.draw.line(s, BONE, (10, 2), (10, 12))
        return s

    def cultist():
        s = surf()
        pygame.draw.polygon(s, BONE, [(7, 0), (11, 5), (12, 14), (2, 14), (3, 5)], 1)
        pygame.draw.ellipse(s, BLACK, (5, 2, 5, 4))
        pygame.draw.line(s, BONE, (12, 4), (12, 14))
        s.set_at((12, 3), BLOOD)
        return s

    def bomber():
        s = surf()
        pygame.draw.circle(s, BONE, (5, 5), 3, 1)
        pygame.draw.polygon(s, BONE, [(2, 8), (8, 7), (10, 14), (2, 14)], 1)
        pygame.draw.circle(s, BLOOD, (11, 9), 2)
        s.set_at((12, 6), BONE)
        s.set_at((13, 5), BLOOD)
        return s

    def revenant():
        s = surf()
        pygame.draw.rect(s, BONE, (2, 6, 10, 8), 1)
        pygame.draw.rect(s, BONE, (4, 0, 7, 6), 1)
        pygame.draw.line(s, BLACK, (5, 3), (9, 3))
        pygame.draw.circle(s, BONE, (2, 7), 2, 1)
        pygame.draw.circle(s, BONE, (12, 7), 2, 1)
        pygame.draw.line(s, BONE, (13, 1), (13, 14))
        return s

    S = {'knight': knight(True), 'knight_bare': knight(False), 'ghoul': ghoul(),
         'archer': archer(), 'cultist': cultist(), 'bomber': bomber(), 'revenant': revenant()}
    eyes = {'ghoul': [(8, 4), (10, 4)], 'archer': [(5, 3), (7, 3)], 'cultist': [(6, 4), (8, 4)],
            'bomber': [(4, 5), (6, 5)], 'revenant': [(6, 3), (8, 3)]}
    for k, pts in eyes.items():
        for p in pts:
            S[k].set_at(p, BLOOD)
    for k in list(S):
        S[k + '_flip'] = pygame.transform.flip(S[k], True, False)
    spear = pygame.Surface((14, 14), pygame.SRCALPHA)
    pygame.draw.line(spear, BONE, (2, 12), (11, 3))
    pygame.draw.polygon(spear, BONE, [(10, 2), (13, 1), (12, 4)])
    spear.set_at((4, 10), BLOOD)
    S['spear'] = spear
    return S


def dither_surface(w, h):
    s = pygame.Surface((w, h))
    s.fill(KEY)
    s.set_colorkey(KEY)
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            s.set_at((x, y), BLACK)
            s.set_at((x + 1, y + 1), BLACK)
    return s


# ------------------------------------------------------------------ level
class Level:
    def __init__(self, depth):
        self.depth = depth
        for _ in range(500):
            if self.generate():
                break

    def generate(self):
        t = [[WALL] * GW for _ in range(GH)]
        target = random.randint(78, 100)
        x, y = GW // 2, GH // 2
        n = 0
        while n < target:
            for cx, cy in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)) if random.random() < 0.3 \
                    else ((x, y),):
                if 1 <= cx < GW - 1 and 1 <= cy < GH - 1 and t[cy][cx] == WALL:
                    t[cy][cx] = FLOOR
                    n += 1
            dx, dy = random.choice(DIRS)
            x = min(GW - 2, max(1, x + dx))
            y = min(GH - 2, max(1, y + dy))
        self.t = t
        # chasms: small clusters well inside open ground
        for _ in range(random.randint(1, 3)):
            open_tiles = [(x, y) for y in range(GH) for x in range(GW)
                          if t[y][x] == FLOOR and self.floor_nbrs(x, y) == 8]
            if not open_tiles:
                break
            cx, cy = random.choice(open_tiles)
            for _ in range(random.randint(2, 5)):
                if t[cy][cx] == FLOOR:
                    t[cy][cx] = CHASM
                dx, dy = random.choice(DIRS)
                nx, ny = cx + dx, cy + dy
                if 1 <= nx < GW - 1 and 1 <= ny < GH - 1:
                    cx, cy = nx, ny
        for _ in range(random.randint(0, 3)):                # lone pillars
            open_tiles = [(x, y) for y in range(GH) for x in range(GW)
                          if t[y][x] == FLOOR and self.floor_nbrs(x, y) == 8]
            if open_tiles:
                x, y = random.choice(open_tiles)
                t[y][x] = WALL
        # keep only the largest connected floor area
        comps, seen = [], set()
        for y in range(GH):
            for x in range(GW):
                if t[y][x] == FLOOR and (x, y) not in seen:
                    comp = self.flood(x, y)
                    seen |= comp
                    comps.append(comp)
        if not comps:
            return False
        main = max(comps, key=len)
        if len(main) < 60:
            return False
        for comp in comps:
            if comp is not main:
                for x, y in comp:
                    t[y][x] = WALL
        # start on the left, stairs as far away as the paths allow
        xs = sorted(main, key=lambda p: p[0])
        self.start = random.choice(xs[:6])
        dist = self.bfs(*self.start)
        far = max(dist.values())
        if far < 9:
            return False
        self.stairs = random.choice([p for p, d in dist.items() if d >= far - 1])
        t[self.stairs[1]][self.stairs[0]] = STAIRS
        self.dist_from_start = dist
        rng = random.Random()
        self.dots = {(x, y): [(rng.randrange(2, 14), rng.randrange(2, 14)) for _ in range(rng.randint(0, 2))]
                     for y in range(GH) for x in range(GW)}
        return True

    def floor_nbrs(self, x, y):
        n = 0
        for dx, dy in DIR8:
            nx, ny = x + dx, y + dy
            if 0 <= nx < GW and 0 <= ny < GH and self.t[ny][nx] == FLOOR:
                n += 1
        return n

    def flood(self, x, y):
        out = {(x, y)}
        q = deque([(x, y)])
        while q:
            cx, cy = q.popleft()
            for dx, dy in DIR8:
                nx, ny = cx + dx, cy + dy
                if (nx, ny) not in out and 0 <= nx < GW and 0 <= ny < GH and \
                        self.t[ny][nx] in (FLOOR, STAIRS):
                    out.add((nx, ny))
                    q.append((nx, ny))
        return out

    def bfs(self, x, y, blocked=()):
        dist = {(x, y): 0}
        q = deque([(x, y)])
        while q:
            cx, cy = q.popleft()
            for dx, dy in DIR8:
                nx, ny = cx + dx, cy + dy
                if (nx, ny) not in dist and self.walkable(nx, ny) and (nx, ny) not in blocked:
                    dist[(nx, ny)] = dist[(cx, cy)] + 1
                    q.append((nx, ny))
        return dist

    def tile(self, x, y):
        if 0 <= x < GW and 0 <= y < GH:
            return self.t[y][x]
        return WALL

    def walkable(self, x, y):
        return self.tile(x, y) in (FLOOR, STAIRS)


class Enemy:
    _next = 0

    def __init__(self, kind, x, y):
        Enemy._next += 1
        self.id = Enemy._next
        self.kind, self.x, self.y = kind, x, y
        self.hp = ENEMIES[kind]['hp']
        self.stun = 0
        self.cool = 0
        self.dead = False
        self.ax, self.ay = float(x * TS), float(y * TS)
        self.face = random.choice((-1, 1))
        self.flash = 0
        self.slow_t = random.randint(0, 1)


class Player:
    def __init__(self):
        self.x = self.y = 0
        self.ax = self.ay = 0.0
        self.hp = self.maxhp = 3
        self.spear = True
        self.leap_cd = self.bash_cd = 0
        self.leap_max, self.leap_range = 3, 2
        self.bash_max, self.bash_push = 4, 1
        self.throw_range = 3
        self.boons = []
        self.face = 1
        self.flash = 0


# ------------------------------------------------------------------ game
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
        pygame.display.set_caption('CENOTAPH')
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()
        self.sfx = Sfx()
        self.spr = make_sprites()
        self.dim = dither_surface(W, H)
        self.best_file = os.path.join(os.environ.get('XDG_DATA_HOME') or
                                      os.path.expanduser('~/.local/share'), 'cenotaph', 'best')
        self.best = 0
        try:
            with open(self.best_file) as f:
                self.best = int(f.read().strip() or 0)
        except (OSError, ValueError):
            pass
        self.t = 0
        self.mouse = (0, 0)
        self.new_run()
        self.state = 'title'

    # ---------------------------------------------------------- run / floors
    def new_run(self):
        self.player = Player()
        self.depth = 0
        self.turns = self.kills = 0
        self.log = []
        self.effects, self.particles = [], []
        self.mode = None
        self.cursor = [0, 0]
        self.shake = 0.0
        self.dead_t = 0
        self.next_floor()

    def next_floor(self):
        self.depth += 1
        self.level = Level(self.depth)
        p = self.player
        p.x, p.y = self.level.start
        p.ax, p.ay = float(p.x * TS), float(p.y * TS)
        p.spear = True
        p.leap_cd = p.bash_cd = 0
        self.spear_at = None
        self.bombs = []
        self.enemies = []
        self.spawn_enemies()
        self.state = 'play'
        self.mode = None
        self.fade = 30
        self.say(f'DEPTH {self.depth}' + ('. THE HEART LIES HERE.' if self.depth == LAST_DEPTH else '.'))
        self.compute_threats()
        if self.depth > self.best:
            self.best = self.depth
            try:
                os.makedirs(os.path.dirname(self.best_file), exist_ok=True)
                with open(self.best_file, 'w') as f:
                    f.write(str(self.best))
            except OSError:
                pass

    def spawn_enemies(self):
        d = self.depth
        lvl = self.level
        n = min(11, 2 + d // 2 + (d >= 3) + (d == LAST_DEPTH) * 2)
        kinds = [(k, v['weight']) for k, v in ENEMIES.items() if d >= v['depth']]
        spots = [p for p, dd in lvl.dist_from_start.items() if dd >= 4 and p != lvl.stairs]
        random.shuffle(spots)
        for x, y in spots[:n]:
            k = random.choices([k for k, _ in kinds], [w for _, w in kinds])[0]
            self.enemies.append(Enemy(k, x, y))

    # ---------------------------------------------------------- helpers
    def say(self, s):
        self.log.append([s, 240])
        self.log = self.log[-3:]

    def enemy_at(self, x, y):
        for e in self.enemies:
            if not e.dead and e.x == x and e.y == y:
                return e
        return None

    def free(self, x, y):
        p = self.player
        return self.level.walkable(x, y) and not self.enemy_at(x, y) and (x, y) != (p.x, p.y)

    def clear_line(self, x0, y0, x1, y1, ignore=None):
        """Every tile strictly between two aligned tiles is open (chasms do not block)."""
        dx, dy = sign(x1 - x0), sign(y1 - y0)
        x, y = x0 + dx, y0 + dy
        while (x, y) != (x1, y1):
            if self.level.tile(x, y) == WALL:
                return False
            e = self.enemy_at(x, y)
            if e and e is not ignore:
                return False
            p = self.player
            if (x, y) == (p.x, p.y) and ignore != 'player':
                return False
            x += dx
            y += dy
        return True

    def ready(self, e):
        return e.stun == 0 and e.cool <= 1

    def threatens(self, e, tx, ty):
        """Would e attack someone standing on (tx, ty) on its next action?"""
        if e.dead or not self.ready(e):
            return False
        dx, dy = tx - e.x, ty - e.y
        d = cheb(e.x, e.y, tx, ty)
        k = e.kind
        if k in ('ghoul', 'revenant'):
            return d == 1
        if k == 'archer':
            return (dx == 0 or dy == 0 or abs(dx) == abs(dy)) and 2 <= d <= 5 \
                and self.clear_line(e.x, e.y, tx, ty, 'player')
        if k == 'cultist':
            return (dx == 0 or dy == 0) and 1 <= d <= 7 and self.clear_line(e.x, e.y, tx, ty, 'player')
        return False

    def compute_threats(self):
        self.threat = {}
        for y in range(GH):
            for x in range(GW):
                if self.level.walkable(x, y):
                    who = [e for e in self.enemies if self.threatens(e, x, y)]
                    if who:
                        self.threat[(x, y)] = who
        self.blast = set()
        for b in self.bombs:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    self.blast.add((b[0] + dx, b[1] + dy))

    def burst(self, x, y, n, spd=2.0, life=20, color=BONE):
        for _ in range(n):
            a = random.uniform(0, TAU)
            v = random.uniform(0.3, 1) * spd
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v,
                                   random.randint(life // 2, life), color])

    def center(self, x, y):
        return GX + x * TS + TS // 2, GY + y * TS + TS // 2

    def wound(self, e, how):
        e.hp -= 1
        e.flash = 8
        cx, cy = self.center(e.x, e.y)
        self.burst(cx, cy, 8, 2, 18, BLOOD)
        if e.hp <= 0:
            e.dead = True
            self.kills += 1
            self.turn_kills += 1
            self.burst(cx, cy, 14, 2.5, 24, BONE)
            self.sfx.play('kill')
            self.say(f'{how} THE {ENEMIES[e.kind]["name"]}.')
        else:
            self.sfx.play('stab')
            self.say(f'{how} THE {ENEMIES[e.kind]["name"]}. IT STILL STANDS.')

    def hurt_player(self, src):
        p = self.player
        p.hp -= 1
        p.flash = 12
        self.shake = 4
        self.sfx.play('hurt')
        cx, cy = self.center(p.x, p.y)
        self.burst(cx, cy, 12, 2, 24, BLOOD)
        self.say(f'{src} WOUNDS YOU.')

    # ---------------------------------------------------------- player actions
    def try_move(self, dx, dy):
        p = self.player
        nx, ny = p.x + dx, p.y + dy
        if not self.free(nx, ny):
            self.sfx.play('no')
            return
        self.begin_turn()
        ox, oy = p.x, p.y
        p.x, p.y = nx, ny
        if dx:
            p.face = dx
        self.sfx.play('step')
        if p.spear:                                           # lunge
            e = self.enemy_at(nx + dx, ny + dy)
            if e:
                self.slash(e)
                self.wound(e, 'YOU LUNGE AT')
        self.stab(ox, oy)
        self.end_player_turn()

    def stab(self, ox, oy):
        p = self.player
        for e in self.enemies:
            if not e.dead and cheb(e.x, e.y, ox, oy) == 1 and cheb(e.x, e.y, p.x, p.y) == 1:
                self.slash(e)
                self.wound(e, 'YOU STAB')

    def slash(self, e):
        self.effects.append(['slash', e.x, e.y, 0, 10])
        self.sfx.play('stab')

    def leap_targets(self):
        p = self.player
        if p.leap_cd:
            return set()
        return {(x, y) for y in range(GH) for x in range(GW)
                if 1 <= cheb(p.x, p.y, x, y) <= p.leap_range and self.free(x, y)}

    def throw_targets(self):
        p = self.player
        if not p.spear:
            return set()
        out = set()
        for dx, dy in DIR8:
            for k in range(1, p.throw_range + 1):
                x, y = p.x + dx * k, p.y + dy * k
                if self.level.tile(x, y) == WALL:
                    break
                if self.enemy_at(x, y):
                    out.add((x, y))
                    break
        return out

    def bash_targets(self):
        p = self.player
        if p.bash_cd:
            return set()
        return {(p.x + dx, p.y + dy) for dx, dy in DIR8 if self.enemy_at(p.x + dx, p.y + dy)}

    def targets(self, mode):
        return {'leap': self.leap_targets, 'throw': self.throw_targets,
                'bash': self.bash_targets}[mode]()

    def leap(self, x, y):
        p = self.player
        if (x, y) not in self.leap_targets():
            self.sfx.play('no')
            return
        self.begin_turn()
        ox, oy = p.x, p.y
        p.x, p.y = x, y
        if x != ox:
            p.face = sign(x - ox)
        p.leap_cd = p.leap_max
        self.sfx.play('leap')
        self.burst(*self.center(x, y), 10, 1.5, 16, BONE)
        self.stab(ox, oy)
        if 'SHOCKWAVE' in p.boons:
            for e in self.enemies:
                if not e.dead and cheb(e.x, e.y, x, y) == 1:
                    e.stun = max(e.stun, 1)
            self.effects.append(['ring', x, y, 0, 14])
        self.end_player_turn()

    def throw(self, x, y):
        p = self.player
        if (x, y) not in self.throw_targets():
            self.sfx.play('no')
            return
        self.begin_turn()
        e = self.enemy_at(x, y)
        self.effects.append(['spear', p.x, p.y, x, y, 0, 8])
        self.sfx.play('throw')
        if x != p.x:
            p.face = sign(x - p.x)
        self.wound(e, 'YOUR SPEAR PIERCES')
        if 'BONE SPEAR' in p.boons:
            self.say('THE SPEAR FLIES BACK TO YOUR HAND.')
        else:
            p.spear = False
            self.spear_at = (x, y)
        self.end_player_turn()

    def bash(self, x, y):
        p = self.player
        if (x, y) not in self.bash_targets():
            self.sfx.play('no')
            return
        self.begin_turn()
        dx, dy = x - p.x, y - p.y
        e = self.enemy_at(x, y)
        p.bash_cd = p.bash_max
        self.sfx.play('bash')
        self.shake = 2
        for _ in range(p.bash_push):
            if e.dead or not self.shove(e, dx, dy):
                break
        if not e.dead:
            e.stun = max(e.stun, 1)
        self.end_player_turn()

    def shove(self, e, dx, dy, depth=0):
        """Push e one tile; returns whether it moved. Chasms swallow, walls stun."""
        tx, ty = e.x + dx, e.y + dy
        tile = self.level.tile(tx, ty)
        p = self.player
        if tile == CHASM:
            e.x, e.y = tx, ty
            e.dead = True
            self.kills += 1
            self.turn_kills += 1
            self.effects.append(['fall', tx, ty, e.kind, 0, 24])
            self.sfx.play('fall')
            self.say(f'THE {ENEMIES[e.kind]["name"]} FALLS INTO THE DARK.')
            return True
        if tile == WALL or (tx, ty) == (p.x, p.y):
            e.stun = max(e.stun, 2)
            self.say(f'THE {ENEMIES[e.kind]["name"]} SLAMS INTO STONE, STUNNED.')
            return False
        o = self.enemy_at(tx, ty)
        if o:
            if depth > 6 or not self.shove(o, dx, dy, depth + 1):
                e.stun = max(e.stun, 2)
                return False
        e.x, e.y = tx, ty
        return True

    def wait(self):
        self.begin_turn()
        self.say('YOU HOLD YOUR GROUND.')
        self.end_player_turn()

    def begin_turn(self):
        self.turn_kills = 0
        self.mode = None

    def end_player_turn(self):
        p = self.player
        self.turns += 1
        if self.spear_at and (p.x, p.y) == self.spear_at:
            p.spear = True
            self.spear_at = None
            self.sfx.play('pickup')
            self.say('YOU TAKE UP YOUR SPEAR.')
        if p.leap_cd:
            p.leap_cd -= 1
        if p.bash_cd:
            p.bash_cd -= 1
        if 'BLOODLUST' in p.boons and self.turn_kills >= 3 and p.hp < p.maxhp:
            p.hp += 1
            self.say('BLOODLUST MENDS A WOUND.')
        if self.level.tile(p.x, p.y) == STAIRS and not self.foes_left_matter():
            self.descend()
            return
        self.enemy_phase()
        if p.hp <= 0:
            p.hp = 0
            self.state = 'dead'
            self.dead_t = 0
            self.sfx.play('toll')
            return
        self.compute_threats()

    def foes_left_matter(self):
        return False      # the stairs can be taken at any time; foes left behind stay behind

    def descend(self):
        if self.depth == LAST_DEPTH:
            self.state = 'won'
            self.dead_t = 0
            self.sfx.play('stairs')
            return
        self.sfx.play('stairs')
        self.open_boons()

    # ---------------------------------------------------------- enemies
    def enemy_phase(self):
        p = self.player
        # bombs thrown last turn burst first
        keep = []
        for b in self.bombs:
            b[2] -= 1
            if b[2] <= 0:
                self.explode(b[0], b[1])
            else:
                keep.append(b)
        self.bombs = keep
        dist = self.level.bfs(p.x, p.y)
        for e in sorted(self.enemies, key=lambda e: dist.get((e.x, e.y), 99)):
            if e.dead or p.hp <= 0:
                continue
            if e.stun > 0:
                e.stun -= 1
                continue
            if e.cool > 0:
                e.cool -= 1
            if self.attack(e):
                continue
            self.enemy_move(e, dist)
        self.enemies = [e for e in self.enemies if not e.dead]

    def attack(self, e):
        p = self.player
        k = e.kind
        if e.cool == 0 and k in ('archer', 'cultist', 'ghoul', 'revenant') and \
                self.threatens(e, p.x, p.y):
            e.face = sign(p.x - e.x) or e.face
            name = ENEMIES[k]['name']
            if k == 'archer':
                self.effects.append(['arrow', e.x, e.y, p.x, p.y, 0, 8])
                self.sfx.play('arrow')
            elif k == 'cultist':
                self.effects.append(['hex', e.x, e.y, p.x, p.y, 0, 14])
                self.sfx.play('hex')
                e.cool = 2
            else:
                self.effects.append(['claw', p.x, p.y, 0, 10])
            self.hurt_player(f'THE {name}')
            return True
        if k == 'bomber' and e.cool == 0 and 2 <= cheb(e.x, e.y, p.x, p.y) <= 4:
            self.bombs.append([p.x, p.y, 1])
            self.effects.append(['lob', e.x, e.y, p.x, p.y, 0, 12])
            self.sfx.play('fuse')
            e.cool = 3
            self.say('A BOMB LANDS AT YOUR FEET.')
            return True
        return False

    def explode(self, x, y):
        p = self.player
        self.sfx.play('boom')
        self.shake = 5
        self.effects.append(['boom', x, y, 0, 16])
        self.burst(*self.center(x, y), 24, 3, 26, BLOOD)
        if cheb(x, y, p.x, p.y) <= 1:
            self.hurt_player('THE BLAST')
        for e in self.enemies:
            if not e.dead and cheb(x, y, e.x, e.y) <= 1:
                self.wound(e, 'THE BLAST TEARS')

    def enemy_move(self, e, dist):
        p = self.player
        k = e.kind
        if k == 'revenant':
            e.slow_t ^= 1
            if e.slow_t:
                return
        opts = [(e.x + dx, e.y + dy) for dx, dy in DIR8 if self.free(e.x + dx, e.y + dy)]
        if not opts:
            return
        here = dist.get((e.x, e.y), 99)
        if k in ('ghoul', 'revenant'):
            best = min(opts, key=lambda q: (dist.get(q, 99), random.random()))
            if dist.get(best, 99) >= here:
                return
        else:
            want = {'archer': 3, 'cultist': 4, 'bomber': 3}[k]

            def score(q):
                s = abs(dist.get(q, 99) - want)
                ox, oy = e.x, e.y
                e.x, e.y = q
                cool = e.cool
                e.cool = 0
                if k == 'bomber':
                    good = 2 <= cheb(q[0], q[1], p.x, p.y) <= 4
                else:
                    good = self.threatens(e, p.x, p.y)
                e.x, e.y, e.cool = ox, oy, cool
                return (0 if good else 1, s, random.random())
            cur = score((e.x, e.y))
            best = min(opts, key=score)
            if score(best)[:2] >= cur[:2]:
                return
        if best[0] != e.x:
            e.face = sign(best[0] - e.x)
        e.x, e.y = best

    # ---------------------------------------------------------- boons
    def open_boons(self):
        p = self.player
        pool = [b for b in BOONS if b != 'MEND']
        if p.maxhp >= 6:
            pool.remove('VIGOR')
        for once in ('FAR LEAP', 'HEAVY SHIELD', 'BONE SPEAR', 'BLOODLUST', 'SHOCKWAVE', 'LONG ARM'):
            if once in p.boons and once in pool:
                pool.remove(once)
        if p.leap_max <= 1 and 'QUICK LEAP' in pool:
            pool.remove('QUICK LEAP')
        if p.bash_max <= 1 and 'SHIELD WALL' in pool:
            pool.remove('SHIELD WALL')
        opts = random.sample(pool, min(3, len(pool)))
        if p.hp < p.maxhp:
            opts[-1] = 'MEND'
        self.boon_opts = opts
        self.boon_sel = 0
        self.boon_t = 0
        self.state = 'boon'

    def pick_boon(self, i):
        if self.boon_t < 15 or not (0 <= i < len(self.boon_opts)):
            return
        b = self.boon_opts[i]
        p = self.player
        if b == 'VIGOR':
            p.maxhp += 1
            p.hp += 1
        elif b == 'MEND':
            p.hp = p.maxhp
        elif b == 'FAR LEAP':
            p.leap_range = 3
        elif b == 'QUICK LEAP':
            p.leap_max -= 1
        elif b == 'SHIELD WALL':
            p.bash_max -= 1
        elif b == 'HEAVY SHIELD':
            p.bash_push = 2
        elif b == 'LONG ARM':
            p.throw_range += 2
        if b != 'MEND':
            p.boons.append(b)
        self.sfx.play('boon')
        self.next_floor()

    # ---------------------------------------------------------- update
    def update(self):
        self.t += 1
        p = self.player
        for o in [p] + self.enemies:
            o.ax += (o.x * TS - o.ax) * 0.35
            o.ay += (o.y * TS - o.ay) * 0.35
            if o.flash:
                o.flash -= 1
        for f in self.effects:
            f[-2] += 1
        self.effects = [f for f in self.effects if f[-2] < f[-1]]
        for q in self.particles:
            q[0] += q[2]
            q[1] += q[3]
            q[2] *= 0.88
            q[3] *= 0.88
            q[4] -= 1
        self.particles = [q for q in self.particles if q[4] > 0]
        for m in self.log:
            m[1] -= 1
        self.shake = max(0.0, self.shake - 0.4)
        if self.fade:
            self.fade -= 1

    # ---------------------------------------------------------- drawing
    def tile_at_mouse(self):
        mx, my = pygame.mouse.get_pos()
        x, y = (mx - GX) // TS, (my - GY) // TS
        if 0 <= x < GW and 0 <= y < GH:
            return x, y
        return None

    def draw_level(self, ox, oy):
        s = self.screen
        lvl = self.level
        for y in range(GH):
            for x in range(GW):
                t = lvl.t[y][x]
                sx, sy = GX + x * TS + ox, GY + y * TS + oy
                if t == WALL:
                    if lvl.floor_nbrs(x, y) or any(lvl.tile(x + dx, y + dy) in (CHASM, STAIRS)
                                                   for dx, dy in DIR8):
                        pygame.draw.rect(s, BONE, (sx + 1, sy + 1, TS - 2, TS - 2), 1)
                        s.fill(BONE, (sx + 1, sy + 6, TS - 2, 1))
                        s.fill(BONE, (sx + 1, sy + 11, TS - 2, 1))
                        s.fill(BONE, (sx + 7, sy + 1, 1, 5))
                        s.fill(BONE, (sx + 4, sy + 6, 1, 5))
                        s.fill(BONE, (sx + 11, sy + 6, 1, 5))
                        s.fill(BONE, (sx + 8, sy + 11, 1, 4))
                    continue
                if t == CHASM:
                    for i in range(0, TS, 4):
                        s.set_at((sx + i + (y % 2) * 2, sy + i), BLOOD)
                    for dx, dy, rect in ((0, -1, (sx, sy, TS, 1)), (0, 1, (sx, sy + TS - 1, TS, 1)),
                                         (-1, 0, (sx, sy, 1, TS)), (1, 0, (sx + TS - 1, sy, 1, TS))):
                        if lvl.tile(x + dx, y + dy) in (FLOOR, STAIRS):
                            s.fill(BONE, rect)
                    continue
                s.set_at((sx, sy), BONE)
                for px, py in lvl.dots[(x, y)]:
                    s.set_at((sx + px, sy + py), BONE)
                if t == STAIRS:
                    if self.depth == LAST_DEPTH:
                        cx, cy = sx + 8, sy + 8
                        r = 4 + (self.t // 15) % 2
                        pygame.draw.circle(s, BLOOD, (cx, cy + 1), r)
                        pygame.draw.circle(s, BONE, (cx - 1, cy - 1), 1)
                        pygame.draw.circle(s, BONE, (cx, cy + 1), r + 2, 1)
                    else:
                        for i in range(4):
                            s.fill(BONE, (sx + 2 + i, sy + 3 + i * 3, TS - 4 - i * 2, 1))
                        s.fill(BLACK, (sx + 6, sy + 12, 4, 2))

    def draw_world(self):
        s = self.screen
        p = self.player
        s.fill(BLACK)
        ox = oy = 0
        if self.shake > 0:
            ox = int(random.uniform(-self.shake, self.shake))
            oy = int(random.uniform(-self.shake, self.shake))
        self.draw_level(ox, oy)
        hover = self.tile_at_mouse()
        hover_e = self.enemy_at(*hover) if hover else None
        # threats: dithered marks on every tile some foe would strike next turn
        for (x, y), who in self.threat.items():
            sx, sy = GX + x * TS + ox, GY + y * TS + oy
            strong = hover_e is not None and hover_e in who
            if hover_e is not None and not strong:
                continue
            for i in range(2, TS - 1, 4):
                for j in range(2, TS - 1, 4):
                    if (i + j) % 8 == 2 or strong:
                        s.set_at((sx + i, sy + j), BLOOD)
            if strong:
                pygame.draw.rect(s, BLOOD, (sx + 1, sy + 1, TS - 2, TS - 2), 1)
        for b in self.bombs:
            sx, sy = GX + (b[0] - 1) * TS + ox, GY + (b[1] - 1) * TS + oy
            if self.t % 20 < 14:
                pygame.draw.rect(s, BLOOD, (sx + 1, sy + 1, TS * 3 - 2, TS * 3 - 2), 1)
            cx, cy = self.center(b[0], b[1])
            pygame.draw.circle(s, BLOOD, (cx + ox, cy + oy + 1), 4)
            pygame.draw.circle(s, BONE, (cx + ox, cy + oy + 1), 4, 1)
            s.set_at((cx + ox + 3, cy + oy - 4), BONE if self.t % 6 < 3 else BLOOD)
        # targeting
        if self.mode and self.state == 'play':
            for x, y in self.targets(self.mode):
                sx, sy = GX + x * TS + ox, GY + y * TS + oy
                pygame.draw.rect(s, BONE, (sx + 1, sy + 1, TS - 2, TS - 2), 1)
            cx, cy = self.cursor
            sx, sy = GX + cx * TS + ox, GY + cy * TS + oy
            if self.t % 20 < 14:
                pygame.draw.rect(s, BLOOD, (sx, sy, TS, TS), 2)
        if self.spear_at:
            x, y = self.spear_at
            s.blit(self.spr['spear'], (GX + x * TS + 1 + ox, GY + y * TS + 1 + oy))
        for e in sorted(self.enemies, key=lambda e: e.y):
            img = self.spr[e.kind + ('_flip' if e.face < 0 else '')]
            x, y = int(GX + e.ax + 1 + ox), int(GY + e.ay + oy)
            if e.flash and self.t % 4 < 2:
                continue
            s.blit(img, (x, y))
            if ENEMIES[e.kind]['hp'] > 1:
                for i in range(e.hp):
                    s.fill(BLOOD, (x + 2 + i * 3, y - 2, 2, 2))
            if e.stun:
                draw_text(s, 'Z', x + 11, y - 3, 1, 'l', BONE)
            elif e.cool > 1 and e.kind in ('cultist', 'bomber'):
                s.set_at((x + 12, y - 1), BONE)
                s.set_at((x + 10, y - 1), BONE)
        if self.state != 'dead' and not (p.flash and self.t % 4 < 2):
            img = self.spr[('knight' if p.spear else 'knight_bare') + ('_flip' if p.face < 0 else '')]
            s.blit(img, (int(GX + p.ax + 1 + ox), int(GY + p.ay + oy)))
        self.draw_effects(ox, oy)
        for q in self.particles:
            s.set_at((int(q[0]) + ox, int(q[1]) + oy), q[5])
        if hover and not self.mode and self.state == 'play':
            sx, sy = GX + hover[0] * TS, GY + hover[1] * TS
            for cx, cy in ((0, 0), (TS - 3, 0), (0, TS - 3), (TS - 3, TS - 3)):
                s.fill(BONE, (sx + cx, sy + cy, 3, 1) if cy == 0 else (sx + cx, sy + cy + 2, 3, 1))

    def draw_effects(self, ox, oy):
        s = self.screen
        for f in self.effects:
            k = f[0]
            t, life = f[-2], f[-1]
            if k == 'slash':
                cx, cy = self.center(f[1], f[2])
                if t < 6:
                    a = t * 0.5
                    pygame.draw.line(s, BONE, (cx - 7 + ox + t, cy - 7 + oy), (cx + 7 + ox - t, cy + 7 + oy), 2)
                    pygame.draw.line(s, BLOOD, (cx - 6 + ox, cy - 6 + oy + a), (cx + 6 + ox, cy + 6 + oy - a))
            elif k == 'claw':
                cx, cy = self.center(f[1], f[2])
                if t < 7:
                    for i in (-3, 0, 3):
                        pygame.draw.line(s, BLOOD, (cx - 5 + i + ox, cy - 6 + oy), (cx + 3 + i + ox, cy + 6 + oy))
            elif k in ('arrow', 'hex', 'spear', 'lob'):
                x0, y0 = self.center(f[1], f[2])
                x1, y1 = self.center(f[3], f[4])
                fr = min(1.0, t / max(1, life - 4))
                if k == 'hex':
                    if t < life - 2:
                        pygame.draw.line(s, BLOOD, (x0 + ox, y0 + oy), (x1 + ox, y1 + oy), 3)
                        pygame.draw.line(s, BONE, (x0 + ox, y0 + oy), (x1 + ox, y1 + oy), 1)
                    continue
                x, y = x0 + (x1 - x0) * fr, y0 + (y1 - y0) * fr
                if k == 'lob':
                    y -= math.sin(fr * math.pi) * 14
                    pygame.draw.circle(s, BLOOD, (int(x) + ox, int(y) + oy), 3)
                else:
                    a = math.atan2(y1 - y0, x1 - x0)
                    ln = 9 if k == 'spear' else 5
                    pygame.draw.line(s, BONE, (x + ox, y + oy),
                                     (x - math.cos(a) * ln + ox, y - math.sin(a) * ln + oy), 2 if k == 'spear' else 1)
            elif k == 'boom':
                cx, cy = self.center(f[1], f[2])
                if t < 4:
                    s.fill(BONE, (cx - TS * 3 // 2 + ox, cy - TS * 3 // 2 + oy, TS * 3, TS * 3))
                else:
                    r = int(10 + t * 1.5)
                    pygame.draw.circle(s, BLOOD, (cx + ox, cy + oy), r, 2)
            elif k == 'ring':
                cx, cy = self.center(f[1], f[2])
                pygame.draw.circle(s, BONE, (cx + ox, cy + oy), 6 + t * 2, 1)
            elif k == 'fall':
                cx, cy = self.center(f[1], f[2])
                sc = max(0.1, 1 - t / life)
                img = pygame.transform.scale(self.spr[f[3]], (max(1, int(14 * sc)), max(1, int(15 * sc))))
                s.blit(img, (cx - img.get_width() // 2 + ox, cy - img.get_height() // 2 + oy))

    def draw_panel(self):
        s = self.screen
        p = self.player
        draw_text(s, 'CENOTAPH', GX, 4, 2, 'l', BLOOD)
        draw_text(s, f'DEPTH {self.depth}/{LAST_DEPTH}', GX + GW * TS, 8, 1, 'r')
        x = PX
        for i in range(p.maxhp):                              # hearts
            hx = x + i * 10
            col = BLOOD if i < p.hp else None
            pts = [(hx + 1, 24), (hx + 3, 22), (hx + 4, 23), (hx + 5, 22), (hx + 7, 24), (hx + 4, 28)]
            if col:
                pygame.draw.polygon(s, col, pts)
            else:
                pygame.draw.polygon(s, BONE, pts, 1)
        rows = [('1', 'LEAP', 'READY' if not p.leap_cd else f'{p.leap_cd} TURNS', not p.leap_cd),
                ('2', 'THROW SPEAR', 'READY' if p.spear else 'ON THE FLOOR', p.spear),
                ('3', 'BASH', 'READY' if not p.bash_cd else f'{p.bash_cd} TURNS', not p.bash_cd)]
        for i, (k, name, st, ok) in enumerate(rows):
            y = 36 + i * 9
            on = self.mode == ('leap', 'throw', 'bash')[i]
            draw_text(s, f'{k} {name}', x, y, 1, 'l', BLOOD if on else BONE)
            draw_text(s, st, W - 4, y, 1, 'r', BONE if ok else BLOOD)
        # whatever is under the mouse
        info = []
        hover = self.tile_at_mouse()
        if self.mode:
            info = [{'leap': 'LEAP', 'throw': 'THROW SPEAR', 'bash': 'BASH'}[self.mode],
                    {'leap': f'JUMP TO A FREE TILE UP TO {p.leap_range} AWAY. STABS STILL COUNT.',
                     'throw': f'KILLS THE FIRST FOE IN A STRAIGHT LINE, UP TO {p.throw_range} TILES. '
                              'WALK OVER THE SPEAR TO TAKE IT BACK.',
                     'bash': 'SHOVE A FOE NEXT TO YOU AWAY AND STUN IT. INTO A CHASM, IT FALLS.'}[self.mode],
                    'CLICK OR ENTER TO CHOOSE, ESC TO CANCEL']
        elif hover:
            e = self.enemy_at(*hover)
            t = self.level.tile(*hover)
            if e:
                d = ENEMIES[e.kind]
                info = [d['name'], d['desc']]
                if e.stun:
                    info.append('STUNNED.')
            elif hover == (p.x, p.y):
                info = ['YOU', 'STEP BETWEEN TWO TILES NEXT TO A FOE TO STAB IT. STEP STRAIGHT AT A FOE '
                        'TWO TILES AWAY TO LUNGE.']
            elif hover == self.spear_at:
                info = ['YOUR SPEAR', 'WALK OVER IT TO TAKE IT BACK.']
            elif t == STAIRS:
                info = ['THE HEART OF THE CENOTAPH', 'TAKE IT.'] if self.depth == LAST_DEPTH else \
                    ['STAIRS', 'DESCEND, AND RECEIVE A BOON.']
            elif t == CHASM:
                info = ['CHASM', 'BASH FOES INTO IT.']
            elif hover in self.blast:
                info = ['A BOMB', 'IT BURSTS AFTER YOUR NEXT MOVE.']
            elif hover in self.threat:
                info = ['DANGER', 'A FOE WOULD STRIKE YOU HERE.']
        y = 68
        for i, para in enumerate(info):
            for line in wrap(para, 36):
                draw_text(s, line, x, y, 1, 'l', BLOOD if i == 0 else BONE, False)
                y += 7
            y += 2
        if p.boons:
            yy = 150
            for line in wrap(', '.join(p.boons), 36)[:4]:
                draw_text(s, line, x, yy, 1, 'l', BONE, False)
                yy += 7
        draw_text(s, 'WASD QEZC MOVE  SPACE WAIT', x, H - 16, 1, 'l', BONE, False)
        draw_text(s, 'CLICK LEAP/BASH  RCLICK THROW', x, H - 9, 1, 'l', BONE, False)
        recent = self.log[-2:]
        for i, (msg, life) in enumerate(recent):
            if life > 0:
                draw_text(s, msg, GX, GY + GH * TS + 4 + i * 8, 1, 'l',
                          BONE if i == len(recent) - 1 else BLOOD, False)

    def draw_boons(self):
        s = self.screen
        s.fill(BLACK)
        self.boon_t += 1
        draw_text(s, 'A BOON', W // 2, 22, 3, 'c', BLOOD)
        draw_text(s, f'DEPTH {self.depth} IS BEHIND YOU.  A/D AND E, 1-3 OR CLICK', W // 2, 44, 1, 'c')
        m = pygame.mouse.get_pos()
        moved = m != self.mouse
        self.mouse = m
        self.boon_rects = []
        bw, bh, gap = 110, 80, 8
        x0 = (W - (bw * 3 + gap * 2)) // 2
        for i, name in enumerate(self.boon_opts):
            r = pygame.Rect(x0 + i * (bw + gap), 62, bw, bh)
            self.boon_rects.append(r)
            if moved and r.collidepoint(m):
                self.boon_sel = i
            sel = i == self.boon_sel
            pygame.draw.rect(s, BLOOD if sel else BONE, r, 2 if sel else 1)
            draw_text(s, str(i + 1), r.x + 4, r.y + 4, 1, 'l', BLOOD, False)
            draw_text(s, name, r.centerx, r.y + 18, 1, 'c', BLOOD if sel else BONE, False)
            for j, line in enumerate(wrap(BOONS[name], 24)):
                draw_text(s, line, r.centerx, r.y + 34 + j * 8, 1, 'c', BONE, False)
        p = self.player
        draw_text(s, f'HEARTS {p.hp}/{p.maxhp}', W // 2, 160, 1, 'c')
        if p.boons:
            for j, line in enumerate(wrap(', '.join(p.boons), 80)[:2]):
                draw_text(s, line, W // 2, 172 + j * 8, 1, 'c', BONE)
        draw_text(s, f'NEXT: DEPTH {self.depth + 1}', W // 2, 200, 1, 'c', BLOOD)

    def draw_title(self):
        s = self.screen
        s.fill(BLACK)
        draw_text(s, 'CENOTAPH', W // 2, 20, 5, 'c')
        draw_text(s, f'DESCEND {LAST_DEPTH} DEPTHS. TAKE THE HEART.', W // 2, 50, 1, 'c', BLOOD)
        lines = ['EVERY MOVE IS AN ATTACK:',
                 'STEP BETWEEN TWO TILES NEXT TO A FOE TO STAB IT',
                 'STEP STRAIGHT AT A FOE TWO TILES AWAY TO LUNGE',
                 '1 LEAP   2 THROW SPEAR   3 BASH (INTO CHASMS!)',
                 'RED MARKS SHOW WHERE FOES WILL STRIKE NEXT TURN',
                 'HOVER A FOE TO SEE ITS REACH',
                 'WASD/ARROWS + Q E Z C DIAGONALS, OR NUMPAD.  SPACE WAITS',
                 'MOUSE: CLICK TO MOVE OR LEAP OR BASH, RIGHT CLICK TO THROW']
        for i, l in enumerate(lines):
            draw_text(s, l, W // 2, 68 + i * 9, 1, 'c', BLOOD if i == 0 else BONE)
        if (self.t // 30) % 2:
            draw_text(s, 'ENTER OR CLICK TO BEGIN', W // 2, 160, 2, 'c', BLOOD)
        draw_text(s, 'ESC PAUSE    F11 FULLSCREEN', W // 2, 186, 1, 'c')
        if self.best:
            draw_text(s, f'DEEPEST: {self.best}', W // 2, 200, 1, 'c')

    def draw_cursor(self):
        mx, my = pygame.mouse.get_pos()
        s = self.screen
        for col, w in ((BLACK, 3), (BONE, 1)):
            for a, b in (((mx - 4, my), (mx - 2, my)), ((mx + 2, my), (mx + 4, my)),
                         ((mx, my - 4), (mx, my - 2)), ((mx, my + 2), (mx, my + 4))):
                pygame.draw.line(s, col, a, b, w)
        s.set_at((mx, my), BLOOD)

    def draw(self):
        s = self.screen
        st = self.state
        if st == 'title':
            self.t += 1
            self.draw_title()
        elif st == 'boon':
            self.draw_boons()
        else:
            self.draw_world()
            self.draw_panel()
            if self.fade:
                for _ in range(self.fade // 8 + 1):
                    s.blit(self.dim, (0, 0))
            if st == 'pause':
                s.blit(self.dim, (0, 0))
                draw_text(s, 'PAUSED', W // 2, 80, 3, 'c')
                draw_text(s, 'ESC  RESUME     X  ABANDON RUN', W // 2, 110, 1, 'c')
            elif st in ('dead', 'won'):
                self.dead_t += 1
                s.blit(self.dim, (0, 0))
                if st == 'dead':
                    draw_text(s, 'ENTOMBED', W // 2, 60, 4, 'c', BLOOD)
                    draw_text(s, f'FELL ON DEPTH {self.depth}   {self.kills} SLAIN   {self.turns} TURNS',
                              W // 2, 92, 1, 'c')
                else:
                    draw_text(s, 'THE HEART IS YOURS', W // 2, 60, 3, 'c', BLOOD)
                    draw_text(s, f'{self.kills} SLAIN   {self.turns} TURNS', W // 2, 92, 1, 'c')
                draw_text(s, f'DEEPEST: {self.best}', W // 2, 104, 1, 'c')
                if self.dead_t > 50:
                    draw_text(s, 'ENTER OR CLICK TO DESCEND AGAIN', W // 2, 140, 2, 'c')
        self.draw_cursor()

    # ---------------------------------------------------------- input / loop
    def use(self, mode, x, y):
        {'leap': self.leap, 'throw': self.throw, 'bash': self.bash}[mode](x, y)

    def click(self, button, pos):
        x, y = (pos[0] - GX) // TS, (pos[1] - GY) // TS
        if not (0 <= x < GW and 0 <= y < GH):
            return
        p = self.player
        if self.mode:
            if button == 1:
                self.use(self.mode, x, y)
            else:
                self.mode = None
            return
        if button == 3:
            self.throw(x, y)
            return
        d = cheb(p.x, p.y, x, y)
        if d == 0:
            self.wait()
        elif d == 1:
            if self.enemy_at(x, y):
                self.bash(x, y)
            else:
                self.try_move(x - p.x, y - p.y)
        elif (x, y) in self.leap_targets():
            self.leap(x, y)
        else:
            self.sfx.play('no')

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        st = self.state
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if st == 'play' and ev.button in (1, 3):
                self.click(ev.button, ev.pos)
            elif st == 'title' and ev.button == 1:
                self.new_run()
            elif st in ('dead', 'won') and ev.button == 1 and self.dead_t > 50:
                self.new_run()
            elif st == 'boon' and ev.button == 1:
                for i, r in enumerate(getattr(self, 'boon_rects', [])):
                    if r.collidepoint(ev.pos):
                        self.pick_boon(i)
            return
        if ev.type != pygame.KEYDOWN:
            return
        key = ev.key
        if key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
        enter = key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        if st == 'title':
            if enter or key == pygame.K_SPACE:
                self.new_run()
            elif key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
        elif st == 'play':
            if self.mode:
                if key == pygame.K_ESCAPE:
                    self.mode = None
                elif key in MOVE_KEYS:
                    dx, dy = MOVE_KEYS[key]
                    self.cursor = [min(GW - 1, max(0, self.cursor[0] + dx)),
                                   min(GH - 1, max(0, self.cursor[1] + dy))]
                elif enter or key == pygame.K_SPACE:
                    self.use(self.mode, *self.cursor)
                elif key in ABILITY_KEYS:
                    self.start_mode(ABILITY_KEYS[key])
                return
            if key == pygame.K_ESCAPE:
                self.state = 'pause'
            elif key in MOVE_KEYS:
                self.try_move(*MOVE_KEYS[key])
            elif key in (pygame.K_SPACE, pygame.K_KP5, pygame.K_PERIOD):
                self.wait()
            elif key in ABILITY_KEYS:
                self.start_mode(ABILITY_KEYS[key])
        elif st == 'pause':
            if key == pygame.K_ESCAPE:
                self.state = 'play'
            elif key == pygame.K_x:
                self.state = 'title'
        elif st == 'boon':
            n = len(self.boon_opts)
            if key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.pick_boon(key - pygame.K_1)
            elif key in (pygame.K_a, pygame.K_LEFT):
                self.boon_sel = (self.boon_sel - 1) % n
            elif key in (pygame.K_d, pygame.K_RIGHT):
                self.boon_sel = (self.boon_sel + 1) % n
            elif key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
                self.pick_boon(self.boon_sel)
        elif st in ('dead', 'won'):
            if self.dead_t > 50 and enter:
                self.new_run()
            elif key == pygame.K_ESCAPE:
                self.state = 'title'

    def start_mode(self, mode):
        targets = self.targets(mode)
        if not targets:
            self.sfx.play('no')
            p = self.player
            self.say({'leap': f'LEAP IS NOT READY.' if p.leap_cd else 'NOWHERE TO LEAP.',
                      'throw': 'YOUR SPEAR LIES ON THE FLOOR.' if not p.spear else 'NO FOE IN A STRAIGHT LINE.',
                      'bash': 'BASH IS NOT READY.' if p.bash_cd else 'NO FOE NEXT TO YOU.'}[mode])
            return
        self.mode = mode
        p = self.player
        self.cursor = list(min(targets, key=lambda q: (cheb(p.x, p.y, *q), q)))

    def run(self):
        while True:
            for ev in pygame.event.get():
                self.handle(ev)
            if self.state in ('play', 'dead', 'won', 'pause'):
                self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(60)


if __name__ == '__main__':
    Game().run()
