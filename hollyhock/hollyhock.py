#!/usr/bin/env python3
"""HOLLYHOCK - a tiny cozy farming sim.

Your aunt left you Hollyhock Farm, overgrown and quiet. The township lease falls due at the
end of every season; pay all four and the farm is yours.
WASD/arrows walk, SPACE (hold) uses the selected tool, E interacts (talk, harvest, pet,
ship, sleep). 1-9/0/-/= or Q/R or the mouse wheel pick a slot, TAB swaps bag rows.
ESC pauses, F11 toggles fullscreen.
"""
import array
import json
import math
import os
import random
import sys

import pygame

W, H = 400, 225
TS = 16
MW, MH = 52, 36
FARM_X1 = 36                    # the farm is x < FARM_X1; the village lies east
INK = (40, 30, 38)
CREAM = (252, 244, 222)
GOLD = (250, 206, 84)
RED = (222, 84, 76)
GREEN = (126, 200, 96)
SKY = (120, 180, 228)
TAU = math.tau
SEASONS = ['SPRING', 'SUMMER', 'AUTUMN', 'WINTER']
DAYS = 12
RENT = [500, 1500, 3000, 4500]
DAY_START, DAY_END = 6 * 60, 26 * 60
MIN_PER_SEC = 8
STAMINA = 120
DIRV = {'down': (0, 1), 'up': (0, -1), 'left': (-1, 0), 'right': (1, 0)}
OUTLINE4 = ((-1, 0), (1, 0), (0, -1), (0, 1))

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
    '<': '001010100010001', '=': '000111000111000', '*': '000101010101000',
    ' ': '000000000000000',
}
_tcache = {}


def text_surf(s, scale=1, color=CREAM):
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


def draw_text(dst, s, x, y, scale=1, align='l', color=CREAM, outline=True):
    t = text_surf(s, scale, color)
    if align == 'c':
        x -= t.get_width() // 2
    elif align == 'r':
        x -= t.get_width()
    if outline:
        o = text_surf(s, scale, INK)
        for dx, dy in OUTLINE4:
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
        'step': (0.04, 160, 120, 0.8, 0.025, 'sq'),
        'hoe': (0.1, 220, 90, 0.8, 0.12, 'sq'),
        'water': (0.25, 600, 300, 0.85, 0.06, 'sin'),
        'fill': (0.4, 300, 700, 0.7, 0.07, 'sin'),
        'chop': (0.09, 300, 120, 0.6, 0.14, 'sq'),
        'pick': (0.08, 1400, 1000, 0.4, 0.1, 'sq'),
        'cut': (0.08, 1600, 2400, 0.9, 0.05, 'sq'),
        'break': (0.25, 200, 60, 0.8, 0.16, 'sq'),
        'plant': (0.07, 500, 300, 0.5, 0.06, 'sin'),
        'pop': (0.12, 500, 1100, 0.0, 0.12, 'sin'),
        'coin': (0.15, 1300, 1800, 0.0, 0.1, 'sin'),
        'blip': (0.03, 900, 900, 0.0, 0.04, 'sq'),
        'click': (0.04, 900, 800, 0.2, 0.06, 'sq'),
        'no': (0.08, 180, 150, 0.0, 0.1, 'sq'),
        'pet': (0.3, 500, 900, 0.0, 0.1, 'sin'),
        'cluck': (0.1, 700, 1200, 0.3, 0.07, 'sq'),
        'moo': (0.5, 150, 110, 0.1, 0.15, 'sin'),
        'baa': (0.35, 320, 290, 0.3, 0.08, 'sq'),
        'squeak': (0.08, 1800, 2400, 0.0, 0.06, 'sin'),
        'sleep': (0.9, 500, 250, 0.0, 0.12, 'sin'),
        'build': (0.4, 150, 80, 0.7, 0.2, 'sq'),
        'chime': (0.7, 700, 1100, 0.0, 0.12, 'sin'),
        'drink': (0.3, 300, 500, 0.4, 0.08, 'sin'),
        'thunder': (1.0, 70, 40, 0.9, 0.22, 'sq'),
        'fail': (1.3, 300, 100, 0.0, 0.2, 'sin'),
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
            s = int(v * min(1.0, t * 40) * (1 - t) ** 2 * vol * 32767)
            for _ in range(ch):
                buf.append(s)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        if self.ok:
            self.s[name].play()


# ------------------------------------------------------------------ data
CROPS = {}


def _crop(name, seasons, days, regrow, seed, sell, shape, col, yld=1):
    CROPS[name] = dict(seasons=seasons, days=days, regrow=regrow, seed=seed, sell=sell,
                       shape=shape, col=col, yld=yld)


_crop('TURNIP', (0,), 4, 0, 20, 40, 'root', (238, 226, 240))
_crop('POTATO', (0,), 6, 0, 40, 85, 'root', (206, 164, 104))
_crop('STRAWBERRY', (0,), 8, 3, 70, 60, 'bush', (232, 52, 64))
_crop('RADISH', (1,), 5, 0, 30, 65, 'root', (226, 64, 96))
_crop('TOMATO', (1,), 8, 3, 50, 50, 'bush', (238, 76, 48))
_crop('CORN', (1, 2), 10, 4, 80, 45, 'tall', (248, 210, 72))
_crop('MELON', (1,), 11, 0, 90, 280, 'gourd', (128, 196, 96))
_crop('WHEAT', (2,), 4, 0, 10, 25, 'tall', (226, 192, 108))
_crop('PUMPKIN', (2,), 11, 0, 110, 330, 'gourd', (238, 134, 40))
_crop('CRANBERRY', (2,), 7, 3, 150, 60, 'bush', (184, 32, 64), 2)
_crop('KALE', (3,), 5, 0, 35, 80, 'leafy', (96, 150, 120))
_crop('SNOWBERRY', (3,), 8, 3, 100, 70, 'bush', (236, 242, 255))
SEED_OF = {n + ' SEEDS': n for n in CROPS}
PRODUCTS = {'EGG': 50, 'LARGE EGG': 90, 'MILK': 125, 'LARGE MILK': 200, 'WOOL': 300, 'FINE WOOL': 450}
EDIBLE = set(CROPS) | {'EGG', 'LARGE EGG', 'MILK', 'LARGE MILK'}
TOOLS = ['HOE', 'CAN', 'AXE', 'PICK', 'SCYTHE']
TIER = ['', 'COPPER ', 'STEEL ']
CAN_CAP = [30, 60, 100]
TOOL_REACH = [1, 3, 5]
TOOL_COST = {'HOE': 2, 'CAN': 1, 'AXE': 3, 'PICK': 3, 'SCYTHE': 1}
ANIMALS = {
    'CHICKEN': dict(home='COOP', price=400, prod='EGG', big='LARGE EGG', every=1, snd='cluck'),
    'COW': dict(home='BARN', price=1200, prod='MILK', big='LARGE MILK', every=1, snd='moo'),
    'SHEEP': dict(home='BARN', price=900, prod='WOOL', big='FINE WOOL', every=3, snd='baa'),
}
PET_NAMES = ['CLOVER', 'BUTTONS', 'MAPLE', 'PEACHES', 'BISCUIT', 'DAISY', 'PUDDING', 'HONEY',
             'PEPPER', 'TOFFEE', 'BEANS', 'MOSS', 'FERN', 'NUTMEG', 'POPPY', 'BRAMBLE', 'MUFFIN',
             'SORREL', 'WAFFLE', 'JUNIPER']
BUILDS = {   # w, h, door tiles (solid unless greenhouse), gold, wood, stone, capacity
    'COOP': dict(w=4, h=3, door=[(1, 2)], gold=500, wood=60, stone=0, cap=4,
                 desc='HOUSES 4 CHICKENS.'),
    'BARN': dict(w=6, h=4, door=[(2, 3), (3, 3)], gold=1500, wood=120, stone=60, cap=4,
                 desc='HOUSES 4 COWS OR SHEEP.'),
    'WELL': dict(w=2, h=2, door=[], gold=200, wood=0, stone=30, cap=0,
                 desc='REFILL YOUR CAN HERE. NEVER FREEZES.'),
    'GREENHOUSE': dict(w=7, h=6, door=[(3, 5)], gold=3000, wood=100, stone=100, cap=0,
                       desc='20 SOIL TILES UNDER GLASS. ANY CROP, ANY SEASON. NO CROWS.'),
    'HOUSE': dict(w=5, h=4, door=[(2, 3)]),
    'STALL': dict(w=4, h=2, door=[]),
    'COTTAGE': dict(w=4, h=3, door=[]),
}
SOLID_OBJS = {'stone', 'boulder', 'branch', 'stump', 'tree', 'scarecrow', 'sprinkler', 'bin'}
OBJ_HP = {'weed': 1, 'tallgrass': 1, 'stone': 1, 'boulder': 4, 'branch': 1, 'stump': 3,
          'tree': 6, 'dead': 1}
WEATHER = [  # season: (weather, weight)
    [('SUN', 6), ('RAIN', 4)],
    [('SUN', 13), ('RAIN', 4), ('STORM', 3)],
    [('SUN', 11), ('RAIN', 7), ('STORM', 2)],
    [('SUN', 1), ('SNOW', 1)],
]
LOOK_PLAYER = ((242, 200, 160), (128, 76, 44), (222, 92, 80), (72, 104, 172), (232, 200, 112))

NPCS = {
    'MARIGOLD': dict(
        stall=(39, 4), hours=(8, 18), trade='SEEDS', awning=(240, 170, 60),
        look=((238, 194, 156), (206, 206, 216), (242, 170, 62), (126, 84, 146), None),
        loves=('STRAWBERRY', 'MELON'),
        lines=["Welcome, welcome! Seeds for the season, tea for the soul.",
               "Your aunt grew the sweetest turnips in the valley. Big shoes to fill, dear.",
               "Water before noon. Plants are like me: grumpy when thirsty.",
               "Crops only grow on days they've been watered. Rain counts, bless it.",
               "A crop out of season withers when the season turns. Mind the calendar.",
               "A cup of my tea will put the spring back in your step."],
        season=["Spring! Turnips are quick, and strawberries keep on giving.",
                "Melons are slow, but they pay for themselves twice over. Plant them early.",
                "Pumpkins, cranberries, wheat... autumn is a generous season.",
                "Kale and snowberries shrug off the frost. Hardy little things."],
        rain="Lovely rain. The sky is doing your watering today.",
        storm="Stay off the open fields today, dear. Lightning has opinions.",
        high=["You've brought that old farm back to life. Your aunt would be so proud.",
              "I saved you the plumpest seed packets. Don't tell the others."],
        love="Oh! My favourite. You remembered!",
        perk="Marigold left a bundle of seeds on your doorstep, with a note: FOR MY FAVOURITE FARMER."),
    'BRAM': dict(
        stall=(45, 13), hours=(9, 17), trade='BUILD', awning=(110, 160, 210),
        look=((204, 152, 112), (96, 64, 44), (92, 134, 84), (112, 82, 62), (148, 104, 64)),
        loves=('PUMPKIN', 'POTATO'),
        lines=["Need a coop? A barn? Bring timber and I'll bring the hammer.",
               "Clear the stumps first. Can't build on stubbornness.",
               "A scarecrow keeps the crows off everything within four tiles of it.",
               "Sprinklers water the four tiles beside them every morning. Lazy, and brilliant.",
               "A copper hoe tills three in a row. Saves your back, that does.",
               "Every log you chop yourself is one you don't buy from me. Clever."],
        season=["Spring is for fences and fresh starts.",
                "Hot work in summer. Keep some tea handy.",
                "Autumn: fix the roof before the snow does it for you.",
                "The pond freezes over in winter. A well never does."],
        rain="Rain drums nice on a workshop roof.",
        storm="Storm's rolling in. Lightning likes a big field with nothing to stop it.",
        high=["Built a lot together, you and I. Feels like the valley's waking up.",
              "If you ever need a hand, you know where the workshop is."],
        love="Now that's a proper gift. Thank you kindly.",
        perk="Bram left two sprinklers by your door. No note, just sawdust."),
    'HAZEL': dict(
        stall=(39, 22), hours=(7, 16), trade='RANCH', awning=(214, 92, 92),
        look=((172, 122, 92), (64, 42, 32), (232, 222, 196), (82, 112, 152), (182, 132, 82)),
        loves=('CORN', 'TOMATO'),
        lines=["Pet your animals every day. They notice, and they remember.",
               "Happy animals give large eggs and fine wool. Simple as that.",
               "Each animal eats one hay every morning. Scythe the tall grass, or buy it here.",
               "Rabbits! The cheek of them. Walk over and they'll scatter.",
               "Sheep give wool every three days. Worth the wait.",
               "Animals go to bed when the sun does. Sensible creatures."],
        season=["Lambing season, they call it. Everything's new.",
                "Keep the hay stocked. A hungry cow is a sulky cow.",
                "Tall grass grows thick in autumn. Good haymaking weather.",
                "Grass won't grow under the snow. Stock up on hay before winter."],
        rain="Wet animals, wet farmer. Still beats an office.",
        storm="Animals hate thunder. Give them an extra scratch tonight.",
        high=["My hens like you, which means I like you.",
              "You've got a way with animals. Not everyone does."],
        love="For me? Oh, you're a treasure.",
        perk="Hazel dropped off thirty bales of hay. The barn cat came too, but left again."),
}


def item_kind(name):
    if name in TOOLS:
        return 'tool'
    if name in SEED_OF:
        return 'seed'
    if name in CROPS:
        return 'crop'
    if name in PRODUCTS:
        return 'product'
    if name in ('SCARECROW', 'SPRINKLER'):
        return 'place'
    return 'drink'


def sell_price(name):
    if name in CROPS:
        return CROPS[name]['sell']
    return PRODUCTS.get(name)


# ------------------------------------------------------------------ art helpers
def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def outlined(s):
    w, h = s.get_size()
    o = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    sil = pygame.mask.from_surface(s).to_surface(setcolor=INK, unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        o.blit(sil, (dx, dy))
    o.blit(s, (1, 1))
    return o


def rect(s, c, x, y, w, h):
    pygame.draw.rect(s, c, (x, y, w, h))


GRASS = [(124, 188, 88), (100, 172, 70), (198, 156, 76), (232, 236, 246)]
LEAF = [(98, 176, 82), (70, 150, 64), (220, 120, 50), (240, 244, 250)]


def ground_tile(kind, season, v):
    r = random.Random('%s%d%d' % (kind, season, v))
    s = pygame.Surface((TS, TS))
    if kind in 'gt':
        base = GRASS[season]
        if kind == 't':
            base = shade(base, 0.82)
        s.fill(base)
        for _ in range(12):
            s.set_at((r.randrange(TS), r.randrange(TS)), shade(base, r.choice((0.88, 1.08))))
        for _ in range(2):
            x, y = r.randrange(1, 14), r.randrange(2, 14)
            c = (200, 214, 230) if season == 3 else shade(base, 0.8)
            s.set_at((x, y), c)
            s.set_at((x + 1, y - 1), c)
            s.set_at((x + 2, y), c)
        if season == 0 and r.random() < 0.25:
            s.set_at((r.randrange(2, 14), r.randrange(2, 14)), r.choice(((250, 250, 250), (250, 220, 90))))
    elif kind == 'p':
        base = (196, 186, 190) if season == 3 else (200, 162, 114)
        s.fill(base)
        for _ in range(14):
            s.set_at((r.randrange(TS), r.randrange(TS)), shade(base, r.choice((0.86, 1.1))))
    elif kind == 'c':
        s.fill((150, 144, 138))
        for i in range(4):
            x, y = (i % 2) * 8 + (4 if i >= 2 else 0) % 8, (i // 2) * 8
            c = shade((184, 178, 170), r.uniform(0.92, 1.06))
            pygame.draw.rect(s, c, (x + 1, y + 1, 6, 6), border_radius=2)
        if season == 3:
            for _ in range(10):
                s.set_at((r.randrange(TS), r.randrange(TS)), (240, 244, 250))
    elif kind == 's':
        base = (232, 228, 236) if season == 3 else (230, 210, 156)
        s.fill(base)
        for _ in range(10):
            s.set_at((r.randrange(TS), r.randrange(TS)), shade(base, r.choice((0.9, 1.06))))
    elif kind == 'w':
        if season == 3:
            s.fill((190, 220, 238))
            pygame.draw.line(s, (230, 244, 252), (r.randrange(8), r.randrange(16)),
                             (r.randrange(8, 16), r.randrange(16)))
        else:
            s.fill((84, 150, 208))
            for _ in range(2):
                x, y = r.randrange(12), r.randrange(2, 15)
                pygame.draw.line(s, (120, 182, 230), (x, y), (x + 3, y))
    return s


def soil_surf(wet, frozen=False):
    s = pygame.Surface((TS, TS), pygame.SRCALPHA)
    base = (104, 72, 54) if wet else (158, 110, 72)
    pygame.draw.rect(s, base, (0, 0, TS, TS), border_radius=3)
    for y in (4, 9, 13):
        pygame.draw.line(s, shade(base, 0.78), (2, y), (13, y))
    if frozen:
        for i in range(8):
            s.set_at(((i * 7) % 15, (i * 5) % 15), (236, 240, 248))
    return s


def crop_surf(name, stage):
    c = CROPS[name]
    col = c['col']
    shape = c['shape']
    s = pygame.Surface((TS, 24), pygame.SRCALPHA)
    g1, g2 = (86, 168, 64), (56, 124, 52)
    if stage == 0:
        for x, y in ((5, 20), (9, 21), (11, 19)):
            rect(s, (110, 76, 48), x, y, 2, 1)
        return s
    if stage == 1:
        pygame.draw.line(s, g2, (8, 21), (8, 17))
        rect(s, g1, 5, 16, 3, 2)
        rect(s, g1, 9, 15, 3, 2)
        return outlined(s)
    ripe = stage == 3
    if shape == 'root':
        for ex, ey in ((4, 11), (8, 9), (12, 11)):
            pygame.draw.line(s, g1, (8, 19), (ex, ey), 2)
        if name == 'TURNIP' and ripe:
            pygame.draw.ellipse(s, (164, 92, 172), (4, 15, 8, 4))
        if ripe:
            pygame.draw.ellipse(s, col, (4, 16, 8, 7))
            rect(s, shade(col, 1.12), 6, 17, 2, 2)
    elif shape == 'bush':
        pygame.draw.ellipse(s, g2, (2, 11, 12, 11))
        pygame.draw.ellipse(s, g1, (3, 11, 10, 8))
        if ripe:
            for x, y in ((4, 14), (9, 13), (6, 18), (11, 17), (7, 15)):
                pygame.draw.circle(s, col, (x, y), 1)
                s.set_at((x - 1, y - 1), shade(col, 1.3))
    elif shape == 'tall':
        top = 2 if ripe else 9
        stalk = col if (ripe and name == 'WHEAT') else g1
        for x in (5, 8, 11):
            pygame.draw.line(s, stalk, (x, 22), (x, top + (x % 3)), 2 if name == 'CORN' else 1)
        if name == 'CORN':
            pygame.draw.line(s, g2, (8, 15), (13, 11), 2)
            pygame.draw.line(s, g2, (5, 17), (2, 13), 2)
            if ripe:
                rect(s, col, 9, 8, 3, 6)
                rect(s, col, 3, 10, 3, 5)
        elif ripe:
            for x in (5, 8, 11):
                rect(s, shade(col, 0.85), x - 1, top + (x % 3), 2, 4)
    elif shape == 'gourd':
        pygame.draw.ellipse(s, g2, (1, 15, 7, 6))
        pygame.draw.ellipse(s, g1, (8, 14, 7, 6))
        pygame.draw.line(s, g2, (2, 21), (14, 19))
        if ripe:
            pygame.draw.ellipse(s, col, (3, 12, 11, 10))
            dk = shade(col, 0.7)
            if name == 'MELON':
                for x in (6, 8, 11):
                    pygame.draw.line(s, dk, (x, 13), (x, 20))
            else:
                pygame.draw.arc(s, dk, (5, 12, 7, 10), 1.6, 4.7)
            rect(s, (110, 80, 40), 8, 10, 2, 3)
    elif shape == 'leafy':
        lc = col if ripe else g1
        r = 6 if ripe else 4
        for a in range(5):
            ang = a / 5 * TAU
            pygame.draw.circle(s, lc, (8 + int(math.cos(ang) * 3), 17 + int(math.sin(ang) * 2)), r // 2 + 1)
        pygame.draw.circle(s, shade(lc, 1.2), (8, 17), 2)
    return outlined(s)


def tree_surf(season, v):
    r = random.Random('tree%d%d' % (season, v))
    s = pygame.Surface((24, 32), pygame.SRCALPHA)
    rect(s, (120, 82, 54), 10, 18, 4, 14)
    rect(s, (96, 64, 42), 12, 20, 2, 12)
    if season == 3:
        for a, b in (((12, 20), (5, 10)), ((12, 18), (19, 9)), ((12, 14), (12, 4))):
            pygame.draw.line(s, (120, 82, 54), a, b, 2)
        for x, y in ((5, 9), (19, 8), (12, 3)):
            rect(s, (244, 248, 252), x - 2, y - 1, 4, 2)
        return outlined(s)
    base = LEAF[season]
    if season == 2:
        base = r.choice(((222, 122, 50), (230, 172, 60), (200, 82, 52)))
    for cx, cy, cr in ((12, 10, 9), (6, 14, 6), (18, 14, 6), (12, 4, 5)):
        pygame.draw.circle(s, shade(base, 0.85), (cx, cy + 1), cr)
    for cx, cy, cr in ((12, 9, 8), (6, 13, 5), (18, 13, 5), (12, 4, 4)):
        pygame.draw.circle(s, base, (cx, cy), cr)
    for _ in range(6):
        s.set_at((r.randrange(4, 20), r.randrange(2, 18)), shade(base, 1.18))
    if season == 0:
        for _ in range(7):
            x, y = r.randrange(4, 20), r.randrange(2, 18)
            if s.get_at((x, y)).a:
                rect(s, (250, 186, 210), x, y, 2, 2)
    if season == 1 and v % 3 == 0:
        for x, y in ((8, 9), (15, 12), (11, 5)):
            pygame.draw.circle(s, (220, 60, 60), (x, y), 1)
    return outlined(s)


def obj_surf(kind, season):
    s = pygame.Surface((TS, TS), pygame.SRCALPHA)
    grass = shade(GRASS[season if season < 3 else 1], 0.8)
    if kind == 'weed':
        for x, h in ((4, 6), (7, 8), (10, 5), (12, 7)):
            pygame.draw.line(s, grass, (x, 15), (x - 1, 15 - h))
        if season == 3:
            rect(s, (240, 244, 250), 4, 8, 8, 2)
    elif kind == 'tallgrass':
        s = pygame.Surface((TS, 20), pygame.SRCALPHA)
        c1 = shade(GRASS[season], 0.75) if season < 3 else (170, 160, 130)
        c2 = shade(GRASS[season], 1.05) if season < 3 else (210, 200, 170)
        for i, x in enumerate((2, 4, 6, 8, 10, 12, 14)):
            pygame.draw.line(s, c1 if i % 2 else c2, (x, 19), (x + (1 if i % 3 else -1), 6 + (i * 5) % 5), 2)
    elif kind == 'stone':
        pygame.draw.ellipse(s, (138, 136, 142), (3, 7, 10, 8))
        pygame.draw.ellipse(s, (172, 170, 176), (4, 7, 7, 5))
    elif kind == 'boulder':
        pygame.draw.ellipse(s, (118, 116, 124), (0, 2, 16, 14))
        pygame.draw.ellipse(s, (156, 154, 162), (2, 2, 11, 9))
        pygame.draw.line(s, (98, 96, 104), (8, 6), (11, 11))
    elif kind == 'branch':
        pygame.draw.line(s, (126, 88, 56), (2, 12), (14, 9), 2)
        pygame.draw.line(s, (126, 88, 56), (8, 11), (10, 6), 1)
        s.set_at((10, 5), (100, 170, 70))
    elif kind == 'stump':
        pygame.draw.ellipse(s, (110, 76, 50), (2, 7, 12, 9))
        rect(s, (110, 76, 50), 2, 6, 12, 6)
        pygame.draw.ellipse(s, (196, 156, 104), (2, 3, 12, 6))
        pygame.draw.ellipse(s, (160, 120, 80), (5, 4, 6, 4), 1)
    elif kind == 'dead':
        for x in (5, 8, 11):
            pygame.draw.line(s, (130, 104, 70), (x, 15), (x + 2, 7))
        rect(s, (150, 120, 80), 8, 6, 3, 2)
    elif kind == 'scarecrow':
        s = pygame.Surface((TS, 24), pygame.SRCALPHA)
        rect(s, (120, 82, 54), 7, 6, 2, 18)
        rect(s, (120, 82, 54), 1, 10, 14, 2)
        rect(s, (90, 130, 200), 4, 10, 8, 8)
        rect(s, (230, 200, 112), 4, 18, 8, 2)
        pygame.draw.circle(s, (238, 214, 160), (8, 5), 4)
        rect(s, (190, 80, 60), 2, 1, 12, 2)
        rect(s, (190, 80, 60), 5, 0, 6, 2)
        s.set_at((6, 5), INK)
        s.set_at((9, 5), INK)
    elif kind == 'sprinkler':
        rect(s, (150, 156, 170), 5, 9, 6, 6)
        rect(s, (196, 202, 214), 7, 5, 2, 5)
        rect(s, (90, 160, 220), 6, 4, 4, 2)
    elif kind == 'bin':
        s = pygame.Surface((TS, 14), pygame.SRCALPHA)
        rect(s, (150, 100, 60), 0, 4, 16, 10)
        for x in (3, 8, 13):
            pygame.draw.line(s, (120, 80, 48), (x, 5), (x, 13))
        rect(s, (184, 126, 74), 0, 0, 16, 4)
        rect(s, (230, 206, 110), 6, 1, 4, 2)
    elif kind == 'flower':
        r = random.Random('fl%d' % season)
        for i in range(4):
            x, y = 3 + (i * 5) % 10, 6 + (i * 3) % 7
            pygame.draw.line(s, (70, 140, 60), (x, y), (x, y + 4))
            c = r.choice(((240, 120, 160), (250, 220, 90), (180, 140, 230), (250, 250, 250)))
            pygame.draw.circle(s, c, (x, y), 1 + (i % 2))
        if season == 3:
            s.fill((0, 0, 0, 0))
            rect(s, (240, 244, 250), 3, 10, 10, 3)
    return outlined(s)


def bld_surf(kind, season, extra_col=None):
    b = BUILDS[kind]
    w, h = b['w'] * TS, b['h'] * TS
    top = {'HOUSE': 14, 'COOP': 12, 'BARN': 16, 'WELL': 12, 'GREENHOUSE': 12, 'STALL': 12,
           'COTTAGE': 14}[kind]
    s = pygame.Surface((w, h + top), pygame.SRCALPHA)
    snow = season == 3
    wood = (120, 82, 54)
    if kind in ('HOUSE', 'COTTAGE'):
        wall = (240, 226, 192) if kind == 'HOUSE' else extra_col[0]
        roof = (194, 82, 72) if kind == 'HOUSE' else extra_col[1]
        rw = top + 22
        rect(s, wall, 3, rw - 4, w - 6, h + top - rw + 4)
        pygame.draw.line(s, shade(wall, 0.8), (3, rw - 4), (3, h + top))
        pygame.draw.polygon(s, roof, [(0, rw), (8, 2), (w - 8, 2), (w, rw)])
        for y in range(6, rw, 5):
            pygame.draw.line(s, shade(roof, 0.8), (max(0, 8 - (y - 2) * 8 // rw), y),
                             (min(w, w - 8 + (y - 2) * 8 // rw), y))
        if snow:
            pygame.draw.polygon(s, (244, 248, 252), [(5, 8), (8, 2), (w - 8, 2), (w - 5, 8)])
        if kind == 'HOUSE':
            rect(s, (150, 86, 70), w - 22, 0, 8, 10)
            dx = 2 * TS + 3
            rect(s, (132, 88, 56), dx, h + top - 22, 10, 22)
            rect(s, (164, 112, 70), dx + 1, h + top - 21, 8, 21)
            s.set_at((dx + 7, h + top - 11), GOLD)
            for wx in (10, w - 26):
                rect(s, wood, wx - 1, rw + 5, 16, 13)
                rect(s, (190, 228, 240), wx, rw + 6, 14, 11)
                pygame.draw.line(s, wood, (wx + 7, rw + 6), (wx + 7, rw + 16))
                pygame.draw.line(s, wood, (wx, rw + 11), (wx + 13, rw + 11))
                rect(s, (150, 100, 60), wx - 1, rw + 18, 16, 3)
                for i in range(4):
                    s.set_at((wx + 1 + i * 4, rw + 17), (240, 110, 150) if i % 2 else (250, 220, 90))
        else:
            rect(s, (132, 88, 56), w // 2 - 5, h + top - 18, 10, 18)
            rect(s, wood, 7, rw + 4, 12, 10)
            rect(s, (190, 228, 240), 8, rw + 5, 10, 8)
    elif kind == 'COOP':
        wall = (228, 192, 132)
        rect(s, wall, 2, top + 8, w - 4, h - 8)
        for x in range(6, w - 4, 6):
            pygame.draw.line(s, shade(wall, 0.85), (x, top + 9), (x, h + top - 1))
        pygame.draw.polygon(s, (150, 92, 62), [(0, top + 10), (10, 0), (w - 10, 0), (w, top + 10)])
        if snow:
            pygame.draw.polygon(s, (244, 248, 252), [(6, 4), (10, 0), (w - 10, 0), (w - 6, 4)])
        rect(s, (90, 60, 40), TS + 3, h + top - 18, 10, 18)
        pygame.draw.line(s, (180, 140, 90), (TS + 1, h + top - 1), (TS + 14, h + top - 1), 2)
        pygame.draw.circle(s, (190, 228, 240), (w - 16, top + 18), 4)
        pygame.draw.circle(s, wood, (w - 16, top + 18), 4, 1)
    elif kind == 'BARN':
        wall = (180, 64, 54)
        rect(s, wall, 2, top + 14, w - 4, h - 14)
        for x in range(8, w - 4, 8):
            pygame.draw.line(s, shade(wall, 0.85), (x, top + 15), (x, h + top - 1))
        pygame.draw.polygon(s, (106, 62, 52), [(0, top + 16), (8, 6), (24, 0), (w - 24, 0), (w - 8, 6), (w, top + 16)])
        if snow:
            pygame.draw.polygon(s, (244, 248, 252), [(14, 3), (24, 0), (w - 24, 0), (w - 14, 3)])
        dx = 2 * TS + 2
        rect(s, (240, 236, 226), dx - 2, h + top - 30, 32, 30)
        rect(s, (140, 50, 44), dx, h + top - 28, 28, 28)
        pygame.draw.line(s, (240, 236, 226), (dx, h + top - 28), (dx + 27, h + top - 1), 2)
        pygame.draw.line(s, (240, 236, 226), (dx + 27, h + top - 28), (dx, h + top - 1), 2)
        rect(s, (240, 236, 226), w // 2 - 6, top + 18, 12, 9)
        rect(s, (60, 40, 36), w // 2 - 4, top + 20, 8, 5)
    elif kind == 'WELL':
        pygame.draw.ellipse(s, (132, 130, 140), (2, top + 14, 28, 16))
        rect(s, (132, 130, 140), 2, top + 10, 28, 12)
        pygame.draw.ellipse(s, (164, 162, 172), (2, top + 4, 28, 14))
        pygame.draw.ellipse(s, (200, 228, 240) if snow else (60, 110, 160), (6, top + 7, 20, 8))
        rect(s, wood, 4, 4, 2, top + 6)
        rect(s, wood, 26, 4, 2, top + 6)
        pygame.draw.polygon(s, (194, 82, 72), [(0, 6), (16, 0), (32, 6)])
        pygame.draw.line(s, wood, (6, 8), (26, 8))
    elif kind == 'GREENHOUSE':
        glass = (190, 228, 236, 150)
        frame = (236, 244, 244)
        tint = pygame.Surface((w - 2 * TS, h - 2 * TS), pygame.SRCALPHA)
        tint.fill((200, 236, 255, 34))
        s.blit(tint, (TS, top + TS))
        rect(s, glass, 0, 0, w, top + TS)                    # back wall and roof
        rect(s, glass, 0, top + TS, TS - 4, h - TS)          # sides
        rect(s, glass, w - TS + 4, top + TS, TS - 4, h - TS)
        rect(s, glass, 0, h + top - 10, 3 * TS, 10)          # front, with a gap for the door
        rect(s, glass, 4 * TS, h + top - 10, 3 * TS, 10)
        for x in range(0, w + 1, 8):
            pygame.draw.line(s, frame, (min(x, w - 1), 0), (min(x, w - 1), top + TS))
        pygame.draw.line(s, frame, (0, 0), (w, 0), 2)
        pygame.draw.line(s, frame, (0, top + TS), (w, top + TS))
        for x, y0 in ((0, top + TS), (TS - 5, top + TS), (w - TS + 4, top + TS), (w - 1, top + TS)):
            pygame.draw.line(s, frame, (x, y0), (x, h + top))
        pygame.draw.line(s, frame, (0, h + top - 10), (3 * TS, h + top - 10))
        pygame.draw.line(s, frame, (4 * TS, h + top - 10), (w, h + top - 10))
        if snow:
            rect(s, (244, 248, 252), 0, 0, w, 3)
    elif kind == 'STALL':
        aw = extra_col
        for i in range(8):
            rect(s, aw if i % 2 == 0 else CREAM, i * 8, 0, 8, 12)
            pygame.draw.circle(s, aw if i % 2 == 0 else CREAM, (i * 8 + 4, 12), 4)
        rect(s, wood, 2, 12, 3, top + TS)
        rect(s, wood, w - 5, 12, 3, top + TS)
        cy = top + TS
        rect(s, (166, 116, 72), 0, cy, w, TS)
        rect(s, (196, 146, 96), 0, cy, w, 4)
        for x in range(6, w, 10):
            pygame.draw.line(s, (140, 96, 60), (x, cy + 5), (x, cy + TS - 1))
        if snow:
            rect(s, (244, 248, 252), 0, 0, w, 3)
    return s


def make_person(look, d, frame):
    skin, hair, shirt, pants, hat = look
    s = pygame.Surface((12, 18), pygame.SRCALPHA)
    l1 = 1 if frame == 1 else 0
    l2 = 1 if frame == 2 else 0
    if d in ('down', 'up'):
        rect(s, pants, 3, 14 - l1, 3, 4)
        rect(s, pants, 6, 14 - l2, 3, 4)
        rect(s, shade(pants, 0.6), 3, 17 - l1, 3, 1)
        rect(s, shade(pants, 0.6), 6, 17 - l2, 3, 1)
    else:
        rect(s, pants, 4 - l1, 14, 4, 4)
        rect(s, shade(pants, 0.6), 4 - l1, 17, 4, 1)
        rect(s, shade(pants, 0.8), 5 + l2, 14, 3, 3)
    rect(s, shirt, 2, 8, 8, 7)
    rect(s, pants, 3, 12, 6, 3)
    if d == 'down':
        rect(s, pants, 3, 9, 1, 4)
        rect(s, pants, 8, 9, 1, 4)
    if d in ('down', 'up'):
        rect(s, shade(shirt, 0.82), 1, 9 + l2, 1, 4)
        rect(s, shade(shirt, 0.82), 10, 9 + l1, 1, 4)
    else:
        rect(s, shade(shirt, 0.82), 5, 9, 2, 4)
    rect(s, skin, 2, 1, 8, 7)
    if d == 'up':
        rect(s, hair, 2, 0, 8, 7)
    else:
        rect(s, hair, 2, 0, 8, 3)
        if d == 'left':
            rect(s, hair, 7, 0, 3, 6)
            s.set_at((3, 4), INK)
        elif d == 'right':
            rect(s, hair, 2, 0, 3, 6)
            s.set_at((8, 4), INK)
        else:
            rect(s, hair, 2, 0, 1, 5)
            rect(s, hair, 9, 0, 1, 5)
            s.set_at((4, 4), INK)
            s.set_at((7, 4), INK)
            s.set_at((3, 5), shade(skin, 0.9))
    if hat:
        rect(s, hat, 0, 2, 12, 2)
        rect(s, hat, 3, 0, 6, 2)
        rect(s, shade(hat, 0.75), 3, 1, 6, 1)
    return outlined(s)


def make_animal(kind, frame):
    if kind == 'CHICKEN':
        s = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (248, 246, 240), (0, 2, 9, 6))
        pygame.draw.circle(s, (248, 246, 240), (7, 3), 2)
        rect(s, (226, 60, 60), 6, 0, 2, 1)
        rect(s, (240, 180, 60), 9, 3, 1, 1)
        s.set_at((7, 2), INK)
        rect(s, (230, 160, 60), 3 + frame, 8, 1, 2)
        rect(s, (230, 160, 60), 5 - frame, 8, 1, 2)
        rect(s, (220, 214, 204), 1, 4, 3, 2)
    elif kind == 'COW':
        s = pygame.Surface((20, 14), pygame.SRCALPHA)
        rect(s, (60, 50, 50), 3 + frame, 9, 2, 5)
        rect(s, (60, 50, 50), 13 - frame, 9, 2, 5)
        pygame.draw.ellipse(s, (246, 242, 236), (0, 2, 17, 9))
        pygame.draw.ellipse(s, (60, 50, 50), (3, 3, 5, 4))
        pygame.draw.ellipse(s, (60, 50, 50), (9, 6, 4, 3))
        rect(s, (246, 242, 236), 14, 1, 5, 6)
        rect(s, (240, 170, 170), 16, 5, 4, 3)
        s.set_at((16, 3), INK)
        rect(s, (220, 210, 180), 14, 0, 1, 1)
        rect(s, (220, 210, 180), 18, 0, 1, 1)
        rect(s, (240, 170, 170), 7, 10, 3, 2)
    elif kind == 'SHEEP':
        s = pygame.Surface((17, 13), pygame.SRCALPHA)
        rect(s, (60, 50, 50), 3 + frame, 9, 2, 4)
        rect(s, (60, 50, 50), 11 - frame, 9, 2, 4)
        for cx, cy in ((4, 5), (8, 4), (11, 5), (6, 8), (10, 8)):
            pygame.draw.circle(s, (242, 238, 226), (cx, cy), 4)
        rect(s, (70, 58, 56), 12, 3, 5, 5)
        s.set_at((15, 4), (240, 240, 240))
        rect(s, (70, 58, 56), 11, 2, 2, 2)
    else:  # rabbit
        s = pygame.Surface((9, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (170, 140, 116), (0, 3 - frame, 7, 5))
        pygame.draw.circle(s, (170, 140, 116), (6, 3 - frame), 2)
        rect(s, (170, 140, 116), 5, 0 - frame, 1, 3)
        rect(s, (170, 140, 116), 7, 0 - frame, 1, 3)
        s.set_at((7, 3 - frame), INK)
        s.set_at((0, 4 - frame), (250, 250, 250))
    return outlined(s)


def icon_surf(name, can_lvl=1, hoe_lvl=1):
    s = pygame.Surface((12, 12), pygame.SRCALPHA)
    wood = (150, 102, 60)
    metal = {1: (164, 164, 176), 2: (212, 130, 78), 3: (206, 216, 232)}
    k = item_kind(name)
    if name == 'HOE':
        pygame.draw.line(s, wood, (2, 11), (9, 2), 2)
        rect(s, metal[hoe_lvl], 7, 1, 5, 3)
    elif name == 'CAN':
        rect(s, metal[can_lvl] if can_lvl > 1 else (90, 150, 210), 1, 4, 7, 7)
        pygame.draw.line(s, (90, 150, 210) if can_lvl == 1 else metal[can_lvl], (7, 7), (11, 3), 2)
        pygame.draw.arc(s, (70, 70, 80), (2, 1, 5, 6), 0, 3.14)
    elif name == 'AXE':
        pygame.draw.line(s, wood, (2, 11), (8, 1), 2)
        pygame.draw.polygon(s, metal[1], [(6, 1), (11, 2), (10, 6), (7, 4)])
    elif name == 'PICK':
        pygame.draw.line(s, wood, (3, 11), (8, 3), 2)
        pygame.draw.arc(s, metal[1], (1, 1, 11, 7), 0.3, 2.9, 2)
    elif name == 'SCYTHE':
        pygame.draw.line(s, wood, (3, 11), (6, 1), 2)
        pygame.draw.arc(s, metal[3], (4, 0, 9, 8), 0.2, 2.5, 2)
    elif k == 'seed':
        col = CROPS[SEED_OF[name]]['col']
        rect(s, (236, 224, 196), 1, 1, 10, 10)
        rect(s, col, 2, 2, 8, 5)
        for x in (3, 6, 8):
            s.set_at((x, 9), (110, 76, 48))
    elif k == 'crop':
        c = CROPS[name]
        col, sh = c['col'], c['shape']
        if sh == 'root':
            pygame.draw.line(s, (86, 168, 64), (6, 5), (3, 0), 2)
            pygame.draw.line(s, (86, 168, 64), (6, 5), (9, 0), 2)
            pygame.draw.ellipse(s, col, (2, 4, 8, 8))
        elif sh == 'bush':
            for x, y in ((4, 5), (8, 6), (6, 9)):
                pygame.draw.circle(s, col, (x, y), 3)
            rect(s, (86, 168, 64), 5, 1, 3, 2)
        elif sh == 'tall':
            if name == 'CORN':
                pygame.draw.ellipse(s, col, (3, 1, 6, 10))
                pygame.draw.line(s, (86, 168, 64), (3, 11), (2, 4), 2)
            else:
                for x in (3, 6, 9):
                    pygame.draw.line(s, col, (x, 11), (x, 3), 1)
                    rect(s, shade(col, 0.85), x - 1, 1, 2, 4)
        elif sh == 'gourd':
            pygame.draw.ellipse(s, col, (0, 3, 12, 9))
            rect(s, (110, 80, 40), 5, 1, 2, 3)
        else:
            pygame.draw.circle(s, col, (6, 6), 5)
            pygame.draw.circle(s, shade(col, 1.2), (6, 6), 2)
    elif name in ('EGG', 'LARGE EGG'):
        pygame.draw.ellipse(s, (248, 240, 222) if name == 'EGG' else (244, 214, 160), (2, 1, 8, 10))
    elif name in ('MILK', 'LARGE MILK'):
        rect(s, (246, 246, 250), 2, 3, 8, 9)
        rect(s, (150, 190, 230), 3, 1, 6, 2)
        rect(s, (150, 190, 230), 2, 6, 8, 2)
    elif name in ('WOOL', 'FINE WOOL'):
        for x, y in ((4, 5), (8, 5), (6, 8), (6, 3)):
            pygame.draw.circle(s, (246, 240, 226), (x, y), 3)
    elif name == 'SCARECROW':
        rect(s, wood, 5, 2, 2, 10)
        rect(s, wood, 1, 5, 10, 2)
        pygame.draw.circle(s, (238, 214, 160), (6, 3), 3)
        rect(s, (190, 80, 60), 2, 0, 8, 2)
    elif name == 'SPRINKLER':
        rect(s, (150, 156, 170), 3, 6, 6, 6)
        rect(s, (196, 202, 214), 5, 2, 2, 5)
        rect(s, (90, 160, 220), 4, 1, 4, 2)
    elif name == 'TEA':
        rect(s, (246, 240, 230), 2, 4, 7, 7)
        rect(s, (170, 110, 60), 3, 5, 5, 2)
        pygame.draw.arc(s, (246, 240, 230), (7, 5, 4, 4), -1.6, 1.6)
        pygame.draw.line(s, (220, 220, 230), (4, 0), (5, 3))
    if name.startswith(('LARGE', 'FINE')):
        for p in ((10, 0), (9, 1), (11, 1), (10, 2)):
            s.set_at(p, GOLD)
    return outlined(s)


def res_icon(kind):
    s = pygame.Surface((7, 7), pygame.SRCALPHA)
    if kind == 'wood':
        rect(s, (150, 102, 60), 0, 1, 7, 5)
        pygame.draw.circle(s, (200, 160, 110), (5, 3), 2)
    elif kind == 'stone':
        pygame.draw.ellipse(s, (160, 158, 166), (0, 1, 7, 6))
    else:
        rect(s, (226, 196, 100), 0, 1, 7, 6)
        pygame.draw.line(s, (180, 150, 70), (0, 3), (6, 3))
    return outlined(s)


def weather_icon(kind):
    s = pygame.Surface((11, 9), pygame.SRCALPHA)
    if kind == 'SUN':
        pygame.draw.circle(s, GOLD, (5, 4), 3)
        for a in range(8):
            x, y = 5 + round(math.cos(a / 8 * TAU) * 5), 4 + round(math.sin(a / 8 * TAU) * 4)
            s.set_at((x, y), GOLD)
    else:
        pygame.draw.circle(s, (220, 226, 236), (4, 4), 3)
        pygame.draw.circle(s, (220, 226, 236), (7, 3), 3)
        rect(s, (220, 226, 236), 1, 4, 9, 3)
        if kind == 'RAIN':
            for x in (2, 5, 8):
                s.set_at((x, 8), (110, 170, 230))
        elif kind == 'STORM':
            pygame.draw.lines(s, GOLD, False, [(6, 4), (4, 6), (6, 6), (4, 8)])
        elif kind == 'SNOW':
            for x in (2, 5, 8):
                s.set_at((x, 8), (255, 255, 255))
    return outlined(s)


HEART = ['01010', '11111', '11111', '01110', '00100']


def heart_surf(full):
    s = pygame.Surface((5, 5), pygame.SRCALPHA)
    for y, row in enumerate(HEART):
        for x, c in enumerate(row):
            if c == '1':
                s.set_at((x, y), RED if full else (110, 96, 110))
    return outlined(s)


# ------------------------------------------------------------------ world layout
def layout():
    g = [['g'] * MW for _ in range(MH)]
    for y in range(MH):
        for x in range(MW):
            if x < 2 or y < 2 or y >= MH - 2 or x >= MW - 2 or x in (FARM_X1, FARM_X1 + 1):
                g[y][x] = 't'
    for y in range(6, 12):
        g[y][6] = 'p'
    for x in range(6, 43):
        for y in (10, 11):
            g[y][x] = 'p' if x < FARM_X1 + 2 else 'c'
    for y in range(2, MH - 2):
        g[y][43] = g[y][44] = 'c'
    for x0, y0 in ((39, 6), (45, 15), (39, 24)):   # cobbles in front of each stall
        for x in range(x0, x0 + 4):
            g[y0][x] = 'c'
        for x in range(x0 + 4 if x0 < 43 else 43, 43 if x0 < 43 else x0):
            g[y0][x] = 'c'
    for y in range(MH):
        for x in range(FARM_X1):
            if g[y][x] == 't':
                continue
            d = ((x - 22) / 5.0) ** 2 + ((y - 25) / 3.4) ** 2
            if d < 1:
                g[y][x] = 'w'
            elif ((x - 22) / 6.2) ** 2 + ((y - 25) / 4.5) ** 2 < 1:
                g[y][x] = 's'
    return g


FIXED_BUILDS = [('HOUSE', 4, 2, None), ('STALL', 39, 4, 'MARIGOLD'), ('STALL', 45, 13, 'BRAM'),
                ('STALL', 39, 22, 'HAZEL'), ('COTTAGE', 45, 3, ((236, 210, 220), (120, 90, 150))),
                ('COTTAGE', 39, 13, ((214, 230, 206), (90, 120, 170))),
                ('COTTAGE', 45, 23, ((240, 226, 180), (170, 100, 70)))]


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
        pygame.display.set_caption('HOLLYHOCK')
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()
        self.sfx = Sfx()
        self.cache = {}
        self.data_dir = os.path.join(os.environ.get('XDG_DATA_HOME') or
                                     os.path.expanduser('~/.local/share'), 'hollyhock')
        self.save_path = os.path.join(self.data_dir, 'save.json')
        self.best = self.load_int('best')
        self.state = 'title'
        self.menu_sel = 0
        self.t = 0.0
        self.night_overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        self.drops = [[random.uniform(0, W), random.uniform(0, H)] for _ in range(90)]
        self.flash = 0.0
        self.toast_msg, self.toast_t = '', 0.0
        self.label_t = 0.0

    # -------------------------------------------------------------- persistence
    def load_int(self, name):
        try:
            with open(os.path.join(self.data_dir, name)) as f:
                return int(f.read().strip() or 0)
        except (OSError, ValueError):
            return 0

    def save_int(self, name, v):
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(os.path.join(self.data_dir, name), 'w') as f:
                f.write(str(v))
        except OSError:
            pass

    @staticmethod
    def k(t):
        return '%d,%d' % t

    @staticmethod
    def unk(s):
        a, b = s.split(',')
        return int(a), int(b)

    def save(self):
        d = dict(day=self.day, season=self.season, gold=self.gold, earned=self.earned,
                 hoe=self.hoe_lvl, can=self.can_lvl, water=self.water, wood=self.wood,
                 stone=self.stone, hay=self.hay, inv=self.inv, weather=self.weather,
                 forecast=self.forecast, friend=self.friend, perks=sorted(self.perks),
                 stamina=self.stamina, seed=self.seed,
                 soil={self.k(t): [s['wet'], s['gh']] for t, s in self.soil.items()},
                 crops={self.k(t): [c['name'], c['age']] for t, c in self.crops.items()},
                 objs={self.k(t): o for t, o in self.objs.items()},
                 built=[[b['kind'], b['x'], b['y']] for b in self.buildings if b.get('built')],
                 animals=[{k: a[k] for k in ('kind', 'name', 'b', 'mood', 'days', 'ready')}
                          for a in self.animals])
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            tmp = self.save_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(d, f)
            os.replace(tmp, self.save_path)
        except OSError:
            pass

    def has_save(self):
        return os.path.exists(self.save_path)

    def delete_save(self):
        try:
            os.remove(self.save_path)
        except OSError:
            pass

    def load(self):
        try:
            with open(self.save_path) as f:
                d = json.load(f)
            self.new_game(d['seed'], debris=False)
            self.day, self.season, self.gold, self.earned = d['day'], d['season'], d['gold'], d['earned']
            self.hoe_lvl, self.can_lvl, self.water = d['hoe'], d['can'], d['water']
            self.wood, self.stone, self.hay = d['wood'], d['stone'], d['hay']
            self.inv = [list(i) if i else None for i in d['inv']]
            self.weather, self.forecast = d['weather'], d['forecast']
            self.friend.update(d['friend'])
            self.perks = set(d['perks'])
            self.stamina = d['stamina']
            self.soil = {self.unk(k): dict(wet=v[0], gh=v[1]) for k, v in d['soil'].items()}
            self.crops = {self.unk(k): dict(name=v[0], age=v[1]) for k, v in d['crops'].items()}
            self.objs = {self.unk(k): list(v) for k, v in d['objs'].items()}
            for kind, x, y in d['built']:
                self.buildings.append(dict(kind=kind, x=x, y=y, built=True))
            self.rebuild_occ()
            for a in d['animals']:
                self.add_animal(a['kind'], a['b'], a['name'], a['mood'], a['days'], a['ready'])
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            return False
        self.state = 'play'
        self.banner(SEASONS[self.season] + ' ' + str(self.day))
        return True

    # -------------------------------------------------------------- setup
    def new_game(self, seed=None, debris=True):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        rng = random.Random(self.seed)
        self.g = layout()
        self.buildings = [dict(kind=k, x=x, y=y, extra=e) for k, x, y, e in FIXED_BUILDS]
        self.objs = {(9, 5): ['bin', 1]}
        self.soil, self.crops = {}, {}
        self.animals, self.rabbits, self.floats = [], [], []
        self.shake = {}
        self.rebuild_occ()
        for _ in range(28):  # village flowers
            x, y = rng.randrange(38, 50), rng.randrange(2, MH - 2)
            if self.g[y][x] == 'g' and (x, y) not in self.occ:
                self.objs[(x, y)] = ['flower', 1]
        if debris:
            counts = [('weed', 70), ('tallgrass', 50), ('stone', 45), ('branch', 45), ('stump', 14),
                      ('boulder', 9), ('tree', 32)]
            for kind, n in counts:
                for _ in range(n):
                    for _try in range(20):
                        x, y = rng.randrange(2, FARM_X1), rng.randrange(2, MH - 2)
                        if 3 <= x <= 11 and 2 <= y <= 9:
                            continue
                        if 12 <= x <= 21 and 3 <= y <= 9:
                            continue
                        if self.g[y][x] != 'g' or (x, y) in self.objs or (x, y) in self.occ:
                            continue
                        if self.g[y - 1][x] == 'p' or self.g[min(MH - 1, y + 1)][x] == 'p':
                            continue
                        self.objs[(x, y)] = [kind, OBJ_HP.get(kind, 1)]
                        break
        self.gold, self.earned = 500, 0
        self.day, self.season = 1, 0
        self.minutes = DAY_START
        self.stamina = STAMINA
        self.hoe_lvl = self.can_lvl = 1
        self.water = CAN_CAP[0]
        self.wood = self.stone = self.hay = 0
        self.inv = [None] * 24
        for t in TOOLS:
            self.add_item(t)
        self.add_item('TURNIP SEEDS', 15)
        self.row, self.sel = 0, 0
        self.friend = {n: 0 for n in NPCS}
        self.talked, self.gifted, self.perks = set(), set(), set()
        self.weather, self.forecast = 'SUN', self.roll_weather(0)
        self.bin = []
        self.px, self.py = 6 * TS + 8, 6 * TS + 12
        self.face = 'down'
        self.walk_t = 0.0
        self.step_t = 0.0
        self.tool_cd = 0.0
        self.swing = 0.0
        self.ground = None
        self.ground_season = -1
        self.last_hour = 6
        self.report = []
        self.dlg = None
        self.shop = None
        self.place = None

    def roll_weather(self, season):
        opts = WEATHER[season]
        return random.choices([o[0] for o in opts], [o[1] for o in opts])[0]

    def rebuild_occ(self):
        self.occ = {}
        for i, b in enumerate(self.buildings):
            spec = BUILDS[b['kind']]
            for dy in range(spec['h']):
                for dx in range(spec['w']):
                    if b['kind'] == 'GREENHOUSE':
                        inner = 0 < dx < spec['w'] - 1 and 0 < dy < spec['h'] - 1
                        if inner or (dx, dy) in spec['door']:
                            continue
                    self.occ[(b['x'] + dx, b['y'] + dy)] = i

    # -------------------------------------------------------------- inventory
    def add_item(self, name, n=1):
        """Add n of an item; returns False (adding nothing) if the bag has no room."""
        for slot in self.inv:
            if slot and slot[0] == name and name not in TOOLS:
                slot[1] += n
                return True
        for i, slot in enumerate(self.inv):
            if slot is None:
                self.inv[i] = [name, n]
                return True
        return False

    def can_add(self, name):
        return any(s is None or (s[0] == name and name not in TOOLS) for s in self.inv)

    def count_item(self, name):
        return sum(s[1] for s in self.inv if s and s[0] == name)

    def take(self, idx, n=1):
        slot = self.inv[idx]
        slot[1] -= n
        if slot[1] <= 0:
            self.inv[idx] = None

    @property
    def sel_idx(self):
        return self.row * 12 + self.sel

    @property
    def held(self):
        s = self.inv[self.sel_idx]
        return s[0] if s else None

    def item_label(self, name):
        if name == 'HOE':
            return TIER[self.hoe_lvl - 1] + 'HOE'
        if name == 'CAN':
            return TIER[self.can_lvl - 1] + 'WATERING CAN'
        if name == 'PICK':
            return 'PICKAXE'
        return name

    def icon(self, name):
        key = ('icon', name, self.can_lvl if name == 'CAN' else 0, self.hoe_lvl if name == 'HOE' else 0)
        if key not in self.cache:
            self.cache[key] = icon_surf(name, self.can_lvl, self.hoe_lvl)
        return self.cache[key]

    def spr(self, key, fn, *args):
        s = self.cache.get(key)
        if s is None:
            s = self.cache[key] = fn(*args)
        return s

    # -------------------------------------------------------------- queries
    def in_farm(self, t):
        return 2 <= t[0] < FARM_X1 and 2 <= t[1] < MH - 2

    def solid(self, x, y):
        if not (0 <= x < MW and 0 <= y < MH):
            return True
        if self.g[y][x] in 'tw':
            return True
        if (x, y) in self.occ:
            return True
        o = self.objs.get((x, y))
        return bool(o and o[0] in SOLID_OBJS)

    def blocked(self, x, y):
        for cx, cy in ((x - 4, y - 3), (x + 4, y - 3), (x - 4, y + 1), (x + 4, y + 1)):
            if self.solid(int(cx // TS), int(cy // TS)):
                return True
        return False

    def ptile(self):
        return int(self.px // TS), int((self.py - 3) // TS)

    def target(self):
        x, y = self.ptile()
        dx, dy = DIRV[self.face]
        return x + dx, y + dy

    def raining(self):
        return self.weather in ('RAIN', 'STORM')

    def npc_open(self, n):
        a, b = NPCS[n]['hours']
        return a * 60 <= self.minutes < b * 60

    def hearts(self, n):
        return min(10, self.friend[n] // 100)

    def has_build(self, kind):
        return any(b['kind'] == kind for b in self.buildings)

    def is_free(self, t, allow_soil=False):
        if not self.in_farm(t) or self.g[t[1]][t[0]] not in 'gp':
            return False
        if t in self.occ or t in self.objs or t in self.crops:
            return False
        if t in self.soil and (not allow_soil or self.soil[t]['gh']):
            return False
        return True

    def protected(self, t):
        for (x, y), o in self.objs.items():
            if o[0] == 'scarecrow' and abs(x - t[0]) <= 4 and abs(y - t[1]) <= 4:
                return True
        return False

    def mature(self, t):
        c = self.crops.get(t)
        return c is not None and c['age'] >= CROPS[c['name']]['days']

    def door_spot(self, b):
        spec = BUILDS[b['kind']]
        dx, dy = spec['door'][0]
        return (b['x'] + dx) * TS + 8, (b['y'] + dy + 1) * TS + 10

    # -------------------------------------------------------------- messages
    def toast(self, s, snd=None):
        self.toast_msg, self.toast_t = s, 2.6
        if snd:
            self.sfx.play(snd)

    def banner(self, s):
        self.banner_msg, self.banner_t = s, 2.5

    def float_at(self, t, text=None, icon=None, color=CREAM):
        self.floats.append(dict(x=t[0] * TS + 8, y=t[1] * TS, text=text, icon=icon, color=color, t=1.2))

    # -------------------------------------------------------------- tools
    def line_tiles(self, n):
        t = self.target()
        dx, dy = DIRV[self.face]
        return [(t[0] + dx * i, t[1] + dy * i) for i in range(n)]

    def use_held(self):
        name = self.held
        if not name:
            return
        kind = item_kind(name)
        t = self.target()
        if kind == 'tool':
            cost = TOOL_COST[name]
            if name == 'HOE':
                cost += self.hoe_lvl - 1
            if name == 'CAN':
                cost += self.can_lvl - 1
            if self.stamina < cost:
                self.toast('TOO TIRED. GET SOME SLEEP, OR SOME TEA.', 'no')
                return
            self.swing = 0.22
            self.scare_rabbits(self.px, self.py, 40)
            if getattr(self, 'tool_' + name.lower())(t):
                self.stamina = max(0, self.stamina - cost)
        elif kind == 'seed':
            self.plant(t)
        elif kind == 'place':
            if self.is_free(t, allow_soil=True) and t != self.ptile():
                self.soil.pop(t, None)
                self.objs[t] = [name.lower(), 1]
                self.take(self.sel_idx)
                self.sfx.play('build')
            else:
                self.toast("CAN'T PLACE THAT THERE.", 'no')
        elif name == 'TEA' or name in EDIBLE:
            if self.stamina >= STAMINA:
                self.toast("YOU'RE NOT HUNGRY RIGHT NOW.", 'no')
                return
            gain = 60 if name == 'TEA' else min(50, max(8, sell_price(name) // 4))
            self.stamina = min(STAMINA, self.stamina + gain)
            self.take(self.sel_idx)
            self.toast(('DRANK THE TEA' if name == 'TEA' else 'ATE THE ' + name) + '. +%d ENERGY.' % gain, 'drink')
        else:
            self.toast('NOTHING TO DO WITH THAT HERE. SHIP IT AT THE BIN.', 'no')
            return
        self.tool_cd = 0.32

    def tool_hoe(self, t):
        done = False
        for tt in self.line_tiles(TOOL_REACH[self.hoe_lvl - 1]):
            o = self.objs.get(tt)
            if o and o[0] in ('weed', 'dead'):
                del self.objs[tt]
                done = True
            elif (self.in_farm(tt) and self.g[tt[1]][tt[0]] == 'g' and tt not in self.objs
                  and tt not in self.occ and tt not in self.soil):
                self.soil[tt] = dict(wet=self.raining(), gh=False)
                done = True
            elif tt != t:
                break
        self.sfx.play('hoe' if done else 'no')
        return done

    def tool_can(self, t):
        b = self.occ.get(t)
        well = b is not None and self.buildings[b]['kind'] == 'WELL'
        if well or (0 <= t[0] < MW and 0 <= t[1] < MH and self.g[t[1]][t[0]] == 'w'):
            if not well and self.season == 3:
                self.toast('THE POND IS FROZEN SOLID. A WELL NEVER FREEZES.', 'no')
                return False
            self.water = CAN_CAP[self.can_lvl - 1]
            self.toast('FILLED THE WATERING CAN.', 'fill')
            return True
        if self.water <= 0:
            self.toast('THE CAN IS EMPTY. REFILL IT AT THE POND OR A WELL.', 'no')
            return False
        done = False
        for tt in self.line_tiles(TOOL_REACH[self.can_lvl - 1]):
            if self.water <= 0:
                break
            s = self.soil.get(tt)
            if s:
                if not s['wet']:
                    s['wet'] = True
                    self.water -= 1
                done = True
            elif tt != t:
                break
        if done:
            self.sfx.play('water')
        return done

    def hit_obj(self, t, kinds):
        o = self.objs.get(t)
        if not o or o[0] not in kinds:
            return False
        o[1] -= 1
        self.shake[t] = 0.2
        kind = o[0]
        if o[1] > 0:
            self.sfx.play('chop' if kind in ('tree', 'stump') else 'pick')
            return True
        drops = {'stone': ('stone', 1), 'boulder': ('stone', 6), 'branch': ('wood', 1),
                 'stump': ('wood', 4), 'tree': ('wood', 8), 'tallgrass': ('hay', 1)}
        if kind == 'tree':
            self.objs[t] = ['stump', OBJ_HP['stump']]
        else:
            del self.objs[t]
        if kind in ('scarecrow', 'sprinkler'):
            self.add_item(kind.upper())
            self.sfx.play('pick')
            return True
        if kind in drops:
            res, n = drops[kind]
            setattr(self, res, getattr(self, res) + n)
            self.float_at(t, '+%d %s' % (n, res.upper()))
        self.sfx.play('cut' if kind in ('weed', 'tallgrass', 'dead') else 'break')
        return True

    def tool_axe(self, t):
        if self.hit_obj(t, ('branch', 'stump', 'tree', 'weed')):
            return True
        self.sfx.play('no')
        return False

    def tool_pick(self, t):
        if self.hit_obj(t, ('stone', 'boulder', 'scarecrow', 'sprinkler', 'weed')):
            return True
        s = self.soil.get(t)
        if s and not s['gh'] and t not in self.crops:
            del self.soil[t]
            self.objs.pop(t, None)
            self.sfx.play('hoe')
            return True
        self.sfx.play('no')
        return False

    def tool_scythe(self, t):
        if self.mature(t):
            self.harvest(t)
            return False
        if self.hit_obj(t, ('weed', 'tallgrass', 'dead')):
            return True
        self.sfx.play('cut')
        return False

    def plant(self, t):
        name = SEED_OF[self.held]
        s = self.soil.get(t)
        if not s or t in self.crops or t in self.objs:
            self.toast('SEEDS NEED TILLED SOIL. USE THE HOE FIRST.', 'no')
            return
        if self.season not in CROPS[name]['seasons'] and not s['gh']:
            self.toast('%s WON\'T GROW IN %s. TRY THE GREENHOUSE.' % (name, SEASONS[self.season]), 'no')
            return
        self.crops[t] = dict(name=name, age=0)
        self.take(self.sel_idx)
        self.sfx.play('plant')

    def harvest(self, t):
        c = self.crops[t]
        spec = CROPS[c['name']]
        n = spec['yld'] + (1 if c['name'] == 'POTATO' and random.random() < 0.3 else 0)
        if not self.add_item(c['name'], n):
            self.toast('YOUR BAG IS FULL.', 'no')
            return
        if spec['regrow']:
            c['age'] = spec['days'] - spec['regrow']
        else:
            del self.crops[t]
        self.float_at(t, icon=c['name'])
        self.sfx.play('pop')

    # -------------------------------------------------------------- interaction
    def interact_info(self):
        """What E would do at the target tile: (label, action) or None."""
        t = self.target()
        b = self.occ.get(t)
        if b is not None:
            bd = self.buildings[b]
            kind = bd['kind']
            if kind == 'STALL':
                n = bd['extra']
                if self.npc_open(n):
                    return 'TALK', lambda: self.talk(n)
                return 'CLOSED', lambda: self.toast("%s'S STALL OPENS AT %d:00." % (n, NPCS[n]['hours'][0]))
            if kind == 'HOUSE':
                return 'SLEEP', self.sleep_prompt
            if kind in ('COOP', 'BARN'):
                return 'LOOK', lambda: self.building_info(b)
            if kind == 'WELL':
                return 'REFILL', lambda: (self.tool_can(t) if self.held == 'CAN'
                                          else self.toast('HOLD THE WATERING CAN TO REFILL IT.'))
        cx, cy = t[0] * TS + 8, t[1] * TS + 10
        for a in self.animals:
            if not a['inside'] and abs(a['x'] - cx) < 12 and abs(a['y'] - cy) < 12:
                if a['ready']:
                    return 'COLLECT', lambda a=a: self.pet(a)
                return 'PET', lambda a=a: self.pet(a)
        if self.mature(t):
            return 'HARVEST', lambda: self.harvest(t)
        o = self.objs.get(t)
        if o and o[0] == 'bin':
            return 'SHIP', self.ship
        return None

    def interact(self):
        info = self.interact_info()
        if info:
            info[1]()

    def ship(self):
        name = self.held
        if name and sell_price(name):
            n = self.inv[self.sel_idx][1]
            self.bin.append([name, n])
            self.inv[self.sel_idx] = None
            self.toast('SHIPPED %d %s. TONIGHT: %dG.' % (n, name, self.bin_value()), 'coin')
        elif self.bin:
            self.toast('THE BIN HOLDS %dG OF GOODS. IT EMPTIES OVERNIGHT.' % self.bin_value())
        else:
            self.toast('HOLD A CROP OR PRODUCE AND PRESS E TO SHIP IT.')

    def bin_value(self):
        return sum(sell_price(n) * c for n, c in self.bin)

    def building_info(self, bi):
        b = self.buildings[bi]
        ins = [a for a in self.animals if a['b'] == bi]
        cap = BUILDS[b['kind']]['cap']
        names = ', '.join(a['name'] for a in ins) or 'EMPTY'
        self.dialog(b['kind'], ['%d OF %d ANIMALS: %s.' % (len(ins), cap, names),
                                'HAY IN STORE: %d. EACH ANIMAL EATS ONE A MORNING.' % self.hay])

    def pet(self, a):
        if a['ready']:
            if not self.add_item(a['ready']):
                self.toast('YOUR BAG IS FULL.', 'no')
                return
            self.toast('COLLECTED %s FROM %s.' % (a['ready'], a['name']), 'pop')
            a['ready'] = None
            collected = True
        else:
            collected = False
        if not a['petted']:
            a['petted'] = True
            self.sfx.play(ANIMALS[a['kind']]['snd'])
            self.floats.append(dict(x=a['x'], y=a['y'] - 14, text=None, icon='HEART', color=RED, t=1.2))
            mood = ['GRUMPY', 'GLUM', 'CONTENT', 'HAPPY', 'OVERJOYED'][min(4, a['mood'] // 2 + (1 if a['mood'] >= 3 else 0))]
            self.toast('%s THE %s LOOKS %s.' % (a['name'], a['kind'], mood))
        elif not collected:
            self.toast('%s HAS HAD A GOOD SCRATCH TODAY.' % a['name'])

    def sleep_prompt(self):
        late = self.minutes >= 24 * 60
        self.dialog('YOUR BED', ['GO TO SLEEP AND END THE DAY?' +
                                 (' IT IS VERY LATE. YOU WILL WAKE TIRED.' if late else '')],
                    [('SLEEP', lambda: self.end_day()), ('NOT YET', None)])

    def dialog(self, name, lines, opts=None, hearts=None):
        self.dlg = dict(name=name, lines=lines, opts=opts or [], sel=0, hearts=hearts)
        self.state = 'dialog'

    def talk(self, n):
        npc = NPCS[n]
        if n not in self.talked:
            self.talked.add(n)
            self.friend[n] += 20
        r = random.random()
        if self.hearts(n) >= 5 and r < 0.3:
            line = random.choice(npc['high'])
        elif self.weather in ('RAIN', 'STORM') and r < 0.55:
            line = npc['rain'] if self.weather == 'RAIN' else npc['storm']
        elif r < 0.65:
            line = npc['season'][self.season]
        else:
            line = random.choice(npc['lines'])
        opts = [('SHOP', lambda: self.open_shop(n))]
        name = self.held
        if name and item_kind(name) in ('crop', 'product') and n not in self.gifted:
            opts.append(('GIFT ' + name, lambda: self.gift(n)))
        opts.append(('BYE', None))
        self.sfx.play('blip')
        self.dialog(n, [line], opts, hearts=self.hearts(n))

    def gift(self, n):
        name = self.held
        self.take(self.sel_idx)
        self.gifted.add(n)
        loved = name in NPCS[n]['loves']
        self.friend[n] += 120 if loved else 50
        line = NPCS[n]['love'] if loved else 'How thoughtful. Thank you, really.'
        self.sfx.play('pet')
        self.dialog(n, [line], [('BYE', None)], hearts=self.hearts(n))

    # -------------------------------------------------------------- shops
    def price(self, n, g):
        return int(g * 0.9) if self.hearts(n) >= 5 else g

    def open_shop(self, n):
        rows = []
        trade = NPCS[n]['trade']
        if trade == 'SEEDS':
            gh = self.has_build('GREENHOUSE')
            for c, spec in CROPS.items():
                ins = self.season in spec['seasons']
                if not ins and not gh:
                    continue
                desc = '%s. %d DAYS%s. SELLS FOR %dG%s.' % (
                    '/'.join(SEASONS[s] for s in spec['seasons']), spec['days'],
                    ', REGROWS IN %d' % spec['regrow'] if spec['regrow'] else '', spec['sell'],
                    ' EACH, 2 PER HARVEST' if spec['yld'] > 1 else '')
                if not ins:
                    desc = 'OUT OF SEASON: GREENHOUSE ONLY. ' + desc
                rows.append(dict(label=c + ' SEEDS', desc=desc, gold=spec['seed'], item=c + ' SEEDS'))
            rows.append(dict(label='TEA', desc='RESTORES 60 ENERGY. SELECT IT AND PRESS SPACE.', gold=80, item='TEA'))
        elif trade == 'BUILD':
            for k in ('COOP', 'BARN', 'WELL', 'GREENHOUSE'):
                if k == 'GREENHOUSE' and self.has_build(k):
                    continue
                b = BUILDS[k]
                rows.append(dict(label=k, desc=b['desc'], gold=b['gold'], wood=b['wood'], stone=b['stone'], build=k))
            rows.append(dict(label='SCARECROW', desc='KEEPS CROWS OFF CROPS WITHIN 4 TILES.', gold=40, wood=10, item='SCARECROW'))
            rows.append(dict(label='SPRINKLER', desc='WATERS THE 4 TILES BESIDE IT EVERY MORNING.', gold=100, stone=10, item='SPRINKLER'))
            for tool, lvl in (('HOE', self.hoe_lvl), ('CAN', self.can_lvl)):
                if lvl < 3:
                    what = 'TILLS' if tool == 'HOE' else 'WATERS'
                    extra = '' if tool == 'HOE' else ' HOLDS %d WATER.' % CAN_CAP[lvl]
                    rows.append(dict(label=TIER[lvl] + ('HOE' if tool == 'HOE' else 'WATERING CAN'),
                                     desc='%s %d TILES IN A ROW.%s' % (what, TOOL_REACH[lvl], extra),
                                     gold=[600, 1800][lvl - 1], stone=[15, 40][lvl - 1], upgrade=tool))
            rows.append(dict(label='10 WOOD', desc='FOR BUILDING. OR CHOP YOUR OWN.', gold=80, res=('wood', 10)))
            rows.append(dict(label='10 STONE', desc='FOR BUILDING. OR BREAK YOUR OWN.', gold=100, res=('stone', 10)))
        else:
            for a, spec in ANIMALS.items():
                rows.append(dict(label=a, desc='LIVES IN A %s. GIVES %s%s.' % (
                    spec['home'], spec['prod'], ' EVERY 3 DAYS' if spec['every'] > 1 else ' DAILY'),
                    gold=spec['price'], animal=a))
            rows.append(dict(label='10 HAY', desc='FEED. EACH ANIMAL EATS ONE A MORNING.', gold=60, res=('hay', 10)))
        for r in rows:
            r['gold'] = self.price(n, r['gold'])
        self.shop = dict(npc=n, rows=rows, sel=0, scroll=0)
        self.state = 'shop'

    def buy(self, r, times=1):
        for _ in range(times):
            if self.gold < r['gold'] or self.wood < r.get('wood', 0) or self.stone < r.get('stone', 0):
                self.toast("YOU CAN'T AFFORD THAT.", 'no')
                return
            if 'item' in r:
                if not self.add_item(r['item']):
                    self.toast('YOUR BAG IS FULL.', 'no')
                    return
            elif 'res' in r:
                res, n = r['res']
                setattr(self, res, getattr(self, res) + n)
            elif 'upgrade' in r:
                if r['upgrade'] == 'HOE':
                    self.hoe_lvl += 1
                else:
                    self.can_lvl += 1
                    self.water = CAN_CAP[self.can_lvl - 1]
                self.pay(r)
                self.toast('BRAM HANDS YOU THE %s.' % r['label'], 'chime')
                self.open_shop(self.shop['npc'])
                return
            elif 'animal' in r:
                spec = ANIMALS[r['animal']]
                home = self.free_home(spec['home'])
                if home is None:
                    self.toast('YOU NEED A %s WITH ROOM FIRST. BRAM CAN BUILD ONE.' % spec['home'], 'no')
                    return
                used = {a['name'] for a in self.animals}
                name = random.choice([p for p in PET_NAMES if p not in used] or PET_NAMES)
                self.add_animal(r['animal'], home, name, 4, 0, None)
                self.pay(r)
                self.toast('%s THE %s IS WAITING AT YOUR %s.' % (name, r['animal'], spec['home']),
                           spec['snd'])
                return
            elif 'build' in r:
                self.place = dict(kind=r['build'], row=r, x=12, y=12)
                self.state = 'place'
                self.shop = None
                return
            self.pay(r)
            self.sfx.play('coin')

    def pay(self, r):
        self.gold -= r['gold']
        self.wood -= r.get('wood', 0)
        self.stone -= r.get('stone', 0)

    def free_home(self, kind):
        for i, b in enumerate(self.buildings):
            if b['kind'] == kind and sum(1 for a in self.animals if a['b'] == i) < BUILDS[kind]['cap']:
                return i
        return None

    def add_animal(self, kind, b, name, mood, days, ready):
        x, y = self.door_spot(self.buildings[b])
        self.animals.append(dict(kind=kind, b=b, name=name, mood=mood, days=days, ready=ready,
                                 petted=False, x=float(x), y=float(y), tx=None, ty=None,
                                 idle=random.uniform(0, 2), inside=False, flip=False, walk=0.0))

    # -------------------------------------------------------------- placement
    def place_ok(self):
        p = self.place
        spec = BUILDS[p['kind']]
        pt = self.ptile()
        for dy in range(spec['h']):
            for dx in range(spec['w']):
                t = (p['x'] + dx, p['y'] + dy)
                if not self.is_free(t) or self.g[t[1]][t[0]] != 'g' or t in self.soil or t == pt:
                    return False
        if spec['door']:   # keep the tile in front of the door clear
            dx, dy = spec['door'][0]
            t = (p['x'] + dx, p['y'] + dy + 1)
            if self.solid(*t) or not self.in_farm(t):
                return False
        return True

    def confirm_place(self):
        if not self.place_ok():
            self.toast('THERE ISN\'T ROOM THERE. CLEAR THE GROUND FIRST.', 'no')
            return
        p = self.place
        self.pay(p['row'])
        self.buildings.append(dict(kind=p['kind'], x=p['x'], y=p['y'], built=True))
        if p['kind'] == 'GREENHOUSE':
            spec = BUILDS['GREENHOUSE']
            for dy in range(1, spec['h'] - 1):
                for dx in range(1, spec['w'] - 1):
                    self.soil[(p['x'] + dx, p['y'] + dy)] = dict(wet=False, gh=True)
        self.rebuild_occ()
        self.place = None
        self.state = 'play'
        self.toast('BRAM BUILT YOUR %s. IT LOOKS WONDERFUL.' % p['kind'], 'build')

    # -------------------------------------------------------------- the night
    def end_day(self, passed=False):
        rep = []
        if passed:
            rep.append('YOU NODDED OFF OUT IN THE FIELDS. MARIGOLD WALKED YOU HOME.')
        total = self.bin_value()
        if total:
            self.gold += total
            self.earned += total
            rep.append('THE SHIPPING BIN EARNED %dG.' % total)
        self.bin = []
        grown = 0
        for t, c in self.crops.items():
            if self.soil.get(t, {}).get('wet'):
                was = self.mature(t)
                c['age'] = min(CROPS[c['name']]['days'], c['age'] + 1)
                grown += (not was) and self.mature(t)
        if grown:
            rep.append('%d CROP%s RIPENED OVERNIGHT.' % (grown, 'S' if grown > 1 else ''))
        for t, s in list(self.soil.items()):
            s['wet'] = False
            if not s['gh'] and t not in self.crops and t not in self.objs and random.random() < 0.1:
                del self.soil[t]
        self.day += 1
        new_season = False
        if self.day > DAYS:
            rent = RENT[self.season]
            if self.gold < rent:
                self.finish(False, 'THE %s LEASE OF %dG FELL DUE, AND YOU HAD ONLY %dG.' % (
                    SEASONS[self.season], rent, self.gold))
                return
            self.gold -= rent
            rep.append('PAID THE %s LEASE: %dG.' % (SEASONS[self.season], rent))
            self.season += 1
            self.day = 1
            if self.season >= 4:
                self.finish(True, '')
                return
            new_season = True
            dead = 0
            for t in list(self.crops):
                if not self.soil[t]['gh'] and self.season not in CROPS[self.crops[t]['name']]['seasons']:
                    del self.crops[t]
                    self.objs[t] = ['dead', 1]
                    dead += 1
            if dead:
                rep.append('THE TURN OF THE SEASON WITHERED %d CROP%s.' % (dead, 'S' if dead > 1 else ''))
        self.weather = 'SUN' if new_season else self.forecast
        self.forecast = 'SUN' if self.day == DAYS else self.roll_weather(self.season)
        outdoor = [t for t, s in self.soil.items() if not s['gh']]
        if self.raining():
            for t in outdoor:
                self.soil[t]['wet'] = True
        for (x, y), o in self.objs.items():
            if o[0] == 'sprinkler':
                for dx, dy in DIRV.values():
                    s = self.soil.get((x + dx, y + dy))
                    if s:
                        s['wet'] = True
        crops_out = [t for t in self.crops if not self.soil[t]['gh']]
        if self.weather == 'SUN' and len(crops_out) >= 6 and random.random() < 0.7:
            exposed = [t for t in crops_out if not self.protected(t)]
            n = min(len(exposed), random.randint(1, max(1, len(crops_out) // 8)))
            for t in random.sample(exposed, n):
                del self.crops[t]
            if n:
                rep.append('CROWS ATE %d CROP%s AT DAWN. A SCARECROW WOULD HELP.' % (n, 'S' if n > 1 else ''))
        if self.weather == 'STORM' and crops_out and random.random() < 0.5:
            t = random.choice([c for c in crops_out if c in self.crops] or [None])
            if t:
                del self.crops[t]
                self.objs[t] = ['dead', 1]
                rep.append('LIGHTNING STRUCK ONE OF YOUR CROPS IN THE NIGHT.')
        if self.animals:
            hungry = 0
            for a in self.animals:
                a['mood'] = max(0, min(10, a['mood'] + (1 if a['petted'] else -1)))
                a['petted'] = False
                a['inside'] = False
                a['x'], a['y'] = map(float, self.door_spot(self.buildings[a['b']]))
                a['tx'] = None
                if self.hay > 0:
                    self.hay -= 1
                    spec = ANIMALS[a['kind']]
                    a['days'] += 1
                    if a['days'] >= spec['every'] and not a['ready']:
                        a['ready'] = spec['big'] if a['mood'] >= 7 else spec['prod']
                        a['days'] = 0
                else:
                    hungry += 1
                    a['mood'] = max(0, a['mood'] - 1)
            if hungry:
                rep.append('NO HAY LEFT! %d ANIMAL%s WENT HUNGRY.' % (hungry, 'S' if hungry > 1 else ''))
            else:
                rep.append('THE ANIMALS ATE. %d HAY LEFT.' % self.hay)
        if self.season < 3:
            for _ in range(10):
                t = (random.randrange(2, FARM_X1), random.randrange(2, MH - 2))
                if self.is_free(t) and self.g[t[1]][t[0]] == 'g' and t != self.ptile():
                    self.objs[t] = ['tallgrass' if random.random() < 0.7 else 'weed', 1]
        for n, npc in NPCS.items():
            if self.friend[n] >= 800 and n not in self.perks:
                self.perks.add(n)
                rep.append(npc['perk'])
                if n == 'MARIGOLD':
                    for c, spec in CROPS.items():
                        if self.season in spec['seasons']:
                            self.add_item(c + ' SEEDS', 5)
                elif n == 'BRAM':
                    self.add_item('SPRINKLER', 2)
                else:
                    self.hay += 30
        if passed:
            self.stamina = STAMINA // 2
        elif self.minutes > 24 * 60:
            self.stamina = STAMINA * 3 // 4
        else:
            self.stamina = STAMINA
        self.talked, self.gifted = set(), set()
        self.minutes = DAY_START
        self.last_hour = 6
        self.rabbits = []
        self.px, self.py = 6 * TS + 8, 6 * TS + 12
        self.face = 'down'
        rent_left = DAYS - self.day + 1
        if rent_left <= 3:
            rep.append('THE %s LEASE OF %dG IS DUE IN %d DAY%s.' % (
                SEASONS[self.season], RENT[self.season], rent_left, 'S' if rent_left > 1 else ''))
        rep.append('FORECAST: ' + {'SUN': 'SUNNY', 'RAIN': 'RAIN', 'STORM': 'THUNDERSTORMS',
                                   'SNOW': 'SNOW'}[self.weather] + '.')
        self.report = rep
        self.new_season = new_season
        self.state = 'night'
        self.night_t = 0.0
        self.sfx.play('sleep')
        self.save()

    def finish(self, won, why):
        self.won = won
        self.why = why
        self.delete_save()
        if self.earned > self.best:
            self.best = self.earned
            self.save_int('best', self.best)
        self.state = 'won' if won else 'over'
        self.menu_sel = 0
        self.sfx.play('chime' if won else 'fail')

    # -------------------------------------------------------------- input
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
        st = self.state
        if ev.type == pygame.MOUSEWHEEL and st == 'play':
            self.sel = (self.sel - ev.y) % 12
            self.label_t = 2.0
            return
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        confirm = k in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE, pygame.K_k)
        up = k in (pygame.K_w, pygame.K_UP, pygame.K_a, pygame.K_LEFT)
        down = k in (pygame.K_s, pygame.K_DOWN, pygame.K_d, pygame.K_RIGHT)
        if st == 'title':
            opts = self.title_opts()
            if up or down:
                self.menu_sel = (self.menu_sel + (1 if down else -1)) % len(opts)
                self.sfx.play('click')
            elif confirm:
                o = opts[self.menu_sel]
                if o == 'CONTINUE':
                    if not self.load():
                        self.toast('THE SAVE COULD NOT BE READ.', 'no')
                elif o == 'NEW FARM':
                    self.new_game()
                    self.state = 'intro'
                else:
                    pygame.quit()
                    sys.exit()
            elif k == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
        elif st == 'intro':
            if confirm or k == pygame.K_ESCAPE:
                self.state = 'play'
                self.banner('SPRING 1')
                self.sfx.play('chime')
        elif st == 'night':
            if (confirm or k == pygame.K_ESCAPE) and self.night_t > 0.4:
                self.state = 'play'
                self.banner(SEASONS[self.season] + ' ' + str(self.day))
                self.sfx.play('chime')
        elif st in ('over', 'won'):
            if (confirm or k == pygame.K_ESCAPE):
                self.state = 'title'
                self.menu_sel = 0
        elif st == 'pause':
            opts = ['RESUME', 'QUIT TO TITLE', 'QUIT GAME']
            if up or down:
                self.menu_sel = (self.menu_sel + (1 if down else -1)) % 3
                self.sfx.play('click')
            elif k == pygame.K_ESCAPE:
                self.state = 'play'
            elif confirm:
                o = opts[self.menu_sel]
                if o == 'RESUME':
                    self.state = 'play'
                elif o == 'QUIT TO TITLE':
                    self.state = 'title'
                    self.menu_sel = 0
                else:
                    pygame.quit()
                    sys.exit()
        elif st == 'dialog':
            d = self.dlg
            if d['opts'] and (up or down):
                d['sel'] = (d['sel'] + (1 if down else -1)) % len(d['opts'])
                self.sfx.play('click')
            elif k == pygame.K_ESCAPE:
                self.state = 'play'
            elif confirm:
                fn = d['opts'][d['sel']][1] if d['opts'] else None
                self.state = 'play'
                self.dlg = None
                if fn:
                    fn()
        elif st == 'shop':
            s = self.shop
            if k in (pygame.K_w, pygame.K_UP):
                s['sel'] = (s['sel'] - 1) % len(s['rows'])
                self.sfx.play('click')
            elif k in (pygame.K_s, pygame.K_DOWN):
                s['sel'] = (s['sel'] + 1) % len(s['rows'])
                self.sfx.play('click')
            elif k == pygame.K_ESCAPE:
                self.state = 'play'
                self.shop = None
            elif confirm:
                times = 5 if ev.mod & pygame.KMOD_SHIFT and 'item' in s['rows'][s['sel']] else 1
                self.buy(s['rows'][s['sel']], times)
        elif st == 'place':
            p = self.place
            mv = {pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
                  pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0)}
            if k in mv:
                spec = BUILDS[p['kind']]
                p['x'] = max(2, min(FARM_X1 - spec['w'], p['x'] + mv[k][0]))
                p['y'] = max(2, min(MH - 2 - spec['h'], p['y'] + mv[k][1]))
            elif k == pygame.K_ESCAPE:
                self.place = None
                self.state = 'play'
                self.toast('BRAM PUTS THE PLANS AWAY. COME BACK ANY TIME.')
            elif k in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
                self.confirm_place()
        elif st == 'play':
            if k in (pygame.K_e, pygame.K_RETURN, pygame.K_k):
                self.interact()
            elif k == pygame.K_ESCAPE:
                self.state = 'pause'
                self.menu_sel = 0
            elif k == pygame.K_TAB:
                self.row = 1 - self.row
                self.label_t = 2.0
                self.sfx.play('click')
            elif k in (pygame.K_q, pygame.K_r):
                self.sel = (self.sel + (1 if k == pygame.K_r else -1)) % 12
                self.label_t = 2.0
            else:
                keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6,
                        pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0, pygame.K_MINUS, pygame.K_EQUALS]
                if k in keys:
                    self.sel = keys.index(k)
                    self.label_t = 2.0

    def title_opts(self):
        return (['CONTINUE'] if self.has_save() else []) + ['NEW FARM', 'QUIT']

    # -------------------------------------------------------------- update
    def update(self, dt):
        self.t += dt
        if self.state != 'play':
            self.tool_cd = max(getattr(self, 'tool_cd', 0), 0.3)
        self.toast_t = max(0.0, self.toast_t - dt)
        self.label_t = max(0.0, self.label_t - dt)
        if getattr(self, 'banner_t', 0) > 0:
            self.banner_t -= dt
        if self.state == 'night':
            self.night_t += dt
        if self.state != 'play':
            return
        self.minutes += dt * MIN_PER_SEC
        hour = int(self.minutes // 60)
        if hour != self.last_hour:
            self.last_hour = hour
            self.hourly()
        if self.minutes >= DAY_END:
            self.end_day(passed=True)
            return
        keys = pygame.key.get_pressed()
        mx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        my = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        if mx or my:
            if mx and not my:
                self.face = 'right' if mx > 0 else 'left'
            elif my and not mx:
                self.face = 'down' if my > 0 else 'up'
            elif self.face not in (('right' if mx > 0 else 'left'), ('down' if my > 0 else 'up')):
                self.face = 'down' if my > 0 else 'up'
            sp = (72 if self.stamina > 0 else 46) * dt
            if mx and my:
                sp *= 0.7071
            nx = self.px + mx * sp
            if not self.blocked(nx, self.py):
                self.px = nx
            ny = self.py + my * sp
            if not self.blocked(self.px, ny):
                self.py = ny
            self.walk_t += dt
            self.step_t -= dt
            if self.step_t <= 0:
                self.step_t = 0.3
                self.sfx.play('step')
        else:
            self.walk_t = 0
        self.tool_cd -= dt
        self.swing = max(0.0, self.swing - dt)
        if (keys[pygame.K_SPACE] or keys[pygame.K_j]) and self.tool_cd <= 0:
            self.use_held()
        for t in list(self.shake):
            self.shake[t] -= dt
            if self.shake[t] <= 0:
                del self.shake[t]
        for f in self.floats:
            f['t'] -= dt
            f['y'] -= 14 * dt
        self.floats = [f for f in self.floats if f['t'] > 0]
        self.update_animals(dt)
        self.update_rabbits(dt)
        if self.weather == 'STORM':
            self.flash = max(0.0, self.flash - dt)
            if random.random() < dt * 0.06:
                self.flash = 0.25
                self.sfx.play('thunder')

    def hourly(self):
        h = self.last_hour
        if 7 <= h <= 17 and self.season < 3 and not self.raining():
            out = [t for t in self.crops if not self.soil[t]['gh']]
            if len(out) >= 5 and random.random() < 0.3:
                self.spawn_rabbit(random.choice(out))
        if h == 22:
            self.toast('IT IS GETTING LATE. YOUR BED IS CALLING.')
        elif h == 24:
            self.toast('MIDNIGHT. YOU WILL BE TIRED TOMORROW.')

    def update_animals(self, dt):
        night = self.minutes >= 19 * 60
        for a in self.animals:
            if a['inside']:
                continue
            b = self.buildings[a['b']]
            spd = 22 if a['kind'] == 'CHICKEN' else 14
            if night:
                tx, ty = self.door_spot(b)
                ty -= 10
            else:
                if a['idle'] > 0:
                    a['idle'] -= dt
                    a['walk'] = 0
                    continue
                if a['tx'] is None:
                    spec = BUILDS[b['kind']]
                    for _ in range(8):
                        x = random.randint(max(2, b['x'] - 4), min(FARM_X1 - 1, b['x'] + spec['w'] + 3))
                        y = random.randint(max(2, b['y'] - 2), min(MH - 3, b['y'] + spec['h'] + 4))
                        if not self.solid(x, y):
                            a['tx'], a['ty'] = x * TS + 8, y * TS + 12
                            break
                    else:
                        a['idle'] = 1.0
                        continue
                tx, ty = a['tx'], a['ty']
            dx, dy = tx - a['x'], ty - a['y']
            d = math.hypot(dx, dy)
            if d < 2:
                if night:
                    a['inside'] = True
                else:
                    a['tx'] = None
                    a['idle'] = random.uniform(1.5, 5)
                continue
            nx, ny = a['x'] + dx / d * spd * dt, a['y'] + dy / d * spd * dt
            if not night and self.solid(int(nx // TS), int(ny // TS)):
                a['tx'] = None
                a['idle'] = 0.5
                continue
            a['x'], a['y'] = nx, ny
            a['flip'] = dx < 0
            a['walk'] += dt

    def spawn_rabbit(self, target):
        side = random.choice('nswe')
        if side in 'ns':
            x, y = random.randrange(3, FARM_X1 - 1), (2 if side == 'n' else MH - 3)
        else:
            x, y = (2 if side == 'w' else FARM_X1 - 1), random.randrange(3, MH - 3)
        self.rabbits.append(dict(x=x * TS + 8.0, y=y * TS + 10.0, t=target, state='go', timer=0.0, hop=0.0, flip=False))
        self.sfx.play('squeak')

    def scare_rabbits(self, x, y, r):
        for rb in self.rabbits:
            if rb['state'] != 'flee' and math.hypot(rb['x'] - x, rb['y'] - y) < r:
                rb['state'] = 'flee'
                rb['timer'] = 3.0
                self.sfx.play('squeak')
                self.floats.append(dict(x=rb['x'], y=rb['y'] - 10, text='!', icon=None, color=CREAM, t=0.8))

    def update_rabbits(self, dt):
        self.scare_rabbits(self.px, self.py, 30)
        for rb in self.rabbits:
            rb['hop'] += dt
            if rb['state'] == 'go':
                if rb['t'] not in self.crops:
                    rb['state'] = 'flee'
                    rb['timer'] = 3.0
                    continue
                tx, ty = rb['t'][0] * TS + 8, rb['t'][1] * TS + 12
                dx, dy = tx - rb['x'], ty - rb['y']
                d = math.hypot(dx, dy)
                if d < 2:
                    rb['state'] = 'eat'
                    rb['timer'] = 6.0
                else:
                    rb['x'] += dx / d * 26 * dt
                    rb['y'] += dy / d * 26 * dt
                    rb['flip'] = dx < 0
            elif rb['state'] == 'eat':
                rb['timer'] -= dt
                if rb['timer'] <= 0:
                    if rb['t'] in self.crops:
                        del self.crops[rb['t']]
                        self.toast('A RABBIT ATE ONE OF YOUR CROPS!', 'squeak')
                    rb['state'] = 'flee'
                    rb['timer'] = 3.0
            else:
                rb['timer'] -= dt
                dx, dy = rb['x'] - self.px, rb['y'] - self.py
                d = math.hypot(dx, dy) or 1
                rb['x'] += dx / d * 90 * dt
                rb['y'] += dy / d * 90 * dt
                rb['flip'] = dx < 0
        self.rabbits = [r for r in self.rabbits if r['state'] != 'flee' or r['timer'] > 0]

    # -------------------------------------------------------------- drawing: world
    def camera(self, fx, fy):
        cx = max(0, min(MW * TS - W, int(fx - W / 2)))
        cy = max(0, min(MH * TS - H, int(fy - H / 2)))
        return cx, cy

    def build_ground(self):
        g = pygame.Surface((MW * TS, MH * TS))
        tiles = {}
        for y in range(MH):
            for x in range(MW):
                k = self.g[y][x]
                v = (x * 7 + y * 13) % 4
                key = (k, v)
                if key not in tiles:
                    tiles[key] = ground_tile(k, self.season, v)
                g.blit(tiles[key], (x * TS, y * TS))
        self.ground = g
        self.ground_season = self.season

    def draw_world(self, cam):
        if self.ground_season != self.season:
            self.build_ground()
        scr = self.screen
        cx, cy = cam
        scr.blit(self.ground, (0, 0), (cx, cy, W, H))
        x0, x1 = max(0, cx // TS - 1), min(MW, (cx + W) // TS + 2)
        y0, y1 = max(0, cy // TS - 1), min(MH, (cy + H) // TS + 3)
        sea = self.season
        if sea < 3:
            for y in range(y0, y1):
                for x in range(x0, x1):
                    if self.g[y][x] == 'w' and (x * 3 + y * 5 + int(self.t * 2)) % 7 == 0:
                        sx = x * TS - cx + (int(self.t * 6) + x * 5) % 12
                        pygame.draw.line(scr, (170, 210, 240), (sx, y * TS - cy + 6), (sx + 3, y * TS - cy + 6))
        wet, dry = self.spr(('soil', 1, sea), soil_surf, True, sea == 3), self.spr(('soil', 0, sea), soil_surf, False, sea == 3)
        ghwet, ghdry = self.spr(('soil', 1, -1), soil_surf, True), self.spr(('soil', 0, -1), soil_surf, False)
        for (x, y), s in self.soil.items():
            if x0 <= x < x1 and y0 <= y < y1:
                if s['gh']:
                    scr.blit(ghwet if s['wet'] else ghdry, (x * TS - cx, y * TS - cy))
                else:
                    scr.blit(wet if s['wet'] else dry, (x * TS - cx, y * TS - cy))
        if self.state == 'play' or self.state == 'dialog':
            tx, ty = self.target()
            pulse = 150 + int(math.sin(self.t * 6) * 60)
            r = pygame.Rect(tx * TS - cx, ty * TS - cy, TS, TS)
            pygame.draw.rect(scr, (pulse, pulse, pulse), r, 1)
        dl = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                if self.g[y][x] == 't':
                    s = self.spr(('tree', sea, (x * 3 + y * 7) % 4), tree_surf, sea, (x * 3 + y * 7) % 4)
                    dl.append(((y + 1) * TS - 1, s, x * TS + 8 - s.get_width() // 2 - cx, (y + 1) * TS - s.get_height() + 2 - cy))
        for (x, y), o in self.objs.items():
            if x0 <= x < x1 and y0 <= y < y1:
                if o[0] == 'tree':
                    s = self.spr(('tree', sea, (x * 3 + y * 7) % 4), tree_surf, sea, (x * 3 + y * 7) % 4)
                else:
                    s = self.spr(('obj', o[0], sea), obj_surf, o[0], sea)
                off = int(math.sin(self.t * 60) * 1.5) if (x, y) in self.shake else 0
                dl.append(((y + 1) * TS - 2, s, x * TS + 8 - s.get_width() // 2 - cx + off,
                           (y + 1) * TS - s.get_height() + 1 - cy))
        for (x, y), c in self.crops.items():
            if x0 <= x < x1 and y0 <= y < y1:
                spec = CROPS[c['name']]
                if c['age'] >= spec['days']:
                    stage = 3
                elif c['age'] == 0:
                    stage = 0
                else:
                    stage = 1 if c['age'] / spec['days'] < 0.5 else 2
                s = self.spr(('crop', c['name'], stage), crop_surf, c['name'], stage)
                dl.append(((y + 1) * TS - 3, s, x * TS + 8 - s.get_width() // 2 - cx,
                           (y + 1) * TS - s.get_height() + 1 - cy))
        for b in self.buildings:
            spec = BUILDS[b['kind']]
            bx, by = b['x'] * TS - cx, b['y'] * TS - cy
            if bx > W or by > H + 20 or bx + spec['w'] * TS < 0 or by + spec['h'] * TS < -20:
                continue
            extra = b.get('extra')
            if b['kind'] == 'STALL':
                extra = NPCS[extra]['awning']
                n = b['extra']
                if self.npc_open(n):
                    face = 'down'
                    if abs(self.px - (b['x'] * TS + 32)) > 40:
                        face = 'right' if self.px > b['x'] * TS + 32 else 'left'
                    frame = 0
                    ps = self.spr(('person', n, face, frame), make_person, NPCS[n]['look'], face, frame)
                    bob = 1 if int(self.t * 1.5 + b['y']) % 2 else 0
                    dl.append(((b['y'] + 1) * TS + 5, ps, b['x'] * TS + 32 - ps.get_width() // 2 - cx,
                               (b['y'] + 1) * TS + 7 - ps.get_height() - cy + bob))
            key = ('bld', b['kind'], sea, str(extra))
            s = self.spr(key, bld_surf, b['kind'], sea, extra)
            dl.append(((b['y'] + spec['h']) * TS, s, bx, by - (s.get_height() - spec['h'] * TS)))
            if b['kind'] == 'STALL':
                label = {'SEEDS': 'SEEDS', 'BUILD': 'BUILD', 'RANCH': 'RANCH'}[NPCS[b['extra']]['trade']]
                ts = text_surf(label, 1, INK)
                cs = pygame.Surface((ts.get_width() + 4, 7), pygame.SRCALPHA)
                cs.fill(CREAM)
                cs.blit(ts, (2, 1))
                dl.append(((b['y'] + spec['h']) * TS + 1, cs, bx + 32 - cs.get_width() // 2, by - 10))
                if not self.npc_open(b['extra']):
                    cl = text_surf('CLOSED', 1, CREAM)
                    dl.append(((b['y'] + spec['h']) * TS + 1, cl, bx + 32 - cl.get_width() // 2, by + 20))
        for a in self.animals:
            if a['inside']:
                continue
            frame = int(a['walk'] * 6) % 2
            s = self.spr(('animal', a['kind'], frame), make_animal, a['kind'], frame)
            if a['flip']:
                s = self.spr(('animalf', a['kind'], frame), pygame.transform.flip, s, True, False)
            dl.append((a['y'], s, int(a['x'] - s.get_width() / 2 - cx), int(a['y'] - s.get_height() + 2 - cy)))
            if a['ready']:
                ic = self.icon(a['ready'])
                bob = int(math.sin(self.t * 4) * 2)
                dl.append((a['y'] + 0.5, ic, int(a['x'] - 7 - cx), int(a['y'] - s.get_height() - 14 - cy + bob)))
        for rb in self.rabbits:
            frame = 1 if rb['state'] != 'eat' and int(rb['hop'] * 8) % 2 else 0
            s = self.spr(('animal', 'RABBIT', frame), make_animal, 'RABBIT', frame)
            if rb['flip']:
                s = self.spr(('animalf', 'RABBIT', frame), pygame.transform.flip, s, True, False)
            dl.append((rb['y'], s, int(rb['x'] - s.get_width() / 2 - cx), int(rb['y'] - s.get_height() + 2 - cy)))
        if self.state != 'place':
            frame = 0 if not self.walk_t else 1 + int(self.walk_t * 7) % 2
            ps = self.spr(('person', 'P', self.face, frame), make_person, LOOK_PLAYER, self.face, frame)
            px, py = int(self.px - ps.get_width() / 2 - cx), int(self.py - ps.get_height() + 2 - cy)
            dl.append((self.py, ps, px, py))
            if self.swing > 0 and self.held:
                ic = self.icon(self.held)
                dx, dy = DIRV[self.face]
                k = self.swing / 0.22
                ox = int(self.px - cx - 7 + dx * (8 + 4 * k))
                oy = int(self.py - cy - 16 + dy * 8 - 6 * k)
                dl.append((self.py + (1 if dy >= 0 else -1), ic, ox, oy))
        dl.sort(key=lambda e: e[0])
        for _, s, x, y in dl:
            scr.blit(s, (x, y))
        for f in self.floats:
            fx, fy = int(f['x'] - cx), int(f['y'] - cy)
            if f['icon'] == 'HEART':
                scr.blit(self.spr(('heart', 1), heart_surf, True), (fx - 3, fy))
            elif f['icon']:
                ic = self.icon(f['icon'])
                scr.blit(ic, (fx - 7, fy - 8))
            if f['text']:
                draw_text(scr, f['text'], fx, fy - 6, 1, 'c', f['color'])
        if self.place:
            self.draw_place(cam)
        self.draw_sky()

    def draw_place(self, cam):
        p = self.place
        spec = BUILDS[p['kind']]
        ok = self.place_ok()
        s = self.spr(('bld', p['kind'], self.season, 'None'), bld_surf, p['kind'], self.season, None).copy()
        s.set_alpha(170)
        bx, by = p['x'] * TS - cam[0], p['y'] * TS - cam[1]
        self.screen.blit(s, (bx, by - (s.get_height() - spec['h'] * TS)))
        ov = pygame.Surface((spec['w'] * TS, spec['h'] * TS), pygame.SRCALPHA)
        ov.fill((120, 230, 120, 70) if ok else (240, 90, 80, 90))
        self.screen.blit(ov, (bx, by))
        pygame.draw.rect(self.screen, GREEN if ok else RED, (bx, by, spec['w'] * TS, spec['h'] * TS), 1)

    def draw_sky(self):
        m = self.minutes
        a = 0
        if m < 7 * 60:
            a = int(70 * (7 * 60 - m) / 60)
        elif m > 18 * 60:
            a = int(min(170, (m - 18 * 60) / 180 * 170))
        if self.weather in ('RAIN', 'STORM'):
            a = max(a, 50)
        if a:
            self.night_overlay.fill((24, 22, 70, a) if m > 12 * 60 or m < 7 * 60 else (40, 40, 60, a))
            self.screen.blit(self.night_overlay, (0, 0))
        if self.weather in ('RAIN', 'STORM', 'SNOW') and self.state in ('play', 'dialog', 'shop', 'pause'):
            snow = self.weather == 'SNOW'
            dt = 1 / 60
            for d in self.drops:
                if self.state == 'play':
                    if snow:
                        d[0] += math.sin(self.t + d[1] * 0.05) * 0.4
                        d[1] += 30 * dt
                    else:
                        d[0] -= 60 * dt
                        d[1] += 260 * dt
                    if d[1] > H:
                        d[1] -= H + 10
                        d[0] = random.uniform(0, W + 40)
                    if d[0] < -10:
                        d[0] += W + 20
                if snow:
                    self.screen.set_at((int(d[0]), int(d[1])), (250, 250, 255))
                else:
                    pygame.draw.line(self.screen, (150, 180, 230), (d[0], d[1]), (d[0] - 2, d[1] + 6))
        if self.flash > 0:
            fl = pygame.Surface((W, H), pygame.SRCALPHA)
            fl.fill((255, 255, 255, int(self.flash * 600)))
            self.screen.blit(fl, (0, 0))

    # -------------------------------------------------------------- drawing: hud
    def panel(self, x, y, w, h, alpha=210):
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, (60, 44, 52, alpha), (0, 0, w, h), border_radius=3)
        pygame.draw.rect(s, (236, 214, 176, 255), (0, 0, w, h), 1, border_radius=3)
        self.screen.blit(s, (x, y))

    def draw_hud(self):
        scr = self.screen
        m = int(self.minutes)
        hh, mm = (m // 60) % 24, m % 60 // 10 * 10
        self.panel(3, 3, 86, 34)
        draw_text(scr, '%s %d' % (SEASONS[self.season], self.day), 7, 7)
        draw_text(scr, '%02d:%02d' % (hh, mm), 7, 15, color=GOLD if m >= 22 * 60 else CREAM)
        scr.blit(self.spr(('wi', self.weather), weather_icon, self.weather), (72, 5))
        rect(scr, INK, 7, 25, 78, 6)
        frac = self.stamina / STAMINA
        col = GREEN if frac > 0.4 else GOLD if frac > 0.15 else RED
        rect(scr, col, 8, 26, int(76 * frac), 4)
        days_left = DAYS - self.day + 1
        rent = RENT[self.season]
        warn = days_left <= 3 and self.gold < rent
        draw_text(scr, 'LEASE %dG IN %d DAY%s' % (rent, days_left, 'S' if days_left > 1 else ''), 4, 41,
                  color=RED if warn else CREAM)
        self.panel(W - 78, 3, 75, 34)
        draw_text(scr, '%dG' % self.gold, W - 7, 7, 1, 'r', GOLD)
        x = W - 74
        for res in ('wood', 'stone', 'hay'):
            scr.blit(self.spr(('res', res), res_icon, res), (x, 15))
            draw_text(scr, str(getattr(self, res)), x + 10, 17)
            x += 24
        draw_text(scr, 'TOMORROW', W - 74, 28)
        scr.blit(self.spr(('wi', self.forecast), weather_icon, self.forecast), (W - 40, 26))
        # hotbar
        hx, hy = (W - 12 * 18) // 2, H - 21
        self.panel(hx - 3, hy - 3, 12 * 18 + 4, 22)
        for i in range(12):
            sx = hx + i * 18
            slot = self.inv[self.row * 12 + i]
            sel = i == self.sel
            rect(scr, (250, 230, 170) if sel else (96, 76, 84), sx, hy, 16, 16)
            rect(scr, (130, 100, 90) if sel else (74, 58, 66), sx + 1, hy + 1, 14, 14)
            if slot:
                scr.blit(self.icon(slot[0]), (sx + 1, hy + 1))
                if slot[1] > 1:
                    draw_text(scr, str(slot[1]), sx + 16, hy + 11, 1, 'r')
                if slot[0] == 'CAN':
                    cap = CAN_CAP[self.can_lvl - 1]
                    rect(scr, INK, sx + 1, hy - 3, 14, 2)
                    rect(scr, (110, 180, 240), sx + 1, hy - 3, int(14 * self.water / cap), 2)
        draw_text(scr, str(self.row + 1), hx - 8, hy + 5, color=(180, 160, 150))
        held = self.held
        if held and self.label_t > 0:
            draw_text(scr, self.item_label(held), W // 2, hy - 11, 1, 'c')
        elif self.state == 'play':
            info = self.interact_info()
            if info:
                draw_text(scr, 'E ' + info[0], W // 2, hy - 11, 1, 'c', GOLD)
        if self.toast_t > 0:
            lines = wrap(self.toast_msg, 70)
            for i, ln in enumerate(lines):
                draw_text(scr, ln, W // 2, 50 + i * 8, 1, 'c')
        if getattr(self, 'banner_t', 0) > 0:
            draw_text(scr, self.banner_msg, W // 2, 64, 3, 'c', GOLD)

    def draw_dialog(self):
        d = self.dlg
        scr = self.screen
        y = H - 74
        self.panel(10, y, W - 20, 50, 235)
        name = d['name']
        draw_text(scr, name, 18, y + 6, 1, 'l', GOLD)
        if d['hearts'] is not None:
            for i in range(10):
                scr.blit(self.spr(('heart', i < d['hearts']), heart_surf, i < d['hearts']), (24 + len(name) * 4 + i * 7, y + 5))
        ly = y + 16
        for line in d['lines']:
            for ln in wrap(line, 88):
                draw_text(scr, ln, 18, ly)
                ly += 8
        if d['opts']:
            x = 18
            for i, (label, _) in enumerate(d['opts']):
                sel = i == d['sel']
                draw_text(scr, ('> ' if sel else '  ') + label, x, y + 40, 1, 'l', GOLD if sel else CREAM)
                x += len(label) * 4 + 20
        else:
            draw_text(scr, 'E', W - 18, y + 40, 1, 'r', GOLD)

    def draw_shop(self):
        s = self.shop
        scr = self.screen
        n = s['npc']
        self.panel(30, 16, W - 60, H - 42, 240)
        draw_text(scr, "%s'S STALL" % n, W // 2, 22, 1, 'c', GOLD)
        if self.hearts(n) >= 5:
            draw_text(scr, 'FRIEND PRICE: 10% OFF', W - 38, 22, 1, 'r', GREEN)
        draw_text(scr, '%dG  %d WOOD  %d STONE' % (self.gold, self.wood, self.stone), 38, 22, 1, 'l')
        rows = s['rows']
        vis = 13
        if s['sel'] < s['scroll']:
            s['scroll'] = s['sel']
        elif s['sel'] >= s['scroll'] + vis:
            s['scroll'] = s['sel'] - vis + 1
        for i in range(s['scroll'], min(len(rows), s['scroll'] + vis)):
            r = rows[i]
            y = 34 + (i - s['scroll']) * 9
            sel = i == s['sel']
            afford = self.gold >= r['gold'] and self.wood >= r.get('wood', 0) and self.stone >= r.get('stone', 0)
            col = GOLD if sel else (CREAM if afford else (150, 130, 130))
            if sel:
                rect(scr, (96, 70, 80), 36, y - 2, W - 72, 9)
            if 'item' in r:
                scr.blit(self.icon(r['item']), (38, y - 4))
            draw_text(scr, r['label'], 54, y, 1, 'l', col)
            cost = '%dG' % r['gold']
            if r.get('wood'):
                cost += ' %dW' % r['wood']
            if r.get('stone'):
                cost += ' %dS' % r['stone']
            draw_text(scr, cost, W - 40, y, 1, 'r', col)
        r = rows[s['sel']]
        desc = r['desc']
        if r.get('wood') or r.get('stone'):
            desc += ' NEEDS %d WOOD, %d STONE.' % (r.get('wood', 0), r.get('stone', 0))
        if 'item' in r:
            desc += ' YOU HAVE %d.' % self.count_item(r['item'])
        for i, ln in enumerate(wrap(desc, 80)):
            draw_text(scr, ln, 38, H - 50 + i * 7, 1, 'l', (220, 210, 190))
        draw_text(scr, 'W/S CHOOSE   E BUY   SHIFT+E BUY 5   ESC LEAVE', W // 2, H - 34, 1, 'c', (180, 160, 150))

    def draw_center_menu(self, opts, y):
        for i, o in enumerate(opts):
            sel = i == self.menu_sel
            draw_text(self.screen, ('> %s <' if sel else '%s') % o, W // 2, y + i * 12, 1, 'c',
                      GOLD if sel else CREAM)

    def draw_title(self):
        scr = self.screen
        for y in range(H):
            k = y / H
            scr.fill((int(150 + 90 * k), int(200 + 30 * k), int(240 - 20 * k)), (0, y, W, 1))
        pygame.draw.circle(scr, (255, 236, 150), (320, 50), 20)
        pygame.draw.circle(scr, (255, 246, 200), (320, 50), 15)
        for i, (col, base, amp, fr) in enumerate((((150, 204, 110), 140, 14, 0.012), ((112, 180, 84), 160, 10, 0.02),
                                                  ((90, 160, 70), 180, 8, 0.03))):
            pts = [(x, base + math.sin(x * fr + i * 2) * amp) for x in range(0, W + 8, 8)]
            pygame.draw.polygon(scr, col, pts + [(W, H), (0, H)])
        r = random.Random(4)
        for _ in range(26):
            x, y = r.randrange(W), r.randrange(186, H)
            h = r.randrange(14, 30)
            sway = math.sin(self.t * 1.5 + x) * 1.5
            pygame.draw.line(scr, (70, 140, 60), (x, y), (x + sway, y - h))
            c = r.choice(((240, 120, 170), (250, 180, 200), (250, 240, 250), (200, 110, 200)))
            for j in range(3):
                pygame.draw.circle(scr, c, (int(x + sway), y - h + j * 5), 2)
        draw_text(scr, 'HOLLYHOCK', W // 2, 46, 5, 'c', (252, 236, 210))
        draw_text(scr, 'A TINY FARM IN FOUR SEASONS', W // 2, 80, 1, 'c')
        self.draw_center_menu(self.title_opts(), 112)
        if self.best:
            draw_text(scr, 'BEST HARVEST: %dG' % self.best, W // 2, 152, 1, 'c', GOLD)
        draw_text(scr, 'W/S CHOOSE   E START   F11 FULLSCREEN', W // 2, H - 10, 1, 'c')
        if self.toast_t > 0:
            draw_text(scr, self.toast_msg, W // 2, 100, 1, 'c', RED)

    def draw_text_screen(self, title, lines, foot, col=GOLD):
        scr = self.screen
        scr.fill((26, 24, 52))
        r = random.Random(9)
        for _ in range(70):
            x, y = r.randrange(W), r.randrange(H)
            if (int(self.t * 2) + x) % 9:
                scr.set_at((x, y), (230, 230, 250))
        pygame.draw.circle(scr, (240, 236, 210), (340, 36), 12)
        pygame.draw.circle(scr, (26, 24, 52), (346, 32), 11)
        draw_text(scr, title, W // 2, 30, 2, 'c', col)
        y = 56
        for line in lines:
            for ln in wrap(line, 80):
                draw_text(scr, ln, W // 2, y, 1, 'c')
                y += 8
            y += 4
        draw_text(scr, foot, W // 2, H - 16, 1, 'c', (180, 170, 200))

    def draw(self):
        scr = self.screen
        st = self.state
        if st == 'title':
            self.draw_title()
        elif st == 'intro':
            self.draw_text_screen('HOLLYHOCK FARM', [
                'YOUR AUNT LEFT YOU HER FARM: OVERGROWN, QUIET, AND YOURS IF YOU CAN KEEP IT.',
                'THE TOWNSHIP LEASE FALLS DUE AT THE END OF EVERY SEASON: %s.' % ', '.join(
                    '%dG' % r for r in RENT),
                'TILL WITH THE HOE, PLANT, AND WATER EVERY DAY. SHIP YOUR HARVEST IN THE BIN BY THE HOUSE. '
                'MARIGOLD, BRAM AND HAZEL KEEP STALLS IN THE VILLAGE TO THE EAST.',
                'WASD WALK. HOLD SPACE TO USE A TOOL. E TO TALK, HARVEST, SHIP, PET AND SLEEP. '
                '1-0 OR Q/R PICK A SLOT, TAB SWAPS BAG ROWS.'], 'PRESS E TO BEGIN', (250, 190, 210))
        elif st == 'night':
            self.draw_text_screen('GOOD MORNING' if not self.new_season else SEASONS[self.season] + ' HAS COME',
                                  ['%s, DAY %d OF %d.' % (SEASONS[self.season], self.day, DAYS)] + self.report,
                                  'PRESS E TO WAKE UP')
        elif st == 'over':
            self.draw_text_screen('THE LEASE LAPSED', [
                self.why, 'THE FARM PASSES BACK TO THE TOWNSHIP. MARIGOLD SAYS YOU CAN ALWAYS TRY AGAIN.',
                'YOU EARNED %dG IN ALL.' % self.earned], 'PRESS E', RED)
        elif st == 'won':
            self.draw_text_screen('THE FARM IS YOURS', [
                'FOUR SEASONS, FOUR LEASES PAID. HOLLYHOCK FARM BELONGS TO YOU NOW.',
                'YOU EARNED %dG IN ALL, AND KEPT %d ANIMALS.' % (self.earned, len(self.animals)),
                'FRIENDS: ' + ', '.join('%s %d HEARTS' % (n, self.hearts(n)) for n in NPCS) + '.'],
                'PRESS E')
        else:
            if self.place:
                cam = self.camera(self.place['x'] * TS + BUILDS[self.place['kind']]['w'] * 8,
                                  self.place['y'] * TS + BUILDS[self.place['kind']]['h'] * 8)
            else:
                cam = self.camera(self.px, self.py - 8)
            self.draw_world(cam)
            if st == 'place':
                self.panel(W // 2 - 120, 4, 240, 20)
                draw_text(scr, 'PLACE YOUR %s' % self.place['kind'], W // 2, 8, 1, 'c', GOLD)
                draw_text(scr, 'WASD MOVE   E BUILD   ESC CANCEL', W // 2, 16, 1, 'c')
                if self.toast_t > 0:
                    draw_text(scr, self.toast_msg, W // 2, 30, 1, 'c')
            else:
                self.draw_hud()
            if st == 'dialog':
                self.draw_dialog()
            elif st == 'shop':
                self.draw_shop()
            elif st == 'pause':
                self.panel(W // 2 - 70, 60, 140, 66, 240)
                draw_text(scr, 'PAUSED', W // 2, 66, 2, 'c', GOLD)
                self.draw_center_menu(['RESUME', 'QUIT TO TITLE', 'QUIT GAME'], 84)
                draw_text(scr, 'THE GAME SAVES EACH NIGHT', W // 2, 118, 1, 'c', (180, 160, 150))
        pygame.display.flip()

    def run(self):
        while True:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)
            for ev in pygame.event.get():
                self.handle(ev)
            self.update(dt)
            self.draw()


if __name__ == '__main__':
    Game().run()
