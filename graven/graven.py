#!/usr/bin/env python3
"""GRAVEN - a tiny dark-fantasy top-down roguelike.

WASD move · mouse aim · LMB strike · RMB cast · SPACE/SHIFT roll · F drink vial
E pick up · ESC pause · F11 fullscreen
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
BLACK = (8, 6, 7)
BONE = (222, 210, 186)
BLOOD = (176, 22, 30)
KEY = (255, 0, 255)
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
DIRS8 = DIRS + [(1, 1), (1, -1), (-1, 1), (-1, -1)]
TAU = math.tau
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
AREAS = ['THE CRYPTS', 'THE OSSUARY', 'THE SUNKEN NAVE', 'THE ASHEN THRONE']

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


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def angdiff(a, b):
    return (a - b + math.pi) % TAU - math.pi


# ------------------------------------------------------------------ sound
class Sfx:
    SPECS = {  # dur, f0, f1, noise, vol, wave
        'swing': (0.09, 500, 150, 0.85, 0.12, 'sq'),
        'hit': (0.08, 260, 60, 0.6, 0.28, 'sq'),
        'deflect': (0.12, 1800, 1200, 0.15, 0.14, 'sq'),
        'cast': (0.18, 300, 1100, 0.05, 0.14, 'sin'),
        'nova': (0.35, 900, 120, 0.3, 0.2, 'sq'),
        'boom': (0.5, 110, 25, 0.85, 0.4, 'sq'),
        'hurt': (0.25, 300, 60, 0.45, 0.35, 'sq'),
        'pickup': (0.1, 500, 1000, 0.0, 0.12, 'sin'),
        'soul': (0.04, 1200, 1700, 0.0, 0.04, 'sin'),
        'stairs': (0.9, 90, 400, 0.1, 0.25, 'sin'),
        'level': (0.4, 300, 900, 0.0, 0.15, 'sin'),
        'empty': (0.05, 160, 140, 0.0, 0.1, 'sq'),
        'roll': (0.1, 200, 90, 0.9, 0.08, 'sq'),
        'drink': (0.3, 200, 500, 0.3, 0.15, 'sin'),
        'bolt': (0.12, 700, 300, 0.2, 0.09, 'sin'),
        'arrow': (0.08, 1100, 400, 0.5, 0.1, 'sq'),
        'draw': (0.35, 300, 600, 0.3, 0.05, 'sq'),
        'slam': (0.35, 90, 30, 0.7, 0.35, 'sq'),
        'die': (0.12, 220, 50, 0.6, 0.22, 'sq'),
        'chest': (0.2, 150, 500, 0.3, 0.18, 'sq'),
        'screech': (0.15, 2000, 2600, 0.4, 0.06, 'sq'),
        'growl': (0.3, 90, 60, 0.6, 0.14, 'sq'),
        'toll': (1.2, 110, 108, 0.0, 0.3, 'sin'),
        'rumble': (0.9, 70, 35, 0.8, 0.25, 'sq'),
        'charge': (1.0, 120, 700, 0.15, 0.12, 'sin'),
        'beam': (0.5, 900, 70, 0.5, 0.32, 'sq'),
        'ward': (0.35, 220, 45, 0.6, 0.3, 'sq'),
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
MELEE = {
    'sword': dict(dmg=4, cd=20, arc=1.9, range=22, kb=2.5, lunge=1.2, tier=0),
    'daggers': dict(dmg=2.5, cd=9, arc=1.2, range=17, kb=1.0, lunge=0.8, tier=1),
    'spear': dict(dmg=5, cd=24, arc=0.7, range=36, kb=3.0, lunge=1.8, tier=1),
    'greataxe': dict(dmg=9, cd=42, arc=2.8, range=27, kb=5.0, lunge=1.5, tier=1),
    'scythe': dict(dmg=5, cd=30, arc=3.8, range=29, kb=3.0, lunge=1.0, tier=2),
    'warhammer': dict(dmg=7, cd=36, arc=2.2, range=24, kb=6.0, lunge=1.4, tier=2),
}
SPELLS = {
    'firebolt': dict(cost=12, cd=18, n=1, spread=0.0, spd=4.0, dmg=5, kind='fire', tier=0,
                     desc='A SEARING BOLT'),
    'hexfan': dict(cost=20, cd=30, n=5, spread=0.5, spd=3.5, dmg=3, kind='fire', tier=1,
                   desc='A FAN OF FIVE BOLTS'),
    'bone spear': dict(cost=16, cd=24, n=1, spread=0.0, spd=7.0, dmg=6, kind='bone', tier=1,
                       desc='FAST, PIERCES THROUGH FOES'),
    'soul leech': dict(cost=18, cd=26, n=3, spread=0.45, spd=2.6, dmg=3, kind='leech', tier=1,
                       desc='HOMING WISPS THAT CAN HEAL YOU'),
    'warding ring': dict(cost=22, cd=40, dmg=4, kind='ring', tier=1,
                         desc='HURLS FOES AWAY AND BREAKS THEIR BOLTS'),
    'soulfire': dict(cost=30, cd=40, n=1, spread=0.0, spd=2.2, dmg=8, kind='orb', tier=2,
                     desc='A SLOW ORB THAT EXPLODES'),
    'blood nova': dict(cost=0, hpcost=2, cd=50, n=16, spread=0.0, spd=3.2, dmg=4,
                       kind='fire', tier=2, ring=True, desc='A RING OF BOLTS, PAID IN BLOOD'),
    'sunder beam': dict(cost=30, cd=30, dmg=14, kind='beam', charge=60, tier=2,
                        desc='CHARGE, THEN A BEAM THAT PIERCES ALL'),
    'spectral blades': dict(cost=35, cd=60, dmg=3, kind='blades', dur=360, tier=2,
                            desc='THREE BLADES CIRCLE YOU FOR 6 SECONDS'),
}
ENEMIES = {
    'ghoul': dict(hp=8, r=5, spd=0.7, souls=2),
    'bat': dict(hp=2, r=3, spd=1.5, souls=1),
    'cultist': dict(hp=7, r=5, spd=0.5, souls=3),
    'archer': dict(hp=6, r=5, spd=0.5, souls=3),
    'revenant': dict(hp=26, r=7, spd=0.45, souls=6),
    'boss': dict(hp=260, r=13, spd=0.7, souls=45),
    'wyrm': dict(hp=240, r=7, spd=1.35, souls=45),
    'wyrmseg': dict(hp=1, r=6, spd=0, souls=0),
}
EYES = {'ghoul': [(1, -3), (3, -3)], 'cultist': [(0, -3), (2, -3)], 'bat': [(-1, 0), (1, 0)],
        'archer': [(-1, -4), (1, -4)], 'revenant': [(0, -5), (2, -5)],
        'boss': [(-2, -7), (2, -7)], 'wyrm': [(3, -3), (5, -3)], 'wyrmseg': []}
BOSS_NAMES = {'boss': 'THE HOLLOW KING', 'wyrm': 'THE OSSUARY WYRM'}
BIG = ('boss', 'wyrm', 'wyrmseg')   # not shoved around by crowding or knockback
SPEAR_THRUST = (2, 9, 13, 13, 11, 8, 4, 1)  # spear extension (px) per swing frame
WYRM_SEGS, WYRM_GAP = 10, 5           # body segments; trail frames between them


def rid(e):
    """Identity that damage is de-duplicated on: wyrm segments share their head's."""
    return e.head.id if e.kind == 'wyrmseg' else e.id
BOONS = [
    ('IRON FLESH', 'MAX HP +4 AND HEAL 4', [('maxhp', '+', 4), ('hp', '+', 4)]),
    ('KEEN EDGE', 'MELEE DEALS 25% MORE', [('mdmg', '*', 1.25)]),
    ('SWIFT HAND', 'STRIKE 20% FASTER', [('aspd', '*', 1.2)]),
    ('DEEP WELL', 'MORE MANA, FASTER REGEN', [('maxmana', '+', 40), ('regen', '*', 1.35)]),
    ('HEXCRAFT', 'SPELLS DEAL 30% MORE', [('sdmg', '*', 1.3)]),
    ('BLOODTHIRST', 'KILLS CAN HEAL YOU', [('blood', '+', 1)]),
    ('LONG REACH', 'MELEE RANGE +25%', [('reach', '*', 1.25)]),
    ('FLEET FOOT', 'MOVE 15% FASTER', [('spd', '*', 1.15)]),
    ('SOUL EATER', 'SOULS RESTORE MORE MANA', [('soulmana', '+', 2)]),
    ('ALCHEMIST', 'ONE MORE VIAL, REFILLED', [('maxvials', '+', 1), ('vials', '+', 1)]),
    ('RIPOSTE', 'DEFLECTED BOLTS HIT TWICE AS HARD', [('riposte', '+', 1)]),
    ('SHADOWSTEP', 'ROLL TWICE AS OFTEN', [('roll_mult', '*', 0.5)]),
    ('LAST RITES', 'SURVIVE ONE LETHAL BLOW', [('spirit', '+', 1)]),
]

# Weapon boons only work while that weapon is in hand: (name, desc, [('wperk', 'add', weapon)])
WEAPON_BOONS = [
    ('RHYTHM OF STEEL', 'SWORD: EVERY THIRD SWING IN A COMBO STRIKES TWICE AS HARD', 'sword'),
    ('KNIFE JUGGLER', 'DAGGERS: EVERY SECOND SWING ALSO THROWS ONE', 'daggers'),
    ('POINT OF FAITH', 'SPEAR: HITS WITH THE TIP DEAL DOUBLE DAMAGE', 'spear'),
    ('RED HARVEST', 'GREATAXE: KILLS BURST IN BLOOD, HURTING NEARBY FOES', 'greataxe'),
    ('REAPER', 'SCYTHE: KILLS HEAL 1 HP', 'scythe'),
    ('TREMOR', 'WARHAMMER: EVERY SWING SENDS OUT A SHOCKWAVE', 'warhammer'),
]
WEAPON_BOONS = [(n, d, [('wperks', 'add', w)]) for n, d, w in WEAPON_BOONS]
WEAPON_PERK = {e[0][2]: d for _, d, e in WEAPON_BOONS}


# ------------------------------------------------------------------ graphics
def make_sprites():
    def surf(w, h):
        return pygame.Surface((w, h), pygame.SRCALPHA)

    def player(s, f):
        pygame.draw.polygon(s, BONE, [(2, 5), (8, 5), (10, 12), (0, 12)])
        pygame.draw.circle(s, BONE, (5, 4), 4)
        pygame.draw.line(s, BLACK, (5, 4), (9, 4))

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

    def archer(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.circle(s, c, (6, 3), 3, w)
        pygame.draw.line(s, c, (6, 6), (6, 12))
        pygame.draw.line(s, c, (4, 8), (8, 8))
        pygame.draw.line(s, c, (4, 10), (8, 10))
        pygame.draw.line(s, c, (4, 13), (8, 13))
        pygame.draw.arc(s, c, (8, 2, 5, 11), -math.pi / 2, math.pi / 2)
        pygame.draw.line(s, c, (10, 2), (10, 12))

    def revenant(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.rect(s, c, (3, 6, 11, 10), w)
        pygame.draw.rect(s, c, (5, 0, 8, 7), w)
        pygame.draw.line(s, BLACK, (7, 3), (11, 3))
        pygame.draw.circle(s, c, (3, 7), 2, w)
        pygame.draw.circle(s, c, (13, 7), 2, w)
        pygame.draw.line(s, c, (15, 2), (15, 15))

    def boss(s, f):
        w, c = (0, BLOOD) if f else (2, BONE)
        pygame.draw.polygon(s, c, [(16, 6), (26, 14), (29, 33), (3, 33), (6, 14)], w)
        pygame.draw.circle(s, c, (16, 10), 5, 0 if f else 1)
        pygame.draw.circle(s, BLACK, (16, 10), 4)
        pygame.draw.polygon(s, c, [(10, 6), (11, 0), (13, 4), (16, 0), (19, 4), (21, 0),
                                   (22, 6)], 0 if f else 1)
        pygame.draw.line(s, c, (16, 16), (16, 30), 1)

    def wyrm(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.polygon(s, c, [(1, 4), (8, 1), (14, 2), (18, 6), (18, 9), (14, 12), (8, 13),
                                   (1, 10)], w)
        pygame.draw.line(s, c, (7, 9), (18, 9))
        for tx in (10, 13, 16):
            pygame.draw.line(s, c, (tx, 9), (tx, 11))
        pygame.draw.line(s, c, (5, 2), (2, 0))
        pygame.draw.line(s, c, (8, 1), (7, 0))
        pygame.draw.ellipse(s, BLACK, (11, 3, 5, 3))

    def wyrmseg(s, f):
        w, c = (0, BLOOD) if f else (1, BONE)
        pygame.draw.circle(s, c, (6, 6), 4, w)
        for a, b in (((6, 0), (6, 2)), ((6, 10), (6, 12)), ((0, 6), (2, 6)), ((10, 6), (12, 6))):
            pygame.draw.line(s, c, a, b)
        s.set_at((6, 6), BLACK if f else BONE)

    defs = {'player': (11, 13, player), 'ghoul': (13, 13, ghoul), 'cultist': (13, 15, cultist),
            'bat': (13, 7, bat), 'archer': (13, 14, archer), 'revenant': (17, 17, revenant),
            'boss': (33, 34, boss), 'wyrm': (19, 15, wyrm), 'wyrmseg': (13, 13, wyrmseg)}
    S = {}
    for k, (w, h, fn) in defs.items():
        a, b = surf(w, h), surf(w, h)
        fn(a, False)
        fn(b, True)
        corpse = pygame.transform.rotate(a, 90)
        for y in range(corpse.get_height()):
            for x in range(corpse.get_width()):
                if (x + y) % 2:
                    corpse.set_at((x, y), (0, 0, 0, 0))
        S[k] = {1: (a, b), -1: (pygame.transform.flip(a, True, False),
                                pygame.transform.flip(b, True, False)), 'corpse': corpse}
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
        s.fill(BLACK, (5 + stride, 17, 2, 1)) if f % 2 else None
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
    corpse = pygame.transform.rotate(frames[1][0], 90)
    for y in range(corpse.get_height()):
        for x in range(corpse.get_width()):
            if (x + y) % 2:
                corpse.set_at((x, y), (0, 0, 0, 0))
    frames['corpse'] = corpse
    return frames


def make_weapon_sprites():
    """Each weapon points right with its grip on the surface centre, pre-rotated to 64 angles."""
    def sword(s, x, c):
        s.set_at((x, c), BONE)
        s.fill(BLOOD, (x + 1, c, 3, 1))
        s.fill(BONE, (x + 4, c - 2, 1, 5))
        s.fill(BONE, (x + 5, c - 1, 9, 3))
        s.fill(BLACK, (x + 6, c, 7, 1))
        s.set_at((x + 14, c), BONE)

    def daggers(s, x, c):
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

    def greataxe(s, x, c):
        s.fill(BONE, (x, c, 16, 1))
        s.fill(BLOOD, (x + 1, c, 3, 1))
        pygame.draw.polygon(s, BONE, [(x + 12, c - 1), (x + 15, c - 1), (x + 18, c - 5),
                                      (x + 18, c - 8), (x + 9, c - 8), (x + 9, c - 5)])
        s.fill(BLACK, (x + 10, c - 6, 8, 1))
        s.fill(BONE, (x + 13, c + 1, 1, 2))
        s.set_at((x + 16, c), BONE)

    def scythe(s, x, c):
        s.fill(BONE, (x, c, 17, 1))
        s.fill(BLOOD, (x + 1, c, 2, 1))
        s.fill(BONE, (x + 8, c + 1, 1, 2))
        pygame.draw.polygon(s, BONE, [(x + 16, c - 1), (x + 17, c + 1), (x + 13, c + 5),
                                      (x + 6, c + 7), (x + 1, c + 7), (x + 7, c + 5),
                                      (x + 12, c + 2)])

    def warhammer(s, x, c):
        s.fill(BONE, (x, c, 13, 1))
        s.fill(BLOOD, (x + 1, c, 3, 1))
        s.fill(BONE, (x + 12, c - 4, 4, 9))
        s.fill(BLACK, (x + 13, c - 3, 2, 1))
        s.fill(BLACK, (x + 13, c + 2, 2, 1))
        s.fill(BONE, (x + 16, c - 1, 2, 3))

    defs = {'sword': (15, sword), 'daggers': (9, daggers), 'spear': (23, spear),
            'greataxe': (18, greataxe), 'scythe': (18, scythe), 'warhammer': (18, warhammer)}
    out = {}
    for name, (length, fn) in defs.items():
        size = 2 * length + 5
        base = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        fn(base, c - 2, c)
        out[name] = [pygame.transform.rotate(base, -math.degrees(i * TAU / 64)) for i in range(64)]
    return out


def light_stamps(r, inner=0.4):
    """Alpha masks for one light radius: transparent = lit. The edge is dithered with a Bayer
    matrix; one variant per 4x4 phase so the pattern can stay fixed to the world while the
    light moves pixel by pixel (no shimmer, no snapping)."""
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
        for row in range(4):
            y = row * 4
            for x in range(0, T, 2):
                self.wall_tile.set_at((x, y), BONE)
            for vx in ((0, 8) if row % 2 == 0 else (4, 12)):
                self.wall_tile.set_at((vx, y + 2), BONE)
        self.surf = pygame.Surface((MW * T, MH * T))
        self.render()
        g = self.grid
        cands = [(x, y) for x, y in self.floor if g[y - 1][x] == 1 and g[y + 1][x] == 0]
        random.shuffle(cands)
        self.braziers = []
        for x, y in cands:
            if len(self.braziers) >= 7 + n // 2:
                break
            if all(abs(x - bx) + abs(y - by) > 6 for bx, by in self.braziers):
                self.braziers.append((x, y))
        self.braziers = [(x * T + 8, y * T + 5) for x, y in self.braziers]
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
        target = min(340 + n * 25, 680)
        steps = 0
        while count < target and steps < 20000:
            steps += 1
            for w in walkers:
                carve(w[0], w[1])
                if random.random() < 0.035:  # crypt chamber
                    rw, rh = random.randint(1, 3), random.randint(1, 2)
                    for a in range(-rw, rw + 1):
                        for b in range(-rh, rh + 1):
                            carve(w[0] + a, w[1] + b)
                r = random.random()
                if r < 0.15:
                    w[2] = (w[2] + 1) % 4
                elif r < 0.3:
                    w[2] = (w[2] + 3) % 4
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

    def ray(self, x, y, a, maxd=400, step=3):
        c, s = math.cos(a) * step, math.sin(a) * step
        d = 0
        while d < maxd:
            x += c
            y += s
            d += step
            if self.solid_at(x, y):
                break
        return x, y

    def render(self):
        s, g = self.surf, self.grid
        s.fill(BLACK)
        for ty in range(MH):
            for tx in range(MW):
                px, py = tx * T, ty * T
                h = (tx * 73856093 ^ ty * 19349663) & 0xFFFF
                if not g[ty][tx]:
                    if h % 3 == 0:
                        s.set_at((px + 1 + h % 14, py + 1 + (h >> 5) % 14), BONE)
                    if h % 23 == 0:  # crack
                        x, y = px + 3 + h % 9, py + 3 + (h >> 4) % 9
                        for i in range(4):
                            s.set_at((x + i, y + (i * h >> 3) % 2), BONE)
                    elif h % 29 == 0:  # bone
                        x, y = px + 4 + h % 7, py + 5 + (h >> 6) % 6
                        s.fill(BONE, (x, y, 5, 1))
                        s.fill(BONE, (x - 1, y - 1, 1, 3))
                        s.fill(BONE, (x + 5, y - 1, 1, 3))
                    elif h % 41 == 0:  # skull
                        x, y = px + 5 + h % 5, py + 5 + (h >> 7) % 5
                        pygame.draw.circle(s, BONE, (x, y), 2)
                        s.set_at((x - 1, y), BLACK)
                        s.set_at((x + 1, y), BLACK)
                    continue
                if not any(0 <= tx + dx < MW and 0 <= ty + dy < MH and not g[ty + dy][tx + dx]
                           for dx, dy in DIRS8):
                    continue
                s.blit(self.wall_tile, (px, py))
                if ty + 1 < MH and not g[ty + 1][tx]:
                    s.fill(BONE, (px, py + T - 2, T, 2))
                if ty > 0 and not g[ty - 1][tx]:
                    s.fill(BONE, (px, py, T, 1))
                if tx > 0 and not g[ty][tx - 1]:
                    s.fill(BONE, (px, py, 1, T))
                if tx + 1 < MW and not g[ty][tx + 1]:
                    s.fill(BONE, (px + T - 1, py, 1, T))

    def bleed(self, x, y, n, spread=5):
        for _ in range(n):
            px, py = x + random.gauss(0, spread), y + random.gauss(0, spread)
            if not self.solid_at(px, py):
                self.surf.set_at((int(px), int(py)), BLOOD)

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
        gx, gy = (tx_, ty_) if best is None else (best[0] * T + 8, best[1] * T + 8)
        dx, dy = gx - x, gy - y
        l = math.hypot(dx, dy) or 1
        return dx / l, dy / l


# ------------------------------------------------------------------ entities
class Player:
    def __init__(self):
        self.x = self.y = 0.0
        self.r = 4
        self.maxhp = self.hp = 12
        self.maxmana, self.mana, self.regen = 100, 100.0, 0.07
        self.vials, self.maxvials = 2, 3
        self.melee, self.spell = 'sword', 'firebolt'
        self.vx = self.vy = self.kx = self.ky = 0.0
        self.wkx = self.wky = self.kox = self.koy = 0.0
        self.acd = self.scd = self.iframes = self.roll_t = self.roll_cd = self.drink_t = 0
        self.rdx = self.rdy = 0.0
        self.aim = 0.0
        self.swing_t, self.swing_side, self.swing_aim = 0, 1, 0.0
        self.xp, self.lv, self.pending = 0, 1, 0
        self.boons = []
        self.mdmg = self.aspd = self.sdmg = self.reach = self.spd = self.roll_mult = 1.0
        self.blood = self.riposte = self.spirit = 0
        self.soulmana = 1
        self.combo = self.combo_t = self.swings = 0
        self.finisher = False
        self.swing_arc = 0.0
        self.swing_hit = set()
        self.charge_t = self.blades_t = 0
        self.blade_cd = {}
        self.walk = 0.0
        self.wperks = set()
        self.moving = False

    def need(self):
        return 14 + self.lv * 9


class Enemy:
    _id = 0

    def __init__(self, kind, x, y, hpm):
        d = ENEMIES[kind]
        Enemy._id += 1
        self.id = Enemy._id
        self.kind, self.x, self.y = kind, x, y
        self.r, self.spd, self.souls = d['r'], d['spd'], d['souls']
        self.hp = self.maxhp = d['hp'] * hpm
        self.cd = random.randint(50, 130)
        self.flash = 0
        self.kx = self.ky = 0.0
        self.face = 1
        self.alert = self.los = self.dead = self.hidden = False
        self.dist = 999.0
        self.wander = random.uniform(0, TAU)
        self.wt = 0
        self.moving = False
        self.strafe = 1
        self.wind = 0     # telegraph / wind-up frames
        self.act = 0      # active attack frames (lunge)
        self.aim = 0.0
        self.burst = 0
        self.phase, self.pt, self.spin = 'stalk', 120, 0.0
        self.bob = random.uniform(0, TAU)


class Pickup:
    __slots__ = ('kind', 'x', 'y', 'vx', 'vy', 'life', 'data')

    def __init__(self, kind, x, y, data=None, vx=0.0, vy=0.0, life=-1):
        self.kind, self.x, self.y, self.data = kind, x, y, data
        self.vx, self.vy, self.life = vx, vy, life


class Bullet:
    __slots__ = ('x', 'y', 'vx', 'vy', 'dmg', 'kind', 'enemy', 'life', 'r', 'hits')

    def __init__(self, x, y, a, spd, dmg, kind, enemy, life=150, r=2):
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * spd, math.sin(a) * spd
        self.dmg, self.kind, self.enemy, self.life, self.r = dmg, kind, enemy, life, r
        self.hits = None


# ------------------------------------------------------------------ game
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H), pygame.SCALED)
        pygame.display.set_caption('GRAVEN')
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()
        self.sfx = Sfx()
        self.spr = make_sprites()
        self.knight = make_knight()
        self.spr['player']['corpse'] = self.knight['corpse']
        self.wspr = make_weapon_sprites()
        self.striking = False
        self.dim = dither_surface(W, H)
        self.dark = pygame.Surface((W, H), pygame.SRCALPHA)
        self.stamps = {r: light_stamps(r) for r in (12, 20, 32, 44, 48, 56, 80)}
        self.state = 'title'
        self.t = 0
        self.best_file = os.path.join(os.environ.get('XDG_DATA_HOME') or
                                      os.path.expanduser('~/.local/share'), 'graven', 'best')
        self.best = 0
        try:
            with open(self.best_file) as f:
                self.best = int(f.read().strip() or 0)
        except (OSError, ValueError):
            pass
        self.show_map = True
        self.embers = [[random.uniform(0, W), random.uniform(0, H), random.uniform(0.2, 0.8)]
                       for _ in range(60)]

    # ---------------------------------------------------------- run setup
    def new_run(self):
        self.player = Player()
        self.n = 1
        self.kills = 0
        self.start_level()
        self.state = 'play'
        self.sfx.play('toll')

    @staticmethod
    def level_name(n, long=False):
        area, sub = (n - 1) // 3 + 1, (n - 1) % 3 + 1
        name = f'{area}-{sub}'
        return f'{AREAS[(area - 1) % len(AREAS)]} {name}' if long else name

    def start_level(self):
        n = self.n
        is_boss = (n - 1) % 3 == 2
        self.level = lvl = Level(n, is_boss)
        p = self.player
        p.x, p.y = lvl.start[0] * T + 8, lvl.start[1] * T + 8
        p.vx = p.vy = p.kx = p.ky = p.wkx = p.wky = p.kox = p.koy = 0
        p.iframes = 60
        p.vials = min(p.maxvials, p.vials + 1) if n > 1 else p.vials
        self.enemies, self.bullets, self.pickups, self.waves = [], [], [], []
        self.particles, self.effects, self.texts = [], [], []
        self.stairs = None
        self.boss = None
        self.frame = 0
        self.freeze = 0
        self.shake = 0.0
        self.trans_t = 0
        self.last_kill = (p.x, p.y)
        self.camx, self.camy = p.x - W / 2, p.y - H / 2
        self.snap_camera()
        self.seen = bytearray(MW * MH)
        self.minimap = pygame.Surface((MW, MH))
        self.minimap.fill(BLACK)
        self.mm_src = None
        self.reveal()

        hpm = 1 + 0.12 * (n - 1)
        pool = ['ghoul'] * 4 + ['bat'] * 2
        if n >= 2:
            pool += ['cultist'] * 3
        if n >= 3:
            pool += ['archer'] * 2
        if n >= 4:
            pool += ['revenant'] * 2
        sx, sy = lvl.start
        far = [f for f in lvl.floor if abs(f[0] - sx) + abs(f[1] - sy) > 10] or lvl.floor
        count = min(10 + n * 3, 42)
        if is_boss:
            count //= 2
        for _ in range(count):
            tx, ty = random.choice(far)
            kind = random.choice(pool)
            group = random.randint(3, 5) if kind == 'bat' else 1
            for _ in range(group):
                en = Enemy(kind, tx * T + 8 + random.uniform(-3, 3),
                           ty * T + 8 + random.uniform(-3, 3), hpm)
                if lvl.box_hits(en.x, en.y, en.r):
                    en.x, en.y = tx * T + 8, ty * T + 8
                self.enemies.append(en)
        if is_boss:
            ax, ay = lvl.arena
            if ((n - 1) // 3) % 2 == 0:
                self.enemies.append(Enemy('boss', ax * T + 8, ay * T + 8, hpm))
            else:
                self.spawn_wyrm(ax * T + 8, ay * T + 8, hpm)
        for kind in ['reliquary', 'coffer'] + (['reliquary'] if is_boss else []):
            tx, ty = random.choice([f for f in lvl.floor
                                    if 6 < abs(f[0] - sx) + abs(f[1] - sy)] or lvl.floor)
            self.pickups.append(Pickup(kind, tx * T + 8, ty * T + 8))

    def spawn_wyrm(self, x, y, hpm):
        head = Enemy('wyrm', x, y, hpm)
        head.trail = deque([(x, y)] * ((WYRM_SEGS + 1) * WYRM_GAP + 1),
                           maxlen=(WYRM_SEGS + 1) * WYRM_GAP + 1)
        head.segs = []
        for i in range(WYRM_SEGS):
            seg = Enemy('wyrmseg', x, y, 1)
            seg.head, seg.idx = head, i
            head.segs.append(seg)
        self.enemies.extend(reversed(head.segs))   # tail first, so the head draws on top
        self.enemies.append(head)

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

    def unstick(self, e):
        """Safety net: anything found overlapping a wall goes to the nearest open floor."""
        if self.level.box_hits(e.x, e.y, e.r):
            e.x, e.y = self.nearest_floor(e.x, e.y)

    def burst(self, x, y, n, spd=2.0, life=20, size=1, color=BONE, glow=False):
        for _ in range(n):
            a = random.uniform(0, TAU)
            s = random.uniform(0.3, spd)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s,
                                   random.randint(life // 2, life), size, 0.9, color, glow])

    def toast(self, s, color=BONE):
        p = self.player
        self.texts.append([p.x, p.y - 14, s, 50, color])

    def add_shake(self, s):
        self.shake = max(self.shake, s)

    def reveal(self):
        """Mark floor the player can see (within light range, line of sight) on the minimap,
        along with the walls around it."""
        p, lvl = self.player, self.level
        tx, ty = int(p.x // T), int(p.y // T)
        if (tx, ty) == self.mm_src:
            return
        self.mm_src = (tx, ty)
        g, seen, mm = lvl.grid, self.seen, self.minimap
        R = 6
        for y in range(max(1, ty - R), min(MH - 1, ty + R + 1)):
            for x in range(max(1, tx - R), min(MW - 1, tx + R + 1)):
                if g[y][x] or seen[y * MW + x] or (x - tx) ** 2 + (y - ty) ** 2 > R * R:
                    continue
                if not lvl.los(p.x, p.y, x * T + 8, y * T + 8):
                    continue
                seen[y * MW + x] = 1
                for dx, dy in DIRS8:
                    nx, ny = x + dx, y + dy
                    if g[ny][nx] and not seen[ny * MW + nx]:
                        seen[ny * MW + nx] = 1
                        mm.set_at((nx, ny), BONE)

    def snap_camera(self):
        # Lock the integer camera to the player's integer position so the player and the
        # world move in identical 1px steps (no sub-pixel jitter).
        p = self.player
        self.ox = math.floor(p.x) - math.floor(p.x - self.camx)
        self.oy = math.floor(p.y) - math.floor(p.y - self.camy)

    # ---------------------------------------------------------- player actions
    def perk(self, weapon):
        p = self.player
        return p.melee == weapon and weapon in p.wperks

    def reachable(self, x, y, r):
        """Clear line from the player to the target's centre or either flank (walls block melee)."""
        p, lvl = self.player, self.level
        a = math.atan2(y - p.y, x - p.x) + math.pi / 2
        ox, oy = math.cos(a) * r * 0.8, math.sin(a) * r * 0.8
        return (lvl.los(p.x, p.y, x, y) or lvl.los(p.x, p.y, x + ox, y + oy)
                or lvl.los(p.x, p.y, x - ox, y - oy))

    def strike(self):
        p = self.player
        m = MELEE[p.melee]
        if p.acd > 0 or p.roll_t > 0 or p.drink_t > 0 or p.charge_t > 0:
            return
        p.acd = max(4, int(m['cd'] / p.aspd))
        p.swing_t = 8
        p.swing_side *= -1
        p.swing_aim = p.aim
        p.swings += 1
        p.combo = p.combo + 1 if p.combo_t > 0 else 1
        p.combo_t = 50
        finisher = self.perk('sword') and p.combo >= 3
        if finisher:
            p.combo = 0
        p.finisher = finisher
        p.swing_arc = m['arc'] * (1.35 if finisher else 1)
        p.swing_hit = set()
        c, s = math.cos(p.aim), math.sin(p.aim)
        lunge = m['lunge'] * (1.6 if finisher else 1)
        p.wkx += c * lunge
        p.wky += s * lunge
        if self.perk('warhammer'):
            self.waves.append([p.x + c * 14, p.y + s * 14, 4, 42, 3 * p.mdmg, False, set(), 2, False])
            self.sfx.play('slam')
        if self.perk('daggers') and p.swings % 2 == 0:
            self.bullets.append(Bullet(p.x + c * 4, p.y + s * 4, p.aim, 6.5, 3 * p.mdmg,
                                       'dagger', False, 70, 2))
        if not self.swing_hits():
            self.sfx.play('swing')

    def swing_hits(self):
        """Resolve the current swing from the knight's current position. Called on the frame
        of the swing and on each following active frame, so enemies (and bolts) that step into
        the arc while it is still on screen are hit too; each enemy at most once per swing."""
        p = self.player
        m = MELEE[p.melee]
        rng, arc = m['range'] * p.reach, p.swing_arc
        c, s = math.cos(p.swing_aim), math.sin(p.swing_aim)
        hit = False
        self.striking = True
        for e in self.enemies:
            if e.dead or e.hidden or rid(e) in p.swing_hit:
                continue
            dx, dy = e.x - p.x, e.y - p.y
            d = math.hypot(dx, dy)
            if d > rng + e.r:
                continue
            # the enemy's whole body counts, not just its centre
            if p.melee == 'spear':
                along = dx * c + dy * s                  # distance along the thrust
                inside = -e.r < along < rng + e.r and abs(-dx * s + dy * c) < e.r + 5
            else:
                half = arc / 2 + math.asin(min(1.0, e.r / max(d, 0.01)))
                inside = abs(angdiff(math.atan2(dy, dx), p.swing_aim)) <= half
            if (inside or d < e.r + p.r + 3) \
                    and self.reachable(e.x, e.y, e.r):
                p.swing_hit.add(rid(e))
                dmg = m['dmg'] * p.mdmg * (2 if p.finisher else 1)
                if self.perk('spear') and d > rng * 0.6:
                    dmg *= 2
                    self.burst(e.x, e.y, 6, 2.5, 14, color=BLOOD, glow=True)
                self.hurt_enemy(e, dmg, c * m['kb'], s * m['kb'])
                self.level.bleed(e.x, e.y, 6)
                hit = True
        self.striking = False
        deflected = False
        for b in self.bullets:
            if not b.enemy:
                continue
            dx, dy = b.x - p.x, b.y - p.y
            if math.hypot(dx, dy) < rng + 5 and self.level.los(p.x, p.y, b.x, b.y) and \
                    abs(angdiff(math.atan2(dy, dx), p.swing_aim)) <= arc / 2 + 0.3:
                sp = max(3.5, math.hypot(b.vx, b.vy) * 1.4)
                b.vx, b.vy = c * sp, s * sp
                b.enemy = False
                b.kind = 'deflect'
                b.dmg = 4 * (1 + p.riposte)
                b.life = 150
                deflected = True
                self.burst(b.x, b.y, 4, 1.5, 10, glow=True)
        if deflected:
            self.sfx.play('deflect')
            self.freeze = max(self.freeze, 2)
        if hit:
            self.freeze = max(self.freeze, 5 if p.finisher else 3)
            self.add_shake(6 if p.finisher else 3)
            self.sfx.play('hit')
        return hit or deflected

    def cast(self):
        p = self.player
        sp = SPELLS[p.spell]
        if p.scd > 0 or p.roll_t > 0 or p.drink_t > 0 or p.charge_t > 0:
            return
        if sp.get('hpcost'):
            if p.hp <= sp['hpcost']:
                self.toast('TOO WEAK', BLOOD)
                p.scd = 20
                return
            p.hp -= sp['hpcost']
            self.level.bleed(p.x, p.y, 10)
        elif p.mana < sp['cost']:
            self.sfx.play('empty')
            self.toast('NOT ENOUGH MANA')
            p.scd = 20
            return
        p.mana -= sp['cost']
        p.scd = sp['cd']
        kind = sp['kind']
        dmg = sp['dmg'] * p.sdmg
        if kind == 'ring':
            self.waves.append([p.x, p.y, 6, 56, dmg, False, set(), 6, True])
            self.burst(p.x, p.y, 18, 3, 22, glow=True)
            self.add_shake(5)
            self.sfx.play('ward')
            return
        if kind == 'beam':
            p.charge_t = sp['charge']
            self.sfx.play('charge')
            return
        if kind == 'blades':
            p.blades_t = sp['dur']
            p.blade_cd = {}
            self.burst(p.x, p.y, 12, 2, 20, glow=True)
            self.sfx.play('cast')
            return
        x, y = p.x + math.cos(p.aim) * 6, p.y + math.sin(p.aim) * 6
        if self.level.solid_at(x, y):
            x, y = p.x, p.y
        for i in range(sp['n']):
            if sp.get('ring'):
                a = p.aim + i * TAU / sp['n']
            elif sp['n'] > 1:
                a = p.aim + (i / (sp['n'] - 1) - 0.5) * sp['spread']
            else:
                a = p.aim
            r = 5 if kind == 'orb' else 2
            b = Bullet(x, y, a, sp['spd'], dmg, kind, False, 200 if kind == 'leech' else 150, r)
            if kind == 'bone':
                b.hits = set()
            self.bullets.append(b)
        p.wkx -= math.cos(p.aim) * 0.8
        p.wky -= math.sin(p.aim) * 0.8
        self.effects.append(['flash', x, y, 0, 0, 0, 4])
        self.add_shake(2 if not sp.get('ring') else 5)
        self.sfx.play('nova' if sp.get('ring') else 'cast')

    def fire_beam(self):
        p = self.player
        c, s = math.cos(p.aim), math.sin(p.aim)
        x0, y0 = p.x + c * 6, p.y + s * 6
        x1, y1 = self.level.ray(x0, y0, p.aim, 420, 2)
        vx, vy = x1 - x0, y1 - y0
        ll = vx * vx + vy * vy or 1
        dmg = SPELLS['sunder beam']['dmg'] * p.sdmg

        def near(px, py, rad):
            t = clamp(((px - x0) * vx + (py - y0) * vy) / ll, 0, 1)
            return math.hypot(x0 + vx * t - px, y0 + vy * t - py) < rad

        struck = set()
        for e in self.enemies:
            if not e.dead and not e.hidden and rid(e) not in struck and near(e.x, e.y, e.r + 4):
                struck.add(rid(e))
                self.hurt_enemy(e, dmg, c * 3, s * 3)
                self.level.bleed(e.x, e.y, 10)
        for b in self.bullets:
            if b.enemy and near(b.x, b.y, 7):
                b.life = 0
        self.effects.append(['beam', x0, y0, x1, y1, 0, 16])
        self.burst(x1, y1, 14, 3, 20, 2, glow=True)
        p.wkx -= c * 3
        p.wky -= s * 3
        self.add_shake(7)
        self.freeze = max(self.freeze, 3)
        self.sfx.play('beam')

    def blade_positions(self):
        p = self.player
        out = []
        for i in range(3):
            a = self.frame * 0.13 + i * TAU / 3
            out.append((p.x + math.cos(a) * 22, p.y + math.sin(a) * 22, a))
        return out

    def update_blades(self):
        p = self.player
        dmg = SPELLS['spectral blades']['dmg'] * p.sdmg
        for bx, by, _ in self.blade_positions():
            for e in self.enemies:
                if e.dead or e.hidden or p.blade_cd.get(rid(e), 0) > self.frame:
                    continue
                if abs(e.x - bx) < e.r + 4 and abs(e.y - by) < e.r + 4:
                    p.blade_cd[rid(e)] = self.frame + 20
                    a = math.atan2(e.y - p.y, e.x - p.x)
                    self.hurt_enemy(e, dmg, math.cos(a) * 2, math.sin(a) * 2)
                    self.sfx.play('hit')
            for b in self.bullets:
                if b.enemy and abs(b.x - bx) < 5 and abs(b.y - by) < 5:
                    b.life = 0
                    self.burst(b.x, b.y, 3, 1.2, 8, glow=True)

    def blood_burst(self, x, y):
        p = self.player
        struck = set()
        for e in self.enemies:
            if not e.dead and rid(e) not in struck and math.hypot(e.x - x, e.y - y) < 30 + e.r:
                struck.add(rid(e))
                a = math.atan2(e.y - y, e.x - x)
                self.hurt_enemy(e, 5 * p.mdmg, math.cos(a) * 3, math.sin(a) * 3)
        self.effects.append(['boom', x, y, 28, 0, 0, 18, BLOOD])
        self.level.bleed(x, y, 40, 9)
        self.burst(x, y, 14, 3, 22, 2, BLOOD)
        self.add_shake(5)
        self.sfx.play('slam')

    def drink(self):
        p = self.player
        if p.vials <= 0 or p.hp >= p.maxhp or p.drink_t > 0 or self.state != 'play':
            if p.vials <= 0:
                self.toast('NO VIALS', BLOOD)
            return
        p.vials -= 1
        p.drink_t = 30
        p.hp = min(p.maxhp, p.hp + 6)
        self.sfx.play('drink')
        self.burst(p.x, p.y, 12, 1.5, 30, color=BLOOD, glow=True)
        self.toast('+6 HP', BLOOD)

    # ---------------------------------------------------------- combat
    def enemy_shot(self, e, a, spd, dmg=2, kind='ebolt', r=3):
        self.bullets.append(Bullet(e.x, e.y, a, spd, dmg, kind, True, 260, r))

    def hurt_enemy(self, e, dmg, kx=0.0, ky=0.0):
        if e.dead or e.hidden:
            return
        if e.kind == 'wyrmseg':          # the body is one creature: hits land on the head
            e.flash = 5
            self.burst(e.x, e.y, 4, 1.8, 14, color=BLOOD)
            e = e.head
            if e.dead:
                return
        e.hp -= dmg
        e.flash = 5
        e.alert = True
        kb = 0.1 if e.kind in BIG else (0.5 if e.kind == 'revenant' else 1.2)
        e.kx += kx * kb
        e.ky += ky * kb
        self.burst(e.x, e.y, 4, 1.8, 14, color=BLOOD)
        self.level.bleed(e.x, e.y, 3)
        if e.hp <= 0:
            self.kill(e)

    def hurt_player(self, dmg):
        p = self.player
        if p.iframes > 0 or self.state != 'play':
            return
        p.hp -= dmg
        p.iframes = 45
        self.add_shake(6)
        self.freeze = 4
        self.sfx.play('hurt')
        self.burst(p.x, p.y, 10, 2.5, color=BLOOD)
        self.level.bleed(p.x, p.y, 12)
        if p.hp <= 0 and p.spirit > 0:
            p.spirit -= 1
            p.hp = 1
            p.iframes = 90
            self.toast('LAST RITES!', BLOOD)
        if p.hp <= 0:
            p.hp = 0
            self.state = 'dead'
            self.dead_t = 0
            self.add_shake(12)
            self.sfx.play('toll')
            self.stamp_corpse('player', p.x, p.y)
            if self.n > self.best:
                self.best = self.n
                try:
                    os.makedirs(os.path.dirname(self.best_file), exist_ok=True)
                    with open(self.best_file, 'w') as f:
                        f.write(str(self.best))
                except OSError:
                    pass

    def explode(self, x, y, r, dmg):
        struck = set()
        for e in self.enemies:
            if not e.dead and rid(e) not in struck and math.hypot(e.x - x, e.y - y) < r + e.r:
                struck.add(rid(e))
                a = math.atan2(e.y - y, e.x - x)
                self.hurt_enemy(e, dmg, math.cos(a) * 3, math.sin(a) * 3)
        self.effects.append(['boom', x, y, r, 0, 0, 22])
        self.burst(x, y, 16, 3.0, 30, 2, BONE, True)
        self.add_shake(7)
        self.sfx.play('boom')

    def stamp_corpse(self, kind, x, y):
        img = self.spr[kind]['corpse']
        self.level.bleed(x, y, 25, 4)
        self.level.surf.blit(img, (int(x) - img.get_width() // 2, int(y) - img.get_height() // 2))

    def kill(self, e):
        p = self.player
        e.dead = True
        self.kills += e.kind != 'wyrmseg'
        self.last_kill = (e.x, e.y)
        self.stamp_corpse(e.kind, e.x, e.y)
        for _ in range(e.souls):
            a = random.uniform(0, TAU)
            s = random.uniform(0.5, 2.5)
            self.pickups.append(Pickup('soul', e.x, e.y, vx=math.cos(a) * s, vy=math.sin(a) * s))
        if random.random() < (0.07 if p.hp < p.maxhp / 2 else 0.03):
            self.pickups.append(Pickup('vial', e.x, e.y, life=900))
        if p.blood and p.hp < p.maxhp and random.random() < 0.08 * p.blood:
            p.hp += 1
            self.toast('+1 HP', BLOOD)
        if self.striking:
            if self.perk('scythe') and p.hp < p.maxhp:
                p.hp += 1
                self.toast('+1 HP', BLOOD)
            elif self.perk('greataxe'):
                self.striking = False
                self.blood_burst(e.x, e.y)
                self.striking = True
        self.burst(e.x, e.y, 12, 2.5, 25, color=BLOOD)
        self.sfx.play('die')
        self.add_shake(2)
        if e.kind == 'wyrm':
            for seg in e.segs:
                if not seg.dead:
                    seg.dead = True
                    self.stamp_corpse('wyrmseg', seg.x, seg.y)
                    self.burst(seg.x, seg.y, 6, 2, 20, color=BLOOD)
        if e.kind in ('boss', 'wyrm'):
            self.freeze = 30
            self.add_shake(16)
            self.boss = None
            for _ in range(5):
                self.effects.append(['boom', e.x + random.uniform(-24, 24),
                                     e.y + random.uniform(-24, 24), 28, 0, 0, 34])
            self.level.bleed(e.x, e.y, 200, 14)
            self.sfx.play('boom')
            self.sfx.play('toll')

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
            self.update_player(ix, iy, keys[pygame.K_SPACE] or keys[pygame.K_LSHIFT])
            if mb[0]:
                self.strike()
            if mb[2]:
                self.cast()
        lvl.update_flow(p.x, p.y)
        for e in self.enemies[:]:
            if not e.dead:
                self.update_enemy(e)
        self.separate()
        # active frames of a swing: resolve against where everything is drawn this frame
        if self.state == 'play' and 3 <= p.swing_t <= 7:
            self.swing_hits()
        self.update_bullets()
        self.update_waves()
        self.update_pickups()
        self.update_fx()
        self.enemies = [e for e in self.enemies if not e.dead]

        if not self.enemies and self.stairs is None and self.frame > 30:
            x, y = self.last_kill
            self.stairs = [x, y, 0]
            self.sfx.play('stairs')
            self.add_shake(5)
        if self.stairs:
            self.stairs[2] += 1
            d = math.hypot(self.stairs[0] - p.x, self.stairs[1] - p.y)
            if d < 9 and self.stairs[2] > 40 and self.state == 'play':
                self.state = 'trans'
                self.trans_t = 0
                self.sfx.play('stairs')

        ax = clamp((mx - W / 2) * 0.25, -40, 40)
        ay = clamp((my - H / 2) * 0.25, -28, 28)
        self.camx += (p.x - p.kox + ax - W / 2 - self.camx) * 0.15
        self.camy += (p.y - p.koy + ay - H / 2 - self.camy) * 0.15
        self.snap_camera()
        self.reveal()
        self.shake *= 0.85
        if self.shake < 1:
            self.shake = 0

    def update_player(self, ix, iy, roll):
        p = self.player
        for a in ('acd', 'scd', 'iframes', 'roll_cd', 'drink_t', 'swing_t'):
            v = getattr(p, a)
            if v > 0:
                setattr(p, a, v - 1)
        p.mana = min(p.maxmana, p.mana + p.regen)
        l = math.hypot(ix, iy)
        if l:
            ix, iy = ix / l, iy / l
        if p.combo_t > 0:
            p.combo_t -= 1
        if p.charge_t > 0:
            p.charge_t -= 1
            if self.frame % 2 == 0:
                a = random.uniform(0, TAU)
                hx, hy = p.x + math.cos(p.aim) * 6, p.y + math.sin(p.aim) * 6
                self.particles.append([hx + math.cos(a) * 18, hy + math.sin(a) * 18,
                                       -math.cos(a) * 1.5, -math.sin(a) * 1.5, 12, 1, 1,
                                       BONE, True])
            if p.charge_t == 0:
                self.fire_beam()
        if p.blades_t > 0:
            p.blades_t -= 1
            self.update_blades()
        if roll and p.roll_t == 0 and p.roll_cd == 0 and p.drink_t == 0:
            p.charge_t = 0
            p.rdx, p.rdy = (ix, iy) if l else (math.cos(p.aim), math.sin(p.aim))
            p.roll_t = 14
            p.roll_cd = int(50 * p.roll_mult)
            p.iframes = max(p.iframes, 12)
            self.sfx.play('roll')
        if p.roll_t > 0:
            p.roll_t -= 1
            dx, dy = p.rdx * 3.2, p.rdy * 3.2
            p.vx, p.vy = dx * 0.5, dy * 0.5
            if self.frame % 3 == 0:
                self.particles.append([p.x, p.y + 3, 0, 0, 15, 1, 1, BONE, False])
        else:
            spd = 1.45 * p.spd * (0.4 if p.drink_t else 1) * (0.6 if p.swing_t > 4 else 1) \
                * (0.35 if p.charge_t else 1)
            p.vx += (ix * spd - p.vx) * 0.35
            p.vy += (iy * spd - p.vy) * 0.35
            dx, dy = p.vx, p.vy
        x0, y0 = p.x, p.y
        tot_x, tot_y = dx + p.kx + p.wkx, dy + p.ky + p.wky
        self.move(p, tot_x, tot_y)
        # weapon lunge/kick displacement is hidden from the camera, which eases back
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
        sp = math.hypot(p.vx, p.vy)
        p.moving = sp > 0.3 and p.roll_t == 0
        p.walk += sp

    def update_enemy(self, e):
        p, lvl = self.player, self.level
        if e.kind == 'wyrmseg':
            self.update_wyrmseg(e)
            return
        if (self.frame + e.id) % 20 == 0 and not e.hidden:
            self.unstick(e)
        dx, dy = p.x - e.x, p.y - e.y
        dist = math.hypot(dx, dy)
        e.dist = dist
        ang = math.atan2(dy, dx)
        if (self.frame + e.id) % 5 == 0:
            e.los = dist < 300 and lvl.los(e.x, e.y, p.x, p.y)
        if not e.alert and e.los and dist < 170:
            e.alert = True
            if e.kind == 'ghoul' and random.random() < 0.5:
                self.sfx.play('growl')
            elif e.kind == 'bat':
                self.sfx.play('screech')
        if e.flash:
            e.flash -= 1
        mvx = mvy = 0.0
        k, spd = e.kind, e.spd

        def chase(mult=1.0):
            if e.los:
                return math.cos(ang) * spd * mult, math.sin(ang) * spd * mult
            nx, ny = lvl.nav(e.x, e.y, p.x, p.y)
            return nx * spd * mult, ny * spd * mult

        if k == 'boss':
            if e.alert:
                self.update_boss(e, dist, ang)
            return
        if k == 'wyrm':
            if e.alert:
                self.update_wyrm(e, dist, ang)
            return
        if not e.alert:
            e.wt -= 1
            if e.wt <= 0:
                e.wander = random.uniform(0, TAU)
                e.wt = random.randint(40, 120)
                e.moving = random.random() < 0.5
            if e.moving:
                mvx, mvy = math.cos(e.wander) * spd * 0.4, math.sin(e.wander) * spd * 0.4
        elif k == 'ghoul':
            if e.act > 0:
                e.act -= 1
                mvx, mvy = math.cos(e.aim) * 3.0, math.sin(e.aim) * 3.0
                if dist < e.r + p.r + 2:
                    self.hurt_player(2)
            elif e.wind > 0:
                e.wind -= 1
                e.aim = ang
                if e.wind == 0:
                    e.act = 10
            else:
                mvx, mvy = chase()
                e.cd -= 1
                if e.los and dist < 34 and e.cd <= 0:
                    e.wind = 16
                    e.cd = random.randint(60, 90)
                if dist < e.r + p.r + 1:
                    self.hurt_player(1)
        elif k == 'bat':
            e.bob += 0.25
            mvx, mvy = chase()
            mvx += math.cos(e.bob * 1.3) * 1.2
            mvy += math.sin(e.bob) * 1.2
            if dist < e.r + p.r + 1:
                self.hurt_player(1)
                e.kx -= math.cos(ang) * 3
                e.ky -= math.sin(ang) * 3
        elif k == 'cultist':
            if e.burst > 0:
                if self.frame % 8 == 0:
                    e.burst -= 1
                    self.enemy_shot(e, ang + random.uniform(-0.1, 0.1),
                                    2.0 + 0.05 * min(self.n, 12))
                    self.sfx.play('bolt')
            elif e.wind > 0:
                e.wind -= 1
                if e.wind == 0:
                    e.burst = 3
                    e.cd = random.randint(110, 160)
            elif e.los:
                e.wt -= 1
                if e.wt <= 0:
                    e.strafe = random.choice((-1, 1))
                    e.wt = random.randint(40, 100)
                pa = ang + math.pi / 2 * e.strafe
                mvx, mvy = math.cos(pa) * spd * 0.6, math.sin(pa) * spd * 0.6
                if dist > 130:
                    mvx += math.cos(ang) * spd
                    mvy += math.sin(ang) * spd
                elif dist < 80:
                    mvx -= math.cos(ang) * spd
                    mvy -= math.sin(ang) * spd
                e.cd -= 1
                if e.cd <= 0 and dist < 220:
                    e.wind = 24
            else:
                mvx, mvy = chase()
        elif k == 'archer':
            if e.wind > 0:
                e.wind -= 1
                if e.wind > 12 and e.los:
                    e.aim = ang
                if e.wind == 0:
                    self.enemy_shot(e, e.aim, 5.5, 3, 'arrow', 2)
                    self.sfx.play('arrow')
                    e.cd = random.randint(100, 150)
            elif e.los and dist < 300:
                e.cd -= 1
                if dist < 80:
                    mvx, mvy = -math.cos(ang) * spd, -math.sin(ang) * spd
                if e.cd <= 0:
                    e.wind = 50
                    e.aim = ang
                    self.sfx.play('draw')
            else:
                mvx, mvy = chase()
        elif k == 'revenant':
            if e.wind > 0:
                e.wind -= 1
                if e.wind == 0:
                    self.waves.append([e.x, e.y, 6, 52, 3, True, set(), 0, False])
                    self.add_shake(6)
                    self.sfx.play('slam')
                    e.cd = random.randint(90, 130)
            else:
                mvx, mvy = chase()
                e.cd -= 1
                if dist < 40 and e.cd <= 0 and e.los:
                    e.wind = 34
                if dist < e.r + p.r + 1:
                    self.hurt_player(2)
        e.face = 1 if dx > 0 else -1
        self.move(e, mvx + e.kx, mvy + e.ky)
        e.kx *= 0.7
        e.ky *= 0.7

    def update_wyrmseg(self, e):
        h = e.head
        if h.dead:
            e.dead = True
            return
        e.hidden = h.hidden
        e.x, e.y = h.trail[-1 - (e.idx + 1) * WYRM_GAP]
        e.face = h.face
        if e.flash:
            e.flash -= 1
        p = self.player
        if not e.hidden and h.alert and math.hypot(p.x - e.x, p.y - e.y) < e.r + p.r:
            self.hurt_player(2)

    def nearest_floor(self, x, y):
        lvl = self.level
        tx, ty = int(x // T), int(y // T)
        for r in range(12):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r and not lvl.solid(tx + dx, ty + dy):
                        return (tx + dx) * T + 8, (ty + dy) * T + 8
        return x, y

    def update_wyrm(self, e, dist, ang):
        p, lvl = self.player, self.level
        if self.boss is None:
            self.boss = e
            self.sfx.play('toll')
        rage = e.hp < e.maxhp / 2
        e.pt -= 1
        if e.phase == 'stalk':
            e.phase, e.pt, e.aim = 'slither', 150, ang
        if e.phase == 'slither':
            spd = e.spd * (1.3 if rage else 1)
            if e.los:
                want = ang + math.sin(self.frame * 0.07) * 0.7
            else:
                nx, ny = lvl.nav(e.x, e.y, p.x, p.y)
                want = math.atan2(ny, nx)
            e.aim += clamp(angdiff(want, e.aim), -0.08, 0.08)
            hx, hy = self.move(e, math.cos(e.aim) * spd + e.kx, math.sin(e.aim) * spd + e.ky)
            if hx:
                e.aim = math.pi - e.aim
            if hy:
                e.aim = -e.aim
            e.trail.append((e.x, e.y))
            if e.pt <= 0:
                e.phase = random.choice(['burrow', 'burrow', 'spit', 'rattle'])
                e.pt = {'burrow': 130, 'spit': 50, 'rattle': 70}[e.phase]
                if e.phase == 'burrow':
                    e.hidden = True
                    for seg in e.segs:
                        self.burst(seg.x, seg.y, 5, 2, 25, color=BONE)
                    self.add_shake(5)
                    self.sfx.play('rumble')
        elif e.phase == 'burrow':
            if e.pt > 40:  # tunnels through stone straight at the player
                a = math.atan2(p.y - e.y, p.x - e.x)
                e.x = clamp(e.x + math.cos(a) * 2.4, T, (MW - 1) * T)
                e.y = clamp(e.y + math.sin(a) * 2.4, T, (MH - 1) * T)
                if self.frame % 2 == 0:
                    self.particles.append([e.x + random.uniform(-5, 5), e.y + random.uniform(-3, 3),
                                           random.uniform(-0.5, 0.5), -random.uniform(0.2, 0.8),
                                           22, 1, 0.95, BONE, True])
            elif e.pt == 40:
                if lvl.box_hits(e.x, e.y, e.r):
                    e.x, e.y = self.nearest_floor(e.x, e.y)
                self.sfx.play('growl')
            elif e.pt == 10:
                e.hidden = False
                e.trail.extend([(e.x, e.y)] * e.trail.maxlen)
                n = 18 if rage else 14
                for i in range(n):
                    self.enemy_shot(e, i * TAU / n + random.uniform(-0.1, 0.1), 2.0, 2, 'ebolt', 3)
                if dist < e.r + p.r + 16:
                    self.hurt_player(3)
                self.burst(e.x, e.y, 24, 3.5, 30, 2, BONE)
                self.add_shake(10)
                self.sfx.play('boom')
                e.aim = ang
            if e.pt <= 0:
                e.phase, e.pt = 'slither', 150
        elif e.phase == 'spit':
            e.aim += clamp(angdiff(ang, e.aim), -0.1, 0.1)
            if e.pt in (40, 28, 16):
                n = 7 if rage else 5
                for i in range(n):
                    self.enemy_shot(e, e.aim + (i - n // 2) * 0.22, 2.6, 2, 'ebolt', 3)
                self.sfx.play('bolt')
                self.add_shake(2)
            if e.pt <= 0:
                e.phase, e.pt = 'slither', 150
        elif e.phase == 'rattle':
            e.flash = 2 if (e.pt // 4) % 2 and e.pt > 55 else 0
            if e.pt in ((50, 30, 10) if rage else (50, 25)):
                prev = e
                for seg in e.segs:
                    a = math.atan2(seg.y - prev.y, seg.x - prev.x)
                    for side in (-1, 1):
                        self.enemy_shot(seg, a + side * math.pi / 2, 1.7, 2, 'ebolt', 3)
                    prev = seg
                self.sfx.play('nova')
                self.add_shake(3)
            if e.pt <= 0:
                e.phase, e.pt = 'slither', 150
        if not e.hidden and dist < e.r + p.r:
            self.hurt_player(3)
        e.face = 1 if math.cos(e.aim) >= 0 else -1
        e.kx *= 0.7
        e.ky *= 0.7

    def update_boss(self, e, dist, ang):
        p = self.player
        if self.boss is None:
            self.boss = e
            self.sfx.play('toll')
        rage = e.hp < e.maxhp / 2
        spd = e.spd * (1.35 if rage else 1)
        e.pt -= 1
        mvx = mvy = 0.0
        if e.phase == 'stalk':
            if e.los:
                mvx, mvy = math.cos(ang) * spd, math.sin(ang) * spd
            else:
                nx, ny = self.level.nav(e.x, e.y, p.x, p.y)
                mvx, mvy = nx * spd, ny * spd
            e.cd -= 1
            if e.cd <= 0 and e.los:
                n = 5 if rage else 3
                for i in range(n):
                    self.enemy_shot(e, ang + (i - n // 2) * 0.22, 2.4)
                self.sfx.play('bolt')
                e.cd = 35 if rage else 45
            if e.pt <= 0:
                opts = ['spiral', 'slam', 'blink', 'spiral', 'slam']
                if sum(1 for x in self.enemies if x.kind == 'ghoul') < 4:
                    opts.append('summon')
                e.phase = random.choice(opts)
                e.pt = {'spiral': 120, 'slam': 80, 'blink': 60, 'summon': 40}[e.phase]
        elif e.phase == 'spiral':
            if e.pt % 5 == 0:
                arms = 3 if rage else 2
                e.spin += 0.21
                for i in range(arms):
                    self.enemy_shot(e, e.spin + i * TAU / arms, 2.0)
                if e.pt % 15 == 0:
                    self.sfx.play('bolt')
            if e.pt <= 0:
                e.phase, e.pt = 'stalk', 140
        elif e.phase == 'slam':
            if e.pt > 50:
                e.flash = 2 if (e.pt // 4) % 2 else 0
            elif e.pt in (50, 38, 26):
                self.waves.append([e.x, e.y, 8, 100, 3, True, set(), 0, False])
                self.add_shake(8)
                self.sfx.play('slam')
            if e.pt <= 0:
                e.phase, e.pt = 'stalk', 140
        elif e.phase == 'blink':
            if e.pt == 59:
                e.hidden = True
                self.burst(e.x, e.y, 24, 3, 30, 2, BLOOD, True)
                self.sfx.play('cast')
            elif e.pt == 20:
                for _ in range(12):
                    a = random.uniform(0, TAU)
                    nx, ny = p.x + math.cos(a) * 75, p.y + math.sin(a) * 75
                    if not self.level.box_hits(nx, ny, e.r):
                        e.x, e.y = nx, ny
                        break
                e.hidden = False
                for i in range(12):
                    self.enemy_shot(e, i * TAU / 12, 1.8)
                self.burst(e.x, e.y, 24, 3, 30, 2, BLOOD, True)
                self.sfx.play('nova')
            if e.pt <= 0:
                e.phase, e.pt = 'stalk', 140
        elif e.phase == 'summon':
            if e.pt == 39:
                for i in range(3):
                    a = i * TAU / 3
                    g = Enemy('ghoul', e.x + math.cos(a) * 20, e.y + math.sin(a) * 20, 1)
                    if not self.level.box_hits(g.x, g.y, g.r):
                        g.alert = True
                        self.enemies.append(g)
                self.burst(e.x, e.y, 16, 2.5, 25, color=BLOOD)
                self.sfx.play('growl')
            if e.pt <= 0:
                e.phase, e.pt = 'stalk', 140
        if not e.hidden and dist < e.r + p.r:
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
                    if a.kind not in BIG:
                        self.move(a, -ux, -uy)
                    if b.kind not in BIG:
                        self.move(b, ux, uy)

    def update_bullets(self):
        p, lvl = self.player, self.level
        keep = []
        for b in self.bullets:
            b.life -= 1
            if b.kind == 'leech':
                tgt, td = None, 160
                for e in self.enemies:
                    if not e.dead and not e.hidden:
                        d = abs(e.x - b.x) + abs(e.y - b.y)
                        if d < td:
                            tgt, td = e, d
                if tgt:
                    cur = math.atan2(b.vy, b.vx)
                    turn = clamp(angdiff(math.atan2(tgt.y - b.y, tgt.x - b.x), cur), -0.16, 0.16)
                    sp = math.hypot(b.vx, b.vy)
                    b.vx, b.vy = math.cos(cur + turn) * sp, math.sin(cur + turn) * sp
            b.x += b.vx
            b.y += b.vy
            if b.kind in ('fire', 'orb', 'leech') and self.frame % 3 == 0:
                self.particles.append([b.x, b.y, random.uniform(-0.3, 0.3), -0.3, 12, 1, 0.95,
                                       BLOOD if b.kind == 'fire' else BONE, True])
            if lvl.solid_at(b.x, b.y) or b.life <= 0:
                if b.kind == 'orb':
                    self.explode(b.x - b.vx, b.y - b.vy, 34, b.dmg)
                else:
                    self.burst(b.x - b.vx, b.y - b.vy, 3, 1.2, 10,
                               color=BLOOD if b.enemy else BONE, glow=True)
                continue
            if b.enemy:
                if math.hypot(p.x - b.x, p.y - b.y) < p.r + b.r - 1 and p.iframes == 0:
                    self.hurt_player(b.dmg)
                    continue
            else:
                hit = None
                for e in self.enemies:
                    if e.dead or e.hidden or (b.hits is not None and rid(e) in b.hits):
                        continue
                    if abs(e.x - b.x) < e.r + b.r and abs(e.y - b.y) < e.r + b.r:
                        hit = e
                        break
                if hit:
                    if b.kind == 'orb':
                        self.explode(b.x, b.y, 34, b.dmg)
                        continue
                    sp = math.hypot(b.vx, b.vy) or 1
                    self.hurt_enemy(hit, b.dmg, b.vx / sp * 1.5, b.vy / sp * 1.5)
                    if b.kind == 'leech' and p.hp < p.maxhp and random.random() < 0.25:
                        p.hp += 1
                        self.toast('+1 HP', BLOOD)
                    if b.hits is not None:
                        b.hits.add(rid(hit))
                    else:
                        continue
            keep.append(b)
        self.bullets = keep

    def update_waves(self):
        # wave = [x, y, radius, max radius, damage, from enemy, already hit, knockback, breaks bolts]
        p = self.player
        keep = []
        for w in self.waves:
            w[2] += 2.6
            x, y, r, maxr, dmg, enemy, hit, kb, breaks = w
            if enemy:
                if 'p' not in hit and abs(math.hypot(p.x - x, p.y - y) - r) < 5 \
                        and p.iframes == 0:
                    hit.add('p')
                    self.hurt_player(dmg)
            else:
                for e in self.enemies:
                    if rid(e) not in hit and not e.dead and \
                            abs(math.hypot(e.x - x, e.y - y) - r) < e.r + 3:
                        hit.add(rid(e))
                        a = math.atan2(e.y - y, e.x - x)
                        self.hurt_enemy(e, dmg, math.cos(a) * kb, math.sin(a) * kb)
                if breaks:
                    for b in self.bullets:
                        if b.enemy and math.hypot(b.x - x, b.y - y) < r + 3:
                            b.life = 0
            if r < maxr:
                keep.append(w)
        self.waves = keep

    def update_pickups(self):
        p = self.player
        keep = []
        for k in self.pickups:
            dx, dy = p.x - k.x, p.y - k.y
            d = math.hypot(dx, dy) or 1
            if k.kind == 'soul':
                if d < 40 or self.stairs:
                    s = 2.5 if d < 40 else 5
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
                    p.mana = min(p.maxmana, p.mana + 1 + p.soulmana)
                    self.sfx.play('soul')
                    if p.xp >= p.need():
                        p.xp -= p.need()
                        p.lv += 1
                        p.pending += 1
                        self.toast('YOU GROW STRONGER')
                        self.sfx.play('level')
                    continue
            elif k.kind == 'vial':
                k.life -= 1
                if k.life <= 0:
                    continue
                if d < p.r + 6 and p.vials < p.maxvials:
                    p.vials += 1
                    self.toast('+1 VIAL', BLOOD)
                    self.sfx.play('pickup')
                    continue
            elif k.kind in ('reliquary', 'coffer'):
                if d < p.r + 8:
                    self.sfx.play('chest')
                    self.burst(k.x, k.y, 12, 2, glow=True)
                    if k.kind == 'reliquary':
                        keep.append(self.roll_item(k.x, k.y))
                    else:
                        for _ in range(8):
                            a = random.uniform(0, TAU)
                            keep.append(Pickup('soul', k.x, k.y, vx=math.cos(a) * 2,
                                               vy=math.sin(a) * 2))
                        keep.append(Pickup('vial', k.x, k.y + 6, life=1200))
                    continue
            keep.append(k)
        self.pickups = keep

    def roll_item(self, x, y):
        p = self.player
        maxt = min(2, (self.n + 1) // 2)
        if random.random() < 0.5:
            opts = [w for w, g in MELEE.items() if g['tier'] <= maxt and w != p.melee]
            return Pickup('melee', x, y, random.choices(opts, [1 + MELEE[w]['tier'] for w in opts])[0])
        opts = [w for w, g in SPELLS.items() if g['tier'] <= maxt and w != p.spell]
        return Pickup('spell', x, y, random.choices(opts, [1 + SPELLS[w]['tier'] for w in opts])[0])

    def interact(self):
        p = self.player
        best, bd = None, 18
        for k in self.pickups:
            if k.kind in ('melee', 'spell'):
                d = math.hypot(k.x - p.x, k.y - p.y)
                if d < bd:
                    best, bd = k, d
        if not best:
            return
        self.pickups.remove(best)
        attr = best.kind
        self.pickups.append(Pickup(attr, p.x, p.y, getattr(p, attr)))
        setattr(p, attr, best.data)
        self.toast(best.data.upper())
        p.charge_t = p.combo = 0
        self.sfx.play('pickup')

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
        if self.frame % 4 == 0:  # brazier embers
            for bx, by in self.level.braziers:
                if abs(bx - self.player.x) < W and abs(by - self.player.y) < H:
                    self.particles.append([bx + random.uniform(-2, 2), by - 3,
                                           random.uniform(-0.2, 0.2), -0.5, 25, 1, 0.98,
                                           BLOOD, True])

    # ---------------------------------------------------------- boons
    def open_boons(self):
        self.state = 'boon'
        p = self.player
        pool = [(b, 2) for b in BOONS]
        pool += [(b, 3 if b[2][0][2] == p.melee else 1) for b in WEAPON_BOONS
                 if b[2][0][2] not in p.wperks]
        self.boon_opts = []
        while len(self.boon_opts) < 4 and pool:
            i = random.choices(range(len(pool)), [w for _, w in pool])[0]
            self.boon_opts.append(pool.pop(i)[0])
        self.boon_t = 0

    def pick_boon(self, i):
        if self.boon_t < 15:
            return
        p = self.player
        name, _, effects = self.boon_opts[i]
        for attr, op, v in effects:
            cur = getattr(p, attr)
            if op == 'add':
                cur.add(v)
            else:
                setattr(p, attr, cur + v if op == '+' else cur * v)
        p.hp = min(p.hp, p.maxhp)
        p.vials = min(p.vials, p.maxvials)
        p.boons.append(name)
        p.pending -= 1
        self.sfx.play('level')
        if p.pending > 0:
            self.open_boons()
        else:
            self.next_level()

    def next_level(self):
        self.n += 1
        self.start_level()
        self.state = 'play'

    # ---------------------------------------------------------- draw
    def light(self, x, y, r):
        # (x, y) is in screen space; pick the dither phase from the world position so the
        # pattern is anchored to the world, not to the light or the screen.
        left, top = int(x) - r, int(y) - r
        st = self.stamps[r][((left + self.lox) % 4, (top + self.loy) % 4)]
        self.dark.blit(st, (left, top), special_flags=pygame.BLEND_RGBA_MIN)

    def weapon_img(self, name, angle):
        return self.wspr[name][int(round(angle / TAU * 64)) % 64]

    def draw_world(self):
        s = self.screen
        sh = int(self.shake)
        ox = self.ox + (random.randint(-sh, sh) if sh else 0)
        oy = self.oy + (random.randint(-sh, sh) if sh else 0)
        fr = self.frame
        self.lox, self.loy = ox, oy
        p = self.player
        s.fill(BLACK)
        s.blit(self.level.surf, (-ox, -oy))
        lights = []
        for k in self.pickups:
            x, y = int(k.x - ox), int(k.y - oy)
            if k.kind == 'vial':
                if 0 < k.life < 120 and (fr // 4) % 2:
                    continue
                pygame.draw.rect(s, BONE, (x - 2, y - 5, 3, 2))
                pygame.draw.circle(s, BLOOD, (x - 1, y + 1), 3)
            elif k.kind == 'reliquary':
                pygame.draw.rect(s, BONE, (x - 7, y - 5, 14, 10), 1)
                pygame.draw.line(s, BONE, (x - 7, y - 2), (x + 6, y - 2))
                s.fill(BLOOD, (x - 1, y - 5, 2, 9))
                lights.append((x, y, 20))
            elif k.kind == 'coffer':
                pygame.draw.rect(s, BONE, (x - 6, y - 4, 12, 8), 1)
                pygame.draw.circle(s, BONE, (x, y + 1), 2, 1)
            elif k.kind in ('melee', 'spell'):
                bob = int(math.sin(fr * 0.1 + k.x) * 1.5)
                if k.kind == 'melee':
                    img = self.weapon_img(k.data, -0.6)
                    s.blit(img, (x - img.get_width() // 2 - 4, y - img.get_height() // 2 + 3 + bob))
                else:
                    pygame.draw.rect(s, BONE, (x - 5, y - 4 + bob, 10, 8))
                    s.fill(BLACK, (x - 4, y - 3 + bob, 1, 6))
                    s.fill(BLACK, (x - 5, y + 3 + bob, 10, 1))
                    rune = (sum(map(ord, k.data)) % 4)
                    cx, cy = x + 1, y - 1 + bob
                    s.fill(BLOOD, (cx, cy - 2, 1, 5))
                    s.fill(BLOOD, (cx - 2 + rune % 2 * 2, cy - 1 + rune // 2 * 2, 3, 1))
                lights.append((x, y, 20))
        for e in self.enemies:
            if e.hidden:
                continue
            spr = self.spr[e.kind][e.face]
            img = spr[1] if e.flash else spr[0]
            x, y = int(e.x - ox), int(e.y - oy)
            if e.kind == 'bat':
                y += int(math.sin(e.bob * 2) * 2)
            s.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2))
        if self.state != 'dead' and not (p.iframes > 0 and (fr // 3) % 2 and p.roll_t == 0):
            face = 1 if math.cos(p.aim) >= 0 else -1
            x, y = int(p.x - ox), int(p.y - oy)
            m = MELEE[p.melee]
            if p.swing_t > 0:
                prog = min(1.0, (8 - p.swing_t) / 3)
                wa = p.swing_aim - p.swing_side * p.swing_arc / 2 * (1 - 2 * prog)
            elif p.charge_t > 0:
                wa = p.aim
            else:
                wa = p.aim + 0.9 * face
            hand = (x + face * 4, y - 1)
            if p.melee == 'spear' and p.swing_t > 0:
                wa = p.swing_aim
                ext = SPEAR_THRUST[8 - p.swing_t]
                arm = hand
                hand = (hand[0] + math.cos(wa) * ext, hand[1] + math.sin(wa) * ext)
            wimg = self.weapon_img(p.melee, wa)
            wpos = (hand[0] - wimg.get_width() // 2, hand[1] - wimg.get_height() // 2)
            behind = math.sin(wa) < -0.2
            if behind:
                s.blit(wimg, wpos)
            img = self.knight[face][int(p.walk / 5) % 4 if p.moving else 0]
            reach_arm = p.melee == 'spear' and p.swing_t > 0 and SPEAR_THRUST[8 - p.swing_t] > 3
            if p.roll_t > 0:
                img = pygame.transform.rotate(img, -face * p.roll_t * 26)
            s.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2 - 3))
            if reach_arm:  # the arm extends with the thrust
                pygame.draw.line(s, BONE, arm, hand, 2)
            if not behind:
                s.blit(wimg, wpos)
            if p.swing_t > 2 and p.melee == 'spear':
                rng = m['range'] * p.reach
                c, sn = math.cos(p.swing_aim), math.sin(p.swing_aim)
                t = 8 - p.swing_t

                def at(dist, side):
                    return (x + c * dist - sn * side, y + sn * dist + c * side)
                if t < 3:  # a thin glint driven out ahead of the spearhead, with speed lines
                    far = rng + 2 + t
                    near = rng * 0.55
                    pygame.draw.polygon(s, BONE, [at(near, -1.5), at(far, 0), at(near, 1.5)])
                    for side in (-4, 4):
                        pygame.draw.line(s, BONE, at(near - 4 + t * 2, side),
                                         at(near + 6 + t * 2, side))
                elif t == 3:
                    pygame.draw.line(s, BONE, at(rng * 0.7, 0), at(rng + 4, 0))
            elif p.swing_t > 2:
                rng = m['range'] * p.reach
                a0 = p.swing_aim - p.swing_side * p.swing_arc / 2
                prog = min(1.0, (8 - p.swing_t) / 3)
                outer, inner = [], []
                for i in range(9):
                    a = a0 + p.swing_side * p.swing_arc * prog * i / 8
                    outer.append((x + math.cos(a) * rng, y + math.sin(a) * rng))
                    inner.append((x + math.cos(a) * rng * 0.6, y + math.sin(a) * rng * 0.6))
                pygame.draw.polygon(s, BLOOD if p.finisher else BONE, outer + inner[::-1],
                                    0 if p.swing_t > 5 else 1)
        if self.state != 'dead' and p.blades_t > 0 and (p.blades_t > 60 or fr % 4 < 2):
            for bx, by, a in self.blade_positions():
                bimg = self.weapon_img('daggers', a + math.pi / 2)
                s.blit(bimg, (int(bx - ox) - bimg.get_width() // 2,
                              int(by - oy) - bimg.get_height() // 2))
                lights.append((int(bx - ox), int(by - oy), 12))
        if p.charge_t > 0 and self.state != 'dead':
            lights.append((int(p.x - ox), int(p.y - oy), 32))
        for b in self.bullets:
            if b.enemy:
                continue
            x, y = int(b.x - ox), int(b.y - oy)
            if b.kind == 'fire':
                pygame.draw.circle(s, BLOOD, (x, y), 3)
                s.fill(BONE, (x - 1, y - 1, 2, 2))
                lights.append((x, y, 20))
            elif b.kind == 'bone':
                pygame.draw.line(s, BONE, (x, y), (int(x - b.vx * 1.5), int(y - b.vy * 1.5)), 2)
                lights.append((x, y, 12))
            elif b.kind == 'orb':
                pygame.draw.circle(s, BONE, (x, y), 4)
                pygame.draw.circle(s, BONE, (x, y), 6 + (fr // 3) % 2, 1)
                lights.append((x, y, 32))
            elif b.kind == 'deflect':
                pygame.draw.circle(s, BONE, (x, y), 3)
                lights.append((x, y, 12))
            elif b.kind == 'leech':
                pygame.draw.circle(s, BLOOD, (x, y), 2)
                s.set_at((x, y), BONE)
                lights.append((x, y, 12))
            elif b.kind == 'dagger':
                img = self.weapon_img('daggers', math.atan2(b.vy, b.vx))
                s.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2))
                lights.append((x, y, 12))
        for q in self.particles:
            if not q[8]:
                s.fill(q[7], (int(q[0] - ox), int(q[1] - oy), q[5], q[5]))
        for f in self.effects:
            k, t, life = f[0], f[5], f[6]
            if k == 'boom':
                x, y, r = int(f[1] - ox), int(f[2] - oy), f[3]
                if t < 4:
                    pygame.draw.circle(s, f[7] if len(f) > 7 else BONE, (x, y), int(r))
                else:
                    pygame.draw.circle(s, BLOOD, (x, y), int(r * (0.7 + 0.5 * t / life)),
                                       max(1, 4 - t // 5))
                lights.append((x, y, 56 if t < 10 else 32))
            elif k == 'flash':
                pygame.draw.circle(s, BONE, (int(f[1] - ox), int(f[2] - oy)), 4 - t)
            elif k == 'beam':
                x0, y0, x1, y1 = f[1] - ox, f[2] - oy, f[3] - ox, f[4] - oy
                n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 30))
                for i in range(n + 1):
                    lights.append((int(x0 + (x1 - x0) * i / n), int(y0 + (y1 - y0) * i / n), 32))
        for w in self.waves:
            if not w[5]:
                pygame.draw.circle(s, BONE, (int(w[0] - ox), int(w[1] - oy)), int(w[2]), 2)

        # ---- darkness
        d = self.dark
        d.fill(BLACK + (255,))
        if self.state != 'dead':
            px, py = int(p.x - ox), int(p.y - oy)
            self.light(px, py, 80)
        for bx, by in self.level.braziers:
            x, y = bx - ox, by - oy
            if -56 < x < W + 56 and -56 < y < H + 56:
                self.light(x, y, 48)
        if self.stairs:
            self.light(self.stairs[0] - ox, self.stairs[1] - oy, 44)
        for x, y, r in lights[:40]:
            self.light(x, y, r)
        s.blit(d, (0, 0))

        # ---- things that glow through the dark
        for bx, by in self.level.braziers:
            x, y = int(bx - ox), int(by - oy)
            if -10 < x < W + 10 and -10 < y < H + 10:
                pygame.draw.polygon(s, BONE, [(x - 4, y), (x + 4, y), (x + 2, y + 3), (x - 2, y + 3)])
                s.fill(BONE, (x - 1, y + 3, 2, 5))
                fl = (fr // 5 + bx) % 3
                pygame.draw.polygon(s, BLOOD, [(x - 3, y), (x + 3, y), (x + fl - 1, y - 6 - fl)])
                s.fill(BONE, (x - 1, y - 2, 2, 2))
        if self.stairs:
            x, y, t = self.stairs
            x, y = int(x - ox), int(y - oy)
            for i in range(4):
                r = 10 - i * 2.5 + (t // 8) % 2 * 0.5
                pygame.draw.rect(s, BONE if i % 2 == 0 else BLOOD,
                                 (x - r, y - r * 0.6, r * 2, r * 1.2), 1)
        for k in self.pickups:
            if k.kind == 'soul':
                x, y = int(k.x - ox), int(k.y - oy)
                s.fill(BONE, (x - 1, y - 1, 2, 2))
                if (fr // 6 + int(k.x)) % 3 == 0:
                    s.set_at((x, y - 3), BONE)
        for e in self.enemies:
            if e.hidden:
                continue
            x, y = int(e.x - ox), int(e.y - oy)
            if e.kind == 'bat':
                y += int(math.sin(e.bob * 2) * 2)
            big = e.wind > 0 and (e.wind // 3) % 2
            for ex, ey in EYES[e.kind]:
                ex *= e.face
                if big:
                    s.fill(BLOOD, (x + ex - 1, y + ey - 1, 2, 2))
                else:
                    s.set_at((x + ex, y + ey), BLOOD)
            if e.kind == 'archer' and e.wind > 0 and (e.wind > 12 or fr % 2):
                x1, y1 = self.level.ray(e.x, e.y, e.aim, 300, 3)
                n = int(math.hypot(x1 - e.x, y1 - e.y) / 5)
                c, sn = math.cos(e.aim) * 5, math.sin(e.aim) * 5
                for i in range(1, n):
                    s.set_at((int(e.x + c * i - ox), int(e.y + sn * i - oy)), BLOOD)
        for b in self.bullets:
            if not b.enemy:
                continue
            x, y = int(b.x - ox), int(b.y - oy)
            if b.kind == 'arrow':
                pygame.draw.line(s, BLOOD, (x, y), (int(x - b.vx * 1.5), int(y - b.vy * 1.5)), 2)
                s.set_at((x, y), BONE)
            else:
                pygame.draw.circle(s, BLOOD, (x, y), b.r)
                s.set_at((x, y), BONE)
        for f in self.effects:
            if f[0] == 'beam':
                t = f[5]
                a, b = (f[1] - ox, f[2] - oy), (f[3] - ox, f[4] - oy)
                wdt = 7 if t < 3 else max(1, 6 - t // 3)
                pygame.draw.line(s, BLOOD, a, b, wdt + 4)
                pygame.draw.line(s, BONE, a, b, wdt)
        if p.charge_t > 0 and self.state == 'play':
            prog = 1 - p.charge_t / SPELLS['sunder beam']['charge']
            hx, hy = p.x + math.cos(p.aim) * 6, p.y + math.sin(p.aim) * 6
            x1, y1 = self.level.ray(hx, hy, p.aim, 420, 3)
            gap = max(2, int(10 - prog * 8))
            n = int(math.hypot(x1 - hx, y1 - hy) / gap)
            c, sn = math.cos(p.aim) * gap, math.sin(p.aim) * gap
            if prog > 0.15 or fr % 2:
                for i in range(1, n):
                    s.set_at((int(hx + c * i - ox), int(hy + sn * i - oy)), BONE)
            pygame.draw.circle(s, BONE, (int(hx - ox), int(hy - oy)), 1 + int(prog * 3))
        for e in self.enemies:
            if e.kind == 'wyrm' and e.phase == 'burrow' and 10 < e.pt <= 40 and fr % 4 < 3:
                rr = 6 + (40 - e.pt) // 3
                pygame.draw.circle(s, BLOOD, (int(e.x - ox), int(e.y - oy)), rr, 1)
                pygame.draw.circle(s, BLOOD, (int(e.x - ox), int(e.y - oy)), 22, 1)
        for w in self.waves:
            if w[5]:
                pygame.draw.circle(s, BLOOD, (int(w[0] - ox), int(w[1] - oy)), int(w[2]), 2)
        for q in self.particles:
            if q[8]:
                s.fill(q[7], (int(q[0] - ox), int(q[1] - oy), q[5], q[5]))
        for k in self.pickups:
            if k.kind in ('melee', 'spell') and math.hypot(k.x - p.x, k.y - p.y) < 18:
                if k.kind == 'spell':
                    info = SPELLS[k.data]['desc']
                elif k.data in p.wperks:
                    info = 'YOUR BOON: ' + WEAPON_PERK[k.data].split(': ', 1)[1]
                else:
                    info = ''
                lines = wrap(info, 32)
                y0 = int(k.y - oy) - 14 - 7 * len(lines)
                draw_text(s, 'E: ' + k.data, int(k.x - ox), y0, align='c')
                for i, line in enumerate(lines):
                    draw_text(s, line, int(k.x - ox), y0 + 7 * (i + 1), align='c', color=BLOOD)
        for x, y, txt, life, col in self.texts:
            if life > 10 or fr % 2:
                draw_text(s, txt, int(x - ox), int(y - oy), align='c', color=col)
        targets = []
        if self.stairs:
            targets = [(self.stairs[0], self.stairs[1])]
        elif len(self.enemies) <= 3:
            targets = [(e.x, e.y) for e in self.enemies]
        for tx, ty in targets:
            sx, sy = tx - ox, ty - oy
            if 0 <= sx < W and 0 <= sy < H:
                continue
            a = math.atan2(sy - H / 2, sx - W / 2)
            c, sn = math.cos(a), math.sin(a)
            kk = min((W / 2 - 10) / abs(c) if c else 1e9, (H / 2 - 10) / abs(sn) if sn else 1e9)
            ax, ay = W / 2 + c * kk, H / 2 + sn * kk
            pygame.draw.polygon(s, BLOOD if not self.stairs else BONE,
                                [(ax + c * 5, ay + sn * 5), (ax - c * 3 - sn * 4, ay - sn * 3 + c * 4),
                                 (ax - c * 3 + sn * 4, ay - sn * 3 - c * 4)])

    def draw_hud(self):
        s, p = self.screen, self.player
        pygame.draw.rect(s, BLACK, (3, 3, 64, 9))
        pygame.draw.rect(s, BONE, (3, 3, 64, 9), 1)
        s.fill(BLOOD, (5, 5, int(60 * max(0, p.hp) / p.maxhp), 5))
        draw_text(s, f'{p.hp}/{p.maxhp}', 71, 5)
        s.fill(BLACK, (3, 13, 64, 5))
        pygame.draw.rect(s, BONE, (3, 13, 64, 5), 1)
        s.fill(BONE, (4, 14, int(62 * p.mana / p.maxmana), 3))
        draw_text(s, f'{int(p.mana)}', 71, 13)
        s.fill(BONE, (3, 20, int(64 * p.xp / p.need()), 1))
        draw_text(s, f'LV{p.lv}' + (' +' * p.pending), 71, 19)
        for i in range(p.maxvials):
            x = 4 + i * 8
            s.fill(BONE, (x + 1, 24, 3, 2))
            if i < p.vials:
                pygame.draw.circle(s, BLOOD, (x + 2, 29), 3)
            else:
                pygame.draw.circle(s, BONE, (x + 2, 29), 3, 1)
        draw_text(s, 'F', 6 + p.maxvials * 8, 27)
        sp = SPELLS[p.spell]
        cost = f"{sp['hpcost']} HP" if sp.get('hpcost') else str(sp['cost'])
        draw_text(s, f'LMB {p.melee}', 4, H - 17)
        draw_text(s, f'RMB {p.spell} ({cost})', 4, H - 9,
                  color=BONE if sp.get('hpcost') or p.mana >= sp['cost'] else BLOOD)
        draw_text(s, self.level_name(self.n, True), W - 4, 4, align='r')
        draw_text(s, f'SLAIN {self.kills}', W - 4, 12, align='r')
        if self.enemies and len(self.enemies) <= 3 and not self.boss:
            draw_text(s, f'{len(self.enemies)} REMAIN', W - 4, 20, align='r', color=BLOOD)
        b = self.boss
        if b and not b.dead:
            draw_text(s, BOSS_NAMES[b.kind], W // 2, 6, align='c', color=BLOOD)
            pygame.draw.rect(s, BONE, (W // 2 - 80, 13, 160, 6), 1)
            s.fill(BLOOD, (W // 2 - 78, 15, int(156 * max(0, b.hp) / b.maxhp), 2))

    def draw_minimap(self):
        if not self.show_map:
            return
        s, p = self.screen, self.player
        x0, y0 = W - MW - 3, H - MH - 3
        s.fill(BLACK, (x0 - 2, y0 - 2, MW + 4, MH + 4))
        pygame.draw.rect(s, BONE, (x0 - 2, y0 - 2, MW + 4, MH + 4), 1)
        s.blit(self.minimap, (x0, y0))
        for bx, by in self.level.braziers:
            tx, ty = int(bx // T), int(by // T)
            if self.seen[ty * MW + tx]:
                s.set_at((x0 + tx, y0 + ty), BLOOD)
        if self.stairs and (self.frame // 15) % 2:
            s.fill(BONE, (x0 + int(self.stairs[0] // T) - 1, y0 + int(self.stairs[1] // T) - 1, 3, 3))
        if (self.frame // 10) % 3:
            s.fill(BLOOD, (x0 + int(p.x // T) - 1, y0 + int(p.y // T) - 1, 3, 3))
        s.set_at((x0 + int(p.x // T), y0 + int(p.y // T)), BONE)

    def draw_cursor(self):
        mx, my = pygame.mouse.get_pos()
        s = self.screen
        for col, w in ((BLACK, 3), (BONE, 1)):
            for a, b in (((mx - 5, my), (mx - 2, my)), ((mx + 2, my), (mx + 5, my)),
                         ((mx, my - 5), (mx, my - 2)), ((mx, my + 2), (mx, my + 5))):
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
        draw_text(s, 'GRAVEN', W // 2, 34, 6, 'c')
        draw_text(s, 'DESCEND.', W // 2, 70, 1, 'c', BLOOD)
        lines = ['WASD  MOVE', 'MOUSE  AIM', 'LMB  STRIKE  (DEFLECTS BOLTS)', 'RMB  CAST',
                 'SPACE / SHIFT  ROLL', 'F  DRINK VIAL    E  TAKE ITEM    M  MAP',
                 'ESC  PAUSE    F11  FULLSCREEN']
        for i, l in enumerate(lines):
            draw_text(s, l, W // 2, 92 + i * 9, 1, 'c')
        if (self.t // 30) % 2:
            draw_text(s, 'CLICK TO BEGIN', W // 2, 170, 2, 'c', BLOOD)
        if self.best:
            draw_text(s, 'DEEPEST: ' + self.level_name(self.best, True), W // 2, 200, 1, 'c')

    def draw_boons(self):
        s = self.screen
        s.fill(BLACK)
        self.boon_t += 1
        draw_text(s, 'A BOON', W // 2, 20, 3, 'c', BLOOD)
        draw_text(s, 'CHOOSE ONE  (1-4 OR CLICK)', W // 2, 42, 1, 'c')
        mx, my = pygame.mouse.get_pos()
        self.boon_rects = []
        bw, bh, gap = 90, 96, 6
        x0 = (W - (bw * 4 + gap * 3)) // 2
        for i, (name, desc, _) in enumerate(self.boon_opts):
            r = pygame.Rect(x0 + i * (bw + gap), 62, bw, bh)
            self.boon_rects.append(r)
            hover = r.collidepoint(mx, my)
            col = BLACK if hover else BONE
            if hover:
                s.fill(BONE, r)
            else:
                pygame.draw.rect(s, BONE, r, 1)
            draw_text(s, str(i + 1), r.centerx, r.y + 6, 2, 'c', BLOOD, False)
            eff = self.boon_opts[i][2][0]
            if eff[1] == 'add':
                icon = self.weapon_img(eff[2], -0.7).copy()
                icon.fill(BLOOD + (255,), special_flags=pygame.BLEND_RGBA_MIN)
                s.set_clip(r.inflate(-4, -4))
                s.blit(icon, (r.right - 15 - icon.get_width() // 2, r.y + 14 - icon.get_height() // 2))
                s.set_clip(None)
            for j, line in enumerate(wrap(name, 20)):
                draw_text(s, line, r.centerx, r.y + 24 + j * 7, 1, 'c', col, False)
            for j, line in enumerate(wrap(desc, 20)):
                draw_text(s, line, r.centerx, r.y + 46 + j * 8, 1, 'c', col, False)
        p = self.player
        if p.boons:
            draw_text(s, 'HELD: ' + ', '.join(p.boons[-5:]), W // 2, 176, 1, 'c')
        draw_text(s, 'NEXT: ' + self.level_name(self.n + 1, True), W // 2, 200, 1, 'c')

    def draw(self):
        s = self.screen
        if self.state == 'title':
            self.draw_title()
        elif self.state == 'boon':
            self.draw_boons()
        else:
            self.draw_world()
            self.draw_hud()
            self.draw_minimap()
            if self.state == 'pause':
                s.blit(self.dim, (0, 0))
                draw_text(s, 'PAUSED', W // 2, 70, 3, 'c')
                draw_text(s, 'ESC  RESUME', W // 2, 105, 1, 'c')
                draw_text(s, 'X  ABANDON RUN', W // 2, 115, 1, 'c')
                pl = self.player
                draw_text(s, WEAPON_PERK[pl.melee] if pl.melee in pl.wperks
                          else f'{pl.melee}: NO BOON YET', W // 2, 160, 1, 'c')
                draw_text(s, f'{pl.spell}: ' + SPELLS[pl.spell]['desc'], W // 2, 170, 1, 'c')
                if self.player.boons:
                    draw_text(s, ', '.join(self.player.boons), W // 2, 140, 1, 'c')
            elif self.state == 'dead':
                self.dead_t += 1
                s.blit(self.dim, (0, 0))
                draw_text(s, 'SLAIN', W // 2, 58, 5, 'c', BLOOD)
                draw_text(s, f'FELL IN {self.level_name(self.n, True)}   '
                             f'SLEW {self.kills}   LV {self.player.lv}', W // 2, 98, 1, 'c')
                draw_text(s, 'DEEPEST: ' + self.level_name(self.best, True), W // 2, 110, 1, 'c')
                if self.dead_t > 50:
                    draw_text(s, 'R OR CLICK TO RISE AGAIN', W // 2, 140, 2, 'c')
            elif self.state == 'trans':
                self.trans_t += 1
                if self.trans_t < 14:
                    for _ in range(self.trans_t // 4 + 1):
                        s.blit(self.dim, (0, 0))
                        s.blit(self.dim, (1, 0))
                else:
                    s.fill(BLACK)
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
            elif key == pygame.K_m:
                self.show_map = not self.show_map
            elif key == pygame.K_f:
                self.drink()
        elif st == 'pause':
            if key == pygame.K_ESCAPE:
                self.state = 'play'
            elif key == pygame.K_x:
                self.state = 'title'
        elif st == 'boon':
            if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.pick_boon(key - pygame.K_1)
            elif click:
                for i, r in enumerate(getattr(self, 'boon_rects', [])):
                    if r.collidepoint(ev.pos):
                        self.pick_boon(i)
        elif st == 'dead':
            if self.dead_t > 50 and (click or key == pygame.K_r):
                self.new_run()
            elif key == pygame.K_ESCAPE:
                self.state = 'title'

    def step(self):
        self.t += 1
        if self.state in ('play', 'dead'):
            self.update()
        elif self.state == 'trans' and self.trans_t > 30:
            if self.player.pending > 0:
                self.open_boons()
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
