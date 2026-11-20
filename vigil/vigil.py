#!/usr/bin/env python3
"""VIGIL - a tiny dark-fantasy wave-survival roguelike.

WASD move · your weapons strike on their own · survive each wave, spend souls between them
ESC pause · F11 fullscreen/window (--windowed starts in a window)
"""
import array
import math
import os
import random
import sys

import pygame

W, H = 400, 225
CH = 200                       # ground chunk size (px)
G = 20                         # spatial grid cell (px)
BLACK = (8, 6, 7)
BONE = (222, 210, 186)
BLOOD = (176, 22, 30)
KEY = (255, 0, 255)
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
TAU = math.tau
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]

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


def angdiff(a, b):
    return (a - b + math.pi) % TAU - math.pi


# ------------------------------------------------------------------ sound
class Sfx:
    SPECS = {  # dur, f0, f1, noise, vol, wave
        'swing': (0.09, 500, 150, 0.85, 0.09, 'sq'),
        'stab': (0.06, 700, 300, 0.7, 0.08, 'sq'),
        'hit': (0.07, 260, 60, 0.6, 0.16, 'sq'),
        'cast': (0.16, 300, 1100, 0.05, 0.1, 'sin'),
        'boom': (0.45, 110, 25, 0.85, 0.3, 'sq'),
        'hurt': (0.25, 300, 60, 0.45, 0.35, 'sq'),
        'soul': (0.04, 1200, 1700, 0.0, 0.04, 'sin'),
        'level': (0.4, 300, 900, 0.0, 0.15, 'sin'),
        'bolt': (0.12, 700, 300, 0.2, 0.08, 'sin'),
        'arrow': (0.08, 1100, 400, 0.5, 0.09, 'sq'),
        'die': (0.12, 220, 50, 0.6, 0.14, 'sq'),
        'buy': (0.2, 150, 500, 0.3, 0.18, 'sq'),
        'sell': (0.15, 800, 300, 0.0, 0.12, 'sin'),
        'toll': (1.2, 110, 108, 0.0, 0.3, 'sin'),
        'clear': (0.9, 200, 600, 0.1, 0.2, 'sin'),
        'zap': (0.12, 1500, 300, 0.5, 0.1, 'sq'),
        'throw': (0.1, 300, 500, 0.6, 0.07, 'sq'),
        'bark': (0.15, 400, 150, 0.5, 0.14, 'sq'),
        'charge': (0.8, 120, 600, 0.15, 0.12, 'sin'),
        'empty': (0.05, 160, 140, 0.0, 0.1, 'sq'),
        'drink': (0.3, 200, 500, 0.3, 0.15, 'sin'),
    }

    def __init__(self):
        self.ok = False
        self.s = {}
        self.last = {}
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
            v = (1.0 if (ph % 1.0) < 0.5 else -1.0) if wave == 'sq' else math.sin(ph * TAU)
            if noise:
                v = v * (1 - noise) + (rnd() * 2 - 1) * noise
            s = int(v * (1 - t) ** 2 * vol * 32767)
            for _ in range(ch):
                buf.append(s)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        # a horde makes a lot of noise: the same sound at most every 50 ms
        if self.ok:
            now = pygame.time.get_ticks()
            if now - self.last.get(name, -999) >= 50:
                self.last[name] = now
                self.s[name].play()


# ------------------------------------------------------------------ data
WEAPONS = {
    'dagger': dict(kind='thrust', dmg=5, cd=30, rng=32, crit=15, kb=1.5, price=14,
                   desc='QUICK STABS THAT CRIT OFTEN'),
    'sword': dict(kind='sweep', dmg=8, cd=50, rng=36, arc=1.8, kb=2.5, price=18,
                  desc='SWEEPS AN ARC'),
    'spear': dict(kind='thrust', dmg=11, cd=60, rng=58, kb=3.5, price=20,
                  desc='LONG THRUST THROUGH A LINE OF FOES'),
    'scythe': dict(kind='sweep', dmg=13, cd=86, rng=46, arc=2.8, kb=3.0, price=24,
                   desc='WIDE REAPING SWEEP'),
    'crossbow': dict(kind='bolt', dmg=10, cd=66, rng=170, kb=1.5, price=20,
                     desc='BOLTS PIERCE ONE FOE MORE PER TIER'),
    'wand': dict(kind='fire', dmg=7, cd=58, rng=150, kb=1.0, price=22,
                 desc='FIREBOLTS BURST ON IMPACT'),
    'hexstaff': dict(kind='chain', dmg=6, cd=62, rng=130, kb=0.5, price=24,
                     desc='A HEX LEAPS FROM FOE TO FOE'),
    'axe': dict(kind='axe', dmg=8, cd=80, rng=110, kb=2.0, price=20,
                desc='THROWN: CUTS GOING OUT AND COMING BACK'),
    'skulls': dict(kind='orbit', dmg=5, cd=36, rng=24, kb=1.5, price=22,
                   desc='SKULLS CIRCLE YOU, ONE MORE PER TIER'),
}
TIER_DMG = (1.0, 1.6, 2.4, 3.5)
TIER_CD = (1.0, 0.9, 0.8, 0.7)
TIER_PRICE = (1.0, 2.1, 3.8, 6.5)
ROMAN = ('I', 'II', 'III', 'IV')
MELEE = ('thrust', 'sweep')
THRUST = (0.2, 0.6, 0.95, 1.0, 0.95, 0.8, 0.6, 0.42, 0.28, 0.16, 0.08, 0.03)
SWEEP_T = 14

ENEMIES = {
    'ghoul': dict(hp=6, r=5, spd=0.75, dmg=2, souls=1),
    'bat': dict(hp=3, r=3, spd=1.25, dmg=1, souls=1),
    'cultist': dict(hp=9, r=5, spd=0.55, dmg=2, souls=2),
    'hound': dict(hp=12, r=5, spd=0.7, dmg=3, souls=2),
    'revenant': dict(hp=45, r=7, spd=0.45, dmg=4, souls=5),
    'bloater': dict(hp=14, r=6, spd=0.5, dmg=2, souls=2),
    'boss': dict(hp=320, r=13, spd=0.6, dmg=5, souls=40),
}
UNLOCK = {'ghoul': (1, 10), 'bat': (2, 6), 'cultist': (3, 3), 'hound': (5, 3),
          'revenant': (6, 2), 'bloater': (8, 3)}   # first wave, spawn weight
EYES = {'ghoul': [(1, -3), (3, -3)], 'cultist': [(0, -3), (2, -3)], 'bat': [(-1, 0), (1, 0)],
        'revenant': [(0, -5), (2, -5)], 'boss': [(-2, -7), (2, -7)], 'hound': [(5, -2)],
        'bloater': [(-1, -5), (1, -5)]}
BOSS_NAME = 'THE PALE SHEPHERD'
KB_RESIST = {'revenant': 0.4, 'boss': 0.0}

STATS = [  # attr, label, percent?
    ('maxhp', 'MAX HP', False), ('regen', 'REGEN', False), ('steal', 'LIFESTEAL', True),
    ('dmg', 'DAMAGE', True), ('aspd', 'ATK SPEED', True), ('crit', 'CRIT', True),
    ('armor', 'ARMOR', False), ('dodge', 'DODGE', True), ('speed', 'SPEED', True),
    ('range', 'RANGE', False), ('magnet', 'PICKUP', False), ('greed', 'GREED', True),
]
LABEL = {a: (l, pct) for a, l, pct in STATS}
LABEL['plague'] = ('PLAGUE', True)
LABEL['thorns'] = ('THORNS', False)

STAT_UPS = [  # level-up boons: name, attr, amount per tier
    ('VIGOR', 'maxhp', 3), ('MENDING', 'regen', 1), ('THIRST', 'steal', 2),
    ('WRATH', 'dmg', 6), ('HASTE', 'aspd', 6), ('CRUELTY', 'crit', 4),
    ('BULWARK', 'armor', 1), ('EVASION', 'dodge', 3), ('SWIFTNESS', 'speed', 4),
    ('REACH', 'range', 10), ('LODESTONE', 'magnet', 15), ('AVARICE', 'greed', 8),
]

RELICS = [  # name, effects, price, description override
    ('GRAVE DIRT', [('armor', 3), ('speed', -3)], 24, None),
    ('VAMPIRE FANG', [('steal', 4)], 30, None),
    ('CRACKED HOURGLASS', [('aspd', 14), ('dmg', -4)], 30, None),
    ("WITCH'S EYE", [('crit', 8)], 28, None),
    ('IRON HEART', [('maxhp', 8), ('speed', -2)], 28, None),
    ('BLACK CANDLE', [('dmg', 15), ('maxhp', -3)], 32, None),
    ('WOLF PELT', [('speed', 10)], 22, None),
    ('ROSARY', [('regen', 3)], 24, None),
    ('LONG SHADOW', [('range', 25)], 26, None),
    ('LODESTONE', [('magnet', 40)], 14, None),
    ('GILDED SKULL', [('greed', 20)], 30, None),
    ('BONE CHARM', [('dodge', 8)], 28, None),
    ('PLAGUE FLASK', [('plague', 20)], 34, '1 IN 5 KILLS BURSTS, HURTING NEARBY FOES'),
    ('THORN MAIL', [('thorns', 6), ('armor', 1)], 26, 'FOES THAT TOUCH YOU TAKE 6 DAMAGE. ARMOR +1'),
]


def fmt_effect(attr, v):
    label, pct = LABEL[attr]
    return f'{label} {v:+d}{"%" if pct else ""}'


# ------------------------------------------------------------------ graphics
def dither_corpse(img):
    corpse = pygame.transform.rotate(img, 90)
    for y in range(corpse.get_height()):
        for x in range(corpse.get_width()):
            if (x + y) % 2:
                corpse.set_at((x, y), (0, 0, 0, 0))
    return corpse


def make_sprites():
    def ghoul(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.circle(s, c, (7, 3), 3, w)
        pygame.draw.polygon(s, c, [(3, 5), (9, 5), (10, 12), (2, 12)], w)
        pygame.draw.line(s, c, (9, 7), (12, 10))
        pygame.draw.line(s, c, (3, 7), (1, 11))

    def cultist(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.polygon(s, c, [(6, 0), (10, 5), (11, 14), (1, 14), (2, 5)], w)
        pygame.draw.ellipse(s, BLACK, (5, 2, 5, 4))

    def bat(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.polygon(s, c, [(0, 1), (3, 3), (4, 1), (6, 3), (8, 1), (9, 3), (12, 1),
                                   (10, 6), (6, 5), (2, 6)], w)
        pygame.draw.circle(s, c, (6, 3), 2)

    def revenant(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.rect(s, c, (3, 6, 11, 10), w)
        pygame.draw.rect(s, c, (5, 0, 8, 7), w)
        pygame.draw.line(s, BLACK, (7, 3), (11, 3))
        pygame.draw.circle(s, c, (3, 7), 2, w)
        pygame.draw.circle(s, c, (13, 7), 2, w)
        pygame.draw.line(s, c, (15, 2), (15, 15))

    def hound(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.ellipse(s, c, (2, 2, 10, 5), w)
        pygame.draw.circle(s, c, (12, 3), 2, w)
        pygame.draw.line(s, c, (13, 4), (14, 5))
        pygame.draw.line(s, c, (11, 1), (11, 0))
        for lx, fx in ((3, 2), (5, 6), (9, 8), (11, 12)):
            pygame.draw.line(s, c, (lx, 6), (fx, 8))
        pygame.draw.line(s, c, (2, 3), (0, 1))

    def bloater(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.circle(s, c, (7, 8), 6, w)
        pygame.draw.circle(s, c, (7, 2), 2, w)
        pygame.draw.line(s, BLACK if f else c, (4, 10), (10, 10))
        for sx in (5, 7, 9):
            s.set_at((sx, 9), BLACK if f else c)
            s.set_at((sx, 11), BLACK if f else c)
        pygame.draw.line(s, c, (1, 8), (0, 12))
        pygame.draw.line(s, c, (13, 8), (14, 12))

    def boss(s, f):
        w, c = (0, BLOOD) if f else (2, BONE)
        pygame.draw.polygon(s, c, [(16, 6), (26, 14), (29, 33), (3, 33), (6, 14)], w)
        pygame.draw.circle(s, c, (16, 10), 5, 0 if f else 1)
        pygame.draw.circle(s, BLACK, (16, 10), 4)
        pygame.draw.polygon(s, c, [(10, 6), (11, 0), (13, 4), (16, 0), (19, 4), (21, 0),
                                   (22, 6)], 0 if f else 1)
        pygame.draw.line(s, c, (16, 16), (16, 30), 1)
        pygame.draw.line(s, c, (31, 4), (31, 33))     # the shepherd's crook
        pygame.draw.arc(s, c, (27, 0, 6, 7), 0, math.pi)

    defs = {'ghoul': (13, 13, ghoul), 'cultist': (13, 15, cultist), 'bat': (13, 7, bat),
            'revenant': (17, 17, revenant), 'hound': (15, 9, hound),
            'bloater': (15, 15, bloater), 'boss': (34, 34, boss)}
    S = {}
    for k, (w, h, fn) in defs.items():
        a = pygame.Surface((w, h), pygame.SRCALPHA)
        b = pygame.Surface((w, h), pygame.SRCALPHA)
        fn(a, False)
        fn(b, True)
        S[k] = {1: (a, b), -1: (pygame.transform.flip(a, True, False),
                                pygame.transform.flip(b, True, False)),
                'corpse': dither_corpse(a)}
    return S


def make_knight():
    """Four-frame walk cycle of the knight, facing right and flipped, plus a corpse."""
    frames = {1: [], -1: []}
    for f in range(4):
        s = pygame.Surface((13, 19), pygame.SRCALPHA)
        flap = (0, 1, 2, 1)[f]
        stride = (0, 1, 0, -1)[f]
        pygame.draw.polygon(s, BLOOD, [(4, 8), (7, 8), (6, 15), (2 - flap // 2, 17),
                                       (max(0, 2 - flap), 13)])
        s.fill(BONE, (5 + stride, 15, 2, 3))
        s.fill(BONE, (8 - stride, 15, 2, 3))
        if f % 2:
            s.fill(BLACK, (5 + stride, 17, 2, 1))
        pygame.draw.rect(s, BONE, (4, 8, 6, 7), border_radius=1)
        s.fill(BLACK, (4, 13, 6, 1))
        s.set_at((7, 13), BLOOD)
        s.fill(BLACK, (6, 9, 1, 3))
        s.fill(BLACK, (5, 10, 3, 1))
        pygame.draw.circle(s, BONE, (8, 8), 2)
        s.set_at((7, 9), BLACK)
        s.fill(BONE, (9, 10, 2, 2))
        pygame.draw.rect(s, BONE, (4, 2, 6, 7), border_radius=2)
        s.fill(BLACK, (7, 4, 3, 1))
        s.set_at((8, 6), BLACK)
        s.set_at((8, 7), BLACK)
        s.set_at((4, 8), BLACK)
        for px, py in ((6, 1), (5, 0), (4, 0), (5, 1), (4, 1), (3, 1), (2, 2),
                       (1, 3 + flap % 2), (0, 4 + flap // 2)):
            s.set_at((px, py), BLOOD)
        frames[1].append(s)
        frames[-1].append(pygame.transform.flip(s, True, False))
    frames['corpse'] = dither_corpse(frames[1][0])
    return frames


def draw_skull(s, x, y):
    pygame.draw.circle(s, BONE, (x, y), 3)
    s.fill(BONE, (x - 1, y + 2, 3, 2))
    s.set_at((x - 1, y), BLACK)
    s.set_at((x + 1, y), BLACK)
    s.set_at((x, y + 3), BLACK)


WLEN = {'sword': 15, 'dagger': 9, 'spear': 23, 'scythe': 18, 'axe': 13, 'crossbow': 13,
        'wand': 15, 'hexstaff': 17, 'skulls': 8}


def make_weapon_sprites():
    """Each weapon points right with its grip on the surface centre, pre-rotated to 64 angles."""
    def sword(s, x, c):
        s.set_at((x, c), BONE)
        s.fill(BLOOD, (x + 1, c, 3, 1))
        s.fill(BONE, (x + 4, c - 2, 1, 5))
        s.fill(BONE, (x + 5, c - 1, 9, 3))
        s.fill(BLACK, (x + 6, c, 7, 1))
        s.set_at((x + 14, c), BONE)

    def dagger(s, x, c):
        s.set_at((x, c), BONE)
        s.fill(BLOOD, (x + 1, c, 2, 1))
        s.fill(BONE, (x + 3, c - 1, 1, 3))
        s.fill(BONE, (x + 4, c - 1, 4, 2))
        s.set_at((x + 8, c - 1), BONE)

    def spear(s, x, c):
        s.fill(BONE, (x, c, 18, 1))
        s.fill(BLOOD, (x + 15, c + 1, 2, 2))
        pygame.draw.polygon(s, BONE, [(x + 17, c - 2), (x + 22, c), (x + 17, c + 2)])
        s.set_at((x + 18, c), BLACK)

    def scythe(s, x, c):
        s.fill(BONE, (x, c, 17, 1))
        s.fill(BLOOD, (x + 1, c, 2, 1))
        s.fill(BONE, (x + 8, c + 1, 1, 2))
        pygame.draw.polygon(s, BONE, [(x + 16, c - 1), (x + 17, c + 1), (x + 13, c + 5),
                                      (x + 6, c + 7), (x + 1, c + 7), (x + 7, c + 5),
                                      (x + 12, c + 2)])

    def axe(s, x, c):
        s.fill(BONE, (x, c, 11, 1))
        s.fill(BLOOD, (x + 1, c, 2, 1))
        pygame.draw.polygon(s, BONE, [(x + 8, c - 1), (x + 10, c - 4), (x + 12, c - 5),
                                      (x + 12, c + 2), (x + 10, c + 1)])
        s.set_at((x + 11, c - 2), BLACK)

    def crossbow(s, x, c):
        s.fill(BONE, (x, c, 12, 1))
        s.fill(BLOOD, (x + 1, c, 3, 1))
        pygame.draw.lines(s, BONE, False, [(x + 7, c - 5), (x + 10, c - 2), (x + 10, c + 2),
                                           (x + 7, c + 5)])
        pygame.draw.line(s, BLOOD, (x + 7, c - 4), (x + 5, c))
        pygame.draw.line(s, BLOOD, (x + 5, c), (x + 7, c + 4))
        s.set_at((x + 12, c), BONE)

    def wand(s, x, c):
        s.fill(BONE, (x, c, 11, 1))
        s.fill(BLOOD, (x + 1, c, 2, 1))
        s.fill(BONE, (x + 10, c - 1, 1, 3))
        pygame.draw.circle(s, BLOOD, (x + 13, c), 2)
        s.set_at((x + 13, c), BONE)

    def hexstaff(s, x, c):
        s.fill(BONE, (x, c, 14, 1))
        s.fill(BLOOD, (x + 1, c, 2, 1))
        pygame.draw.lines(s, BONE, False, [(x + 13, c), (x + 16, c - 2), (x + 15, c - 4),
                                           (x + 13, c - 4)])
        s.set_at((x + 15, c - 2), BLOOD)

    def skulls(s, x, c):
        draw_skull(s, x + 4, c)

    fns = {'sword': sword, 'dagger': dagger, 'spear': spear, 'scythe': scythe, 'axe': axe,
           'crossbow': crossbow, 'wand': wand, 'hexstaff': hexstaff, 'skulls': skulls}
    out = {}
    for name, fn in fns.items():
        size = 2 * WLEN[name] + 5
        base = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        fn(base, c - 2, c)
        out[name] = [pygame.transform.rotate(base, -math.degrees(i * TAU / 64)) for i in range(64)]
    return out


def light_stamps(r, inner=0.4):
    """Alpha masks for one light radius: transparent = lit. The edge is dithered with a Bayer
    matrix; one variant per 4x4 phase so the pattern stays fixed to the world while the light
    moves pixel by pixel (no shimmer, no snapping)."""
    size = 2 * r
    ring = []
    for y in range(size):
        dy = y - r + 0.5
        for x in range(size):
            dx = x - r + 0.5
            d = math.sqrt(dx * dx + dy * dy) / r
            if inner <= d < 1:
                ring.append((x, y, (d - inner) / (1 - inner) * 16))
    lit = (255, 255, 255, 0)
    variants = {}
    for py in range(4):
        for px in range(4):
            s = pygame.Surface((size, size), pygame.SRCALPHA)
            s.fill((255, 255, 255, 255))
            pygame.draw.circle(s, lit, (r, r), int(r * inner) + 1)
            for x, y, v in ring:
                if v < BAYER[(y + py) % 4][(x + px) % 4] + 0.5:
                    s.set_at((x, y), lit)
            variants[(px, py)] = s
    return variants


def dither_surface(w, h):
    s = pygame.Surface((w, h))
    s.fill(KEY)
    s.set_colorkey(KEY)
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            s.set_at((x, y), BLACK)
            s.set_at((x + 1, y + 1), BLACK)
    return s


# ------------------------------------------------------------------ entities
class Player:
    def __init__(self):
        self.x = self.y = 0.0
        self.r = 5
        self.maxhp = 20
        self.hp = 20.0
        self.regen = self.steal = self.dmg = self.aspd = 0
        self.crit = 5
        self.armor = self.dodge = self.speed = self.range = self.magnet = 0
        self.greed = self.plague = self.thorns = 0
        self.souls = self.xp = 0
        self.lv = 1
        self.pending = 0
        self.weapons = []
        self.relics = []
        self.inv = 0
        self.face = 1
        self.walk = 0.0
        self.moving = False
        self.regen_acc = self.soul_frac = 0.0
        self.steal_cd = 0

    def need(self):
        return int((self.lv + 4) ** 2 * (1 + 0.04 * self.lv))


class Weapon:
    def __init__(self, kind, tier=1):
        self.kind, self.tier = kind, tier
        self.cd = random.randint(0, 20)
        self.t = -1                 # attack animation frame, -1 when idle
        self.aim = -math.pi / 2
        self.side = 1
        self.hits = set()
        self.hitcd = {}
        self.ax = self.ay = 0.0
        self.a0 = self.prev = self.cur = 0.0
        self.orbs = []


class Enemy:
    _next = 0

    def __init__(self, kind, x, y, wave):
        Enemy._next += 1
        self.id = Enemy._next
        d = ENEMIES[kind]
        hpm = (1 + 0.35 * (wave - 1) + 0.06 * (wave - 1) ** 2) * 1.08 ** (wave - 1)
        if kind == 'boss':
            hpm = (1 + 0.5 * (wave - 5) + 0.05 * (wave - 5) ** 2) * 1.08 ** (wave - 5)
        self.kind, self.x, self.y = kind, x, y
        self.hp = self.maxhp = d['hp'] * hpm
        self.dmg = d['dmg'] * (1 + 0.2 * (wave - 1) + 0.006 * (wave - 1) ** 2)
        self.r, self.souls = d['r'], d['souls']
        self.spd = d['spd'] * random.uniform(0.9, 1.1) * (1 + min(0.3, 0.015 * (wave - 1)))
        self.kx = self.ky = 0.0
        self.flash = 0
        self.face = 1
        self.t = random.randint(0, 99)
        self.dead = False
        self.phase, self.pt = 'chase', 0
        self.aim = 0.0
        self.cd = random.randint(60, 160)
        self.wind = 0
        self.side = random.choice((-1, 1))
        self.spin = 0.0
        self.last = None


class Bullet:
    def __init__(self, x, y, a, spd, kind, enemy, dmg=0, life=150, r=2, src=None, pierce=0):
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * spd, math.sin(a) * spd
        self.kind, self.enemy, self.dmg, self.life, self.r = kind, enemy, dmg, life, r
        self.src = src              # the Weapon that fired it
        self.pierce = pierce
        self.hits = set()
        self.out = True
        self.dist = 0.0
        self.maxd = 0.0
        self.rot = 0.0


class Pickup:
    def __init__(self, kind, x, y, value=1):
        self.kind, self.x, self.y, self.value = kind, x, y, value
        a = random.uniform(0, TAU)
        v = random.uniform(0.3, 1.4)
        self.vx, self.vy = math.cos(a) * v, math.sin(a) * v
        self.pull = False


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
        pygame.display.set_caption('VIGIL')
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()
        self.sfx = Sfx()
        self.spr = make_sprites()
        self.knight = make_knight()
        self.wspr = make_weapon_sprites()
        self.dim = dither_surface(W, H)
        self.dark = pygame.Surface((W, H), pygame.SRCALPHA)
        self.stamps = {r: light_stamps(r) for r in (12, 18, 32)}
        self.stamps[110] = light_stamps(110, 0.5)
        self.state = 'title'
        self.t = 0
        self.best_file = os.path.join(os.environ.get('XDG_DATA_HOME') or
                                      os.path.expanduser('~/.local/share'), 'vigil', 'best')
        self.best = 0
        try:
            with open(self.best_file) as f:
                self.best = int(f.read().strip() or 0)
        except (OSError, ValueError):
            pass
        self.embers = [[random.uniform(0, W), random.uniform(0, H), random.uniform(0.2, 0.6)]
                       for _ in range(40)]
        self.mouse = (0, 0)
        self.rects = []
        self.new_run(start=False)

    # ---------------------------------------------------------- run / waves
    def new_run(self, start=True):
        self.player = Player()
        self.seed = random.randrange(1 << 30)
        self.chunks = {}
        self.enemies, self.bullets, self.pickups, self.marks = [], [], [], []
        self.particles, self.effects, self.texts, self.dmgnums = [], [], [], []
        self.blasts, self.booms = [], []
        self.grid = {}
        self.wave = 0
        self.wave_t = 0
        self.spawn_t = 0
        self.boss = None
        self.kills = 0
        self.frame = 0
        self.shake = 0.0
        self.camx, self.camy = -W / 2, -H / 2
        self.ox, self.oy = int(self.camx), int(self.camy)
        self.offers = []
        self.reroll_cost = 1
        self.msg, self.msg_t = '', 0
        self.dead_t = 0
        if start:
            picks = random.sample(list(WEAPONS), 4)
            self.open_cards('pick', [self.weapon_card(k, 1) for k in picks])

    def wave_len(self, n):
        return min(60, 20 + 5 * (n - 1))

    def start_wave(self):
        self.wave += 1
        p = self.player
        p.hp = p.maxhp
        p.inv = 60
        self.state = 'play'
        self.wave_t = self.wave_len(self.wave) * 60
        self.spawn_t = 40
        self.boss = None
        self.bullets, self.marks, self.blasts = [], [], []
        if self.wave % 5 == 0:
            a = random.uniform(0, TAU)
            self.marks.append([p.x + math.cos(a) * 120, p.y + math.sin(a) * 80, 'boss', -40])
            self.banner = BOSS_NAME
        else:
            self.banner = f'WAVE {self.wave}'
        self.banner_t = 120
        self.sfx.play('toll')

    def end_wave(self):
        self.state = 'harvest'
        self.harvest_t = 0
        for e in self.enemies:
            if not e.dead:
                self.burst(e.x, e.y, 5, 1.5, 18)
        self.enemies, self.bullets, self.marks, self.blasts, self.booms = [], [], [], [], []
        self.boss = None
        for k in self.pickups:
            k.pull = True
        self.sfx.play('clear')
        self.banner, self.banner_t = 'DAWN, FOR NOW', 90
        if self.wave > self.best:
            self.best = self.wave
            self.save_best()

    def save_best(self):
        try:
            os.makedirs(os.path.dirname(self.best_file), exist_ok=True)
            with open(self.best_file, 'w') as f:
                f.write(str(self.best))
        except OSError:
            pass

    def after_harvest(self):
        if self.player.pending > 0:
            self.open_levelup()
        else:
            self.open_shop()

    # ---------------------------------------------------------- cards (pick / level up)
    def weapon_card(self, kind, tier):
        w = Weapon(kind, tier)
        return dict(title=f'{kind} {ROMAN[tier - 1]}', lines=self.weapon_lines(w),
                    icon=kind, data=(kind, tier))

    def weapon_lines(self, w):
        d = WEAPONS[w.kind]
        dmg = d['dmg'] * TIER_DMG[w.tier - 1] * max(0.1, 1 + self.player.dmg / 100)
        rate = 60 / self.cooldown(w)
        extra = ''
        if d['kind'] == 'chain':
            extra = f'  {2 + w.tier} FOES'
        elif d['kind'] == 'orbit':
            extra = f'  {1 + w.tier} SKULLS'
        elif d['kind'] == 'bolt':
            extra = f'  PIERCE {w.tier}'
        return [d['desc'], f'DMG {dmg:.0f}  {rate:.1f}/S{extra}']

    def open_cards(self, kind, cards):
        self.state = kind
        self.cards = cards
        self.card_sel = 0
        self.card_t = 0
        self.mouse = pygame.mouse.get_pos()

    def open_levelup(self):
        w = self.wave
        cards = []
        for name, attr, amt in random.sample(STAT_UPS, 4):
            r = random.random()
            tier = 3 if r < min(0.25, w * 0.012) else 2 if r < min(0.5, w * 0.035) else 1
            v = amt * tier
            cards.append(dict(title=name + ('' if tier == 1 else ' ' + ROMAN[tier - 1]),
                              lines=[fmt_effect(attr, v)], icon=None, data=(attr, v),
                              tier=tier))
        self.open_cards('level', cards)

    def pick_card(self, i):
        if self.card_t < 15 or not (0 <= i < len(self.cards)):
            return
        c = self.cards[i]
        p = self.player
        if self.state == 'pick':
            p.weapons.append(Weapon(*c['data']))
            self.start_wave()
            return
        attr, v = c['data']
        self.apply(attr, v)
        p.pending -= 1
        self.sfx.play('level')
        self.after_harvest()

    def apply(self, attr, v):
        p = self.player
        setattr(p, attr, getattr(p, attr) + v)
        if attr == 'maxhp':
            p.maxhp = max(1, p.maxhp)
            p.hp = min(p.maxhp, p.hp + max(0, v))

    # ---------------------------------------------------------- shop
    def price(self, base):
        return max(1, round(base * (1 + 0.18 * (self.wave - 1))))

    def roll_offers(self):
        w = self.wave
        offers = []
        for _ in range(4):
            if random.random() < 0.55:
                r = random.random()
                tier = 1
                if w >= 12 and r < min(0.2, (w - 11) * 0.03):
                    tier = 4
                elif w >= 7 and r < min(0.4, (w - 6) * 0.06):
                    tier = 3
                elif w >= 3 and r < min(0.65, (w - 2) * 0.09):
                    tier = 2
                kind = random.choice(list(WEAPONS))
                c = self.weapon_card(kind, tier)
                c['type'] = 'weapon'
                c['price'] = self.price(WEAPONS[kind]['price'] * TIER_PRICE[tier - 1])
            else:
                name, eff, base, note = random.choice(RELICS)
                c = dict(title=name, type='relic', icon=None, data=eff,
                         lines=[note or ', '.join(fmt_effect(a, v) for a, v in eff)],
                         price=self.price(base))
            offers.append(c)
        self.offers = offers

    def open_shop(self):
        self.state = 'shop'
        self.roll_offers()
        self.reroll_cost = 1 + self.wave // 2
        self.ssel = [0, 0]
        self.card_t = 0
        self.mouse = pygame.mouse.get_pos()

    def shop_rows(self):
        return [len(self.offers), len(self.player.weapons), 2]

    def say(self, s):
        self.msg, self.msg_t = s, 120

    def merge_target(self, kind, tier, exclude=None):
        for w in self.player.weapons:
            if w is not exclude and w.kind == kind and w.tier == tier and tier < 4:
                return w
        return None

    def buy(self, i):
        p = self.player
        if not (0 <= i < len(self.offers)) or self.offers[i] is None:
            return
        o = self.offers[i]
        if p.souls < o['price']:
            self.say('NOT ENOUGH SOULS')
            self.sfx.play('empty')
            return
        if o['type'] == 'weapon':
            kind, tier = o['data']
            if len(p.weapons) < 6:
                p.weapons.append(Weapon(kind, tier))
            else:
                m = self.merge_target(kind, tier)
                if not m:
                    self.say('NO ROOM: SELL OR COMBINE A WEAPON')
                    self.sfx.play('empty')
                    return
                m.tier += 1
                self.say(f'{kind} RISES TO {ROMAN[m.tier - 1]}')
        else:
            for a, v in o['data']:
                self.apply(a, v)
            p.relics.append(o['title'])
        p.souls -= o['price']
        self.offers[i] = None
        self.sfx.play('buy')

    def sell_value(self, w):
        return max(1, self.price(WEAPONS[w.kind]['price'] * TIER_PRICE[w.tier - 1]) * 2 // 5)

    def sell(self, j):
        p = self.player
        if not (0 <= j < len(p.weapons)):
            return
        if len(p.weapons) == 1:
            self.say('YOU NEED AT LEAST ONE WEAPON')
            self.sfx.play('empty')
            return
        w = p.weapons.pop(j)
        p.souls += self.sell_value(w)
        self.sfx.play('sell')
        self.ssel[1] = min(self.ssel[1], len(p.weapons) - 1)

    def combine(self, j):
        p = self.player
        if not (0 <= j < len(p.weapons)):
            return
        w = p.weapons[j]
        m = self.merge_target(w.kind, w.tier, exclude=w)
        if not m:
            self.say('COMBINE NEEDS TWO OF THE SAME WEAPON AND TIER' if w.tier < 4
                     else 'ALREADY AT ITS HIGHEST TIER')
            self.sfx.play('empty')
            return
        p.weapons.remove(m)
        w.tier += 1
        self.say(f'{w.kind} RISES TO {ROMAN[w.tier - 1]}')
        self.sfx.play('level')
        self.ssel[1] = p.weapons.index(w)

    def reroll(self):
        p = self.player
        if p.souls < self.reroll_cost:
            self.say('NOT ENOUGH SOULS')
            self.sfx.play('empty')
            return
        p.souls -= self.reroll_cost
        self.reroll_cost += 1 + self.wave // 4
        self.roll_offers()
        self.sfx.play('sell')

    def shop_act(self, row, col):
        if self.card_t < 15:
            return
        if row == 0:
            self.buy(col)
        elif row == 1:
            self.sell(col)
        elif col == 0:
            self.reroll()
        else:
            self.start_wave()

    # ---------------------------------------------------------- helpers
    def burst(self, x, y, n, spd=2.0, life=20, size=1, color=BONE, glow=False):
        for _ in range(n):
            a = random.uniform(0, TAU)
            v = random.uniform(0.3, 1) * spd
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v,
                                   random.randint(life // 2, life), size, 0.9, color, glow])

    def toast(self, s, color=BONE):
        p = self.player
        self.texts.append([p.x, p.y - 16, s, 50, color])

    def dmgnum(self, x, y, txt, color):
        self.dmgnums.append([x + random.uniform(-3, 3), y, random.uniform(-0.25, 0.25),
                             -1.1, txt, 40, color])

    def cooldown(self, w):
        return max(6.0, WEAPONS[w.kind]['cd'] * TIER_CD[w.tier - 1]
                   / max(0.3, 1 + self.player.aspd / 100))

    def reach(self, w):
        d = WEAPONS[w.kind]
        return d['rng'] + self.player.range * (0.5 if d['kind'] in MELEE else 1)

    def roll(self, w):
        d = WEAPONS[w.kind]
        dmg = d['dmg'] * TIER_DMG[w.tier - 1] * max(0.1, 1 + self.player.dmg / 100)
        crit = random.random() * 100 < self.player.crit + d.get('crit', 0)
        return (dmg * 2, True) if crit else (dmg, False)

    def build_grid(self):
        g = {}
        for e in self.enemies:
            if not e.dead:
                g.setdefault((int(e.x) // G, int(e.y) // G), []).append(e)
        self.grid = g

    def query(self, x, y, r):
        """Enemies whose cell lies within r (+ the widest enemy) of (x, y)."""
        g = self.grid
        r += 14
        out = []
        for cy in range(int(y - r) // G, int(y + r) // G + 1):
            for cx in range(int(x - r) // G, int(x + r) // G + 1):
                cell = g.get((cx, cy))
                if cell:
                    out.extend(cell)
        return out

    def nearest(self, x, y, reach, skip=()):
        best, bd = None, reach
        for e in self.enemies:
            if e.dead or e in skip:
                continue
            d = math.hypot(e.x - x, e.y - y) - e.r
            if d < bd:
                best, bd = e, d
        return best

    # ---------------------------------------------------------- ground
    def chunk(self, cx, cy):
        c = self.chunks.get((cx, cy))
        if c is None:
            c = self.make_chunk(cx, cy)
            self.chunks[(cx, cy)] = c
            if len(self.chunks) > 48:
                px, py = self.player.x // CH, self.player.y // CH
                far = max(self.chunks, key=lambda k: abs(k[0] - px) + abs(k[1] - py))
                del self.chunks[far]
        return c

    def make_chunk(self, cx, cy):
        rng = random.Random((self.seed * 73856093) ^ (cx * 19349663) ^ (cy * 83492791))
        s = pygame.Surface((CH, CH))
        s.fill(BLACK)
        R = lambda: rng.randint(10, CH - 10)
        for _ in range(45):
            s.set_at((rng.randrange(CH), rng.randrange(CH)), BONE)
        for _ in range(14):                                   # grass tufts
            x, y = R(), R()
            for dx, h in ((-1, 2), (0, 3), (1, 2)):
                if rng.random() < 0.8:
                    pygame.draw.line(s, BONE, (x, y), (x + dx, y - h))
        if rng.random() < 0.6:                                # a cluster of graves
            gx, gy = rng.randint(30, CH - 30), rng.randint(30, CH - 30)
            for _ in range(rng.randint(1, 4)):
                x, y = gx + rng.randint(-24, 24), gy + rng.randint(-18, 18)
                if rng.random() < 0.6:
                    pygame.draw.rect(s, BONE, (x - 3, y - 8, 7, 9), 1,
                                     border_top_left_radius=3, border_top_right_radius=3)
                    s.fill(BONE, (x - 1, y - 5, 3, 1))
                    s.fill(BONE, (x, y - 6, 1, 3))
                else:
                    pygame.draw.line(s, BONE, (x, y - 10), (x, y))
                    pygame.draw.line(s, BONE, (x - 3, y - 7), (x + 3, y - 7))
                for i in range(-5, 6, 2):
                    s.set_at((x + i, y + 2), BONE)
                    if abs(i) < 4:
                        s.set_at((x + i + 1, y + 4), BONE)
        if rng.random() < 0.35:                               # a dead tree
            x, y = R(), R()
            top = (x + rng.randint(-3, 3), y - rng.randint(16, 24))
            pygame.draw.line(s, BONE, (x, y), top)
            pygame.draw.line(s, BONE, (x + 1, y), (top[0] + 1, top[1] + 4))
            for _ in range(rng.randint(3, 5)):
                f = rng.uniform(0.3, 0.9)
                bx, by = x + (top[0] - x) * f, y + (top[1] - y) * f
                a = -math.pi / 2 + rng.uniform(-1.3, 1.3)
                ln = rng.randint(4, 9)
                ex, ey = bx + math.cos(a) * ln, by + math.sin(a) * ln
                pygame.draw.line(s, BONE, (bx, by), (ex, ey))
                pygame.draw.line(s, BONE, (ex, ey), (ex + rng.randint(-3, 3), ey - 3))
        for _ in range(rng.randint(0, 3)):                    # scattered bones
            x, y = R(), R()
            a = rng.uniform(0, math.pi)
            pygame.draw.line(s, BONE, (x, y), (x + math.cos(a) * 4, y + math.sin(a) * 4))
            s.set_at((x - 1, y), BONE)
        for _ in range(rng.randint(0, 2)):                    # stones
            pygame.draw.ellipse(s, BONE, (R(), R(), 6, 4), 1)
        if rng.random() < 0.08:                               # a standing stone
            x, y = R(), R()
            pygame.draw.rect(s, BONE, (x - 3, y - 14, 7, 15), 1)
            pygame.draw.lines(s, BONE, False, [(x - 1, y - 12), (x + 1, y - 9), (x, y - 6)])
        if rng.random() < 0.1:                                # old blood
            x, y = R(), R()
            for _ in range(30):
                a, d = rng.uniform(0, TAU), rng.uniform(0, 7)
                s.set_at((int(x + math.cos(a) * d), int(y + math.sin(a) * d * 0.6)), BLOOD)
        return s

    def ground_blit(self, img, x, y):
        w, h = img.get_size()
        for cy in range(int(y // CH), int((y + h) // CH) + 1):
            for cx in range(int(x // CH), int((x + w) // CH) + 1):
                self.chunk(cx, cy).blit(img, (int(x - cx * CH), int(y - cy * CH)))

    def bleed(self, x, y, n, spread=5):
        for _ in range(n):
            px = int(x + random.gauss(0, spread))
            py = int(y + random.gauss(0, spread * 0.7))
            self.chunk(px // CH, py // CH).set_at((px % CH, py % CH), BLOOD)

    # ---------------------------------------------------------- combat
    def hurt_enemy(self, e, dmg, kx=0.0, ky=0.0, crit=False):
        if e.dead:
            return
        e.hp -= dmg
        self.dmgnum(e.x, e.y - e.r - 3, str(max(1, round(dmg))), BLOOD if crit else BONE)
        e.flash = 5
        kb = KB_RESIST.get(e.kind, 1.0)
        e.kx += kx * kb
        e.ky += ky * kb
        self.burst(e.x, e.y, 3, 1.6, 12, color=BLOOD)
        self.sfx.play('hit')
        p = self.player
        if p.steal > 0 and p.steal_cd <= 0 and random.random() * 100 < p.steal:
            p.hp = min(p.maxhp, p.hp + 1)
            p.steal_cd = 6
        if e.hp <= 0:
            self.kill(e)

    def hit_with(self, w, e, fx, fy):
        """A weapon hit pushing away from (fx, fy)."""
        dmg, crit = self.roll(w)
        a = math.atan2(e.y - fy, e.x - fx)
        kb = WEAPONS[w.kind]['kb']
        self.hurt_enemy(e, dmg, math.cos(a) * kb, math.sin(a) * kb, crit)

    def kill(self, e):
        e.dead = True
        self.kills += 1
        p = self.player
        self.burst(e.x, e.y, 8, 2.2, 22, color=BLOOD)
        self.bleed(e.x, e.y, 6 if e.kind != 'boss' else 40)
        if e.kind in ('revenant', 'boss') or random.random() < 0.2:   # keep the moor legible
            c = self.spr[e.kind]['corpse']
            self.ground_blit(c, e.x - c.get_width() // 2, e.y - c.get_height() // 2)
        self.sfx.play('die')
        for _ in range(e.souls):
            self.pickups.append(Pickup('soul', e.x + random.uniform(-3, 3),
                                       e.y + random.uniform(-3, 3)))
        if random.random() < 0.02:
            self.pickups.append(Pickup('vial', e.x, e.y))
        if e.kind == 'bloater':
            self.blasts.append([e.x, e.y, 0, e.dmg * 2])
        if p.plague and random.random() * 100 < p.plague:
            self.booms.append((e.x, e.y, 22, (4 + self.wave * 1.5) * max(0.1, 1 + p.dmg / 100)))
        if e is self.boss:
            self.boss = None
            self.bleed(e.x, e.y, 60, 14)
            self.burst(e.x, e.y, 40, 4, 50, 2, BLOOD, True)
            self.shake = 8
            self.end_wave()

    def explode(self, x, y, r, roll):
        """roll() -> (damage, crit) for each foe caught."""
        for e in self.query(x, y, r):
            if not e.dead and math.hypot(e.x - x, e.y - y) < r + e.r:
                dmg, crit = roll()
                a = math.atan2(e.y - y, e.x - x)
                self.hurt_enemy(e, dmg, math.cos(a) * 2, math.sin(a) * 2, crit)
        self.effects.append(['boom', x, y, r, 0, 14])
        self.burst(x, y, 10, 2.5, 18, color=BLOOD, glow=True)
        self.sfx.play('boom')

    def hurt_player(self, dmg, src=None):
        p = self.player
        if p.inv > 0 or self.state != 'play':
            return
        if random.random() * 100 < min(60, p.dodge):
            p.inv = 20
            self.dmgnum(p.x, p.y - 14, 'DODGE', BONE)
            return
        dmg *= 10 / (10 + p.armor) if p.armor >= 0 else 1 - p.armor * 0.1
        p.hp -= dmg
        p.inv = 36
        self.shake = max(self.shake, 4)
        self.sfx.play('hurt')
        self.burst(p.x, p.y, 8, 2, 20, color=BLOOD)
        if src is not None and p.thorns and not src.dead:
            self.hurt_enemy(src, p.thorns * max(0.1, 1 + p.dmg / 100))
        if p.hp <= 0:
            p.hp = 0
            self.state = 'dead'
            self.dead_t = 0
            self.sfx.play('toll')
            c = self.knight['corpse']
            self.ground_blit(c, p.x - 9, p.y - 6)
            self.bleed(p.x, p.y, 30, 8)

    # ---------------------------------------------------------- update
    def update(self):
        self.frame += 1
        p = self.player
        keys = pygame.key.get_pressed()
        ix = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        iy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        if self.state in ('play', 'harvest'):
            self.update_player(ix, iy)
        if self.state == 'play':
            self.update_spawns()
            for e in self.enemies:
                if not e.dead:
                    self.update_enemy(e)
            self.build_grid()
            self.separate()
            self.update_weapons()
            self.update_bullets()
            self.update_blasts()
            while self.booms:
                x, y, r, dmg = self.booms.pop()
                self.explode(x, y, r, lambda d=dmg: (d, False))
            self.enemies = [e for e in self.enemies if not e.dead]
            if self.state == 'play' and not self.wave_boss():
                self.wave_t -= 1
                if self.wave_t <= 0:
                    self.end_wave()
        elif self.state == 'harvest':
            self.harvest_t += 1
            if self.harvest_t > 240:
                for k in self.pickups:
                    self.collect(k)
                self.pickups = []
            if self.harvest_t > 70 and not self.pickups:
                self.after_harvest()
        self.update_pickups()
        self.update_fx()
        # camera
        self.camx += (p.x - W / 2 - self.camx) * 0.15
        self.camy += (p.y - H / 2 - self.camy) * 0.15
        self.ox = math.floor(p.x) - math.floor(p.x - self.camx)
        self.oy = math.floor(p.y) - math.floor(p.y - self.camy)

    def wave_boss(self):
        return self.wave % 5 == 0

    def update_player(self, ix, iy):
        p = self.player
        if p.inv > 0:
            p.inv -= 1
        if p.steal_cd > 0:
            p.steal_cd -= 1
        if p.regen > 0 and p.hp < p.maxhp:
            p.regen_acc += p.regen / 600
            if p.regen_acc >= 1:
                p.regen_acc -= 1
                p.hp = min(p.maxhp, p.hp + 1)
        p.moving = bool(ix or iy)
        if p.moving:
            n = math.hypot(ix, iy)
            spd = 1.25 * max(0.4, 1 + p.speed / 100)
            p.x += ix / n * spd
            p.y += iy / n * spd
            p.walk += 0.15 * spd
            if ix:
                p.face = 1 if ix > 0 else -1

    def update_spawns(self):
        w = self.wave
        p = self.player
        boss = self.wave_boss()
        self.spawn_t -= 1
        cap = min(220, 120 + w * 6)
        if self.spawn_t <= 0 and len(self.enemies) + len(self.marks) < cap:
            self.spawn_t = max(18, 70 - w * 3) * (2 if boss else 1)
            kinds = [(k, wt) for k, (first, wt) in UNLOCK.items() if w >= first]
            kind = random.choices([k for k, _ in kinds], [wt for _, wt in kinds])[0]
            n = random.randint(1 + w // 4, min(12, 3 + w // 2))
            if kind == 'bat':
                n = min(16, n * 2)
            elif kind == 'revenant':
                n = max(1, n // 3)
            a = random.uniform(0, TAU)
            d = random.uniform(70, 190)
            cx, cy = p.x + math.cos(a) * d, p.y + math.sin(a) * d * 0.7
            for _ in range(n):
                self.marks.append([cx + random.uniform(-16, 16), cy + random.uniform(-16, 16),
                                   kind, random.randint(-8, 0)])
        keep = []
        for m in self.marks:
            m[3] += 1
            if m[3] >= 50:
                e = Enemy(m[2], m[0], m[1], w)
                self.enemies.append(e)
                if m[2] == 'boss':
                    self.boss = e
                    e.phase, e.pt = 'walk', 120
                    self.sfx.play('charge')
            else:
                keep.append(m)
        self.marks = keep

    def update_enemy(self, e):
        p = self.player
        dx, dy = p.x - e.x, p.y - e.y
        d = math.hypot(dx, dy) or 0.01
        ang = math.atan2(dy, dx)
        e.t += 1
        if e.flash:
            e.flash -= 1
        k = e.kind
        mx = my = 0.0
        if d > 330 and k != 'boss':
            # left far behind on the endless field: it returns from the dark ahead of you
            a = random.uniform(0, TAU)
            e.x, e.y = p.x + math.cos(a) * 230, p.y + math.sin(a) * 160
            e.phase = 'chase'
            return
        if k == 'boss':
            mx, my = self.update_boss(e, d, ang)
        elif k == 'cultist':
            e.face = 1 if dx > 0 else -1
            if e.wind > 0:
                e.wind -= 1
                if e.wind == 0:
                    self.bullets.append(Bullet(e.x, e.y, ang, 1.9, 'ebolt', True, e.dmg, 200, 3))
                    self.sfx.play('bolt')
            else:
                if d > 110:
                    a = ang
                elif d < 75:
                    a = ang + math.pi
                else:
                    a = ang + e.side * math.pi / 2
                mx, my = math.cos(a) * e.spd, math.sin(a) * e.spd
                e.cd -= 1
                if e.cd <= 0 and d < 170:
                    e.wind, e.cd = 30, random.randint(150, 220)
        elif k == 'hound':
            if e.phase == 'wind':
                e.pt -= 1
                if e.pt > 12:
                    e.aim = ang
                if e.pt <= 0:
                    e.phase, e.pt = 'dash', 24
                    self.sfx.play('bark')
            elif e.phase == 'dash':
                mx, my = math.cos(e.aim) * 3.4, math.sin(e.aim) * 3.4
                e.pt -= 1
                if e.pt <= 0:
                    e.phase, e.pt = 'rest', 40
            elif e.phase == 'rest':
                mx, my = dx / d * e.spd * 0.3, dy / d * e.spd * 0.3
                e.pt -= 1
                if e.pt <= 0:
                    e.phase = 'chase'
            else:
                mx, my = dx / d * e.spd, dy / d * e.spd
                e.cd -= 1
                if d < 100 and e.cd <= 0:
                    e.phase, e.pt, e.aim, e.cd = 'wind', 32, ang, 150
            e.face = 1 if math.cos(e.aim if e.phase in ('wind', 'dash') else ang) > 0 else -1
        elif k == 'bat':
            a = ang + math.sin(e.t * 0.12 + e.id) * 0.9
            mx, my = math.cos(a) * e.spd, math.sin(a) * e.spd
            e.face = 1 if dx > 0 else -1
        else:
            mx, my = dx / d * e.spd, dy / d * e.spd
            e.face = 1 if dx > 0 else -1
        e.x += mx + e.kx
        e.y += my + e.ky
        e.kx *= 0.75
        e.ky *= 0.75
        if d < e.r + p.r:
            self.hurt_player(e.dmg, e)

    def update_boss(self, e, d, ang):
        e.face = 1 if math.cos(ang) > 0 else -1
        e.pt -= 1
        ph = e.phase
        mx = my = 0.0
        if ph == 'walk':
            # the shepherd will not be outrun: it lengthens its stride when far away
            spd = e.spd * min(3.0, max(1.0, (d - 90) / 40))
            mx, my = math.cos(ang) * spd, math.sin(ang) * spd
            if e.pt <= 0:
                e.phase = random.choice([a for a in ('ring', 'spiral', 'summon', 'charge')
                                         if a != e.last])
                e.last = e.phase
                e.pt = {'ring': 110, 'spiral': 150, 'summon': 50, 'charge': 85}[e.phase]
                e.spin = ang
                if e.phase == 'charge':
                    self.sfx.play('charge')
        elif ph == 'ring':
            if e.pt in (70, 45, 20):
                off = e.pt * 0.07
                for i in range(18):
                    self.bullets.append(Bullet(e.x, e.y, off + i * TAU / 18, 1.6, 'ebolt', True,
                                               e.dmg * 0.6, 260, 3))
                self.sfx.play('bolt')
            e.flash = 2 if e.pt > 70 and e.pt % 6 < 3 else e.flash
        elif ph == 'spiral':
            mx, my = math.cos(ang) * 0.2, math.sin(ang) * 0.2
            if e.pt % 5 == 0:
                for j in range(3):
                    self.bullets.append(Bullet(e.x, e.y, e.spin + j * TAU / 3, 1.5, 'ebolt', True,
                                               e.dmg * 0.6, 260, 3))
                e.spin += 0.22
                if e.pt % 15 == 0:
                    self.sfx.play('bolt')
        elif ph == 'summon':
            if e.pt == 25:
                p = self.player
                for i in range(6):
                    a = i * TAU / 6 + random.uniform(-0.3, 0.3)
                    self.marks.append([p.x + math.cos(a) * 60, p.y + math.sin(a) * 45,
                                       'ghoul', 10])
                self.sfx.play('charge')
        elif ph == 'charge':
            if e.pt > 40:
                if e.pt > 55:
                    e.aim = ang
                e.flash = 2 if e.pt % 6 < 3 else 0
            else:
                mx, my = math.cos(e.aim) * 3.6, math.sin(e.aim) * 3.6
                e.face = 1 if mx > 0 else -1
        if ph != 'walk' and e.pt <= 0:
            e.phase, e.pt = 'walk', random.randint(90, 150)
        return mx, my

    def separate(self):
        g = self.grid
        for (cx, cy), cell in g.items():
            for e in cell:
                if e.kind == 'boss':
                    continue
                for ny in (cy - 1, cy, cy + 1):
                    for nx in (cx - 1, cx, cx + 1):
                        for o in g.get((nx, ny), ()):
                            if o.id <= e.id or o.kind == 'boss':
                                continue
                            dx, dy = o.x - e.x, o.y - e.y
                            rr = e.r + o.r
                            d2 = dx * dx + dy * dy
                            if 0.0001 < d2 < rr * rr:
                                d = math.sqrt(d2)
                                push = (rr - d) / d * 0.25
                                e.x -= dx * push
                                e.y -= dy * push
                                o.x += dx * push
                                o.y += dy * push
        b = self.boss
        if b and not b.dead:
            for o in self.query(b.x, b.y, b.r + 8):
                if o is b:
                    continue
                dx, dy = o.x - b.x, o.y - b.y
                d = math.hypot(dx, dy) or 0.01
                if d < b.r + o.r:
                    o.x += dx / d * (b.r + o.r - d)
                    o.y += dy / d * (b.r + o.r - d)

    def update_weapons(self):
        p = self.player
        n = len(p.weapons)
        for i, w in enumerate(p.weapons):
            d = WEAPONS[w.kind]
            k = d['kind']
            a = -math.pi / 2 + (i + 0.5) * TAU / max(1, n)
            w.ax, w.ay = p.x + math.cos(a) * 11, p.y + 1 + math.sin(a) * 8
            if k == 'orbit':
                self.update_orbit(w)
                continue
            reach = self.reach(w)
            if w.cd > 0:
                w.cd -= 1
            if w.t >= 0:
                w.t += 1
                if k == 'thrust':
                    self.thrust_hits(w, reach)
                    if w.t >= len(THRUST):
                        w.t = -1
                else:
                    self.sweep_hits(w, reach)
                    if w.t >= SWEEP_T:
                        w.t = -1
                continue
            tgt = self.nearest(w.ax, w.ay, reach * 1.6)
            want = math.atan2(tgt.y - w.ay, tgt.x - w.ax) if tgt else a
            w.aim += angdiff(want, w.aim) * 0.3
            if w.cd <= 0 and tgt and math.hypot(tgt.x - w.ax, tgt.y - w.ay) - tgt.r <= reach:
                self.attack(w, tgt, reach)

    def attack(self, w, tgt, reach):
        d = WEAPONS[w.kind]
        k = d['kind']
        p = self.player
        ang = math.atan2(tgt.y - w.ay, tgt.x - w.ax)
        w.aim = ang
        w.cd = self.cooldown(w)
        if k == 'thrust':
            w.t, w.hits = 0, set()
            self.sfx.play('stab')
        elif k == 'sweep':
            w.t, w.hits = 0, set()
            w.side = -w.side
            ang = math.atan2(tgt.y - p.y, tgt.x - p.x)
            w.a0 = ang - w.side * d['arc'] / 2
            w.prev = w.cur = w.a0
            w.aim = ang
            self.sfx.play('swing')
        elif k == 'bolt':
            self.bullets.append(Bullet(w.ax, w.ay, ang, 5.5, 'bolt', False, life=int(reach / 5.5) + 4,
                                       src=w, pierce=w.tier))
            self.sfx.play('arrow')
        elif k == 'fire':
            self.bullets.append(Bullet(w.ax, w.ay, ang, 3.6, 'fire', False, life=int(reach / 3.6) + 4,
                                       r=3, src=w))
            self.sfx.play('cast')
        elif k == 'axe':
            b = Bullet(w.ax, w.ay, ang, 3.4, 'axe', False, life=400, r=4, src=w)
            b.maxd = reach
            self.bullets.append(b)
            self.sfx.play('throw')
        elif k == 'chain':
            pts, chain, cur = [(w.ax, w.ay)], [], tgt
            for _ in range(2 + w.tier):
                chain.append(cur)
                pts.append((cur.x, cur.y))
                fx, fy = pts[-2]
                self.hit_with(w, cur, fx, fy)
                cur = self.nearest(cur.x, cur.y, 70, chain)
                if cur is None:
                    break
            self.effects.append(['zap', pts, 0, 10])
            self.sfx.play('zap')

    def thrust_hits(self, w, reach):
        if not 1 <= w.t <= 5:
            return
        ext = THRUST[w.t] * reach
        c, s = math.cos(w.aim), math.sin(w.aim)
        x0, y0 = w.ax, w.ay
        for e in self.query(x0 + c * ext / 2, y0 + s * ext / 2, ext / 2 + 4):
            if e.dead or e.id in w.hits:
                continue
            dx, dy = e.x - x0, e.y - y0
            along = dx * c + dy * s
            if -e.r < along < ext + e.r and abs(-dx * s + dy * c) < e.r + 3:
                w.hits.add(e.id)
                self.hit_with(w, e, x0, y0)

    def sweep_hits(self, w, reach):
        d = WEAPONS[w.kind]
        p = self.player
        if w.t <= 8:
            f = w.t / 8
            w.cur = w.a0 + w.side * d['arc'] * (1 - (1 - f) ** 2)
        if not 1 <= w.t <= 8:
            return
        lo, hi = sorted((w.prev, w.cur))
        mid, half = (lo + hi) / 2, (hi - lo) / 2
        for e in self.query(p.x, p.y, reach):
            if e.dead or e.id in w.hits:
                continue
            dist = math.hypot(e.x - p.x, e.y - p.y)
            if dist > reach + e.r:
                continue
            allow = math.asin(min(1.0, e.r / max(dist, 0.01)))
            if abs(angdiff(math.atan2(e.y - p.y, e.x - p.x), mid)) <= half + allow \
                    or dist < e.r + 6:
                w.hits.add(e.id)
                self.hit_with(w, e, p.x, p.y)
        w.prev = w.cur

    def update_orbit(self, w):
        p = self.player
        n = 1 + w.tier
        rad = self.reach(w)
        w.orbs = []
        cd = int(self.cooldown(w))
        for j in range(n):
            a = self.frame * 0.065 + j * TAU / n
            x, y = p.x + math.cos(a) * rad, p.y + math.sin(a) * rad * 0.85
            w.orbs.append((x, y))
            for e in self.query(x, y, 4):
                if not e.dead and math.hypot(e.x - x, e.y - y) < e.r + 4 \
                        and w.hitcd.get(e.id, -1) <= self.frame:
                    w.hitcd[e.id] = self.frame + cd
                    self.hit_with(w, e, p.x, p.y)
        if len(w.hitcd) > 400:
            w.hitcd = {k: v for k, v in w.hitcd.items() if v > self.frame}

    def update_bullets(self):
        p = self.player
        keep = []
        for b in self.bullets:
            b.x += b.vx
            b.y += b.vy
            b.life -= 1
            alive = b.life > 0
            if b.enemy:
                if math.hypot(b.x - p.x, b.y - p.y) < b.r + p.r - 1:
                    self.hurt_player(b.dmg)
                    alive = False
            else:
                if b.kind == 'axe':
                    b.rot += 0.45
                    if b.out:
                        b.dist += 3.4
                        if b.dist >= b.maxd:
                            b.out, b.hits = False, set()
                    else:
                        a = math.atan2(p.y - b.y, p.x - b.x)
                        b.vx, b.vy = math.cos(a) * 4, math.sin(a) * 4
                        if math.hypot(p.x - b.x, p.y - b.y) < 8:
                            alive = False
                for e in self.query(b.x, b.y, b.r):
                    if not alive:
                        break
                    if e.dead or e.id in b.hits or math.hypot(e.x - b.x, e.y - b.y) >= e.r + b.r:
                        continue
                    b.hits.add(e.id)
                    w = b.src
                    if b.kind == 'fire':
                        self.explode(b.x, b.y, 18, lambda w=w: self.roll(w))
                        alive = False
                    else:
                        self.hit_with(w, e, b.x - b.vx * 3, b.y - b.vy * 3)
                        if b.kind == 'bolt':
                            b.pierce -= 1
                            if b.pierce < 0:
                                alive = False
            if alive:
                keep.append(b)
        self.bullets = keep

    def update_blasts(self):
        keep = []
        p = self.player
        for bl in self.blasts:
            bl[2] += 1
            if bl[2] >= 40:
                x, y, _, dmg = bl
                if math.hypot(p.x - x, p.y - y) < 26 + p.r:
                    self.hurt_player(dmg)
                self.explode(x, y, 26, lambda: (15, False))
            else:
                keep.append(bl)
        self.blasts = keep

    def update_pickups(self):
        p = self.player
        mag = 30 + p.magnet
        keep = []
        for k in self.pickups:
            d = math.hypot(p.x - k.x, p.y - k.y)
            if k.pull or d < mag:
                # fly straight in, quickening (no momentum, so nothing ever orbits)
                k.pull = True
                k.sp = min(6.0, getattr(k, 'sp', 1.0) + 0.25)
                k.vx = (p.x - k.x) / max(d, 0.01) * min(k.sp, d)
                k.vy = (p.y - k.y) / max(d, 0.01) * min(k.sp, d)
            else:
                k.vx *= 0.9
                k.vy *= 0.9
            k.x += k.vx
            k.y += k.vy
            if d < 7:
                self.collect(k)
            else:
                keep.append(k)
        if len(keep) > 400:        # too many on the field: fold the oldest into the rest
            extra = keep[:-400]
            keep = keep[-400:]
            for k in extra:
                keep[random.randrange(len(keep))].value += k.value
        self.pickups = keep

    def collect(self, k):
        p = self.player
        if k.kind == 'vial':
            p.hp = min(p.maxhp, p.hp + 5)
            self.sfx.play('drink')
            self.dmgnum(p.x, p.y - 14, '+5', BLOOD)
            return
        v = k.value * max(0.0, 1 + p.greed / 100) + p.soul_frac
        whole = int(v)
        p.soul_frac = v - whole
        p.souls += whole
        p.xp += whole
        self.sfx.play('soul')
        while p.xp >= p.need():
            p.xp -= p.need()
            p.lv += 1
            p.pending += 1
            p.maxhp += 1
            p.hp += 1
            self.toast('LEVEL UP', BLOOD)
            self.sfx.play('level')

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
        self.particles = keep[-700:]
        for f in self.effects:
            f[-2] += 1
        self.effects = [f for f in self.effects if f[-2] < f[-1]]
        for t in self.texts:
            t[1] -= 0.3
            t[3] -= 1
        self.texts = [t for t in self.texts if t[3] > 0]
        for t in self.dmgnums:   # pop up, then drift and settle
            t[0] += t[2]
            t[1] += t[3]
            t[3] = min(t[3] + 0.08, 0.0)
            t[5] -= 1
        self.dmgnums = [t for t in self.dmgnums if t[5] > 0][-80:]
        if self.shake > 0:
            self.shake = max(0.0, self.shake - 0.4)
        if self.msg_t > 0:
            self.msg_t -= 1
        if getattr(self, 'banner_t', 0) > 0:
            self.banner_t -= 1

    # ---------------------------------------------------------- drawing
    def light(self, x, y, r):
        left, top = int(x) - r, int(y) - r
        st = self.stamps[r][((left + self.lox) % 4, (top + self.loy) % 4)]
        self.dark.blit(st, (left, top), special_flags=pygame.BLEND_RGBA_MIN)

    def weapon_img(self, name, angle):
        return self.wspr[name][int(round(angle / TAU * 64)) % 64]

    def blit_c(self, img, x, y):
        self.screen.blit(img, (int(x) - img.get_width() // 2, int(y) - img.get_height() // 2))

    def draw_world(self):
        s = self.screen
        p = self.player
        fr = self.frame
        sx = sy = 0
        if self.shake > 0:
            sx = int(random.uniform(-self.shake, self.shake))
            sy = int(random.uniform(-self.shake, self.shake))
        ox, oy = self.ox + sx, self.oy + sy
        self.lox, self.loy = ox, oy
        lights = []

        # ---- ground
        for cy in range(oy // CH, (oy + H) // CH + 1):
            for cx in range(ox // CH, (ox + W) // CH + 1):
                s.blit(self.chunk(cx, cy), (cx * CH - ox, cy * CH - oy))

        # ---- enemies
        for e in sorted(self.enemies, key=lambda e: e.y):
            img = self.spr[e.kind][e.face][1 if e.flash > 0 else 0]
            bob = 0
            if e.kind == 'bat':
                bob = int(math.sin(e.t * 0.3) * 2)
            elif e.kind == 'hound' and e.phase == 'wind':
                bob = random.randint(-1, 1)
            x, y = int(e.x - ox), int(e.y - oy) + bob
            if -40 < x < W + 40 and -40 < y < H + 40:
                s.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2))

        # ---- the knight and the ring of weapons
        if self.state != 'dead':
            behind = [w for w in p.weapons if w.ay < p.y]
            front = [w for w in p.weapons if w.ay >= p.y]
            for w in behind:
                self.draw_weapon(w, ox, oy, lights)
            if p.inv <= 0 or fr % 4 < 2:
                img = self.knight[p.face][int(p.walk) % 4 if p.moving else 0]
                s.blit(img, (int(p.x - ox) - 6, int(p.y - oy) - 12))
            for w in front:
                self.draw_weapon(w, ox, oy, lights)

        # ---- player missiles and plain particles
        for b in self.bullets:
            x, y = int(b.x - ox), int(b.y - oy)
            if b.enemy:
                continue
            if b.kind == 'bolt':
                a = math.atan2(b.vy, b.vx)
                pygame.draw.line(s, BONE, (x, y), (x - math.cos(a) * 5, y - math.sin(a) * 5))
                lights.append((x, y, 12))
            elif b.kind == 'axe':
                self.blit_c(self.weapon_img('axe', b.rot), x, y)
                lights.append((x, y, 12))
            elif b.kind == 'fire':
                lights.append((x, y, 18))
        for q in self.particles:
            if not q[8]:
                s.fill(q[7], (int(q[0] - ox), int(q[1] - oy), q[5], q[5]))
        for f in self.effects:
            if f[0] == 'boom':
                lights.append((f[1] - ox, f[2] - oy, 32))

        # ---- darkness
        d = self.dark
        d.fill(BLACK + (255,))
        if self.state != 'dead':
            self.light(p.x - ox, p.y - oy, 110)
        for x, y, r in lights[:50]:
            self.light(x, y, r)
        s.blit(d, (0, 0))

        # ---- things that glow through the dark
        for m in self.marks:
            x, y = int(m[0] - ox), int(m[1] - oy)
            if m[3] < 0:
                continue
            big = m[2] == 'boss'
            if (m[3] // (6 if m[3] < 30 else 3)) % 2 == 0:
                r = 5 if big else 2
                pygame.draw.line(s, BLOOD, (x - r, y - r), (x + r, y + r), 2 if big else 1)
                pygame.draw.line(s, BLOOD, (x - r, y + r), (x + r, y - r), 2 if big else 1)
        for bl in self.blasts:
            x, y = int(bl[0] - ox), int(bl[1] - oy)
            if (bl[2] // (5 if bl[2] < 25 else 2)) % 2 == 0:
                pygame.draw.circle(s, BLOOD, (x, y), 26, 1)
            pygame.draw.circle(s, BLOOD, (x, y), max(1, bl[2] * 26 // 40), 1)
        for k in self.pickups:
            x, y = int(k.x - ox), int(k.y - oy)
            if k.kind == 'soul':
                if (fr + int(k.x)) % 20 < 14:
                    s.fill(BLOOD, (x - 1, y - 1, 3, 3))
                    s.set_at((x, y), BONE)
                else:
                    s.set_at((x, y), BLOOD)
            else:
                pygame.draw.rect(s, BONE, (x - 2, y - 3, 5, 7), 1)
                s.fill(BLOOD, (x - 1, y, 3, 3))
        for e in self.enemies:
            x, y = int(e.x - ox), int(e.y - oy)
            if not (-20 < x < W + 20 and -20 < y < H + 20):
                continue
            if e.kind == 'bat':
                y += int(math.sin(e.t * 0.3) * 2)
            big = e.kind in ('boss', 'revenant')
            for ex, ey in EYES[e.kind]:
                ex *= e.face
                if big:
                    s.fill(BLOOD, (x + ex - 1, y + ey - 1, 2, 2))
                else:
                    s.set_at((x + ex, y + ey), BLOOD)
            if e.kind == 'cultist' and e.wind > 0:
                pygame.draw.circle(s, BLOOD, (x, y - 9), 1 + (30 - e.wind) // 10)
            if (e.kind == 'hound' and e.phase == 'wind') or \
                    (e.kind == 'boss' and e.phase == 'charge' and e.pt > 40):
                ln = 60 if e.kind == 'hound' else 130
                if fr % 4 < 3:
                    for i in range(4, ln, 6):
                        s.set_at((int(x + math.cos(e.aim) * i), int(y + math.sin(e.aim) * i)),
                                 BLOOD)
        for b in self.bullets:
            x, y = int(b.x - ox), int(b.y - oy)
            if b.enemy:
                pygame.draw.circle(s, BLOOD, (x, y), b.r)
                s.set_at((x, y), BONE)
            elif b.kind == 'fire':
                pygame.draw.circle(s, BLOOD, (x, y), 3)
                s.fill(BONE, (x - 1, y - 1, 2, 2))
        for f in self.effects:
            if f[0] == 'boom':
                _, x, y, r, t, life = f
                x, y = int(x - ox), int(y - oy)
                if t < 3:
                    pygame.draw.circle(s, BONE, (x, y), int(r))
                else:
                    pygame.draw.circle(s, BLOOD, (x, y), int(r * (0.6 + t / life * 0.6)), 1)
            elif f[0] == 'zap':
                pts = f[1]
                if f[2] % 3 != 2:
                    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                        mx = (x0 + x1) / 2 + random.uniform(-5, 5)
                        my = (y0 + y1) / 2 + random.uniform(-5, 5)
                        pl = [(x0 - ox, y0 - oy), (mx - ox, my - oy), (x1 - ox, y1 - oy)]
                        pygame.draw.lines(s, BLOOD, False, pl, 2)
                        pygame.draw.lines(s, BONE, False, pl, 1)
        for q in self.particles:
            if q[8]:
                s.fill(q[7], (int(q[0] - ox), int(q[1] - oy), q[5], q[5]))
        for x, y, _, _, txt, life, col in self.dmgnums:
            if life > 8 or fr % 2:
                draw_text(s, txt, int(x - ox), int(y - oy), align='c', color=col)
        for x, y, txt, life, col in self.texts:
            if life > 10 or fr % 2:
                draw_text(s, txt, int(x - ox), int(y - oy), align='c', color=col)
        b = self.boss
        if b and not b.dead:
            bx, by = b.x - ox, b.y - oy
            if not (0 <= bx < W and 0 <= by < H) and fr % 30 < 20:
                a = math.atan2(by - H / 2, bx - W / 2)
                cx = W / 2 + math.cos(a) * (W / 2 - 14)
                cy = H / 2 + math.sin(a) * (H / 2 - 22)
                pygame.draw.polygon(s, BLOOD, [(cx + math.cos(a) * 6, cy + math.sin(a) * 6),
                                               (cx + math.cos(a + 2.4) * 5, cy + math.sin(a + 2.4) * 5),
                                               (cx + math.cos(a - 2.4) * 5, cy + math.sin(a - 2.4) * 5)])

    def draw_weapon(self, w, ox, oy, lights):
        s = self.screen
        p = self.player
        k = WEAPONS[w.kind]['kind']
        if k == 'orbit':
            for x, y in w.orbs:
                draw_skull(s, int(x - ox), int(y - oy))
                lights.append((x - ox, y - oy, 12))
            return
        if k == 'sweep' and w.t >= 0:
            reach = self.reach(w)
            ang = w.cur
            gx = p.x + math.cos(ang) * (reach - WLEN[w.kind])
            gy = p.y + math.sin(ang) * (reach - WLEN[w.kind])
            if w.t <= 9:
                # a short sliver trailing the blade, thickest at the edge
                a1 = ang - w.side * min(0.9, abs(ang - w.a0))
                n = 6
                outer, inner = [], []
                for i in range(n + 1):
                    a = a1 + (ang - a1) * i / n
                    th = 0.5 + 2.5 * i / n
                    outer.append((p.x - ox + math.cos(a) * reach, p.y - oy + math.sin(a) * reach))
                    inner.append((p.x - ox + math.cos(a) * (reach - th),
                                  p.y - oy + math.sin(a) * (reach - th)))
                if abs(ang - a1) > 0.05:
                    pygame.draw.polygon(s, BONE, outer + inner[::-1])
            self.blit_c(self.weapon_img(w.kind, ang), gx - ox, gy - oy)
            return
        ext = 0
        if k == 'thrust' and w.t >= 0:
            ext = max(0.0, THRUST[min(w.t, len(THRUST) - 1)] * self.reach(w) - WLEN[w.kind])
        gx = w.ax + math.cos(w.aim) * ext
        gy = w.ay + math.sin(w.aim) * ext
        self.blit_c(self.weapon_img(w.kind, w.aim), gx - ox, gy - oy)
        if w.kind == 'wand' and w.cd > self.cooldown(w) - 6:
            lights.append((gx - ox, gy - oy, 12))

    def draw_hud(self):
        s = self.screen
        p = self.player
        s.fill(BLACK, (3, 3, 82, 8))
        pygame.draw.rect(s, BONE, (3, 3, 82, 8), 1)
        s.fill(BLOOD, (4, 4, int(80 * max(0, p.hp) / p.maxhp), 6))
        draw_text(s, f'{math.ceil(p.hp)}/{p.maxhp}', 89, 4)
        pygame.draw.rect(s, BONE, (3, 13, 82, 3), 1)
        s.fill(BONE, (4, 14, int(80 * p.xp / p.need()), 1))
        draw_text(s, f'LV {p.lv}', 89, 12)
        s.fill(BLOOD, (4, 21, 3, 3))
        s.set_at((5, 22), BONE)
        draw_text(s, str(p.souls), 10, 20)
        if self.wave_boss() and self.boss:
            draw_text(s, f'WAVE {self.wave}', W // 2, 3, 1, 'c', BLOOD)
        elif self.state == 'play':
            draw_text(s, f'WAVE {self.wave}', W // 2, 3, 1, 'c', BLOOD)
            secs = math.ceil(self.wave_t / 60)
            draw_text(s, str(secs), W // 2, 11, 2, 'c', BLOOD if secs <= 5 else BONE)
        draw_text(s, f'SLAIN {self.kills}', W - 4, 4, align='r')
        b = self.boss
        if b and not b.dead:
            draw_text(s, BOSS_NAME, W // 2, H - 18, 1, 'c', BLOOD)
            s.fill(BLACK, (W // 2 - 80, H - 10, 160, 5))
            pygame.draw.rect(s, BONE, (W // 2 - 80, H - 10, 160, 5), 1)
            s.fill(BLOOD, (W // 2 - 79, H - 9, int(158 * max(0, b.hp) / b.maxhp), 3))
        if getattr(self, 'banner_t', 0) > 0 and (self.banner_t > 20 or self.frame % 2):
            draw_text(s, self.banner, W // 2, 50, 3 if len(self.banner) < 14 else 2, 'c', BLOOD)

    def stat_lines(self):
        p = self.player
        out = []
        for attr, label, pct in STATS:
            v = getattr(p, attr)
            if attr == 'maxhp':
                out.append((f'MAX HP {v}', BONE))
            else:
                out.append((f'{label} {v:+d}{"%" if pct else ""}',
                            BLOOD if v < 0 else BONE))
        for attr in ('plague', 'thorns'):
            v = getattr(p, attr)
            if v:
                out.append((fmt_effect(attr, v), BONE))
        return out

    def draw_icon(self, kind, x, y):
        self.blit_c(self.weapon_img(kind, -0.6), x, y)

    def update_hover(self):
        """Mouse selection only takes over once the mouse actually moves."""
        m = pygame.mouse.get_pos()
        moved = m != self.mouse
        self.mouse = m
        return m, moved

    def draw_cards(self):
        s = self.screen
        s.fill(BLACK)
        self.card_t += 1
        title = 'CHOOSE A WEAPON' if self.state == 'pick' else 'THE NIGHT GIVES'
        draw_text(s, title, W // 2, 14, 3, 'c', BLOOD)
        hint = 'A/D AND E, 1-4 OR CLICK'
        if self.state == 'level' and self.player.pending > 1:
            hint = f'{self.player.pending} TO CHOOSE   ' + hint
        draw_text(s, hint, W // 2, 36, 1, 'c')
        (mx, my), moved = self.update_hover()
        self.rects = []
        bw, bh, gap = 90, 100, 6
        x0 = (W - (bw * 4 + gap * 3)) // 2
        for i, c in enumerate(self.cards):
            r = pygame.Rect(x0 + i * (bw + gap), 50, bw, bh)
            self.rects.append((r, i))
            if moved and r.collidepoint(mx, my):
                self.card_sel = i
            self.draw_card(r, c, i == self.card_sel, str(i + 1))
        if self.state == 'level':
            for i, (txt, col) in enumerate(self.stat_lines()[:12]):
                draw_text(s, txt, 12 + (i % 6) * 64, 168 + (i // 6) * 9, 1, 'l', col, False)
        draw_text(s, f'WAVE {self.wave + 1} AWAITS' if self.state == 'pick' else
                  f'WAVE {self.wave} SURVIVED', W // 2, 205, 1, 'c')

    def draw_card(self, r, c, sel, label, price=None):
        s = self.screen
        pygame.draw.rect(s, BLOOD if sel else BONE, r, 2 if sel else 1)
        if sel:
            pygame.draw.polygon(s, BLOOD, [(r.centerx - 4, r.bottom + 3), (r.centerx + 4, r.bottom + 3),
                                           (r.centerx, r.bottom + 7)])
        draw_text(s, label, r.x + 4, r.y + 4, 1, 'l', BLOOD, False)
        if c.get('icon'):
            s.set_clip(r.inflate(-4, -4))
            self.draw_icon(c['icon'], r.centerx, r.y + 17)
            s.set_clip(None)
        elif c.get('tier', 1) > 1:
            draw_text(s, ROMAN[c['tier'] - 1], r.centerx, r.y + 12, 2, 'c', BLOOD, False)
        width = (r.w - 6) // 4
        y = r.y + 32
        for line in wrap(c['title'], width):
            draw_text(s, line, r.centerx, y, 1, 'c', BLOOD if sel else BONE, False)
            y += 7
        y += 4
        for para in c['lines']:
            for line in wrap(para, width):
                draw_text(s, line, r.centerx, y, 1, 'c', BONE, False)
                y += 7
            y += 2
        if price is not None:
            ok = self.player.souls >= price
            draw_text(s, f'{price} SOULS', r.centerx, r.bottom - 9, 1, 'c', BONE if ok else BLOOD,
                      False)

    def draw_shop(self):
        s = self.screen
        p = self.player
        s.fill(BLACK)
        self.card_t += 1
        draw_text(s, 'THE PEDLAR', 4, 4, 2, 'l', BLOOD)
        draw_text(s, f'NEXT: WAVE {self.wave + 1}' + ('  THE SHEPHERD COMES' if (self.wave + 1) % 5 == 0
                                                    else ''), 90, 8)
        s.fill(BLOOD, (W - 52, 6, 3, 3))
        s.set_at((W - 51, 7), BONE)
        draw_text(s, f'{p.souls}', W - 46, 6, 1, 'l', BONE)
        (mx, my), moved = self.update_hover()
        self.rects = []
        sel = self.ssel
        # offers
        for i, o in enumerate(self.offers):
            r = pygame.Rect(4 + i * 80, 20, 76, 94)
            self.rects.append((r, (0, i)))
            if moved and r.collidepoint(mx, my):
                sel[:] = [0, i]
            if o is None:
                pygame.draw.rect(s, BONE, r, 1)
                draw_text(s, 'SOLD', r.centerx, r.centery - 2, 1, 'c', BLOOD, False)
                if sel == [0, i]:
                    pygame.draw.rect(s, BLOOD, r, 2)
                continue
            self.draw_card(r, o, sel == [0, i], str(i + 1), o['price'])
        # stats
        draw_text(s, 'STATS', 330, 20, 1, 'l', BLOOD, False)
        for i, (txt, col) in enumerate(self.stat_lines()):
            draw_text(s, txt, 330, 29 + i * 7, 1, 'l', col, False)
        # weapons
        draw_text(s, f'WEAPONS {len(p.weapons)}/6', 4, 122, 1, 'l', BLOOD, False)
        for j, w in enumerate(p.weapons):
            r = pygame.Rect(4 + j * 31, 130, 28, 28)
            self.rects.append((r, (1, j)))
            if moved and r.collidepoint(mx, my):
                sel[:] = [1, j]
            on = sel == [1, j]
            pygame.draw.rect(s, BLOOD if on else BONE, r, 2 if on else 1)
            s.set_clip(r.inflate(-2, -2))
            self.draw_icon(w.kind, r.centerx, r.centery - 2)
            s.set_clip(None)
            draw_text(s, ROMAN[w.tier - 1], r.right - 3, r.bottom - 7, 1, 'r', BLOOD, False)
        # detail line for whatever is selected
        info = []
        if sel[0] == 1 and sel[1] < len(p.weapons):
            w = p.weapons[sel[1]]
            info = [f'{w.kind} {ROMAN[w.tier - 1]}'] + self.weapon_lines(w)
            can = self.merge_target(w.kind, w.tier, exclude=w) is not None
            info.append(f'E/CLICK SELL +{self.sell_value(w)}' +
                        ('   C/RIGHT CLICK COMBINE' if can else ''))
        elif sel[0] == 0 and sel[1] < len(self.offers) and self.offers[sel[1]]:
            o = self.offers[sel[1]]
            if o['type'] == 'weapon' and len(p.weapons) >= 6:
                info = ['YOUR HANDS ARE FULL', 'BUYING COMBINES IT WITH A MATCHING WEAPON'
                        if self.merge_target(*o['data']) else 'SELL OR COMBINE A WEAPON FIRST']
        for i, line in enumerate(info):
            draw_text(s, line, 196, 124 + i * 8, 1, 'l', BLOOD if i == 0 else BONE, False)
        # relics
        if p.relics:
            names = ', '.join(p.relics)
            for i, line in enumerate(wrap('RELICS: ' + names, 96)[:2]):
                draw_text(s, line, 4, 166 + i * 7, 1, 'l', BONE, False)
        # buttons
        for col, (label, x) in enumerate(((f'REROLL {self.reroll_cost}', 4),
                                          ('NEXT WAVE >', W - 84))):
            r = pygame.Rect(x, 196, 80, 16)
            self.rects.append((r, (2, col)))
            if moved and r.collidepoint(mx, my):
                sel[:] = [2, col]
            on = sel == [2, col]
            pygame.draw.rect(s, BLOOD if on else BONE, r, 2 if on else 1)
            draw_text(s, label, r.centerx, r.y + 6, 1, 'c', BLOOD if on else BONE, False)
        draw_text(s, 'WASD MOVE  E CHOOSE  C COMBINE  R REROLL', W // 2, 186, 1, 'c', BONE, False)
        if self.msg_t > 0:
            draw_text(s, self.msg, W // 2, 204, 1, 'c', BLOOD)

    def draw_cursor(self):
        mx, my = pygame.mouse.get_pos()
        s = self.screen
        for col, w in ((BLACK, 3), (BONE, 1)):
            for a, b in (((mx - 4, my), (mx - 2, my)), ((mx + 2, my), (mx + 4, my)),
                         ((mx, my - 4), (mx, my - 2)), ((mx, my + 2), (mx, my + 4))):
                pygame.draw.line(s, col, a, b, w)
        s.set_at((mx, my), BLOOD)

    def draw_title(self):
        s = self.screen
        s.fill(BLACK)
        for em in self.embers:
            em[1] -= em[2]
            em[0] += math.sin(self.t * 0.03 + em[2] * 10) * 0.2
            if em[1] < 0:
                em[0], em[1] = random.uniform(0, W), H
            s.set_at((int(em[0]), int(em[1])), BLOOD)
        draw_text(s, 'VIGIL', W // 2, 30, 6, 'c')
        draw_text(s, 'THE NIGHT IS LONG.', W // 2, 66, 1, 'c', BLOOD)
        lines = ['WASD  MOVE', 'YOUR WEAPONS STRIKE ON THEIR OWN',
                 'SURVIVE EACH WAVE, SPEND SOULS BETWEEN THEM',
                 'EVERY FIFTH NIGHT THE SHEPHERD COMES',
                 'ESC  PAUSE    F11  FULLSCREEN']
        for i, l in enumerate(lines):
            draw_text(s, l, W // 2, 86 + i * 9, 1, 'c')
        if (self.t // 30) % 2:
            draw_text(s, 'E OR CLICK TO BEGIN', W // 2, 150, 2, 'c', BLOOD)
        if self.best:
            draw_text(s, f'LONGEST VIGIL: WAVE {self.best}', W // 2, 190, 1, 'c')

    def draw(self):
        s = self.screen
        st = self.state
        if st == 'title':
            self.draw_title()
        elif st in ('pick', 'level'):
            self.draw_cards()
        elif st == 'shop':
            self.draw_shop()
        else:
            self.draw_world()
            self.draw_hud()
            if st == 'pause':
                s.blit(self.dim, (0, 0))
                draw_text(s, 'PAUSED', W // 2, 40, 3, 'c')
                draw_text(s, 'ESC  RESUME     X  ABANDON RUN', W // 2, 66, 1, 'c')
                ws = '  '.join(f'{w.kind} {ROMAN[w.tier - 1]}' for w in self.player.weapons)
                draw_text(s, ws, W // 2, 86, 1, 'c', BLOOD)
                for i, (txt, col) in enumerate(self.stat_lines()[:12]):
                    draw_text(s, txt, 12 + (i % 6) * 64, 104 + (i // 6) * 9, 1, 'l', col)
                for i, line in enumerate(wrap(', '.join(self.player.relics), 90)[:3]):
                    draw_text(s, line, W // 2, 130 + i * 8, 1, 'c')
            elif st == 'dead':
                self.dead_t += 1
                s.blit(self.dim, (0, 0))
                draw_text(s, 'THE NIGHT TAKES YOU', W // 2, 60, 3, 'c', BLOOD)
                draw_text(s, f'FELL ON WAVE {self.wave}   SLEW {self.kills}   LV {self.player.lv}',
                          W // 2, 92, 1, 'c')
                draw_text(s, f'LONGEST VIGIL: WAVE {self.best}', W // 2, 104, 1, 'c')
                if self.dead_t > 50:
                    draw_text(s, 'R OR CLICK TO KEEP VIGIL AGAIN', W // 2, 140, 2, 'c')
        if st in ('title', 'pick', 'level', 'shop', 'dead'):
            self.draw_cursor()

    # ---------------------------------------------------------- input / loop
    def handle(self, ev):
        st = self.state
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
        click = ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
        rclick = ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3
        key = ev.key if ev.type == pygame.KEYDOWN else None
        left = key in (pygame.K_a, pygame.K_LEFT)
        right = key in (pygame.K_d, pygame.K_RIGHT)
        ok = key in (pygame.K_e, pygame.K_RETURN)
        if st == 'title':
            if click or ok or key == pygame.K_SPACE:
                self.new_run()
            elif key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
        elif st in ('play', 'harvest'):
            if key == pygame.K_ESCAPE and st == 'play':
                self.state = 'pause'
        elif st == 'pause':
            if key == pygame.K_ESCAPE:
                self.state = 'play'
            elif key == pygame.K_x:
                self.state = 'title'
        elif st in ('pick', 'level'):
            n = len(self.cards)
            if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.pick_card(key - pygame.K_1)
            elif left:
                self.card_sel = (self.card_sel - 1) % n
            elif right:
                self.card_sel = (self.card_sel + 1) % n
            elif ok:
                self.pick_card(self.card_sel)
            elif click:
                for r, i in self.rects:
                    if r.collidepoint(ev.pos):
                        self.pick_card(i)
            elif key == pygame.K_ESCAPE and st == 'pick':
                self.state = 'title'
        elif st == 'shop':
            rows = self.shop_rows()
            sel = self.ssel
            if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                sel[:] = [0, key - pygame.K_1]
                self.shop_act(0, key - pygame.K_1)
            elif left or right:
                sel[1] = (sel[1] + (1 if right else -1)) % max(1, rows[sel[0]])
            elif key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
                step = 1 if key in (pygame.K_s, pygame.K_DOWN) else -1
                r = (sel[0] + step) % 3
                if rows[r] == 0:
                    r = (r + step) % 3
                sel[:] = [r, min(sel[1], rows[r] - 1)]
            elif ok:
                self.shop_act(*sel)
            elif key == pygame.K_c and sel[0] == 1:
                self.combine(sel[1])
            elif key == pygame.K_r:
                self.reroll()
            elif click or rclick:
                for r, (row, col) in self.rects:
                    if r.collidepoint(ev.pos):
                        sel[:] = [row, col]
                        if rclick and row == 1:
                            self.combine(col)
                        elif click:
                            self.shop_act(row, col)
        elif st == 'dead':
            if self.dead_t > 50 and (click or key == pygame.K_r):
                self.new_run()
            elif key == pygame.K_ESCAPE:
                self.state = 'title'

    def step(self):
        self.t += 1
        if self.state in ('play', 'harvest', 'dead'):
            if self.state == 'dead':
                self.frame += 1
                self.update_fx()
            else:
                self.update()

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
