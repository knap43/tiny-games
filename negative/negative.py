#!/usr/bin/env python3
"""NEGATIVE - a tiny 1-bit top-down roguelike shooter.

WASD move · mouse aim · LMB fire · RMB/SPACE roll · E pick up · Q/wheel swap
ESC pause · F11 fullscreen
"""
import array
import math
import os
import random
import sys
from collections import deque

import pygame

W, H = 400, 225
T = 16
MW = MH = 64
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
KEY = (255, 0, 255)
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
DIRS8 = DIRS + [(1, 1), (1, -1), (-1, 1), (-1, -1)]
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
    '(': '010100100100010', ')': '010001001001010', "'": '010010000000000',
    '>': '100010001010100', '<': '001010100010001', ' ': '000000000000000',
}
_tcache = {}


def text_surf(s, scale=1, color=WHITE):
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


def draw_text(dst, s, x, y, scale=1, align='l', color=WHITE, outline=True):
    t = text_surf(s, scale, color)
    if align == 'c':
        x -= t.get_width() // 2
    elif align == 'r':
        x -= t.get_width()
    if outline:
        o = text_surf(s, scale, BLACK if color == WHITE else WHITE)
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


# ------------------------------------------------------------------ sound
class Sfx:
    SPECS = {  # dur, f0, f1, noise, vol, wave
        'shot': (0.07, 700, 200, 0.25, 0.16, 'sq'),
        'shotgun': (0.18, 300, 60, 0.75, 0.28, 'sq'),
        'thump': (0.12, 220, 80, 0.3, 0.25, 'sq'),
        'laser': (0.15, 1500, 500, 0.0, 0.12, 'sq'),
        'plasma': (0.25, 300, 900, 0.1, 0.15, 'sin'),
        'hit': (0.04, 420, 150, 0.5, 0.14, 'sq'),
        'hurt': (0.22, 320, 70, 0.4, 0.35, 'sq'),
        'boom': (0.5, 120, 25, 0.85, 0.45, 'sq'),
        'pickup': (0.08, 600, 1300, 0.0, 0.12, 'sq'),
        'rad': (0.03, 1400, 1900, 0.0, 0.04, 'sin'),
        'portal': (0.7, 200, 900, 0.0, 0.22, 'sin'),
        'level': (0.35, 400, 1600, 0.0, 0.15, 'sq'),
        'empty': (0.03, 200, 200, 0.0, 0.1, 'sq'),
        'roll': (0.08, 200, 100, 0.9, 0.08, 'sq'),
        'aim': (0.3, 1000, 1000, 0.0, 0.06, 'sin'),
        'fuse': (0.2, 900, 1600, 0.0, 0.1, 'sq'),
        'die': (0.07, 300, 90, 0.6, 0.2, 'sq'),
        'chest': (0.15, 300, 800, 0.1, 0.18, 'sq'),
        'swap': (0.05, 500, 700, 0.2, 0.08, 'sq'),
        'eshot': (0.06, 500, 250, 0.3, 0.1, 'sq'),
    }

    def __init__(self):
        self.ok = False
        self.s = {}
        try:
            pygame.mixer.init(22050, -16, 1, 512)
            freq, _, ch = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(24)
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
            if wave == 'sq':
                v = 1.0 if (ph % 1.0) < 0.5 else -1.0
            else:
                v = math.sin(ph * TAU)
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
WEAPONS = {
    'revolver': dict(ammo='bullet', cost=1, cd=12, dmg=3, spd=6.0, spread=0.05, n=1,
                     kind='bullet', kick=0.6, shake=1.5, tier=0, len=7, snd='shot'),
    'machinegun': dict(ammo='bullet', cost=1, cd=6, dmg=3, spd=6.0, spread=0.16, n=1,
                       kind='bullet', kick=0.5, shake=1.5, tier=1, len=9, snd='shot'),
    'assault rifle': dict(ammo='bullet', cost=3, cd=24, dmg=3, spd=6.5, spread=0.06, n=1,
                          burst=3, bdelay=4, kind='bullet', kick=0.6, shake=1.8, tier=1,
                          len=10, snd='shot'),
    'minigun': dict(ammo='bullet', cost=1, cd=3, dmg=3, spd=6.0, spread=0.3, n=1,
                    kind='bullet', kick=0.9, shake=2.2, tier=3, len=11, snd='shot'),
    'shotgun': dict(ammo='shell', cost=1, cd=30, dmg=3, spd=5.0, spread=0.55, n=6,
                    kind='pellet', kick=2.0, shake=4, tier=0, len=9, snd='shotgun'),
    'double shotgun': dict(ammo='shell', cost=2, cd=44, dmg=3, spd=5.2, spread=0.75, n=13,
                           kind='pellet', kick=3.5, shake=7, tier=2, len=10, snd='shotgun'),
    'grenade launcher': dict(ammo='explo', cost=1, cd=30, dmg=0, spd=4.0, spread=0.03, n=1,
                             kind='grenade', kick=1.5, shake=2.5, tier=1, len=10, snd='thump'),
    'laser rifle': dict(ammo='energy', cost=1, cd=16, dmg=5, spread=0.0, n=1,
                        kind='laser', kick=0.5, shake=2, tier=1, len=10, snd='laser'),
    'plasma cannon': dict(ammo='energy', cost=2, cd=38, dmg=6, spd=2.6, spread=0.0, n=1,
                          kind='plasma', kick=2.5, shake=4, tier=3, len=11, snd='plasma'),
}
AMMO_TYPES = ['bullet', 'shell', 'explo', 'energy']
AMMO_LABEL = {'bullet': 'BUL', 'shell': 'SHL', 'explo': 'EXP', 'energy': 'NRG'}
AMMO_MAX = {'bullet': 255, 'shell': 55, 'explo': 30, 'energy': 45}
AMMO_DROP = {'bullet': 40, 'shell': 10, 'explo': 4, 'energy': 8}

ENEMIES = {
    'bandit': dict(hp=6, r=5, spd=0.55, rads=2),
    'rat': dict(hp=3, r=4, spd=1.25, rads=1),
    'bomber': dict(hp=4, r=5, spd=1.0, rads=2),
    'sniper': dict(hp=8, r=5, spd=0.45, rads=4),
    'shotgunner': dict(hp=14, r=6, spd=0.5, rads=4),
    'boss': dict(hp=200, r=12, spd=0.75, rads=40),
}

MUTATIONS = [
    ('THICK SKIN', 'MAX HP +4 AND HEAL 4', [('maxhp', '+', 4), ('hp', '+', 4)]),
    ('TRIGGER FINGERS', 'FIRE 20% FASTER', [('fr', '*', 1.2)]),
    ('EXTRA FEET', 'MOVE 15% FASTER', [('spd', '*', 1.15)]),
    ('BACK MUSCLE', 'CARRY 60% MORE AMMO', [('ammo_mult', '+', 0.6)]),
    ('SCAVENGER', 'ENEMIES DROP MORE AMMO', [('scav', '+', 1)]),
    ('BLOODLUST', 'KILLS CAN HEAL YOU', [('blood', '+', 1)]),
    ('PLUTONIUM', 'FASTER, HARDER BULLETS', [('bspd', '*', 1.2), ('dmg', '*', 1.15)]),
    ('EAGLE EYES', 'MUCH TIGHTER SPREAD', [('spread', '*', 0.55)]),
    ('BOOM BOOM', 'BIGGER BLASTS AND NO SELF DAMAGE', [('boom', '+', 1)]),
    ('RAD MAGNET', 'PULL RADS FROM FAR AWAY', [('magnet', '+', 60)]),
    ('NIMBLE', 'ROLL TWICE AS OFTEN', [('roll_mult', '*', 0.5)]),
    ('LUCKY SHOT', 'KILLS CAN REFUND AMMO', [('lucky', '+', 1)]),
    ('SECOND WIND', 'SURVIVE ONE LETHAL HIT', [('spirit', '+', 1)]),
]


def clamp(v, a, b):
    return a if v < a else b if v > b else v


# ------------------------------------------------------------------ sprites
def make_sprites():
    def surf(w, h):
        return pygame.Surface((w, h), pygame.SRCALPHA)

    def build(w, h, fn):
        a, b = surf(w, h), surf(w, h)
        fn(a, False)
        fn(b, True)
        return a, b

    def player(s, f):
        pygame.draw.circle(s, WHITE, (6, 6), 6)
        pygame.draw.rect(s, BLACK, (7, 4, 2, 3))
        pygame.draw.rect(s, BLACK, (10, 4, 1, 3))

    def bandit(s, f):
        w = 0 if f else 1
        e = BLACK if f else WHITE
        pygame.draw.rect(s, WHITE, (1, 4, 11, 9), w)
        pygame.draw.polygon(s, WHITE, [(1, 4), (6, 0), (11, 4)], w)
        pygame.draw.rect(s, e, (6, 7, 2, 2))
        pygame.draw.rect(s, e, (9, 7, 2, 2))

    def rat(s, f):
        w = 0 if f else 1
        pygame.draw.ellipse(s, WHITE, (3, 1, 9, 7), w)
        pygame.draw.line(s, WHITE, (0, 2), (3, 5))
        s.set_at((9, 3), BLACK if f else WHITE)

    def sniper(s, f):
        w = 0 if f else 1
        pygame.draw.rect(s, WHITE, (1, 3, 8, 11), w)
        pygame.draw.line(s, WHITE, (5, 0), (5, 3))
        pygame.draw.circle(s, BLACK if f else WHITE, (6, 7), 2)

    def bomber(s, f):
        w = 0 if f else 1
        e = BLACK if f else WHITE
        pygame.draw.circle(s, WHITE, (6, 7), 5, w)
        pygame.draw.line(s, e, (4, 5), (8, 9))
        pygame.draw.line(s, e, (8, 5), (4, 9))
        pygame.draw.line(s, WHITE, (6, 2), (8, 0))

    def shotgunner(s, f):
        w = 0 if f else 1
        e = BLACK if f else WHITE
        pygame.draw.polygon(s, WHITE, [(3, 0), (11, 0), (14, 6), (11, 13), (3, 13), (0, 6)], w)
        pygame.draw.rect(s, e, (7, 4, 2, 2))
        pygame.draw.rect(s, e, (10, 4, 2, 2))
        pygame.draw.line(s, e, (6, 9), (11, 9))

    def boss(s, f):
        w = 0 if f else 2
        e = BLACK if f else WHITE
        pts = [(9, 4), (21, 4), (28, 11), (28, 23), (21, 30), (9, 30), (2, 23), (2, 11)]
        pygame.draw.polygon(s, WHITE, pts, w)
        for cx in (8, 15, 22):
            pygame.draw.polygon(s, WHITE, [(cx - 3, 5), (cx, 0), (cx + 3, 5)], 0 if f else 1)
        pygame.draw.circle(s, e, (17, 17), 6, 1)
        pygame.draw.circle(s, e, (18, 17), 2)
        pygame.draw.line(s, e, (9, 25), (21, 25), 1)

    defs = {'player': (13, 13, player), 'bandit': (13, 13, bandit), 'rat': (13, 9, rat),
            'sniper': (10, 14, sniper), 'bomber': (13, 13, bomber),
            'shotgunner': (15, 14, shotgunner), 'boss': (31, 32, boss)}
    S = {}
    for k, (w, h, fn) in defs.items():
        a, b = build(w, h, fn)
        corpse = pygame.transform.rotate(a, 90)
        for y in range(corpse.get_height()):
            for x in range(corpse.get_width()):
                if (x + y) % 2:
                    corpse.set_at((x, y), (0, 0, 0, 0))
        S[k] = {1: (a, b), -1: (pygame.transform.flip(a, True, False),
                                pygame.transform.flip(b, True, False)), 'corpse': corpse}
    return S


def dither_surface(w, h, every=2):
    """Black pixels on a checker; magenta colorkey elsewhere. Used to 'dim' in 1-bit."""
    s = pygame.Surface((w, h))
    s.fill(KEY)
    s.set_colorkey(KEY)
    tile = pygame.Surface((2, 2))
    tile.fill(KEY)
    tile.set_at((0, 0), BLACK)
    tile.set_at((1, 1), BLACK)
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            s.blit(tile, (x, y))
    return s


# ------------------------------------------------------------------ level
class Level:
    def __init__(self, n, boss):
        self.grid = [[1] * MW for _ in range(MH)]
        self.arena = None
        self.generate(n, boss)
        self.floor = [(x, y) for y in range(MH) for x in range(MW) if not self.grid[y][x]]
        self.wall_tile = pygame.Surface((T, T))
        self.wall_tile.fill(BLACK)
        for y in range(0, T, 2):
            for x in range((y // 2) % 2, T, 2 if y % 4 == 0 else 4):
                self.wall_tile.set_at((x, y), WHITE)
        self.surf = pygame.Surface((MW * T, MH * T))
        self.render(0, 0, MW - 1, MH - 1)
        self.flow = None
        self.flow_src = None

    def generate(self, n, boss):
        g = self.grid
        sx, sy = MW // 2, MH // 2
        self.start = (sx, sy)
        count = 0

        def carve(x, y):
            nonlocal count
            if 2 <= x < MW - 2 and 2 <= y < MH - 2 and g[y][x]:
                g[y][x] = 0
                count += 1

        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                carve(sx + dx, sy + dy)
        walkers = [[sx, sy, random.randrange(4)]]
        target = min(320 + n * 25, 650)
        steps = 0
        while count < target and steps < 20000:
            steps += 1
            for w in walkers:
                carve(w[0], w[1])
                if random.random() < 0.05:
                    for a in (-1, 0, 1):
                        for b in (-1, 0, 1):
                            carve(w[0] + a, w[1] + b)
                r = random.random()
                if r < 0.2:
                    w[2] = (w[2] + 1) % 4
                elif r < 0.4:
                    w[2] = (w[2] + 3) % 4
                elif r < 0.43:
                    w[2] = (w[2] + 2) % 4
                nx, ny = w[0] + DIRS[w[2]][0], w[1] + DIRS[w[2]][1]
                if 3 <= nx < MW - 3 and 3 <= ny < MH - 3:
                    w[0], w[1] = nx, ny
                else:
                    w[2] = (w[2] + 2) % 4
            if random.random() < 0.04 and len(walkers) < 5:
                walkers.append(list(random.choice(walkers)))
            if random.random() < 0.03 and len(walkers) > 1:
                walkers.pop(random.randrange(len(walkers)))
        if boss:
            floors = [(x, y) for y in range(MH) for x in range(MW) if not g[y][x]]
            fx, fy = max(floors, key=lambda f: (f[0] - sx) ** 2 + (f[1] - sy) ** 2)
            ax, ay = clamp(fx, 8, MW - 9), clamp(fy, 8, MH - 9)
            for y in range(ay - 5, ay + 6):
                for x in range(ax - 5, ax + 6):
                    carve(x, y)
            for px, py in ((-3, -3), (3, -3), (-3, 3), (3, 3)):
                g[ay + py][ax + px] = 1
            self.arena = (ax, ay)

    def solid(self, tx, ty):
        if 0 <= tx < MW and 0 <= ty < MH:
            return self.grid[ty][tx] == 1
        return True

    def solid_at(self, x, y):
        return self.solid(int(x // T), int(y // T))

    def box_hits(self, x, y, r):
        for ty in range(int((y - r) // T), int((y + r) // T) + 1):
            for tx in range(int((x - r) // T), int((x + r) // T) + 1):
                if self.solid(tx, ty):
                    return True
        return False

    def los(self, x0, y0, x1, y1):
        d = math.hypot(x1 - x0, y1 - y0)
        n = int(d / 5) + 1
        for i in range(1, n):
            t = i / n
            if self.solid_at(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t):
                return False
        return True

    def ray(self, x, y, a, maxd=400, step=2):
        c, s = math.cos(a) * step, math.sin(a) * step
        d = 0
        while d < maxd:
            x += c
            y += s
            d += step
            if self.solid_at(x, y):
                break
        return x, y

    def destroy(self, cx, cy, rad):
        tx0, ty0 = int((cx - rad) // T), int((cy - rad) // T)
        tx1, ty1 = int((cx + rad) // T), int((cy + rad) // T)
        changed = False
        for ty in range(max(1, ty0), min(MH - 1, ty1 + 1)):
            for tx in range(max(1, tx0), min(MW - 1, tx1 + 1)):
                if self.grid[ty][tx] and math.hypot(tx * T + 8 - cx, ty * T + 8 - cy) < rad:
                    self.grid[ty][tx] = 0
                    changed = True
        if changed:
            self.render(tx0 - 1, ty0 - 1, tx1 + 1, ty1 + 1)
            self.flow_src = None
        return changed

    def render(self, x0, y0, x1, y1):
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(MW - 1, x1), min(MH - 1, y1)
        s, g = self.surf, self.grid
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                px, py = tx * T, ty * T
                s.fill(BLACK, (px, py, T, T))
                if not g[ty][tx]:
                    h = (tx * 73856093 ^ ty * 19349663) & 0xFFFF
                    if h % 3 == 0:
                        s.set_at((px + 1 + h % 14, py + 1 + (h >> 5) % 14), WHITE)
                    continue
                if not any(0 <= tx + dx < MW and 0 <= ty + dy < MH and not g[ty + dy][tx + dx]
                           for dx, dy in DIRS8):
                    continue
                s.blit(self.wall_tile, (px, py))
                if ty + 1 < MH and not g[ty + 1][tx]:
                    s.fill(WHITE, (px, py + T - 2, T, 2))
                if ty > 0 and not g[ty - 1][tx]:
                    s.fill(WHITE, (px, py, T, 1))
                if tx > 0 and not g[ty][tx - 1]:
                    s.fill(WHITE, (px, py, 1, T))
                if tx + 1 < MW and not g[ty][tx + 1]:
                    s.fill(WHITE, (px + T - 1, py, 1, T))

    def update_flow(self, x, y):
        src = (int(x // T), int(y // T))
        if src == self.flow_src or self.solid(*src):
            return
        self.flow_src = src
        dist = [[-1] * MW for _ in range(MH)]
        dist[src[1]][src[0]] = 0
        q = deque([src])
        g = self.grid
        while q:
            cx, cy = q.popleft()
            nd = dist[cy][cx] + 1
            for dx, dy in DIRS:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < MW and 0 <= ny < MH and not g[ny][nx] and dist[ny][nx] < 0:
                    dist[ny][nx] = nd
                    q.append((nx, ny))
        self.flow = dist

    def nav(self, x, y, tx_, ty_):
        """Direction (unit vector) toward the flow-field target from world pos."""
        d = self.flow
        tx, ty = int(x // T), int(y // T)
        if d is None or self.solid(tx, ty):
            a = math.atan2(ty_ - y, tx_ - x)
            return math.cos(a), math.sin(a)
        cur = d[ty][tx]
        best, bd = None, cur if cur >= 0 else 1 << 30
        for dx, dy in DIRS8:
            nx, ny = tx + dx, ty + dy
            if self.solid(nx, ny):
                continue
            if dx and dy and (self.solid(tx + dx, ty) or self.solid(tx, ty + dy)):
                continue
            v = d[ny][nx]
            if 0 <= v < bd:
                bd, best = v, (nx, ny)
        if best is None:
            gx, gy = tx_, ty_
        else:
            gx, gy = best[0] * T + 8, best[1] * T + 8
        dx, dy = gx - x, gy - y
        l = math.hypot(dx, dy) or 1
        return dx / l, dy / l


# ------------------------------------------------------------------ entities
class Player:
    def __init__(self):
        self.x = self.y = 0.0
        self.r = 4
        self.maxhp = self.hp = 10
        self.weapons = ['revolver', None]
        self.ammo = {'bullet': 96, 'shell': 0, 'explo': 0, 'energy': 0}
        self.vx = self.vy = self.kx = self.ky = 0.0
        self.wkx = self.wky = self.kox = self.koy = 0.0  # weapon kick + its camera offset
        self.cd = self.burst_left = self.burst_t = 0
        self.iframes = self.roll_t = self.roll_cd = 0
        self.rdx = self.rdy = 0.0
        self.aim = 0.0
        self.recoil = 0.0
        self.xp, self.lv, self.pending = 0, 1, 0
        self.muts = []
        self.fr = self.spd = self.ammo_mult = self.dmg = self.bspd = self.spread = 1.0
        self.roll_mult = 1.0
        self.scav = self.blood = self.boom = self.lucky = self.spirit = 0
        self.magnet = 36

    def maxammo(self, t):
        return int(AMMO_MAX[t] * self.ammo_mult)

    def need(self):
        return 12 + self.lv * 8

    def add_ammo(self, t, n):
        self.ammo[t] = min(self.maxammo(t), self.ammo[t] + n)


class Enemy:
    _id = 0

    def __init__(self, kind, x, y, hpm):
        d = ENEMIES[kind]
        Enemy._id += 1
        self.id = Enemy._id
        self.kind, self.x, self.y = kind, x, y
        self.r, self.spd, self.rads = d['r'], d['spd'], d['rads']
        self.hp = self.maxhp = d['hp'] * hpm
        self.cd = random.randint(50, 130)
        self.flash = 0
        self.kx = self.ky = 0.0
        self.face = 1
        self.alert = self.los = self.dead = False
        self.dist = 999.0
        self.wander = random.uniform(0, TAU)
        self.wt = 0
        self.moving = False
        self.strafe = 1
        self.aim_t = 0
        self.aim = 0.0
        self.fuse = 0
        self.phase, self.pt, self.spin = 'chase', 100, 0.0


class Pickup:
    __slots__ = ('kind', 'x', 'y', 'vx', 'vy', 'life', 'data', 'fresh')

    def __init__(self, kind, x, y, data=None, vx=0.0, vy=0.0, life=-1, fresh=False):
        self.kind, self.x, self.y, self.data = kind, x, y, data
        self.vx, self.vy, self.life, self.fresh = vx, vy, life, fresh


class Bullet:
    __slots__ = ('x', 'y', 'vx', 'vy', 'dmg', 'kind', 'enemy', 'life', 'r')

    def __init__(self, x, y, a, spd, dmg, kind, enemy, life=120, r=2):
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * spd, math.sin(a) * spd
        self.dmg, self.kind, self.enemy, self.life, self.r = dmg, kind, enemy, life, r


# ------------------------------------------------------------------ game
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H), pygame.SCALED)
        pygame.display.set_caption('NEGATIVE')
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()
        self.sfx = Sfx()
        self.spr = make_sprites()
        self.dim = dither_surface(W, H)
        self.state = 'title'
        self.t = 0
        self.best_file = os.path.join(os.environ.get('XDG_DATA_HOME') or
                                      os.path.expanduser('~/.local/share'), 'negative', 'best')
        self.best = 0
        try:
            with open(self.best_file) as f:
                self.best = int(f.read().strip() or 0)
        except (OSError, ValueError):
            pass
        self.stars = [[random.uniform(0, W), random.uniform(0, H), random.uniform(0.2, 1.2)]
                      for _ in range(70)]

    # ---------------------------------------------------------- run setup
    def new_run(self):
        self.player = Player()
        self.n = 1
        self.kills = 0
        self.start_level()
        self.state = 'play'

    @staticmethod
    def level_name(n):
        return f'{(n - 1) // 3 + 1}-{(n - 1) % 3 + 1}'

    def start_level(self):
        n = self.n
        is_boss = (n - 1) % 3 == 2
        self.level = lvl = Level(n, is_boss)
        p = self.player
        p.x, p.y = lvl.start[0] * T + 8, lvl.start[1] * T + 8
        p.vx = p.vy = p.kx = p.ky = 0
        p.wkx = p.wky = p.kox = p.koy = 0
        p.iframes = 60
        self.enemies, self.bullets, self.pickups = [], [], []
        self.particles, self.effects, self.corpses, self.texts = [], [], [], []
        self.portal = None
        self.boss = None
        self.frame = 0
        self.freeze = 0
        self.shake = 0.0
        self.trans_t = 0
        self.last_kill = (p.x, p.y)
        self.camx, self.camy = p.x - W / 2, p.y - H / 2
        self.snap_camera()

        hpm = 1 + 0.12 * (n - 1)
        pool = ['bandit'] * 4 + ['rat'] * 3
        if n >= 2:
            pool += ['bomber'] * 2
        if n >= 4:
            pool += ['sniper'] * 2
        if n >= 5:
            pool += ['shotgunner'] * 2
        sx, sy = lvl.start
        far = [f for f in lvl.floor if abs(f[0] - sx) + abs(f[1] - sy) > 10] or lvl.floor
        count = min(10 + n * 3, 45)
        if is_boss:
            count //= 2
        for _ in range(count):
            tx, ty = random.choice(far)
            kind = random.choice(pool)
            group = random.randint(2, 4) if kind == 'rat' else 1
            for _ in range(group):
                self.enemies.append(Enemy(kind, tx * T + 8 + random.uniform(-3, 3),
                                          ty * T + 8 + random.uniform(-3, 3), hpm))
        if is_boss:
            ax, ay = lvl.arena
            self.enemies.append(Enemy('boss', ax * T + 8, ay * T + 8, hpm))
        for kind in ['wchest', 'achest'] + (['wchest'] if is_boss else []):
            tx, ty = random.choice([f for f in lvl.floor
                                    if 6 < abs(f[0] - sx) + abs(f[1] - sy)] or lvl.floor)
            self.pickups.append(Pickup(kind, tx * T + 8, ty * T + 8))

    # ---------------------------------------------------------- helpers
    def move(self, e, dx, dy):
        """Move with wall collision, in steps no longer than a few pixels so nothing can
        tunnel through a wall however hard it is shoved. A blocked axis slides flush against
        the wall, and never ends up further inside a wall than where it started."""
        lvl, r = self.level, e.r
        hx = hy = False
        steps = int(max(abs(dx), abs(dy)) / 4) + 1
        sx, sy = dx / steps, dy / steps
        for _ in range(steps):
            if sx:
                nx = e.x + sx
                if lvl.box_hits(nx, e.y, r):
                    hx = True
                    snap = ((nx + r) // T) * T - r - 0.01 if sx > 0 else ((nx - r) // T + 1) * T + r + 0.01
                    if (snap - e.x) * sx > 0 and not lvl.box_hits(snap, e.y, r):
                        e.x = snap
                    sx = 0
                else:
                    e.x = nx
            if sy:
                ny = e.y + sy
                if lvl.box_hits(e.x, ny, r):
                    hy = True
                    snap = ((ny + r) // T) * T - r - 0.01 if sy > 0 else ((ny - r) // T + 1) * T + r + 0.01
                    if (snap - e.y) * sy > 0 and not lvl.box_hits(e.x, snap, r):
                        e.y = snap
                    sy = 0
                else:
                    e.y = ny
            if not sx and not sy:
                break
        return hx, hy

    def burst(self, x, y, n, spd=2.0, life=20, size=1):
        for _ in range(n):
            a = random.uniform(0, TAU)
            s = random.uniform(0.3, spd)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s,
                                   random.randint(life // 2, life), size, 0.9])

    def toast(self, s, x=None, y=None):
        p = self.player
        self.texts.append([p.x if x is None else x, (p.y - 12) if y is None else y, s, 50])

    def add_shake(self, s):
        self.shake = max(self.shake, s)

    # ---------------------------------------------------------- combat
    def fire(self, p, w, use_cost=True):
        g = WEAPONS[w]
        tipx = p.x + math.cos(p.aim) * g['len']
        tipy = p.y + math.sin(p.aim) * g['len']
        if self.level.solid_at(tipx, tipy):
            tipx, tipy = p.x, p.y
        dmg = g['dmg'] * p.dmg
        if g['kind'] == 'laser':
            x1, y1 = self.level.ray(tipx, tipy, p.aim)
            vx, vy = x1 - tipx, y1 - tipy
            ll = vx * vx + vy * vy or 1
            for e in self.enemies:
                if e.dead:
                    continue
                t = clamp(((e.x - tipx) * vx + (e.y - tipy) * vy) / ll, 0, 1)
                if math.hypot(tipx + vx * t - e.x, tipy + vy * t - e.y) < e.r + 3:
                    e_dx, e_dy = math.cos(p.aim), math.sin(p.aim)
                    self.hurt_enemy(e, dmg, e_dx, e_dy)
            self.effects.append(['laser', tipx, tipy, x1, y1, 0, 9])
            self.burst(x1, y1, 4, 1.5, 12)
        else:
            for _ in range(g['n']):
                a = p.aim + random.uniform(-1, 1) * g['spread'] * p.spread
                spd = g['spd'] * p.bspd * (random.uniform(0.75, 1.15) if g['kind'] == 'pellet' else 1)
                life = 120
                r = 2
                if g['kind'] == 'grenade':
                    life = 50
                    r = 3
                elif g['kind'] == 'plasma':
                    r = 5
                    life = 240
                self.bullets.append(Bullet(tipx, tipy, a, spd, dmg, g['kind'], False, life, r))
            if g['ammo'] in ('bullet', 'shell'):
                a = p.aim + math.pi / 2 * random.choice((-1, 1)) + random.uniform(-0.4, 0.4)
                self.particles.append([p.x, p.y, math.cos(a) * 1.5, math.sin(a) * 1.5,
                                       160, 1, 0.85])
        self.effects.append(['flash', tipx, tipy, 0, 0, 0, 3])
        p.wkx -= math.cos(p.aim) * g['kick'] * 0.5
        p.wky -= math.sin(p.aim) * g['kick'] * 0.5
        p.recoil = 3
        self.add_shake(g['shake'])
        self.sfx.play(g['snd'])

    def try_fire(self, p):
        w = p.weapons[0]
        g = WEAPONS[w]
        if p.cd > 0 or p.burst_left > 0:
            return
        if p.ammo[g['ammo']] < g['cost']:
            self.sfx.play('empty')
            p.cd = 20
            self.toast('NOT ENOUGH ' + {'bullet': 'BULLETS', 'shell': 'SHELLS',
                                        'explo': 'EXPLOSIVES', 'energy': 'ENERGY'}[g['ammo']])
            return
        p.ammo[g['ammo']] -= g['cost']
        p.cd = max(1, int(g['cd'] / p.fr))
        if g.get('burst'):
            p.burst_left = g['burst'] - 1
            p.burst_t = g['bdelay']
        self.fire(p, w)

    def enemy_shot(self, e, a, spd, dmg=2, r=3):
        self.bullets.append(Bullet(e.x, e.y, a, spd, dmg, 'ebullet', True, 240, r))

    def hurt_enemy(self, e, dmg, kx=0.0, ky=0.0):
        if e.dead:
            return
        e.hp -= dmg
        e.flash = 4
        e.alert = True
        kb = 0.1 if e.kind == 'boss' else 1.2
        e.kx += kx * kb
        e.ky += ky * kb
        self.sfx.play('hit')
        if e.hp <= 0:
            self.kill(e)

    def hurt_player(self, dmg):
        p = self.player
        if p.iframes > 0 or self.state != 'play':
            return
        p.hp -= dmg
        p.iframes = 40
        self.add_shake(6)
        self.freeze = 4
        self.sfx.play('hurt')
        self.burst(p.x, p.y, 8, 2.5)
        if p.hp <= 0 and p.spirit > 0:
            p.spirit -= 1
            p.hp = 1
            p.iframes = 90
            self.toast('SECOND WIND!')
        if p.hp <= 0:
            p.hp = 0
            self.state = 'dead'
            self.dead_t = 0
            self.add_shake(12)
            self.corpses.append((self.spr['player']['corpse'], p.x, p.y))
            if self.n > self.best:
                self.best = self.n
                try:
                    os.makedirs(os.path.dirname(self.best_file), exist_ok=True)
                    with open(self.best_file, 'w') as f:
                        f.write(str(self.best))
                except OSError:
                    pass

    def explode(self, x, y, r, dmg, player_dmg, from_player):
        p = self.player
        if from_player:
            r *= 1 + 0.3 * p.boom
        for e in self.enemies:
            if not e.dead and math.hypot(e.x - x, e.y - y) < r + e.r:
                a = math.atan2(e.y - y, e.x - x)
                self.hurt_enemy(e, dmg, math.cos(a) * 3, math.sin(a) * 3)
        if player_dmg and not (from_player and p.boom):
            if math.hypot(p.x - x, p.y - y) < r + p.r:
                self.hurt_player(player_dmg)
        self.level.destroy(x, y, r * 0.75)
        self.effects.append(['boom', x, y, r, 0, 0, 22])
        self.burst(x, y, 18, 3.0, 30, 2)
        self.add_shake(8)
        self.sfx.play('boom')

    def kill(self, e):
        p = self.player
        e.dead = True
        self.kills += 1
        self.last_kill = (e.x, e.y)
        self.corpses.append((self.spr[e.kind]['corpse'], e.x, e.y))
        if len(self.corpses) > 150:
            self.corpses.pop(0)
        for _ in range(e.rads):
            a = random.uniform(0, TAU)
            s = random.uniform(0.5, 2.5)
            self.pickups.append(Pickup('rad', e.x, e.y, vx=math.cos(a) * s, vy=math.sin(a) * s))
        if random.random() < 0.16 * (1 + 0.6 * p.scav):
            self.pickups.append(Pickup('ammo', e.x, e.y, life=600))
        elif random.random() < (0.1 if p.hp < p.maxhp / 2 else 0.04):
            self.pickups.append(Pickup('hp', e.x, e.y, life=600))
        if p.blood and p.hp < p.maxhp and random.random() < 0.08 * p.blood:
            p.hp += 1
            self.toast('+1 HP')
        if p.lucky and random.random() < 0.12 * p.lucky:
            t = WEAPONS[p.weapons[0]]['ammo']
            p.add_ammo(t, max(1, AMMO_DROP[t] // 3))
            self.toast('LUCKY!')
        self.burst(e.x, e.y, 8, 2.2)
        self.sfx.play('die')
        self.add_shake(2)
        if e.kind == 'bomber':
            self.explode(e.x, e.y, 30, 6, 4, False)
        if e.kind == 'boss':
            self.freeze = 25
            self.add_shake(16)
            self.boss = None
            for _ in range(4):
                self.effects.append(['boom', e.x + random.uniform(-20, 20),
                                     e.y + random.uniform(-20, 20), 26, 0, 0, 30])
            self.sfx.play('boom')

    # ---------------------------------------------------------- update
    def update(self):
        if self.freeze > 0:
            self.freeze -= 1
            return
        self.frame += 1
        p, lvl = self.player, self.level
        mx, my = pygame.mouse.get_pos()
        p.aim = math.atan2(my + self.oy - p.y, mx + self.ox - p.x)
        keys = pygame.key.get_pressed()
        mb = pygame.mouse.get_pressed()
        ix = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        iy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        if self.state == 'play':
            self.update_player(ix, iy, keys[pygame.K_SPACE] or keys[pygame.K_LSHIFT] or mb[2])
            if mb[0]:
                self.try_fire(p)
        lvl.update_flow(p.x, p.y)
        for e in self.enemies[:]:
            if not e.dead:
                self.update_enemy(e)
        self.separate()
        self.update_bullets()
        self.update_pickups()
        self.update_fx()
        self.enemies = [e for e in self.enemies if not e.dead]

        if not self.enemies and self.portal is None and self.frame > 30:
            x, y = self.last_kill
            self.portal = [x, y, 0]
            self.sfx.play('portal')
            self.add_shake(5)
        if self.portal:
            self.portal[2] += 1
            dx, dy = self.portal[0] - p.x, self.portal[1] - p.y
            d = math.hypot(dx, dy) or 1
            if d < 60 and self.portal[2] > 40:
                pull = 0.5 * (1 - d / 60) + 0.1
                p.kx += dx / d * pull
                p.ky += dy / d * pull
            if d < 9 and self.portal[2] > 40 and self.state == 'play':
                self.state = 'trans'
                self.trans_t = 0
                self.sfx.play('portal')

        # camera
        ax = clamp((mx - W / 2) * 0.3, -50, 50)
        ay = clamp((my - H / 2) * 0.3, -35, 35)
        self.camx += (p.x - p.kox + ax - W / 2 - self.camx) * 0.15
        self.camy += (p.y - p.koy + ay - H / 2 - self.camy) * 0.15
        self.snap_camera()
        self.shake *= 0.85
        if self.shake < 1:
            self.shake = 0

    def snap_camera(self):
        # Lock the integer camera to the player's integer position so the player and the
        # world move in identical 1px steps; only the (smooth) lag/aim offset changes.
        p = self.player
        self.ox = math.floor(p.x) - math.floor(p.x - self.camx)
        self.oy = math.floor(p.y) - math.floor(p.y - self.camy)

    def update_player(self, ix, iy, roll):
        p = self.player
        if p.cd > 0:
            p.cd -= 1
        if p.burst_left > 0:
            p.burst_t -= 1
            if p.burst_t <= 0:
                p.burst_left -= 1
                p.burst_t = WEAPONS[p.weapons[0]].get('bdelay', 4)
                self.fire(p, p.weapons[0])
        if p.iframes > 0:
            p.iframes -= 1
        if p.roll_cd > 0:
            p.roll_cd -= 1
        p.recoil *= 0.7
        l = math.hypot(ix, iy)
        if l:
            ix, iy = ix / l, iy / l
        if roll and p.roll_t == 0 and p.roll_cd == 0:
            if l:
                p.rdx, p.rdy = ix, iy
            else:
                p.rdx, p.rdy = math.cos(p.aim), math.sin(p.aim)
            p.roll_t = 14
            p.roll_cd = int(50 * p.roll_mult)
            p.iframes = max(p.iframes, 10)
            self.sfx.play('roll')
        if p.roll_t > 0:
            p.roll_t -= 1
            dx, dy = p.rdx * 3.2, p.rdy * 3.2
            p.vx, p.vy = dx * 0.5, dy * 0.5
            if self.frame % 3 == 0:
                self.particles.append([p.x, p.y + 3, 0, 0, 15, 1, 1])
        else:
            spd = 1.5 * p.spd
            p.vx += (ix * spd - p.vx) * 0.35
            p.vy += (iy * spd - p.vy) * 0.35
            dx, dy = p.vx, p.vy
        x0, y0 = p.x, p.y
        self.move(p, dx + p.kx + p.wkx, dy + p.ky + p.wky)
        # Credit the weapon-kick share of the actual movement to the camera offset, so the
        # camera ignores it and only drifts back to the player gently.
        tot_x, tot_y = dx + p.kx + p.wkx, dy + p.ky + p.wky
        if tot_x:
            p.kox += (p.x - x0) * p.wkx / tot_x if abs(p.wkx) < abs(tot_x) else p.x - x0
        if tot_y:
            p.koy += (p.y - y0) * p.wky / tot_y if abs(p.wky) < abs(tot_y) else p.y - y0
        p.kox *= 0.9
        p.koy *= 0.9
        p.wkx *= 0.6
        p.wky *= 0.6
        p.kx *= 0.6
        p.ky *= 0.6

    def update_enemy(self, e):
        p, lvl = self.player, self.level
        dx, dy = p.x - e.x, p.y - e.y
        dist = math.hypot(dx, dy)
        e.dist = dist
        ang = math.atan2(dy, dx)
        if (self.frame + e.id) % 5 == 0:
            e.los = dist < 330 and lvl.los(e.x, e.y, p.x, p.y)
        if not e.alert and e.los and dist < 230:
            e.alert = True
        if e.flash:
            e.flash -= 1
        mvx = mvy = 0.0
        k, spd = e.kind, e.spd

        def chase(mult=1.0):
            if e.los:
                return math.cos(ang) * spd * mult, math.sin(ang) * spd * mult
            nx, ny = lvl.nav(e.x, e.y, p.x, p.y)
            return nx * spd * mult, ny * spd * mult

        if not e.alert:
            e.wt -= 1
            if e.wt <= 0:
                e.wander = random.uniform(0, TAU)
                e.wt = random.randint(40, 120)
                e.moving = random.random() < 0.6
            if e.moving:
                mvx, mvy = math.cos(e.wander) * spd * 0.4, math.sin(e.wander) * spd * 0.4
        elif k == 'rat':
            mvx, mvy = chase()
            if dist < e.r + p.r + 1:
                self.hurt_player(1)
        elif k in ('bandit', 'shotgunner'):
            pref = 110 if k == 'bandit' else 65
            if e.los:
                e.wt -= 1
                if e.wt <= 0:
                    e.strafe = random.choice((-1, 1))
                    e.wt = random.randint(30, 90)
                if e.cd > 12:
                    pa = ang + math.pi / 2 * e.strafe
                    mvx, mvy = math.cos(pa) * spd * 0.7, math.sin(pa) * spd * 0.7
                    if dist > pref + 30:
                        mvx += math.cos(ang) * spd
                        mvy += math.sin(ang) * spd
                    elif dist < pref - 30:
                        mvx -= math.cos(ang) * spd
                        mvy -= math.sin(ang) * spd
                e.cd -= 1
                if e.cd <= 0 and dist < 240:
                    bs = 2.2 + 0.05 * min(self.n, 12)
                    if k == 'bandit':
                        self.enemy_shot(e, ang + random.uniform(-0.12, 0.12), bs)
                        e.cd = random.randint(70, 130)
                    else:
                        for i in range(5):
                            self.enemy_shot(e, ang + (i - 2) * 0.18, bs * random.uniform(0.8, 1.1))
                        e.cd = random.randint(110, 160)
                    self.sfx.play('eshot')
            else:
                mvx, mvy = chase()
        elif k == 'sniper':
            if e.aim_t > 0:
                e.aim_t -= 1
                if e.aim_t > 15 and e.los:
                    e.aim = ang
                if e.aim_t == 0:
                    self.enemy_shot(e, e.aim, 6.0, 4, 3)
                    self.sfx.play('eshot')
                    e.cd = random.randint(120, 180)
            elif e.los and dist < 330:
                e.cd -= 1
                if dist < 90:
                    mvx, mvy = -math.cos(ang) * spd, -math.sin(ang) * spd
                if e.cd <= 0:
                    e.aim_t = 70
                    e.aim = ang
                    self.sfx.play('aim')
            else:
                mvx, mvy = chase()
        elif k == 'bomber':
            if e.fuse > 0:
                e.fuse -= 1
                e.flash = 2 if (e.fuse // 3) % 2 else 0
                if e.fuse == 0:
                    self.kill(e)
                    return
            else:
                mvx, mvy = chase()
                if dist < 22:
                    e.fuse = 28
                    self.sfx.play('fuse')
        elif k == 'boss':
            self.update_boss(e, dist, ang)
            return
        e.face = 1 if dx > 0 else -1
        self.move(e, mvx + e.kx, mvy + e.ky)
        e.kx *= 0.7
        e.ky *= 0.7

    def update_boss(self, e, dist, ang):
        p = self.player
        if self.boss is None:
            self.boss = e
            self.sfx.play('portal')
        rage = e.hp < e.maxhp / 2
        spd = e.spd * (1.35 if rage else 1)
        e.pt -= 1
        mvx = mvy = 0.0
        if e.phase == 'chase':
            if e.los:
                mvx, mvy = math.cos(ang) * spd, math.sin(ang) * spd
            else:
                nx, ny = self.level.nav(e.x, e.y, p.x, p.y)
                mvx, mvy = nx * spd, ny * spd
            e.cd -= 1
            if e.cd <= 0 and e.los:
                n = 5 if rage else 3
                for i in range(n):
                    self.enemy_shot(e, ang + (i - n // 2) * 0.2, 2.6)
                self.sfx.play('eshot')
                e.cd = 30 if rage else 40
            if e.pt <= 0:
                opts = ['radial', 'dash', 'radial', 'dash']
                if sum(1 for x in self.enemies if x.kind == 'rat') < 6:
                    opts.append('summon')
                e.phase = random.choice(opts)
                e.pt = {'radial': 100, 'dash': 75, 'summon': 40}[e.phase]
        elif e.phase == 'radial':
            if e.pt % 22 == 0:
                n = 20 if rage else 16
                e.spin += 0.2
                for i in range(n):
                    self.enemy_shot(e, e.spin + i * TAU / n, 2.0)
                self.sfx.play('eshot')
                self.add_shake(2)
            if e.pt <= 0:
                e.phase, e.pt = 'chase', 120
        elif e.phase == 'dash':
            if e.pt > 40:
                e.aim = ang
                e.flash = 2 if (e.pt // 4) % 2 else 0
            else:
                hx, hy = self.move(e, math.cos(e.aim) * 4.5, math.sin(e.aim) * 4.5)
                if self.frame % 2 == 0:
                    self.particles.append([e.x, e.y, 0, 0, 20, 3, 1])
                if hx or hy:
                    self.add_shake(5)
                    e.pt = 0
            if e.pt <= 0:
                e.phase, e.pt = 'chase', 120
        elif e.phase == 'summon':
            if e.pt == 39:
                for i in range(3):
                    a = i * TAU / 3
                    r = Enemy('rat', e.x + math.cos(a) * 16, e.y + math.sin(a) * 16, 1)
                    if not self.level.box_hits(r.x, r.y, r.r):
                        r.alert = True
                        self.enemies.append(r)
                self.burst(e.x, e.y, 12, 2.5)
            if e.pt <= 0:
                e.phase, e.pt = 'chase', 120
        if dist < e.r + p.r:
            self.hurt_player(3)
        e.face = 1 if p.x > e.x else -1
        self.move(e, mvx + e.kx, mvy + e.ky)
        e.kx *= 0.7
        e.ky *= 0.7

    def separate(self):
        es = self.enemies
        for i in range(len(es)):
            a = es[i]
            if a.dead:
                continue
            for j in range(i + 1, len(es)):
                b = es[j]
                dx, dy = b.x - a.x, b.y - a.y
                md = a.r + b.r
                if b.dead or abs(dx) > md or abs(dy) > md:
                    continue
                d = math.hypot(dx, dy) or 0.01
                if d < md:
                    push = (md - d) * 0.25
                    ux, uy = dx / d * push, dy / d * push
                    if a.kind != 'boss':
                        self.move(a, -ux, -uy)
                    if b.kind != 'boss':
                        self.move(b, ux, uy)

    def update_bullets(self):
        p, lvl = self.player, self.level
        keep = []
        for b in self.bullets:
            b.life -= 1
            alive = b.life > 0
            if b.kind == 'grenade':
                b.x += b.vx
                if lvl.solid_at(b.x, b.y):
                    b.x -= b.vx
                    b.vx *= -0.6
                b.y += b.vy
                if lvl.solid_at(b.x, b.y):
                    b.y -= b.vy
                    b.vy *= -0.6
                b.vx *= 0.96
                b.vy *= 0.96
                hit = any(not e.dead and math.hypot(e.x - b.x, e.y - b.y) < e.r + b.r
                          for e in self.enemies)
                if hit or not alive:
                    self.explode(b.x, b.y, 30, 8, 3, True)
                    continue
                keep.append(b)
                continue
            b.x += b.vx
            b.y += b.vy
            if b.kind == 'pellet':
                b.vx *= 0.93
                b.vy *= 0.93
                if b.vx * b.vx + b.vy * b.vy < 1.2:
                    alive = False
            if lvl.solid_at(b.x, b.y):
                if b.kind == 'plasma':
                    self.explode(b.x - b.vx, b.y - b.vy, 22, b.dmg, 0, True)
                else:
                    self.burst(b.x - b.vx, b.y - b.vy, 3, 1.2, 10)
                continue
            if b.enemy:
                if math.hypot(p.x - b.x, p.y - b.y) < p.r + b.r - 1 and p.iframes == 0:
                    self.hurt_player(b.dmg)
                    continue
            else:
                hit = None
                for e in self.enemies:
                    if not e.dead and abs(e.x - b.x) < e.r + b.r and abs(e.y - b.y) < e.r + b.r:
                        hit = e
                        break
                if hit:
                    sp = math.hypot(b.vx, b.vy) or 1
                    if b.kind == 'plasma':
                        self.explode(b.x, b.y, 22, b.dmg, 0, True)
                        continue
                    self.hurt_enemy(hit, b.dmg, b.vx / sp * 1.5, b.vy / sp * 1.5)
                    self.burst(b.x, b.y, 3, 1.5, 10)
                    continue
            if alive:
                keep.append(b)
        self.bullets = keep

    def update_pickups(self):
        p = self.player
        keep = []
        for k in self.pickups:
            dx, dy = p.x - k.x, p.y - k.y
            d = math.hypot(dx, dy) or 1
            if k.kind == 'rad':
                if d < p.magnet or self.portal:
                    s = 2.5 if d < p.magnet else 5
                    k.vx += dx / d * 0.4
                    k.vy += dy / d * 0.4
                    sp = math.hypot(k.vx, k.vy)
                    if sp > s:
                        k.vx, k.vy = k.vx / sp * s, k.vy / sp * s
                    k.x += k.vx
                    k.y += k.vy
                else:
                    nx, ny = k.x + k.vx, k.y + k.vy
                    if not self.level.solid_at(nx, ny):
                        k.x, k.y = nx, ny
                    k.vx *= 0.88
                    k.vy *= 0.88
                if d < p.r + 4:
                    p.xp += 1
                    self.sfx.play('rad')
                    if p.xp >= p.need():
                        p.xp -= p.need()
                        p.lv += 1
                        p.pending += 1
                        self.toast('LEVEL UP!')
                        self.sfx.play('level')
                    continue
            elif k.kind in ('ammo', 'hp'):
                k.life -= 1
                if k.life <= 0:
                    continue
                if d < p.r + 6:
                    if k.kind == 'ammo':
                        types = {WEAPONS[w]['ammo'] for w in p.weapons if w}
                        for t in types:
                            p.add_ammo(t, AMMO_DROP[t])
                        self.toast('+' + ' +'.join(AMMO_LABEL[t] for t in types))
                    else:
                        if p.hp >= p.maxhp:
                            keep.append(k)
                            continue
                        p.hp = min(p.maxhp, p.hp + 2)
                        self.toast('+2 HP')
                    self.sfx.play('pickup')
                    continue
            elif k.kind in ('wchest', 'achest'):
                if d < p.r + 8:
                    self.sfx.play('chest')
                    self.burst(k.x, k.y, 10, 2)
                    if k.kind == 'wchest':
                        keep.append(Pickup('weapon', k.x, k.y, self.roll_weapon(), fresh=True))
                    else:
                        for _ in range(2):
                            keep.append(Pickup('ammo', k.x + random.uniform(-6, 6),
                                               k.y + random.uniform(-6, 6), life=900))
                        if random.random() < 0.4:
                            keep.append(Pickup('hp', k.x, k.y + 6, life=900))
                    continue
            keep.append(k)
        self.pickups = keep

    def roll_weapon(self):
        maxt = min(3, (self.n + 1) // 2)
        held = set(self.player.weapons)
        opts = [w for w, g in WEAPONS.items() if g['tier'] <= maxt and w not in held]
        weights = [1 + WEAPONS[w]['tier'] for w in opts]
        return random.choices(opts, weights)[0] if opts else 'shotgun'

    def interact(self):
        p = self.player
        best, bd = None, 18
        for k in self.pickups:
            if k.kind == 'weapon':
                d = math.hypot(k.x - p.x, k.y - p.y)
                if d < bd:
                    best, bd = k, d
        if not best:
            return
        self.pickups.remove(best)
        if p.weapons[1] is None:
            p.weapons[1] = p.weapons[0]
        else:
            self.pickups.append(Pickup('weapon', p.x, p.y, p.weapons[0]))
        p.weapons[0] = best.data
        p.burst_left = 0
        if best.fresh:
            t = WEAPONS[best.data]['ammo']
            p.add_ammo(t, AMMO_DROP[t] * 2)
        self.toast(best.data.upper())
        self.sfx.play('pickup')

    def swap(self):
        p = self.player
        if p.weapons[1]:
            p.weapons.reverse()
            p.burst_left = 0
            p.cd = max(p.cd, 6)
            self.sfx.play('swap')
            self.toast(p.weapons[0].upper())

    def update_fx(self):
        keep = []
        for q in self.particles:
            q[0] += q[2]
            q[1] += q[3]
            q[2] *= q[6]
            q[3] *= q[6]
            q[4] -= 1
            if q[4] > 0:
                keep.append(q)
        self.particles = keep[-600:]
        for f in self.effects:
            f[5] += 1
        self.effects = [f for f in self.effects if f[5] < f[6]]
        for t in self.texts:
            t[1] -= 0.3
            t[3] -= 1
        self.texts = [t for t in self.texts if t[3] > 0]

    # ---------------------------------------------------------- mutation
    def open_mutations(self):
        self.state = 'mutate'
        self.mut_opts = random.sample(MUTATIONS, 4)
        self.mut_t = 0

    def pick_mutation(self, i):
        if self.mut_t < 15:
            return
        p = self.player
        name, _, effects = self.mut_opts[i]
        for attr, op, v in effects:
            cur = getattr(p, attr)
            setattr(p, attr, cur + v if op == '+' else cur * v)
        p.hp = min(p.hp, p.maxhp)
        p.muts.append(name)
        p.pending -= 1
        self.sfx.play('level')
        if p.pending > 0:
            self.open_mutations()
        else:
            self.next_level()

    def next_level(self):
        self.n += 1
        self.start_level()
        self.state = 'play'

    # ---------------------------------------------------------- draw
    def draw_world(self):
        s = self.screen
        sh = int(self.shake)
        ox = self.ox + (random.randint(-sh, sh) if sh else 0)
        oy = self.oy + (random.randint(-sh, sh) if sh else 0)
        s.fill(BLACK)
        s.blit(self.level.surf, (-ox, -oy))
        for img, x, y in self.corpses:
            s.blit(img, (int(x - ox) - img.get_width() // 2, int(y - oy) - img.get_height() // 2))
        fr = self.frame
        for k in self.pickups:
            x, y = int(k.x - ox), int(k.y - oy)
            if k.life > 0 and k.life < 120 and (fr // 4) % 2:
                continue
            if k.kind == 'rad':
                s.fill(WHITE, (x - 1, y - 1, 2 + (fr // 8 + int(k.x)) % 2, 2))
            elif k.kind == 'ammo':
                pygame.draw.rect(s, WHITE, (x - 4, y - 3, 8, 6), 1)
                s.fill(WHITE, (x - 2, y - 1, 1, 2))
                s.fill(WHITE, (x, y - 1, 1, 2))
                s.fill(WHITE, (x + 2, y - 1, 1, 2))
            elif k.kind == 'hp':
                s.fill(WHITE, (x - 1, y - 4, 3, 9))
                s.fill(WHITE, (x - 4, y - 1, 9, 3))
            elif k.kind == 'wchest':
                pygame.draw.rect(s, WHITE, (x - 7, y - 5, 14, 10))
                s.fill(BLACK, (x - 6, y - 1, 12, 1))
                s.fill(BLACK, (x - 1, y - 2, 2, 3))
            elif k.kind == 'achest':
                pygame.draw.rect(s, WHITE, (x - 6, y - 4, 12, 8), 1)
                for i in range(-3, 4, 2):
                    s.fill(WHITE, (x + i, y - 2, 1, 4))
            elif k.kind == 'weapon':
                bob = int(math.sin(fr * 0.1 + k.x) * 1.5)
                pygame.draw.line(s, WHITE, (x - 5, y + bob), (x + 5, y + bob), 3)
                s.fill(WHITE, (x - 4, y + bob, 2, 4))
                if math.hypot(k.x - self.player.x, k.y - self.player.y) < 18:
                    draw_text(s, 'E: ' + k.data, x, y - 12, align='c')
        if self.portal:
            x, y, t = self.portal
            x, y = int(x - ox), int(y - oy)
            rr = min(14, t * 0.5)
            for i in range(3):
                r = rr * (1 - ((t * 0.04 + i / 3) % 1))
                if r > 1:
                    pygame.draw.circle(s, WHITE, (x, y), int(r), 1)
            pygame.draw.circle(s, WHITE, (x, y), max(1, int(rr * 0.25)))
        for e in self.enemies:
            spr = self.spr[e.kind][e.face]
            img = spr[1] if e.flash else spr[0]
            x, y = int(e.x - ox), int(e.y - oy)
            s.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2))
            if e.alert and e.kind in ('bandit', 'shotgunner'):
                a = math.atan2(self.player.y - e.y, self.player.x - e.x)
                pygame.draw.line(s, WHITE, (x, y + 2),
                                 (x + math.cos(a) * 7, y + 2 + math.sin(a) * 7), 2)
            if e.kind == 'sniper' and e.aim_t > 0 and (e.aim_t > 15 or fr % 2):
                x1, y1 = self.level.ray(e.x, e.y, e.aim, 330, 3)
                n = int(math.hypot(x1 - e.x, y1 - e.y) / 4)
                c, sn = math.cos(e.aim) * 4, math.sin(e.aim) * 4
                for i in range(1, n):
                    s.set_at((int(e.x + c * i - ox), int(e.y + sn * i - oy)), WHITE)
        p = self.player
        if self.state != 'dead' and not (p.iframes > 0 and (fr // 3) % 2 and p.roll_t == 0):
            face = 1 if math.cos(p.aim) >= 0 else -1
            x, y = int(p.x - ox), int(p.y - oy)
            g = WEAPONS[p.weapons[0]]
            c, sn = math.cos(p.aim), math.sin(p.aim)
            back = p.recoil
            gun = ((x + c * (2 - back), y + 1 + sn * (2 - back)),
                   (x + c * (g['len'] - back), y + 1 + sn * (g['len'] - back)))
            width = 3 if g['ammo'] in ('explo', 'energy') or g['kind'] == 'pellet' else 2
            if sn < 0:
                pygame.draw.line(s, WHITE, *gun, width)
            img = self.spr['player'][face][0]
            if p.roll_t > 0:
                img = pygame.transform.rotate(img, -face * p.roll_t * 26)
            s.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2))
            if sn >= 0:
                pygame.draw.line(s, BLACK, *gun, width + 2)
                pygame.draw.line(s, WHITE, *gun, width)
        for b in self.bullets:
            x, y = int(b.x - ox), int(b.y - oy)
            if b.enemy:
                pygame.draw.circle(s, WHITE, (x, y), b.r)
                pygame.draw.circle(s, BLACK, (x, y), b.r - 2)
            elif b.kind == 'bullet':
                pygame.draw.line(s, WHITE, (x, y), (int(x - b.vx), int(y - b.vy)), 2)
            elif b.kind == 'pellet':
                s.fill(WHITE, (x - 1, y - 1, 2, 2))
            elif b.kind == 'grenade':
                pygame.draw.circle(s, WHITE, (x, y), 3)
                if (b.life // 4) % 2:
                    pygame.draw.circle(s, BLACK, (x, y), 1)
            elif b.kind == 'plasma':
                pygame.draw.circle(s, WHITE, (x, y), 4)
                pygame.draw.circle(s, WHITE, (x, y), 6 + (fr // 3) % 2, 1)
        for q in self.particles:
            sz = q[5]
            s.fill(WHITE, (int(q[0] - ox), int(q[1] - oy), sz, sz))
        for f in self.effects:
            k, t, life = f[0], f[5], f[6]
            if k == 'boom':
                x, y, r = int(f[1] - ox), int(f[2] - oy), f[3]
                if t < 4:
                    pygame.draw.circle(s, WHITE, (x, y), int(r))
                else:
                    rr = int(r * (0.7 + 0.5 * t / life))
                    pygame.draw.circle(s, WHITE, (x, y), rr, max(1, 4 - t // 5))
            elif k == 'laser':
                pygame.draw.line(s, WHITE, (f[1] - ox, f[2] - oy), (f[3] - ox, f[4] - oy),
                                 3 if t < 3 else 1)
            elif k == 'flash':
                pygame.draw.circle(s, WHITE, (int(f[1] - ox), int(f[2] - oy)), 4 - t)
        for x, y, txt, life in self.texts:
            if life > 10 or fr % 2:
                draw_text(s, txt, int(x - ox), int(y - oy), align='c')
        # arrows to the portal / last few enemies
        targets = []
        if self.portal:
            targets = [(self.portal[0], self.portal[1])]
        elif len(self.enemies) <= 3:
            targets = [(e.x, e.y) for e in self.enemies]
        for tx, ty in targets:
            sx, sy = tx - ox, ty - oy
            if 0 <= sx < W and 0 <= sy < H:
                continue
            a = math.atan2(sy - H / 2, sx - W / 2)
            c, sn = math.cos(a), math.sin(a)
            k = min((W / 2 - 10) / abs(c) if c else 1e9, (H / 2 - 10) / abs(sn) if sn else 1e9)
            ax, ay = W / 2 + c * k, H / 2 + sn * k
            pts = [(ax + c * 5, ay + sn * 5), (ax - c * 3 - sn * 4, ay - sn * 3 + c * 4),
                   (ax - c * 3 + sn * 4, ay - sn * 3 - c * 4)]
            pygame.draw.polygon(s, WHITE, pts)
        return ox, oy

    def draw_hud(self):
        s, p = self.screen, self.player
        pygame.draw.rect(s, BLACK, (3, 3, 54, 9))
        pygame.draw.rect(s, WHITE, (3, 3, 54, 9), 1)
        s.fill(WHITE, (5, 5, int(50 * p.hp / p.maxhp), 5))
        draw_text(s, f'{p.hp}/{p.maxhp}', 61, 5)
        s.fill(BLACK, (3, 14, 54, 4))
        pygame.draw.rect(s, WHITE, (3, 14, 54, 4), 1)
        s.fill(WHITE, (4, 15, int(52 * p.xp / p.need()), 2))
        lvtxt = f'LV{p.lv}' + (' +' * p.pending)
        draw_text(s, lvtxt, 61, 14)
        draw_text(s, '> ' + p.weapons[0], 4, 22)
        if p.weapons[1]:
            draw_text(s, '  ' + p.weapons[1], 4, 30)
        cur = WEAPONS[p.weapons[0]]['ammo']
        x = 4
        for t in AMMO_TYPES:
            txt = f'{AMMO_LABEL[t]} {p.ammo[t]}'
            w = len(txt) * 4 + 3
            if t == cur:
                s.fill(WHITE, (x - 2, H - 11, w, 9))
                draw_text(s, txt, x, H - 9, color=BLACK, outline=False)
            else:
                draw_text(s, txt, x, H - 9)
            x += w + 4
        draw_text(s, 'AREA ' + self.level_name(self.n), W - 4, 4, align='r')
        draw_text(s, f'KILLS {self.kills}', W - 4, 12, align='r')
        if self.enemies and len(self.enemies) <= 3 and not self.boss:
            draw_text(s, f'{len(self.enemies)} LEFT', W - 4, 20, align='r')
        b = self.boss
        if b and not b.dead:
            draw_text(s, 'THE WARDEN', W // 2, 6, align='c')
            pygame.draw.rect(s, WHITE, (W // 2 - 80, 13, 160, 6), 1)
            s.fill(WHITE, (W // 2 - 78, 15, int(156 * max(0, b.hp) / b.maxhp), 2))

    def draw_cursor(self):
        mx, my = pygame.mouse.get_pos()
        s = self.screen
        for col, w in ((BLACK, 3), (WHITE, 1)):
            for a, b in (((mx - 5, my), (mx - 2, my)), ((mx + 2, my), (mx + 5, my)),
                         ((mx, my - 5), (mx, my - 2)), ((mx, my + 2), (mx, my + 5))):
                pygame.draw.line(s, col, a, b, w)
        s.set_at((mx, my), WHITE)

    def draw_title(self):
        s = self.screen
        s.fill(BLACK)
        for st in self.stars:
            st[0] -= st[2]
            if st[0] < 0:
                st[0], st[1] = W, random.uniform(0, H)
            s.fill(WHITE, (int(st[0]), int(st[1]), 1 + int(st[2] > 1), 1))
        draw_text(s, 'NEGATIVE', W // 2, 40, 5, 'c')
        draw_text(s, 'A ONE-BIT ROGUELIKE', W // 2, 72, 1, 'c')
        lines = ['WASD  MOVE', 'MOUSE  AIM', 'LMB  FIRE', 'RMB / SPACE  ROLL',
                 'E  PICK UP WEAPON', 'Q / WHEEL  SWAP WEAPON', 'ESC  PAUSE    F11  FULLSCREEN']
        for i, l in enumerate(lines):
            draw_text(s, l, W // 2, 96 + i * 9, 1, 'c')
        if (self.t // 30) % 2:
            draw_text(s, 'CLICK TO START', W // 2, 170, 2, 'c')
        if self.best:
            draw_text(s, 'BEST: ' + self.level_name(self.best), W // 2, 200, 1, 'c')

    def draw_mutate(self):
        s = self.screen
        s.fill(BLACK)
        self.mut_t += 1
        draw_text(s, 'MUTATION', W // 2, 22, 3, 'c')
        draw_text(s, 'CHOOSE ONE  (1-4 OR CLICK)', W // 2, 44, 1, 'c')
        mx, my = pygame.mouse.get_pos()
        self.mut_rects = []
        bw, bh, gap = 90, 96, 6
        x0 = (W - (bw * 4 + gap * 3)) // 2
        for i, (name, desc, _) in enumerate(self.mut_opts):
            r = pygame.Rect(x0 + i * (bw + gap), 64, bw, bh)
            self.mut_rects.append(r)
            hover = r.collidepoint(mx, my)
            col = BLACK if hover else WHITE
            if hover:
                s.fill(WHITE, r)
            else:
                pygame.draw.rect(s, WHITE, r, 1)
            draw_text(s, str(i + 1), r.centerx, r.y + 6, 2, 'c', col, False)
            for j, line in enumerate(wrap(name, 20)):
                draw_text(s, line, r.centerx, r.y + 24 + j * 7, 1, 'c', col, False)
            for j, line in enumerate(wrap(desc, 20)):
                draw_text(s, line, r.centerx, r.y + 48 + j * 8, 1, 'c', col, False)
        p = self.player
        if p.muts:
            draw_text(s, 'HAVE: ' + ', '.join(p.muts[-6:]), W // 2, 176, 1, 'c')
        draw_text(s, f'NEXT: AREA {self.level_name(self.n + 1)}', W // 2, 200, 1, 'c')

    def draw(self):
        s = self.screen
        if self.state == 'title':
            self.draw_title()
        elif self.state == 'mutate':
            self.draw_mutate()
        else:
            self.draw_world()
            self.draw_hud()
            if self.state == 'pause':
                s.blit(self.dim, (0, 0))
                draw_text(s, 'PAUSED', W // 2, 70, 3, 'c')
                draw_text(s, 'ESC  RESUME', W // 2, 105, 1, 'c')
                draw_text(s, 'X  QUIT TO TITLE', W // 2, 115, 1, 'c')
                if self.player.muts:
                    draw_text(s, ', '.join(self.player.muts), W // 2, 140, 1, 'c')
            elif self.state == 'dead':
                self.dead_t += 1
                s.blit(self.dim, (0, 0))
                draw_text(s, 'YOU DIED', W // 2, 60, 4, 'c')
                draw_text(s, f'REACHED {self.level_name(self.n)}   KILLS {self.kills}   '
                             f'LV {self.player.lv}', W // 2, 100, 1, 'c')
                draw_text(s, 'BEST: ' + self.level_name(self.best), W // 2, 112, 1, 'c')
                if self.dead_t > 40:
                    draw_text(s, 'R OR CLICK TO RETRY', W // 2, 140, 2, 'c')
            elif self.state == 'trans':
                self.trans_t += 1
                pygame.draw.circle(s, WHITE, (W // 2, H // 2), self.trans_t * 9)
        self.draw_cursor()

    # ---------------------------------------------------------- loop
    def handle(self, ev):
        st = self.state
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
        click = ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
        key = ev.key if ev.type == pygame.KEYDOWN else None
        if st == 'title':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE):
                self.new_run()
            elif key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
        elif st == 'play':
            if key == pygame.K_ESCAPE:
                self.state = 'pause'
            elif key == pygame.K_e:
                self.interact()
            elif key == pygame.K_q:
                self.swap()
            elif ev.type == pygame.MOUSEWHEEL:
                self.swap()
        elif st == 'pause':
            if key == pygame.K_ESCAPE:
                self.state = 'play'
            elif key == pygame.K_x:
                self.state = 'title'
        elif st == 'mutate':
            if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.pick_mutation(key - pygame.K_1)
            elif click:
                for i, r in enumerate(getattr(self, 'mut_rects', [])):
                    if r.collidepoint(ev.pos):
                        self.pick_mutation(i)
        elif st == 'dead':
            if self.dead_t > 40 and (click or key == pygame.K_r):
                self.new_run()
            elif key == pygame.K_ESCAPE:
                self.state = 'title'

    def step(self):
        self.t += 1
        if self.state in ('play', 'dead'):
            self.update()
        elif self.state == 'trans' and self.trans_t > 28:
            if self.player.pending > 0:
                self.open_mutations()
            else:
                self.next_level()

    def run(self):
        while True:
            for ev in pygame.event.get():
                self.handle(ev)
            self.step()
            self.draw()
            pygame.display.flip()
            self.clock.tick(60)


if __name__ == '__main__':
    Game().run()
