#!/usr/bin/env python3
"""RELIQUARY - a tiny dark-fantasy roguelike deck builder.

Climb three acts of a ruined cathedral, fight with a deck of cards, gather relics.
Mouse: click or drag a card onto a foe (or above the hand), right click cancels.
Keys: A/D (or 1-9/0) pick a card and E chooses it; with several foes, A/D then pick the
target and E plays. SPACE ends the turn, Q/W view the draw/discard pile, Z/X/C drink a potion,
V views the deck outside combat.
ESC pauses or cancels, F11 toggles fullscreen.
"""
import array
import math
import os
import random
import re
import sys

import pygame

W, H = 400, 225
BLACK = (8, 6, 7)
BONE = (222, 210, 186)
BLOOD = (176, 22, 30)
KEY = (255, 0, 255)
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
TAU = math.tau
CW, CH = 56, 80                 # card size
HAND_Y, HAND_UP = 150, 138      # resting and raised card tops
FIELD_Y = 134                   # above this a dragged card is played
ACT_NAMES = ['THE CATACOMBS', 'THE DROWNED NAVE', 'THE PALE THRONE']
FLOORS = 11                     # map floors per act, then the boss

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


# ------------------------------------------------------------------ sound
class Sfx:
    SPECS = {  # dur, f0, f1, noise, vol, wave
        'card': (0.06, 700, 400, 0.6, 0.06, 'sq'),
        'hit': (0.12, 400, 90, 0.75, 0.18, 'sq'),
        'block': (0.12, 900, 700, 0.3, 0.08, 'sq'),
        'blocked': (0.1, 1300, 900, 0.5, 0.1, 'sq'),
        'buff': (0.3, 300, 800, 0.0, 0.12, 'sin'),
        'debuff': (0.3, 600, 150, 0.2, 0.12, 'sin'),
        'poison': (0.2, 200, 120, 0.5, 0.1, 'sin'),
        'kill': (0.35, 260, 40, 0.6, 0.22, 'sq'),
        'hurt': (0.3, 300, 60, 0.45, 0.3, 'sq'),
        'draw': (0.04, 1200, 1500, 0.5, 0.04, 'sq'),
        'coin': (0.15, 1300, 1800, 0.0, 0.1, 'sin'),
        'heal': (0.4, 300, 700, 0.0, 0.13, 'sin'),
        'click': (0.04, 900, 800, 0.2, 0.06, 'sq'),
        'no': (0.06, 160, 140, 0.0, 0.1, 'sq'),
        'turn': (0.5, 220, 330, 0.0, 0.12, 'sin'),
        'relic': (0.6, 400, 1200, 0.0, 0.14, 'sin'),
        'toll': (1.4, 110, 108, 0.0, 0.3, 'sin'),
        'step': (0.08, 200, 150, 0.6, 0.06, 'sq'),
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


# ------------------------------------------------------------------ pixel art
# '#' bone, '+' bone dither, 'r' blood, 'k' solid black, '.' empty; outlines are added.
ART = {
    'PLAYER': """
.....####.......
....######......
...##kkkk#......
...#kkkkr#......
...#kkkkk#......
...##kkk##......
..####kk###.....
.######+####..#.
.##+#######.##..
.##+######.##...
.##+#####+#+....
.##+########....
..#+######......
..##++####......
...########.....
...##+##+##.....
...#########....
..##########....
..###########...
.############...""",
    'HOOD': """
......####......
.....######.....
....##kkkk##....
....#kkkkkk#....
....#krkkrk#....
....#kkkkkk#....
...##kkkkkk##...
..####kkkk####..
..############..
.##+########+##.
.##+########+##.
.##.########.##.
.##.##++++##.##.
.k#.########.#k.
....########....
....##+##+##....
....########....
...##########...
...##########...
..############..""",
    'SKEL': """
.....######.....
....########....
....#kk##kk#....
....#rk##rk#....
....###kk###....
.....#k#k#k.....
......####......
....#..##..#....
...##.####.##...
...#.#.##.#.#...
...#..####..#...
..#..#.##.#..#..
..#...####...#..
.......##.......
......#..#......
.....##..##.....
.....#....#.....
.....#....#.....
....##....##....
....##....##....""",
    'GHOUL': """
................
.....####.......
....######......
...##rk#rk#.....
...#########....
....#kkkk##.....
.....####.###...
...########.##..
..##.######..#..
.##..#####..##..
.#...######.#...
##...######.....
#....#.##.#.....
r...##.##.##....
....#..#...#....
...##..#...##...
...#..##....#...
..##..#.....##..
..r..##......r..
.....r..........""",
    'RAT': """
...........##..
..........####.
....#######rk##
..#############
.##########.##.
##.##++##......
#..#..#..#.....
#..............""",
    'BLOB': """
......########......
....############....
...##############...
..######rr##rr####..
..######rr##rr####..
.##################.
.######kkkkkk######.
.#####kk#k#kkk#####.
.######kkkkkk######.
.##################.
.###+###+###+###+##.
##+###+###+###+###+#
####################
.##################.
..##.##..##..##.##..
..r...r...r...r..r..""",
    'KNIGHT': """
......######......
.....########.....
.....#kkkkkk#.....
.....#rk##kr#.....
.....########.....
......#k#k#k......
...############...
..##############..
..###+######+###..
..##.########.##..
..##.###rr###.##..
..##.########.##..
.###.########.###.
.#k#.###++###.#k#.
.....########.....
.....###..###.....
.....###..###.....
.....##....##.....
.....##....##.....
....###....###....
....###....###....""",
    'WRAITH': """
.....######.....
....########....
...##kkkkkk##...
...#kkrkkrkk#...
...#kkkkkkkk#...
...##kkkkkk##...
..####kkkk####..
.##############.
##.##########.##
#..##########..#
...###+##+###...
...##########...
....#+####+#....
....########....
.....#+##+#.....
.....######.....
......#..#......
......#..#......
.......##.......
.......#........""",
    'GARG': """
#....................#
##.......####.......##
.##.....######.....##.
.###...#r####r#...###.
..###..########..###..
..####..#kkkk#..####..
...#####.####.#####...
...################...
....##############....
.....############.....
......##########......
......##.####.##......
.....###.####.###.....
.....##..#..#..##.....
....###.........###...
....r#...........#r...""",
    'HOUND': """
...............##...
..............####..
.............##rk##.
............######kk
..#.........#####...
.###########.####...
.###+###+####.##....
..############......
..############......
...##+###+###.......
...##.......##......
...#.#.....#.#......
..##.#.....#.##.....
..r..r.....r..r.....""",
    'BISHOP': """
.......##.......
......####......
.....##rr##.....
.....######.....
....##rrrr##....
....########....
....##kkkk##....
....#kkkkkk#....
....#krkkrk#....
....#kkkkkk#....
...##kkkkkk##...
..####kkkk####..
..######r#####..
.##+###rrr##+##.
.##+####r###+##.
.##.########.##.
.##.##++++##.##.
.k#.########.#k.
....########....
....##+##+##....
...##########...
..############..""",
    'CHOIR': """
.......######.......
......########......
.....##kkkkkk##.....
.....#kkrkkrkk#.....
.###.#kkkkkkkk#.###.
#####.##kkkk##.#####
#kkk#.########.#kkk#
#rkr#.##kkkk##.#rkr#
#kkk#.#kk##kk#.#kkk#
.###..########..###.
.###.##########.###.
####.##########.####
####.###+##+###.####
.##..##########..##.
.##...#+####+#...##.
.#....########....#.
......#+#++#+#......
.......######.......
........#..#........
........#..#........""",
    'KING': """
..#..#..##..#..#..
..##.##.##.##.##..
..##############..
..#r####rr####r#..
....##########....
....#kk####kk#....
....#rk####rk#....
....#####kk###....
.....##k#k#k#.....
......######......
...############...
..#.##########.#..
.##.####rr####.##.
.#..##########..#.
.#..###+##+###..#.
.k..##########..k.
....##########....
....###+##+###....
...############...
..##############..
..##############..
.################.""",
}


def build_sprite(name, scale):
    rows = [r for r in ART[name].strip('\n').split('\n')]
    w = max(len(r) for r in rows)
    h = len(rows)
    s = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    filled = {(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch != '.'}
    for x, y in filled:
        for dx, dy in DIRS:
            s.set_at((x + 1 + dx, y + 1 + dy), BLACK)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == '.':
                continue
            col = {'#': BONE, 'r': BLOOD, 'k': BLACK}.get(ch)
            if ch == '+':
                col = BONE if (x + y) % 2 else BLACK
            s.set_at((x + 1, y + 1), col)
    s = pygame.transform.scale(s, ((w + 2) * scale, (h + 2) * scale))
    flash = pygame.mask.from_surface(s).to_surface(setcolor=BONE, unsetcolor=(0, 0, 0, 0))
    return s, flash, pygame.transform.flip(s, True, False)


ICONS = {
    'fight': '#.....#.#...#...#.#.....#.....#.#..##...###.....#',
    'elite': '#.....###...##.#####..#r#r#..#####...#.#....###..',
    'rest': '...#.....##.....###...##r#...#rrr#..#rrr#...###..',
    'shop': '..###.....#....#####.##.#.###.###.###.#.##.#####.',
    'event': '.####..##..##.....##....##....##...........##....',
    'chest': '........#####.#.....#########..r..##.....########',
    'atk': '......#.....#.....#..#..#....##.....##....#..#...',
    'blk': '########.....##.###.##.###.#.#.#.#...#.#.....#...',
    'buf': '...#.....###...#####....#.....r#r.....#......#...',
    'deb': '...r......r.....rrr...rrrrr..rrrrr...rrr.........',
    'unk': '.####..##..##.....##....##....##...........##....',
    'sum': '...#.....#.....#...#######...#.....#.....#.......',
}


def icon_surf(name, scale=1, color=BONE):
    bits = ICONS[name]
    s = pygame.Surface((9, 9), pygame.SRCALPHA)
    pts = []
    for i, ch in enumerate(bits[:49]):
        if ch in '#r':
            pts.append((i % 7 + 1, i // 7 + 1, BLOOD if ch == 'r' else color))
    for x, y, _ in pts:
        for dx, dy in DIRS:
            s.set_at((x + dx, y + dy), BLACK)
    for x, y, c in pts:
        s.set_at((x, y), c)
    if scale > 1:
        s = pygame.transform.scale(s, (9 * scale, 9 * scale))
    return s


def dither_surface(w, h, dense=False):
    s = pygame.Surface((w, h))
    s.fill(KEY)
    s.set_colorkey(KEY)
    for y in range(h):
        for x in range(w):
            if (x + y) % 2 == 0 or (dense and y % 2 == 0):
                s.set_at((x, y), BLACK)
    return s


# ------------------------------------------------------------------ cards
def C(cost, typ, rar, tgt, text, v=(), vu=None, fx=None, **kw):
    d = dict(cost=cost, type=typ, rar=rar, tgt=tgt, text=text, v=tuple(v),
             vu=tuple(vu) if vu is not None else tuple(v), fx=fx or (lambda g, c, t: None))
    d.update(kw)
    return d


def _heavy(g, c):
    return g.p.st.get('str', 0) * (c.v[1] - 1)


def _devour(g, c, t):
    g.hit(t, c.v[0])
    if t.hp <= 0:
        g.p.maxhp += c.v[1]
        g.heal(c.v[1])
        g.float(g.p, f'+{c.v[1]} MAX HP', BONE)


def _reap(g, c, t):
    g.heal(g.hit_all(c.v[0]))


def _purge(g, c, t):
    for o in [o for o in g.hand if o.type != 'atk']:
        g.hand.remove(o)
        g.exhaust(o)
        g.gain_block(c.v[0])


def _sacrifice(g, c, t):
    if g.hand:
        o = random.choice(g.hand)
        g.hand.remove(o)
        g.exhaust(o)
    g.draw_cards(c.v[0])


def _catalyst(g, c, t):
    if t.st.get('poison'):
        t.st['poison'] *= c.v[0]
        g.float(t, f'POISON {t.st["poison"]}', BLOOD)
        g.sfx.play('poison')


def _limit(g, c, t):
    if g.p.st.get('str', 0) > 0:
        g.buff('str', g.p.st['str'])


def _bane(g, c, t):
    g.hit(t, c.v[0])
    if t.st.get('poison') and t.hp > 0:
        g.hit(t, c.v[0])


CARDS = {
    # basic
    'STRIKE': C(1, 'atk', 'basic', 'one', 'DEAL {D0} DAMAGE.', (6,), (9,),
                lambda g, c, t: g.hit(t, c.v[0])),
    'WARD': C(1, 'skl', 'basic', 'none', 'GAIN {B0} BLOCK.', (5,), (8,),
              lambda g, c, t: g.gain_block(c.v[0])),
    'REND': C(2, 'atk', 'basic', 'one', 'DEAL {D0} DAMAGE. APPLY {1} VULNERABLE.', (8, 2), (10, 3),
              lambda g, c, t: (g.hit(t, c.v[0]), g.apply(t, 'vuln', c.v[1]))),
    # common attacks
    'CLEAVE': C(1, 'atk', 'common', 'all', 'DEAL {D0} DAMAGE TO ALL ENEMIES.', (8,), (11,),
                lambda g, c, t: g.hit_all(c.v[0])),
    'TWIN CUT': C(1, 'atk', 'common', 'one', 'DEAL {D0} DAMAGE TWICE.', (5,), (7,),
                  lambda g, c, t: g.hits(t, c.v[0], 2)),
    'HEW': C(2, 'atk', 'common', 'one', 'DEAL {D0} DAMAGE.', (15,), (20,),
             lambda g, c, t: g.hit(t, c.v[0])),
    'SHIELD BASH': C(1, 'atk', 'common', 'one', 'DEAL DAMAGE EQUAL TO YOUR BLOCK.', cu=0,
                     fx=lambda g, c, t: g.hit(t, g.p.block)),
    'IRON EDGE': C(1, 'atk', 'common', 'one', 'GAIN {B1} BLOCK. DEAL {D0} DAMAGE.', (5, 5), (7, 7),
                   lambda g, c, t: (g.gain_block(c.v[1]), g.hit(t, c.v[0]))),
    'POMMEL': C(1, 'atk', 'common', 'one', 'DEAL {D0} DAMAGE. DRAW {1} CARD(S).', (9, 1), (10, 2),
                lambda g, c, t: (g.hit(t, c.v[0]), g.draw_cards(c.v[1]))),
    'SOUR BLADE': C(1, 'atk', 'common', 'one', 'DEAL {D0} DAMAGE. APPLY {1} POISON.', (6, 3), (8, 4),
                    lambda g, c, t: (g.hit(t, c.v[0]), g.apply(t, 'poison', c.v[1]))),
    'HAMSTRING': C(1, 'atk', 'common', 'one', 'DEAL {D0} DAMAGE. APPLY {1} WEAK.', (8, 2), (10, 3),
                   lambda g, c, t: (g.hit(t, c.v[0]), g.apply(t, 'weak', c.v[1]))),
    'BLOOD PRICE': C(1, 'atk', 'common', 'one', 'LOSE 2 HP. DEAL {D0} DAMAGE.', (12,), (16,),
                     lambda g, c, t: (g.lose_hp(2), g.hit(t, c.v[0]))),
    'FLURRY': C(1, 'atk', 'common', 'rnd', 'DEAL {D0} DAMAGE TO A RANDOM ENEMY {1} TIMES.', (3, 3), (3, 4),
                lambda g, c, t: [g.hit(g.rnd_enemy(), c.v[0]) for _ in range(c.v[1])]),
    # common skills
    'BRACE': C(1, 'skl', 'common', 'none', 'GAIN {B0} BLOCK. DRAW 1 CARD.', (7,), (10,),
               lambda g, c, t: (g.gain_block(c.v[0]), g.draw_cards(1))),
    'SIDESTEP': C(1, 'skl', 'common', 'none', 'GAIN {B0} BLOCK. NEXT TURN, GAIN {1} BLOCK.', (5, 5), (7, 7),
                  lambda g, c, t: (g.gain_block(c.v[0]), g.buff('nextblk', c.v[1], quiet=True))),
    'CENSER': C(1, 'skl', 'common', 'none', 'APPLY {0} POISON TO ALL ENEMIES.', (3,), (5,),
                lambda g, c, t: g.apply_all('poison', c.v[0])),
    'DREAD': C(0, 'skl', 'common', 'none', 'APPLY {0} WEAK TO ALL ENEMIES. EXHAUST.', (1,), (2,),
               lambda g, c, t: g.apply_all('weak', c.v[0]), ex=True),
    'FLAGELLATE': C(0, 'skl', 'common', 'none', 'LOSE 3 HP. GAIN {0} ENERGY.', (2,), (3,),
                    lambda g, c, t: (g.lose_hp(3), g.gain_energy(c.v[0]))),
    'SCRIPTURE': C(1, 'skl', 'common', 'none', 'DRAW {0} CARDS.', (2,), (3,),
                   lambda g, c, t: g.draw_cards(c.v[0])),
    # uncommon attacks
    'WHIRL': C(-1, 'atk', 'uncommon', 'all', 'DEAL {D0} DAMAGE TO ALL ENEMIES X TIMES.', (5,), (8,),
               lambda g, c, t: [g.hit_all(c.v[0]) for _ in range(g.X)]),
    'HEAVY BLOW': C(2, 'atk', 'uncommon', 'one', 'DEAL {D0} DAMAGE. STRENGTH COUNTS {1} TIMES.', (14, 3), (14, 5),
                    lambda g, c, t: g.hit(t, c.v[0] + _heavy(g, c)), bonus=_heavy),
    'REAP': C(2, 'atk', 'uncommon', 'all', 'DEAL {D0} DAMAGE TO ALL. HEAL BY UNBLOCKED DAMAGE. EXHAUST.',
              (4,), (5,), _reap, ex=True),
    'DEVOUR': C(1, 'atk', 'uncommon', 'one', 'DEAL {D0} DAMAGE. ON A KILL, GAIN {1} MAX HP. EXHAUST.',
                (10, 3), (12, 4), _devour, ex=True),
    'UPPERCUT': C(2, 'atk', 'uncommon', 'one', 'DEAL {D0} DAMAGE. APPLY {1} WEAK AND {1} VULNERABLE.',
                  (13, 1), (13, 2),
                  lambda g, c, t: (g.hit(t, c.v[0]), g.apply(t, 'weak', c.v[1]), g.apply(t, 'vuln', c.v[1]))),
    'BANE': C(1, 'atk', 'uncommon', 'one', 'DEAL {D0} DAMAGE. IF POISONED, AGAIN.', (7,), (10,), _bane),
    # uncommon skills
    'CATALYST': C(1, 'skl', 'uncommon', 'one', 'MULTIPLY AN ENEMY\'S POISON BY {0}. EXHAUST.', (2,), (3,),
                  _catalyst, ex=True),
    'PESTILENCE': C(2, 'skl', 'uncommon', 'one', 'APPLY {0} POISON.', (8,), (11,),
                    lambda g, c, t: g.apply(t, 'poison', c.v[0])),
    'ENTRENCH': C(2, 'skl', 'uncommon', 'none', 'DOUBLE YOUR BLOCK.', cu=1,
                  fx=lambda g, c, t: g.add_block(g.p.block)),
    'BULWARK': C(2, 'skl', 'uncommon', 'none', 'GAIN {B0} BLOCK.', (14,), (19,),
                 lambda g, c, t: g.gain_block(c.v[0])),
    'ADRENAL': C(0, 'skl', 'uncommon', 'none', 'GAIN {0} ENERGY. DRAW 2 CARDS. EXHAUST.', (1,), (2,),
                 lambda g, c, t: (g.gain_energy(c.v[0]), g.draw_cards(2)), ex=True),
    'DISARM': C(1, 'skl', 'uncommon', 'one', 'AN ENEMY LOSES {0} STRENGTH. EXHAUST.', (2,), (3,),
                lambda g, c, t: g.apply(t, 'str', -c.v[0]), ex=True),
    'TERROR': C(1, 'skl', 'uncommon', 'one', 'APPLY 99 VULNERABLE. EXHAUST.', cu=0,
                fx=lambda g, c, t: g.apply(t, 'vuln', 99), ex=True),
    'PURGE': C(1, 'skl', 'uncommon', 'none', 'EXHAUST YOUR NON-ATTACKS. GAIN {B0} BLOCK FOR EACH.',
               (5,), (7,), _purge),
    'SACRIFICE': C(0, 'skl', 'uncommon', 'none', 'EXHAUST A RANDOM CARD IN HAND. DRAW {0} CARDS.',
                   (2,), (3,), _sacrifice),
    # uncommon powers
    'WRATH': C(1, 'pow', 'uncommon', 'none', 'GAIN {0} STRENGTH.', (2,), (3,),
               lambda g, c, t: g.buff('str', c.v[0])),
    'IRON SKIN': C(1, 'pow', 'uncommon', 'none', 'AT THE END OF YOUR TURN, GAIN {0} BLOCK.', (3,), (4,),
                   lambda g, c, t: g.buff('plated', c.v[0])),
    'THORN CROWN': C(1, 'pow', 'uncommon', 'none', 'GAIN {0} THORNS.', (3,), (5,),
                     lambda g, c, t: g.buff('thorns', c.v[0])),
    'BLIGHT': C(1, 'pow', 'uncommon', 'none', 'AT THE START OF YOUR TURN, APPLY {0} POISON TO ALL ENEMIES.',
                (2,), (3,), lambda g, c, t: g.buff('noxious', c.v[0])),
    'FOOTWORK': C(1, 'pow', 'uncommon', 'none', 'GAIN {0} DEXTERITY.', (2,), (3,),
                  lambda g, c, t: g.buff('dex', c.v[0])),
    'NUMBNESS': C(1, 'pow', 'uncommon', 'none', 'WHENEVER A CARD IS EXHAUSTED, GAIN {0} BLOCK.', (3,), (4,),
                  lambda g, c, t: g.buff('nopain', c.v[0])),
    # rare
    'BLUDGEON': C(3, 'atk', 'rare', 'one', 'DEAL {D0} DAMAGE.', (32,), (42,),
                  lambda g, c, t: g.hit(t, c.v[0])),
    'IMMOLATE': C(2, 'atk', 'rare', 'all', 'DEAL {D0} DAMAGE TO ALL ENEMIES. ADD A BURN TO YOUR DISCARD.',
                  (21,), (28,), lambda g, c, t: (g.hit_all(c.v[0]), g.add_card('BURN', 'disc'))),
    'LIMIT BREAK': C(1, 'skl', 'rare', 'none', 'DOUBLE YOUR STRENGTH. EXHAUST.', fx=_limit, ex=True, exu=False,
                     textu='DOUBLE YOUR STRENGTH.'),
    'OFFERING': C(0, 'skl', 'rare', 'none', 'LOSE 6 HP. GAIN 2 ENERGY. DRAW {0} CARDS. EXHAUST.', (3,), (5,),
                  lambda g, c, t: (g.lose_hp(6), g.gain_energy(2), g.draw_cards(c.v[0])), ex=True),
    'IMPERVIOUS': C(2, 'skl', 'rare', 'none', 'GAIN {B0} BLOCK. EXHAUST.', (30,), (40,),
                    lambda g, c, t: g.gain_block(c.v[0]), ex=True),
    'DARK RITE': C(3, 'pow', 'rare', 'none', 'AT THE START OF YOUR TURN, GAIN {0} STRENGTH.', (2,), (3,),
                   lambda g, c, t: g.buff('darkrite', c.v[0])),
    'BARRICADE': C(3, 'pow', 'rare', 'none', 'BLOCK IS NO LONGER REMOVED AT THE START OF YOUR TURN.', cu=2,
                   fx=lambda g, c, t: g.buff('barricade', 1)),
    'WRAITH FORM': C(3, 'pow', 'rare', 'none', 'GAIN {0} VEIL. AT THE END OF YOUR TURN, LOSE 1 DEXTERITY.',
                     (2,), (3,), lambda g, c, t: (g.buff('veil', c.v[0]), g.buff('wraith', 1, quiet=True))),
    'ENVENOM': C(2, 'pow', 'rare', 'none', 'UNBLOCKED ATTACK DAMAGE ALSO APPLIES 1 POISON.', cu=1,
                 fx=lambda g, c, t: g.buff('envenom', 1)),
    'MARTYR': C(2, 'pow', 'rare', 'none', 'WHENEVER YOU GAIN BLOCK, DEAL {0} DAMAGE TO A RANDOM ENEMY.',
                (5,), (7,), lambda g, c, t: g.buff('martyr', c.v[0])),
    # status and curses
    'SLIME': C(1, 'status', 'none', 'none', 'EXHAUST.', ex=True),
    'BURN': C(0, 'status', 'none', 'none', 'UNPLAYABLE. AT THE END OF YOUR TURN, TAKE 2 DAMAGE.', unplay=True),
    'DAZED': C(0, 'status', 'none', 'none', 'UNPLAYABLE. ETHEREAL.', unplay=True, eth=True),
    'WOUND': C(0, 'status', 'none', 'none', 'UNPLAYABLE.', unplay=True),
    'DOUBT': C(0, 'curse', 'none', 'none', 'UNPLAYABLE. AT THE END OF YOUR TURN, GAIN 1 WEAK.', unplay=True),
    'GUILT': C(0, 'curse', 'none', 'none', 'UNPLAYABLE. AT THE END OF YOUR TURN, LOSE 1 HP.', unplay=True),
}
POOL = {r: [k for k, d in CARDS.items() if d['rar'] == r] for r in ('common', 'uncommon', 'rare')}
TYPE_NAME = {'atk': 'ATTACK', 'skl': 'SKILL', 'pow': 'POWER', 'status': 'STATUS', 'curse': 'CURSE'}

KEYWORDS = {
    'VULNERABLE': 'VULNERABLE: TAKES 50% MORE ATTACK DAMAGE.',
    'WEAK': 'WEAK: DEALS 25% LESS ATTACK DAMAGE.',
    'POISON': 'POISON: LOSES THAT MUCH HP AT THE START OF ITS TURN, THEN IT FALLS BY 1.',
    'BLOCK': 'BLOCK: STOPS DAMAGE. REMOVED AT THE START OF YOUR TURN.',
    'EXHAUST': 'EXHAUST: REMOVED FOR THE REST OF COMBAT.',
    'STRENGTH': 'STRENGTH: ADDS TO THE DAMAGE OF EACH HIT.',
    'DEXTERITY': 'DEXTERITY: ADDS TO THE BLOCK OF EACH CARD.',
    'THORNS': 'THORNS: DEALS THAT MUCH DAMAGE BACK TO ATTACKERS.',
    'VEIL': 'VEIL: TAKE AT MOST 1 DAMAGE FROM EACH HIT. FALLS BY 1 EACH TURN.',
    'ETHEREAL': 'ETHEREAL: EXHAUSTED IF STILL IN HAND AT THE END OF YOUR TURN.',
    'BURN': 'BURN: A STATUS CARD THAT HURTS YOU AT THE END OF YOUR TURN.',
    'X ': 'X: SPENDS ALL YOUR ENERGY; X IS HOW MUCH.',
}


class Card:
    def __init__(self, key, up=False):
        self.key, self.up = key, up
        self.x = self.y = None   # animated hand position

    @property
    def d(self):
        return CARDS[self.key]

    @property
    def name(self):
        return self.key + ('+' if self.up else '')

    @property
    def type(self):
        return self.d['type']

    @property
    def cost(self):
        return self.d.get('cu', self.d['cost']) if self.up else self.d['cost']

    @property
    def v(self):
        return self.d['vu'] if self.up else self.d['v']

    @property
    def exhausts(self):
        if self.up and 'exu' in self.d:
            return self.d['exu']
        return self.d.get('ex', False)

    @property
    def upgradable(self):
        return not self.up and self.type not in ('status', 'curse')

    def raw_text(self):
        return self.d['textu'] if self.up and 'textu' in self.d else self.d['text']


# ------------------------------------------------------------------ relics, potions
RELICS = {
    'BURIAL SHROUD': ('start', 'AT THE END OF COMBAT, HEAL 6 HP.'),
    'ANCHOR STONE': ('common', 'START EACH COMBAT WITH 10 BLOCK.'),
    'WAX CANDLE': ('common', 'GAIN 1 ENERGY ON THE FIRST TURN OF EACH COMBAT.'),
    'BONE TOOTH': ('common', 'START EACH COMBAT WITH 1 STRENGTH.'),
    'SAINT KNUCKLE': ('common', 'START EACH COMBAT WITH 1 DEXTERITY.'),
    'PRAYER BEADS': ('common', 'DRAW 2 MORE CARDS ON THE FIRST TURN OF EACH COMBAT.'),
    'THORN RING': ('common', 'START EACH COMBAT WITH 3 THORNS.'),
    'BLOOD VIAL': ('common', 'HEAL 2 HP AT THE START OF EACH COMBAT.'),
    'CHALICE': ('common', 'RAISE YOUR MAX HP BY 10.'),
    'WIDOW MARBLES': ('common', 'AT THE START OF EACH COMBAT, APPLY 1 VULNERABLE TO ALL ENEMIES.'),
    'IRON NAIL': ('uncommon', 'EVERY THIRD ATTACK YOU PLAY IN A TURN GRANTS 1 STRENGTH.'),
    'STONE HEART': ('uncommon', 'IF YOU END YOUR TURN WITHOUT BLOCK, GAIN 6 BLOCK.'),
    'RED SKULL': ('uncommon', 'WHILE AT HALF HP OR LESS, YOUR HITS DEAL 3 MORE DAMAGE.'),
    'CARRION': ('uncommon', 'AT THE END OF COMBAT, IF AT HALF HP OR LESS, HEAL 12 HP.'),
    'SERPENT SKULL': ('uncommon', 'WHENEVER YOU APPLY POISON, APPLY 1 MORE.'),
    'HOURGLASS': ('uncommon', 'EVERY THIRD TURN, GAIN 1 ENERGY.'),
    'WHETSTONE': ('uncommon', 'UPGRADE 2 RANDOM ATTACKS IN YOUR DECK.'),
    'WAR PAINT': ('uncommon', 'UPGRADE 2 RANDOM SKILLS IN YOUR DECK.'),
    'PHOENIX ASH': ('rare', 'ONCE, WHEN YOU WOULD DIE, HEAL TO HALF HP INSTEAD.'),
    'INK QUILL': ('rare', 'EVERY 10TH ATTACK YOU PLAY DEALS DOUBLE DAMAGE.'),
    'MERCURY BELL': ('rare', 'AT THE START OF YOUR TURN, DEAL 3 DAMAGE TO ALL ENEMIES.'),
    'BLACK CANDLE': ('boss', 'GAIN 1 ENERGY EACH TURN. YOU CAN NO LONGER REST AT FIRES.'),
    'HOLLOW CROWN': ('boss', 'GAIN 1 ENERGY EACH TURN. ENEMY INTENTS ARE HIDDEN.'),
    'MISER BONE': ('boss', 'GAIN 1 ENERGY EACH TURN. YOU NO LONGER FIND GOLD.'),
    'SOUL CAGE': ('boss', 'GAIN 1 ENERGY EACH TURN. EACH COMBAT STARTS WITH 2 DAZED IN YOUR DRAW PILE.'),
    'GRAVE TOME': ('boss', 'DRAW 1 MORE CARD EACH TURN.'),
}
ENERGY_RELICS = ('BLACK CANDLE', 'HOLLOW CROWN', 'MISER BONE', 'SOUL CAGE')

POTIONS = {  # target, desc
    'BLOOD DRAUGHT': ('none', 'HEAL 25% OF YOUR MAX HP.'),
    'FIRE FLASK': ('one', 'DEAL 20 DAMAGE.'),
    'IRON TONIC': ('none', 'GAIN 12 BLOCK.'),
    'WRATH TONIC': ('none', 'GAIN 2 STRENGTH.'),
    'SWIFT TONIC': ('none', 'DRAW 3 CARDS.'),
    'SPIRIT': ('none', 'GAIN 2 ENERGY.'),
    'VENOM': ('one', 'APPLY 7 POISON.'),
    'HEX FLASK': ('one', 'APPLY 3 VULNERABLE.'),
}

STATUS = {  # short, description, is_debuff
    'str': ('STR', 'STRENGTH: EACH HIT DEALS THAT MUCH MORE DAMAGE.', False),
    'dex': ('DEX', 'DEXTERITY: EACH BLOCK CARD GIVES THAT MUCH MORE BLOCK.', False),
    'weak': ('WEAK', 'WEAK: DEALS 25% LESS ATTACK DAMAGE. TURNS LEFT.', True),
    'vuln': ('VULN', 'VULNERABLE: TAKES 50% MORE ATTACK DAMAGE. TURNS LEFT.', True),
    'frail': ('FRAIL', 'FRAIL: GAINS 25% LESS BLOCK FROM CARDS. TURNS LEFT.', True),
    'poison': ('PSN', 'POISON: LOSES THAT MUCH HP AT THE START OF ITS TURN, THEN IT FALLS BY 1.', True),
    'thorns': ('THRN', 'THORNS: ATTACKERS TAKE THAT MUCH DAMAGE BACK.', False),
    'ritual': ('RITE', 'RITUAL: GAINS THAT MUCH STRENGTH AT THE START OF ITS TURN.', False),
    'plated': ('IRON', 'IRON SKIN: GAINS THAT MUCH BLOCK AT THE END OF ITS TURN.', False),
    'enrage': ('RAGE', 'ENRAGE: GAINS THAT MUCH STRENGTH WHENEVER YOU PLAY A SKILL.', False),
    'artifact': ('WARD', 'WARD: NEGATES THAT MANY DEBUFFS.', False),
    'veil': ('VEIL', 'VEIL: TAKES AT MOST 1 DAMAGE FROM EACH HIT. FALLS BY 1 EACH OF ITS TURNS.', False),
    'barricade': ('BARR', 'BARRICADE: BLOCK IS NOT REMOVED AT THE START OF THE TURN.', False),
    'darkrite': ('DARK', 'DARK RITE: GAIN THAT MUCH STRENGTH AT THE START OF YOUR TURN.', False),
    'noxious': ('BLGT', 'BLIGHT: POISON ALL ENEMIES BY THAT MUCH AT THE START OF YOUR TURN.', False),
    'nopain': ('NUMB', 'NUMBNESS: GAIN THAT MUCH BLOCK WHENEVER A CARD IS EXHAUSTED.', False),
    'envenom': ('ENVN', 'ENVENOM: UNBLOCKED ATTACK DAMAGE APPLIES 1 POISON.', False),
    'martyr': ('MRTR', 'MARTYR: GAINING BLOCK DEALS THAT MUCH DAMAGE TO A RANDOM ENEMY.', False),
    'nextblk': ('NEXT', 'GAIN THAT MUCH BLOCK AT THE START OF YOUR NEXT TURN.', False),
    'wraith': ('WRTH', 'WRAITH FORM: LOSE THAT MUCH DEXTERITY AT THE END OF YOUR TURN.', True),
}

# ------------------------------------------------------------------ enemies
# move keys: dmg, hits, blk, self [(status, n)], you [(status, n)], add [(card, n, pile)],
# heal, allstr, allblk, summon; intent: atk / blk / buf / deb / sum (combined automatically)
ENEMIES = {
    # act 1
    'GHOUL': dict(hp=(42, 46), art='GHOUL', moves=dict(
        CLAW=dict(dmg=11), GNAW=dict(dmg=5, hits=2), RAKE=dict(dmg=7, you=[('weak', 1)])),
        rand=[('CLAW', 45), ('GNAW', 30), ('RAKE', 25)]),
    'CULTIST': dict(hp=(48, 54), art='HOOD', moves=dict(
        RITE=dict(self=[('ritual', 3)]), SLASH=dict(dmg=6)), first=['RITE'], cycle=['SLASH']),
    'RAT': dict(hp=(11, 15), art='RAT', scale=2, moves=dict(
        BITE=dict(dmg=4), FILTH=dict(dmg=2, you=[('frail', 1)])),
        rand=[('BITE', 65), ('FILTH', 35)]),
    'SKELETON': dict(hp=(24, 28), art='SKEL', moves=dict(
        SLASH=dict(dmg=8), GUARD=dict(blk=8, dmg=4)), rand=[('SLASH', 55), ('GUARD', 45)]),
    'BLOAT': dict(hp=(62, 68), art='BLOB', moves=dict(
        SPEW=dict(add=[('SLIME', 2, 'disc')]), CRUSH=dict(dmg=14), SMOTHER=dict(dmg=8, you=[('frail', 1)])),
        cycle=['SPEW', 'CRUSH', 'SMOTHER']),
    'GRAVE KNIGHT': dict(hp=(84, 88), art='KNIGHT', elite=True, moves=dict(
        BELLOW=dict(self=[('enrage', 2)]), CLEAVE=dict(dmg=14), REND=dict(dmg=7, hits=2)),
        first=['BELLOW'], cycle=['CLEAVE', 'REND']),
    'BELL WITCH': dict(hp=(72, 76), art='HOOD', elite=True, moves=dict(
        TOLL=dict(you=[('weak', 2)], add=[('DAZED', 2, 'draw')]), KNELL=dict(dmg=12), PEAL=dict(dmg=5, hits=3)),
        first=['TOLL'], rand=[('KNELL', 40), ('PEAL', 35), ('TOLL', 25)]),
    'HOLLOW BISHOP': dict(hp=(210, 210), art='BISHOP', scale=3, boss=True, moves=dict(
        CENSER=dict(dmg=5, hits=2, add=[('BURN', 1, 'disc')]), SMITE=dict(dmg=18),
        SERMON=dict(blk=15, self=[('str', 2)]), SCOURGE=dict(dmg=4, hits=4)),
        cycle=['CENSER', 'SMITE', 'SERMON', 'SCOURGE']),
    # act 2
    'WIGHT': dict(hp=(64, 70), art='WRAITH', moves=dict(
        DRAIN=dict(dmg=10, heal=6), CHILL=dict(dmg=7, you=[('frail', 2)]), KEEN=dict(blk=8, self=[('str', 2)])),
        rand=[('DRAIN', 40), ('CHILL', 35), ('KEEN', 25)]),
    'BONE ARCHER': dict(hp=(36, 40), art='SKEL', moves=dict(
        VOLLEY=dict(dmg=4, hits=3), AIM=dict(blk=8, self=[('str', 2)]), SHOT=dict(dmg=11)),
        rand=[('VOLLEY', 40), ('SHOT', 35), ('AIM', 25)]),
    'GARGOYLE': dict(hp=(76, 82), art='GARG', start=[('plated', 4)], moves=dict(
        ROOST=dict(blk=14), DIVE=dict(dmg=17), BUFFET=dict(dmg=8, hits=2)),
        cycle=['ROOST', 'DIVE', 'BUFFET']),
    'PLAGUE MONK': dict(hp=(54, 60), art='HOOD', moves=dict(
        MIASMA=dict(you=[('poison', 5)]), CUDGEL=dict(dmg=13), CHANT=dict(allblk=9)),
        first=['MIASMA'], rand=[('CUDGEL', 50), ('CHANT', 25), ('MIASMA', 25)]),
    'CHORISTER': dict(hp=(22, 26), art='WRAITH', scale=1, moves=dict(
        HYMN=dict(allstr=1), SHRIEK=dict(dmg=6)), cycle=['HYMN', 'SHRIEK', 'SHRIEK']),
    'EXECUTIONER': dict(hp=(132, 136), art='KNIGHT', elite=True, moves=dict(
        WINDUP=dict(blk=12, self=[('str', 3)]), CHOP=dict(dmg=26), FLAIL=dict(dmg=9, hits=2)),
        cycle=['WINDUP', 'CHOP', 'FLAIL']),
    'FLESH ABBOT': dict(hp=(150, 158), art='BLOB', elite=True, moves=dict(
        GORGE=dict(dmg=18, heal=10), VOMIT=dict(dmg=8, add=[('WOUND', 3, 'draw')]), BULK=dict(blk=12, self=[('str', 3)])),
        first=['VOMIT'], rand=[('GORGE', 45), ('VOMIT', 25), ('BULK', 30)]),
    'WEEPING CHOIR': dict(hp=(300, 300), art='CHOIR', scale=3, boss=True, moves=dict(
        LAMENT=dict(dmg=8, you=[('weak', 2), ('vuln', 2)]), REQUIEM=dict(dmg=7, hits=3),
        GATHER=dict(blk=15, summon='CHORISTER'), DIRGE=dict(dmg=26)),
        cycle=['LAMENT', 'REQUIEM', 'GATHER', 'DIRGE'], escort=['CHORISTER', 'CHORISTER']),
    # act 3
    'REVENANT': dict(hp=(92, 100), art='SKEL', moves=dict(
        GRIP=dict(dmg=13, you=[('vuln', 2)]), BATTER=dict(dmg=8, hits=2), ENDURE=dict(blk=12, self=[('str', 2)])),
        rand=[('GRIP', 35), ('BATTER', 40), ('ENDURE', 25)]),
    'DREAD HOUND': dict(hp=(46, 52), art='HOUND', moves=dict(
        BITE=dict(dmg=11), HOWL=dict(allstr=2), MAUL=dict(dmg=6, hits=2)),
        rand=[('BITE', 45), ('MAUL', 35), ('HOWL', 20)], rep=1),
    'SHADE': dict(hp=(60, 66), art='WRAITH', moves=dict(
        FADE=dict(self=[('veil', 1)], blk=6), TOUCH=dict(dmg=15, you=[('weak', 1)]), WAIL=dict(dmg=5, hits=3)),
        cycle=['FADE', 'TOUCH', 'WAIL']),
    'LICH ACOLYTE': dict(hp=(70, 76), art='HOOD', moves=dict(
        HEX=dict(you=[('vuln', 2), ('frail', 2)]), BOLT=dict(dmg=18)), cycle=['HEX', 'BOLT', 'BOLT']),
    'DEATH KNIGHT': dict(hp=(210, 220), art='KNIGHT', elite=True, start=[('artifact', 2)], moves=dict(
        MOURN=dict(blk=20, self=[('str', 3)]), EXECUTE=dict(dmg=15, hits=2), SWEEP=dict(dmg=26, you=[('frail', 2)])),
        cycle=['MOURN', 'EXECUTE', 'SWEEP']),
    'THE MAW': dict(hp=(230, 240), art='BLOB', elite=True, moves=dict(
        ROAR=dict(you=[('weak', 3), ('frail', 3)]), DEVOUR=dict(dmg=30), CHEW=dict(dmg=7, hits=4)),
        first=['ROAR'], rand=[('DEVOUR', 40), ('CHEW', 40), ('ROAR', 20)]),
    'PALE KING': dict(hp=(440, 440), art='KING', scale=3, boss=True, moves=dict(
        CROWN=dict(blk=30, self=[('ritual', 1), ('artifact', 2)]), JUDGEMENT=dict(dmg=9, hits=4),
        DECREE=dict(you=[('vuln', 2)], add=[('DAZED', 2, 'draw'), ('WOUND', 1, 'draw')]),
        EXECUTION=dict(dmg=40), TITHE=dict(heal=25, blk=20)),
        first=['CROWN'], cycle=['JUDGEMENT', 'DECREE', 'EXECUTION', 'TITHE']),
}
ENCOUNTERS = [
    dict(easy=[['GHOUL'], ['CULTIST'], ['RAT', 'RAT'], ['SKELETON']],
         hard=[['RAT', 'RAT', 'RAT'], ['BLOAT'], ['SKELETON', 'SKELETON'], ['GHOUL', 'RAT'],
               ['CULTIST', 'RAT'], ['SKELETON', 'RAT']],
         elite=[['GRAVE KNIGHT'], ['BELL WITCH']], boss=['HOLLOW BISHOP']),
    dict(easy=[['WIGHT'], ['BONE ARCHER', 'BONE ARCHER'], ['PLAGUE MONK']],
         hard=[['GARGOYLE'], ['WIGHT', 'CHORISTER'], ['CHORISTER', 'CHORISTER', 'CHORISTER'],
               ['PLAGUE MONK', 'BONE ARCHER'], ['GARGOYLE', 'CHORISTER']],
         elite=[['EXECUTIONER'], ['FLESH ABBOT']], boss=['WEEPING CHOIR']),
    dict(easy=[['REVENANT'], ['DREAD HOUND', 'DREAD HOUND'], ['SHADE']],
         hard=[['LICH ACOLYTE', 'DREAD HOUND'], ['SHADE', 'SHADE'], ['REVENANT', 'LICH ACOLYTE'],
               ['DREAD HOUND', 'DREAD HOUND', 'DREAD HOUND'], ['REVENANT', 'SHADE']],
         elite=[['DEATH KNIGHT'], ['THE MAW']], boss=['PALE KING']),
]


class Unit:
    def __init__(self, hp):
        self.hp = self.maxhp = hp
        self.block = 0
        self.st = {}
        self.shake = 0
        self.flash = 0
        self.lunge = 0
        self.x = self.y = 0   # feet position

    def has(self, k):
        return self.st.get(k, 0)


class Enemy(Unit):
    def __init__(self, key, sprites):
        d = ENEMIES[key]
        super().__init__(random.randint(*d['hp']))
        self.key = key
        self.d = d
        self.turn = 0
        self.history = []
        self.intent = None
        self.offset = random.randrange(len(d.get('cycle', [1]))) if 'first' not in d and not d.get('boss') else 0
        self.spr = sprites[(d['art'], d.get('scale', 2))]
        self.dead = False
        self.die_t = 0
        for k, n in d.get('start', []):
            self.st[k] = n

    @property
    def w(self):
        return self.spr[0].get_width()

    @property
    def h(self):
        return self.spr[0].get_height()

    def rect(self):
        return pygame.Rect(self.x - self.w // 2, self.y - self.h, self.w, self.h)


class Player(Unit):
    pass


# ------------------------------------------------------------------ events
EVENTS = ['STATUE', 'FONT', 'PILGRIM', 'MIRROR', 'DICE', 'CRYPT', 'LIBRARY', 'ALTAR']


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
        pygame.display.set_caption('RELIQUARY')
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()
        self.sfx = Sfx()
        self.sprites = {}
        for k, d in ENEMIES.items():
            key = (d['art'], d.get('scale', 2))
            if key not in self.sprites:
                self.sprites[key] = build_sprite(*key)
        self.pspr = build_sprite('PLAYER', 2)
        self.dim = dither_surface(W, H)
        self.dim2 = dither_surface(W, H, True)
        self.icons = {k: icon_surf(k) for k in ICONS}
        self.icons_red = {k: icon_surf(k, 1, BLOOD) for k in ICONS}
        self.boss_icon = icon_surf('elite', 2)
        self.card_cache = {}
        self.data_dir = os.path.join(os.environ.get('XDG_DATA_HOME') or
                                     os.path.expanduser('~/.local/share'), 'reliquary')
        self.best = self.load_int('best')
        self.wins = self.load_int('wins')
        self.state = 'title'
        self.t = 0
        self.mouse = (0, 0)
        self.floats = []
        self.overlay = None   # deck picker / viewer
        self.paused = False
        self.msg = ''
        self.msg_t = 0

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

    # -------------------------------------------------------------- run setup
    def new_run(self):
        self.p = Player(80)
        self.gold = 99
        self.deck = [Card('STRIKE') for _ in range(5)] + [Card('WARD') for _ in range(4)] + [Card('REND')]
        self.relics = ['BURIAL SHROUD']
        self.potions = [None, None, None]
        self.act = 0
        self.fights = 0
        self.removals = 0
        self.quill = 0
        self.phoenix_used = False
        self.seen_events = []
        self.last_enc = None
        self.relic_pool = {r: [k for k, v in RELICS.items() if v[0] == r]
                           for r in ('common', 'uncommon', 'rare', 'boss')}
        for v in self.relic_pool.values():
            random.shuffle(v)
        self.overlay = None
        self.paused = False
        self.floats = []
        self.gen_map()
        self.state = 'map'
        self.sfx.play('toll')

    @property
    def floor_no(self):
        if self.mpos == 'boss':
            return (self.act + 1) * (FLOORS + 1)
        return self.act * (FLOORS + 1) + (self.mpos[0] + 1 if self.mpos else 0)

    def has(self, r):
        return r in self.relics

    def flash_msg(self, s):
        self.msg = s
        self.msg_t = 150

    # -------------------------------------------------------------- map
    def gen_map(self):
        L = 7
        edges = set()
        nodes = set()
        starts = []
        for i in range(6):
            l = random.randrange(L)
            while i == 1 and l == starts[0]:
                l = random.randrange(L)
            starts.append(l)
            for f in range(FLOORS - 1):
                nodes.add((f, l))
                opts = [d for d in (-1, 0, 1) if 0 <= l + d < L]
                random.shuffle(opts)
                for d in opts:
                    if d and ((f, l + d), (f + 1, l)) in edges:
                        continue
                    break
                else:
                    d = 0
                edges.add(((f, l), (f + 1, l + d)))
                l += d
            nodes.add((FLOORS - 1, l))
        types = {}
        weights = [('fight', 45), ('event', 22), ('elite', 15), ('rest', 12), ('shop', 6)]
        for n in sorted(nodes):
            f = n[0]
            if f == 0:
                t = 'fight'
            elif f == 5:
                t = 'chest'
            elif f == FLOORS - 1:
                t = 'rest'
            else:
                parents = {types[a] for a, b in edges if b == n}
                for _ in range(30):
                    opts = [(k, w) for k, w in weights
                            if not (k == 'elite' and f < 4) and not (k == 'rest' and (f < 3 or f == FLOORS - 2))
                            and not (k == 'shop' and f < 2)]
                    t = random.choices([k for k, _ in opts], [w for _, w in opts])[0]
                    if t in ('elite', 'rest', 'shop') and t in parents:
                        continue
                    break
            types[n] = t
        self.nodes, self.edges, self.ntype = nodes, edges, types
        self.mpos = None
        self.visited = []
        self.msel = 0

    def node_xy(self, n):
        if n == 'boss':
            return 362, 104
        return 22 + n[0] * 30, 34 + n[1] * 24

    def reachable(self):
        if self.mpos is None:
            return sorted(n for n in self.nodes if n[0] == 0)
        if self.mpos == 'boss':
            return []
        if self.mpos[0] == FLOORS - 1:
            return ['boss']
        return sorted(b for a, b in self.edges if a == self.mpos)

    def enter_node(self, n):
        self.sfx.play('step')
        self.mpos = n
        self.visited.append(n)
        if self.floor_no > self.best:
            self.best = self.floor_no
            self.save_int('best', self.best)
        t = 'boss' if n == 'boss' else self.ntype[n]
        if t == 'event':
            r = random.random()
            if r < 0.15:
                t = 'fight'
            elif r < 0.22:
                t = 'shop'
            elif r < 0.27:
                t = 'chest'
        self.room = t
        if t == 'fight':
            enc = ENCOUNTERS[self.act]
            pool = enc['easy'] if self.fights < 3 else enc['hard']
            opts = [e for e in pool if e != self.last_enc] or pool
            group = random.choice(opts)
            self.last_enc = group
            self.fights += 1
            self.start_combat(group)
        elif t == 'elite':
            self.start_combat(random.choice(ENCOUNTERS[self.act]['elite']), elite=True)
        elif t == 'boss':
            self.start_combat(ENCOUNTERS[self.act]['boss'], boss=True)
        elif t == 'rest':
            self.state = 'rest'
            self.sel = 0
        elif t == 'shop':
            self.open_shop()
        elif t == 'chest':
            self.open_chest()
        else:
            self.open_event()

    # -------------------------------------------------------------- relics
    def gain_relic(self, r):
        self.relics.append(r)
        for pool in self.relic_pool.values():
            if r in pool:
                pool.remove(r)
        self.sfx.play('relic')
        if r == 'CHALICE':
            self.p.maxhp += 10
            self.p.hp += 10
        elif r in ('WHETSTONE', 'WAR PAINT'):
            typ = 'atk' if r == 'WHETSTONE' else 'skl'
            cands = [c for c in self.deck if c.type == typ and c.upgradable]
            for c in random.sample(cands, min(2, len(cands))):
                c.up = True

    def random_relic(self, rar=None, skip=0):
        if rar is None:
            rar = random.choices(['common', 'uncommon', 'rare'], [50, 33, 17])[0]
        for r in (rar, 'common', 'uncommon', 'rare'):
            if len(self.relic_pool[r]) > skip:
                return self.relic_pool[r][skip]
        return None

    def gain_gold(self, n):
        if self.has('MISER BONE') or n <= 0:
            return 0
        self.gold += n
        self.sfx.play('coin')
        return n

    def gain_potion(self, k):
        for i, p in enumerate(self.potions):
            if p is None:
                self.potions[i] = k
                return True
        return False

    def card_choices(self, n=3, elite=False, boss=False):
        out = []
        for _ in range(n):
            for _ in range(50):
                if boss:
                    rar = 'rare'
                else:
                    r = random.random()
                    rare_p = 0.1 if elite else 0.04
                    unc_p = 0.4 if elite else 0.33
                    rar = 'rare' if r < rare_p else 'uncommon' if r < rare_p + unc_p else 'common'
                k = random.choice(POOL[rar])
                if k not in [c.key for c in out]:
                    break
            out.append(Card(k, random.random() < 0.08 * self.act + (0.04 if elite else 0)))
        return out

    # -------------------------------------------------------------- combat setup
    def start_combat(self, group, elite=False, boss=False):
        self.state = 'combat'
        self.elite, self.boss = elite, boss
        self.enemies = []
        for k in group:
            self.enemies.append(Enemy(k, self.sprites))
            for esc in ENEMIES[k].get('escort', []):
                self.enemies.insert(0, Enemy(esc, self.sprites))
        self.layout_enemies()
        self.drawp = [Card(c.key, c.up) for c in self.deck]
        random.shuffle(self.drawp)
        if self.has('SOUL CAGE'):
            for _ in range(2):
                self.drawp.insert(random.randrange(len(self.drawp) + 1), Card('DAZED'))
        self.hand, self.disc, self.exh = [], [], []
        self.p.block = 0
        self.p.st = {}
        self.turn = 0
        self.sel = None
        self.tsel = 0
        self.potsel = None
        self.drag = None
        self.phase = 'player'
        self.ptimer = 0
        self.X = 0
        self.quill_on = False
        self.victory_done = False
        self.floats = []
        for e in self.enemies:
            self.choose_intent(e)
        self.start_player_turn(first=True)
        self.sfx.play('toll' if boss else 'turn')

    def layout_enemies(self):
        alive = [e for e in self.enemies if not e.dead or e.die_t > 0]
        gap = 6
        slot = [max(e.w, 50) for e in alive]
        total = sum(slot) + gap * (len(alive) - 1)
        x = max(140, 392 - total)
        for e, w in zip(alive, slot):
            e.x = x + w // 2
            e.y = 112
            x += w + gap
        self.p.x, self.p.y = 66, 112

    def alive(self):
        return [e for e in self.enemies if not e.dead]

    def rnd_enemy(self):
        a = self.alive()
        return random.choice(a) if a else None

    # -------------------------------------------------------------- intents
    def choose_intent(self, e):
        d = e.d
        first = d.get('first', [])
        if e.turn < len(first):
            m = first[e.turn]
        elif 'cycle' in d and not ('rand' in d and e.turn >= len(first)):
            cyc = d['cycle']
            m = cyc[(e.turn - len(first) + e.offset) % len(cyc)]
        else:
            rep = d.get('rep', 2)
            opts = [(k, w) for k, w in d['rand']
                    if not (len(e.history) >= rep and all(h == k for h in e.history[-rep:]))]
            m = random.choices([k for k, _ in opts], [w for _, w in opts])[0]
        if d['moves'][m].get('summon') and len(self.alive()) >= 3:
            m = 'REQUIEM' if 'REQUIEM' in d['moves'] else m
        e.turn += 1
        e.history.append(m)
        e.intent = m

    def intent_info(self, e):
        mv = e.d['moves'][e.intent]
        kinds = []
        if 'dmg' in mv:
            kinds.append('atk')
        if 'blk' in mv or 'allblk' in mv:
            kinds.append('blk')
        if 'self' in mv or 'allstr' in mv or 'heal' in mv:
            kinds.append('buf')
        if 'you' in mv or 'add' in mv:
            kinds.append('deb')
        if 'summon' in mv:
            kinds.append('sum')
        label = ''
        if 'dmg' in mv:
            d = self.calc_dmg(e, self.p, mv['dmg'])
            hits = mv.get('hits', 1)
            label = f'{d}X{hits}' if hits > 1 else str(d)
        return kinds, label

    def intent_desc(self, e):
        mv = e.d['moves'][e.intent]
        parts = []
        if 'dmg' in mv:
            d = self.calc_dmg(e, self.p, mv['dmg'])
            hits = mv.get('hits', 1)
            parts.append(f'ATTACK FOR {d}' + (f' X{hits}' if hits > 1 else '') + '.')
        if 'blk' in mv:
            parts.append(f'BLOCK {mv["blk"]}.')
        if 'allblk' in mv:
            parts.append(f'GIVE ALL ALLIES {mv["allblk"]} BLOCK.')
        for k, n in mv.get('self', []):
            parts.append(f'GAIN {n} {STATUS[k][1].split(":")[0]}.')
        if 'allstr' in mv:
            parts.append(f'ALL ALLIES GAIN {mv["allstr"]} STRENGTH.')
        if 'heal' in mv:
            parts.append(f'HEAL {mv["heal"]}.')
        for k, n in mv.get('you', []):
            parts.append(f'GIVE YOU {n} {STATUS[k][1].split(":")[0]}.')
        for k, n, pile in mv.get('add', []):
            parts.append(f'ADD {n} {k} TO YOUR {"DRAW" if pile == "draw" else "DISCARD"} PILE.')
        if 'summon' in mv:
            parts.append('SUMMON ALLIES.')
        return f'{e.intent}: ' + ' '.join(parts)

    # -------------------------------------------------------------- numbers
    def calc_dmg(self, src, tgt, base):
        d = base + src.st.get('str', 0)
        if src is self.p and self.has('RED SKULL') and self.p.hp * 2 <= self.p.maxhp:
            d += 3
        if src.st.get('weak'):
            d *= 0.75
        if tgt is not None and tgt.st.get('vuln'):
            d *= 1.5
        if src is self.p and self.quill_on:
            d *= 2
        d = max(0, int(d))
        if tgt is not None and tgt.st.get('veil'):
            d = min(d, 1)
        return d

    def calc_blk(self, base):
        b = base + self.p.st.get('dex', 0)
        if self.p.st.get('frail'):
            b *= 0.75
        return max(0, int(b))

    def float(self, u, text, color=BONE):
        n = sum(1 for f in self.floats if f[5] is u and f[4] > 30)
        self.floats.append([u.x + random.randint(-6, 6),
                            max(30, u.y - (u.h if isinstance(u, Enemy) else 42) - n * 7),
                            text, color, 50, u])

    # -------------------------------------------------------------- combat actions
    def hit(self, t, base, src=None, attack=True):
        src = src or self.p
        if t is None or (isinstance(t, Enemy) and t.dead) or t.hp <= 0:
            return 0
        d = self.calc_dmg(src, t, base) if attack else base
        return self.take(t, d, src if attack else None)

    def hits(self, t, base, k):
        return sum(self.hit(t, base) for _ in range(k))

    def hit_all(self, base):
        return sum(self.hit(e, base) for e in self.alive())

    def take(self, t, d, src=None, through_block=False):
        """Deal d damage to t. src is the attacker (for thorns); returns unblocked damage."""
        if t.hp <= 0:
            return 0
        if not through_block and t.block:
            b = min(t.block, d)
            t.block -= b
            d -= b
            if b and not d:
                self.float(t, 'BLOCKED', BONE)
                self.sfx.play('blocked')
        if d > 0:
            t.hp -= d
            t.shake = 10
            t.flash = 6
            self.float(t, str(d), BLOOD)
            self.sfx.play('hurt' if t is self.p else 'hit')
            if src is self.p and self.p.st.get('envenom') and isinstance(t, Enemy):
                self.apply(t, 'poison', 1)
        if src is not None and t.st.get('thorns') and src.hp > 0:
            self.take(src, t.st['thorns'])
        if t.hp <= 0:
            self.on_death(t)
        return max(0, d)

    def on_death(self, t):
        if t is self.p:
            if self.has('PHOENIX ASH') and not self.phoenix_used:
                self.phoenix_used = True
                self.p.hp = self.p.maxhp // 2
                self.float(self.p, 'PHOENIX ASH', BLOOD)
                self.sfx.play('relic')
                return
            self.p.hp = 0
            if self.phase != 'defeat':
                self.phase = 'defeat'
                self.ptimer = 90
                self.sfx.play('toll')
            return
        if not t.dead:
            t.hp = 0
            t.dead = True
            t.die_t = 40
            self.sfx.play('kill')
            if self.sel is not None and self.alive():
                self.tsel = min(self.tsel, len(self.alive()) - 1)
            if not self.alive() and self.phase != 'defeat':
                self.phase = 'victory'
                self.ptimer = 50

    def gain_block(self, base):
        self.add_block(self.calc_blk(base))

    def add_block(self, b, unit=None):
        u = unit or self.p
        if b <= 0:
            return
        u.block += b
        self.sfx.play('block')
        if u is self.p and self.p.st.get('martyr'):
            self.hit(self.rnd_enemy(), self.p.st['martyr'], attack=False)

    def apply(self, t, st, n, src_player=True):
        if t is None or t.hp <= 0:
            return
        debuff = STATUS[st][2] or (st == 'str' and n < 0)
        if debuff and t.st.get('artifact'):
            t.st['artifact'] -= 1
            if not t.st['artifact']:
                del t.st['artifact']
            self.float(t, 'NEGATED', BONE)
            return
        if st == 'poison' and src_player and isinstance(t, Enemy) and self.has('SERPENT SKULL'):
            n += 1
        t.st[st] = t.st.get(st, 0) + n
        if t.st[st] == 0:
            del t.st[st]
        self.float(t, f'{STATUS[st][0]} {"+" if n > 0 else ""}{n}', BLOOD if debuff else BONE)
        self.sfx.play('poison' if st == 'poison' else 'debuff' if debuff else 'buff')

    def apply_all(self, st, n):
        for e in self.alive():
            self.apply(e, st, n)

    def buff(self, st, n, quiet=False):
        self.p.st[st] = self.p.st.get(st, 0) + n
        if not quiet:
            self.float(self.p, f'{STATUS[st][0]} +{n}', BONE)
            self.sfx.play('buff')

    def heal(self, n, u=None):
        u = u or self.p
        n = min(n, u.maxhp - u.hp)
        if n > 0:
            u.hp += n
            self.float(u, f'+{n}', BONE)
            self.sfx.play('heal')

    def lose_hp(self, n):
        self.take(self.p, n, through_block=True)

    def gain_energy(self, n):
        self.energy += n

    def draw_cards(self, n):
        for _ in range(n):
            if len(self.hand) >= 10:
                break
            if not self.drawp:
                if not self.disc:
                    break
                self.drawp = self.disc
                self.disc = []
                random.shuffle(self.drawp)
            c = self.drawp.pop()
            c.x, c.y = 4, 200
            self.hand.append(c)
        self.sfx.play('draw')

    def add_card(self, key, pile):
        c = Card(key)
        if pile == 'draw':
            self.drawp.insert(random.randrange(len(self.drawp) + 1), c)
        elif pile == 'hand' and len(self.hand) < 10:
            self.hand.append(c)
        else:
            self.disc.append(c)

    def exhaust(self, c):
        self.exh.append(c)
        if self.p.st.get('nopain'):
            self.add_block(self.p.st['nopain'])

    # -------------------------------------------------------------- turns
    def start_player_turn(self, first=False):
        self.phase = 'player'
        self.turn += 1
        p = self.p
        if not p.st.get('barricade'):
            p.block = 0
        if p.st.get('veil'):
            p.st['veil'] -= 1
            if not p.st['veil']:
                del p.st['veil']
        if p.st.get('poison'):
            self.take(p, p.st['poison'], through_block=True)
            p.st['poison'] -= 1
            if not p.st['poison']:
                del p.st['poison']
            if p.hp <= 0 and self.phase == 'defeat':
                return
        if first:
            if self.has('ANCHOR STONE'):
                p.block += 10
            if self.has('BONE TOOTH'):
                p.st['str'] = p.st.get('str', 0) + 1
            if self.has('SAINT KNUCKLE'):
                p.st['dex'] = p.st.get('dex', 0) + 1
            if self.has('THORN RING'):
                p.st['thorns'] = p.st.get('thorns', 0) + 3
            if self.has('BLOOD VIAL'):
                self.heal(2)
            if self.has('WIDOW MARBLES'):
                for e in self.alive():
                    self.apply(e, 'vuln', 1)
        if p.st.get('nextblk'):
            self.add_block(p.st.pop('nextblk'))
        if p.st.get('darkrite'):
            p.st['str'] = p.st.get('str', 0) + p.st['darkrite']
            self.float(p, f'STR +{p.st["darkrite"]}')
        if p.st.get('noxious'):
            self.apply_all('poison', p.st['noxious'])
        if self.has('MERCURY BELL'):
            for e in self.alive():
                self.hit(e, 3, attack=False)
        self.energy = 3 + sum(1 for r in ENERGY_RELICS if self.has(r))
        if first and self.has('WAX CANDLE'):
            self.energy += 1
        if self.has('HOURGLASS') and self.turn % 3 == 0:
            self.energy += 1
        self.attacks_turn = 0
        self.aiming = False
        self.kidx = 0
        n = 5 + (2 if first and self.has('PRAYER BEADS') else 0) + (1 if self.has('GRAVE TOME') else 0)
        self.draw_cards(n)
        self.sel = None
        self.potsel = None

    def end_turn(self):
        if self.phase != 'player':
            return
        self.sfx.play('turn')
        p = self.p
        for c in list(self.hand):
            if c.key == 'BURN':
                self.take(p, 2)
            elif c.key == 'GUILT':
                self.lose_hp(1)
            elif c.key == 'DOUBT':
                self.apply(p, 'weak', 1, src_player=False)
        for c in self.hand:
            if c.d.get('eth'):
                self.exhaust(c)
            else:
                self.disc.append(c)
        self.hand = []
        self.sel = None
        self.potsel = None
        if p.st.get('plated'):
            self.add_block(p.st['plated'])
        if self.has('STONE HEART') and p.block == 0:
            self.add_block(6)
        if p.st.get('wraith'):
            p.st['dex'] = p.st.get('dex', 0) - p.st['wraith']
        for k in ('weak', 'vuln', 'frail'):
            if p.st.get(k):
                p.st[k] -= 1
                if not p.st[k]:
                    del p.st[k]
        if self.phase in ('defeat', 'victory'):
            return
        self.phase = 'enemy'
        self.equeue = list(self.alive())
        self.ptimer = 24

    def enemy_act(self, e):
        if e.dead:
            return
        if not e.st.get('barricade'):
            e.block = 0
        if e.st.get('veil'):
            e.st['veil'] -= 1
            if not e.st['veil']:
                del e.st['veil']
        if e.st.get('poison'):
            self.take(e, e.st['poison'], through_block=True)
            e.st['poison'] -= 1
            if not e.st['poison']:
                del e.st['poison']
            if e.dead:
                return
        if e.st.get('ritual'):
            e.st['str'] = e.st.get('str', 0) + e.st['ritual']
        mv = e.d['moves'][e.intent]
        if 'blk' in mv:
            self.add_block(mv['blk'], e)
        if 'allblk' in mv:
            for o in self.alive():
                self.add_block(mv['allblk'], o)
        if 'dmg' in mv:
            e.lunge = 12
            for _ in range(mv.get('hits', 1)):
                if self.p.hp <= 0 or e.dead:
                    break
                self.hit(self.p, mv['dmg'], src=e)
        for k, n in mv.get('self', []):
            e.st[k] = e.st.get(k, 0) + n
            self.float(e, f'{STATUS[k][0]} +{n}')
            self.sfx.play('buff')
        if 'allstr' in mv:
            for o in self.alive():
                o.st['str'] = o.st.get('str', 0) + mv['allstr']
                self.float(o, f'STR +{mv["allstr"]}')
            self.sfx.play('buff')
        if 'heal' in mv:
            self.heal(mv['heal'], e)
        for k, n in mv.get('you', []):
            self.apply(self.p, k, n, src_player=False)
        for k, n, pile in mv.get('add', []):
            for _ in range(n):
                self.add_card(k, pile)
            self.float(self.p, f'+{n} {k}', BLOOD)
        if 'summon' in mv:
            for _ in range(2):
                if len(self.alive()) < 3:
                    ne = Enemy(mv['summon'], self.sprites)
                    self.enemies.insert(0, ne)
                    self.choose_intent(ne)
            self.enemies = [o for o in self.enemies if not o.dead or o.die_t > 0]
            self.layout_enemies()
        if e.dead:
            return
        if e.st.get('plated'):
            self.add_block(e.st['plated'], e)
        for k in ('weak', 'vuln', 'frail'):
            if e.st.get(k):
                e.st[k] -= 1
                if not e.st[k]:
                    del e.st[k]
        self.choose_intent(e)

    # -------------------------------------------------------------- playing cards
    def playable(self, c):
        if c.d.get('unplay'):
            return False
        return c.cost == -1 or self.energy >= c.cost

    def needs_target(self, c):
        return c.d['tgt'] == 'one'

    def play_card(self, c, target=None):
        if self.phase != 'player' or c not in self.hand:
            return False
        if not self.playable(c):
            self.sfx.play('no')
            self.flash_msg('NOT ENOUGH ENERGY' if not c.d.get('unplay') else 'UNPLAYABLE')
            return False
        if self.needs_target(c):
            if target is None or target.dead:
                return False
        self.hand.remove(c)
        if c.cost == -1:
            self.X = self.energy
            self.energy = 0
        else:
            self.energy -= c.cost
        self.sfx.play('card')
        if c.type == 'atk':
            self.quill += 1
            self.quill_on = self.has('INK QUILL') and self.quill % 10 == 0
            self.attacks_turn += 1
            self.p.lunge = 10
        c.d['fx'](self, c, target)
        self.quill_on = False
        if c.type == 'atk' and self.has('IRON NAIL') and self.attacks_turn % 3 == 0:
            self.buff('str', 1)
        if c.type == 'skl':
            for e in self.alive():
                if e.st.get('enrage'):
                    e.st['str'] = e.st.get('str', 0) + e.st['enrage']
                    self.float(e, f'STR +{e.st["enrage"]}')
        if c.type == 'pow':
            pass
        elif c.exhausts:
            self.exhaust(c)
        else:
            self.disc.append(c)
        self.sel = None
        return True

    def use_potion(self, i, target=None):
        k = self.potions[i]
        if k is None:
            return False
        tgt = POTIONS[k][0]
        in_combat = self.state == 'combat' and self.phase == 'player'
        if not in_combat and k != 'BLOOD DRAUGHT':
            self.flash_msg('ONLY IN COMBAT')
            self.sfx.play('no')
            return False
        if tgt == 'one' and (target is None or target.dead):
            return False
        self.potions[i] = None
        self.potsel = None
        if k == 'BLOOD DRAUGHT':
            self.heal(self.p.maxhp // 4)
        elif k == 'FIRE FLASK':
            self.hit(target, 20, attack=False)
        elif k == 'IRON TONIC':
            self.add_block(12)
        elif k == 'WRATH TONIC':
            self.buff('str', 2)
        elif k == 'SWIFT TONIC':
            self.draw_cards(3)
        elif k == 'SPIRIT':
            self.energy += 2
        elif k == 'VENOM':
            self.apply(target, 'poison', 7)
        elif k == 'HEX FLASK':
            self.apply(target, 'vuln', 3)
        return True

    # -------------------------------------------------------------- after combat
    def win_combat(self):
        p = self.p
        if self.has('BURIAL SHROUD'):
            self.heal(6)
        if self.has('CARRION') and p.hp * 2 <= p.maxhp:
            self.heal(12)
        self.p.st = {}
        self.p.block = 0
        lines = []
        if self.boss:
            g = self.gain_gold(random.randint(90, 110))
        elif self.elite:
            g = self.gain_gold(random.randint(25, 35))
        else:
            g = self.gain_gold(random.randint(10, 20))
        if g:
            lines.append(f'{g} GOLD')
        if self.elite:
            r = self.random_relic()
            if r:
                self.gain_relic(r)
                lines.append(f'RELIC: {r}')
        if not self.boss and random.random() < (0.5 if self.elite else 0.4):
            k = random.choice(list(POTIONS))
            if self.gain_potion(k):
                lines.append(f'POTION: {k}')
        self.reward_lines = lines
        self.reward_cards = self.card_choices(3, self.elite, self.boss)
        self.reward_next = 'bossrelic' if self.boss else 'map'
        self.state = 'reward'
        self.sel = 0

    def take_reward(self, i):
        if i is not None and 0 <= i < len(self.reward_cards):
            self.deck.append(self.reward_cards[i])
            self.sfx.play('card')
        else:
            self.sfx.play('click')
        if self.reward_next == 'bossrelic':
            if self.act == 2:
                self.wins += 1
                self.save_int('wins', self.wins)
                self.state = 'won'
                self.end_t = 0
                self.sfx.play('toll')
                return
            pool = self.relic_pool['boss'][:]
            random.shuffle(pool)
            self.boss_choices = pool[:3]
            self.state = 'bossrelic'
            self.sel = 0
        elif self.reward_next == 'event':
            self.state = 'event_done'
        else:
            self.state = 'map'

    def pick_boss_relic(self, i):
        if i is not None and i < len(self.boss_choices):
            self.gain_relic(self.boss_choices[i])
        self.act += 1
        self.p.hp += int((self.p.maxhp - self.p.hp) * 0.75)
        self.fights = 0
        self.gen_map()
        self.state = 'map'
        self.sfx.play('toll')

    # -------------------------------------------------------------- rest, shop, chest
    def rest_options(self):
        return [('REST', 'HEAL 30% OF YOUR MAX HP.', not self.has('BLACK CANDLE')),
                ('HONE', 'UPGRADE A CARD IN YOUR DECK.', any(c.upgradable for c in self.deck))]

    def do_rest(self, i):
        opts = self.rest_options()
        if not opts[i][2]:
            self.sfx.play('no')
            return
        if i == 0:
            self.heal(int(self.p.maxhp * 0.3))
            self.state = 'map'
        else:
            self.open_picker('UPGRADE A CARD', lambda c: c.upgradable, self.upgrade_card,
                             cancel=True, preview_up=True)

    def upgrade_card(self, c):
        c.up = True
        self.sfx.play('buff')
        self.state = 'map'

    def open_shop(self):
        self.state = 'shop'
        mult = 1 + 0.05 * self.act
        self.shop = []
        cards = self.card_choices(5)
        for c in cards:
            base = {'common': 50, 'uncommon': 75, 'rare': 150}[c.d['rar']]
            self.shop.append(['card', c, int(base * mult * random.uniform(0.9, 1.1)), False])
        for j in range(2):
            r = self.random_relic(skip=j)
            if r and r not in [it[1] for it in self.shop]:
                base = {'common': 150, 'uncommon': 220, 'rare': 290}[RELICS[r][0]]
                self.shop.append(['relic', r, int(base * random.uniform(0.95, 1.05)), False])
        for k in random.sample(list(POTIONS), 2):
            self.shop.append(['potion', k, random.randint(48, 70), False])
        self.shop.append(['remove', None, 75 + 25 * self.removals, False])
        self.sel = 0

    def shop_rects(self):
        rects = []
        cards = [s for s in self.shop if s[0] == 'card']
        x0 = (W - len(cards) * 62 + 6) // 2
        i = 0
        for s in self.shop:
            if s[0] == 'card':
                rects.append(pygame.Rect(x0 + i * 62, 30, CW, CH))
                i += 1
        others = [s for s in self.shop if s[0] != 'card']
        x0 = (W - len(others) * 74 + 4) // 2
        for j, s in enumerate(others):
            rects.append(pygame.Rect(x0 + j * 74, 136, 70, 34))
        return rects

    def buy(self, i):
        if not (0 <= i < len(self.shop)):
            return
        kind, item, price, sold = self.shop[i]
        if sold:
            return
        if self.gold < price:
            self.sfx.play('no')
            self.flash_msg('NOT ENOUGH GOLD')
            return
        if kind == 'potion' and None not in self.potions:
            self.sfx.play('no')
            self.flash_msg('POTION SLOTS FULL')
            return
        if kind == 'remove':
            def done(c):
                self.deck.remove(c)
                self.gold -= price
                self.removals += 1
                self.shop[i][3] = True
                self.sfx.play('coin')
                self.state = 'shop'
            self.open_picker('REMOVE A CARD', lambda c: True, done, cancel=True, back='shop')
            return
        self.gold -= price
        self.sfx.play('coin')
        if kind == 'card':
            self.deck.append(item)
        elif kind == 'relic':
            self.gain_relic(item)
        elif kind == 'potion':
            self.gain_potion(item)
        self.shop[i][3] = True

    def open_chest(self):
        r = self.random_relic()
        lines = []
        if r:
            self.gain_relic(r)
            lines.append(f'RELIC: {r}')
            lines.append(RELICS[r][1])
        g = self.gain_gold(random.randint(25, 50))
        if g:
            lines.append(f'{g} GOLD')
        self.chest_lines = lines
        self.state = 'chest'

    # -------------------------------------------------------------- deck picker
    def open_picker(self, title, filt, on_pick, cancel=True, preview_up=False, back=None, cards=None):
        src = cards if cards is not None else self.deck
        self.picker = dict(title=title, cards=[c for c in src if filt(c)], pick=on_pick,
                           cancel=cancel, up=preview_up, back=back or self.state, scroll=0, sel=0)
        if not self.picker['cards']:
            self.flash_msg('NO CARDS')
            return
        self.overlay = 'picker'

    def view_pile(self, cards, title):
        cs = sorted(cards, key=lambda c: (c.type, c.key)) if title != 'DISCARD PILE' else cards
        self.picker = dict(title=title, cards=list(cs), pick=None, cancel=True, up=False,
                           back=self.state, scroll=0, sel=0)
        self.overlay = 'picker'

    def picker_rects(self):
        pk = self.picker
        out = []
        for i in range(len(pk['cards'])):
            col, row = i % 6, i // 6
            out.append(pygame.Rect(17 + col * 62, 26 + row * 86 - pk['scroll'], CW, CH))
        return out

    def picker_choose(self, i):
        pk = self.picker
        if pk['pick'] is None or not (0 <= i < len(pk['cards'])):
            return
        self.overlay = None
        pk['pick'](pk['cards'][i])

    # -------------------------------------------------------------- events
    def open_event(self):
        opts = [e for e in EVENTS if e not in self.seen_events] or EVENTS
        ev = random.choice(opts)
        self.seen_events.append(ev)
        self.event = ev
        self.event_result = None
        self.sel = 0
        self.state = 'event'

    def event_data(self):
        p = self.p
        ev = self.event
        if ev == 'STATUE':
            return ('A WEEPING STATUE', 'A SAINT OF BLACK STONE WEEPS SOMETHING THICKER THAN TEARS. '
                    'COINS GLINT IN THE CRACKS OF HER ROBE.', [
                        ('PRAY: HEAL 25% OF YOUR MAX HP.', True),
                        ('PRY OUT THE COINS: GAIN 85 GOLD. BECOME CURSED: GUILT.', True),
                        ('LEAVE.', True)])
        if ev == 'FONT':
            return ('THE BLOOD FONT', 'A BASIN OF STILL RED WATER. SOMETHING RESTS AT THE BOTTOM, '
                    'AND THE WATER WANTS SOMETHING BACK.', [
                        ('BLEED INTO IT: LOSE 12 HP. GAIN A RELIC.', p.hp > 12),
                        ('DRINK: RAISE MAX HP BY 6.', True),
                        ('LEAVE.', True)])
        if ev == 'PILGRIM':
            return ('A DYING PILGRIM', 'AN OLD PILGRIM LIES AGAINST A PILLAR, A FAT PURSE ON HIS BELT. '
                    'HE ASKS YOU TO HEAR HIS LAST CONFESSION.', [
                        ('LISTEN: REMOVE A CARD FROM YOUR DECK.', len(self.deck) > 1),
                        ('TAKE THE PURSE: GAIN 100 GOLD. BECOME CURSED: DOUBT.', True),
                        ('LEAVE.', True)])
        if ev == 'MIRROR':
            return ('THE BLACK MIRROR', 'YOUR REFLECTION MOVES A MOMENT AFTER YOU DO. IT OFFERS '
                    'TO TRADE PLACES WITH ONE OF YOUR MEMORIES.', [
                        ('GAZE: DUPLICATE A CARD IN YOUR DECK.', True),
                        ('SHATTER IT: UPGRADE 2 RANDOM CARDS. LOSE 7 HP.', p.hp > 7),
                        ('LEAVE.', True)])
        if ev == 'DICE':
            return ('THE BONE DICE', 'A HOODED FIGURE ROLLS KNUCKLEBONES IN THE DARK. "DOUBLE OR '
                    'NOTHING, WANDERER? THE DEAD ARE SPORTING."', [
                        (f'WAGER {min(self.gold, 50)} GOLD: HALF THE TIME, WIN TWICE THAT.', self.gold >= 10),
                        ('WAGER BLOOD: LOSE 6 HP. HALF THE TIME, GAIN A RARE CARD.', p.hp > 6),
                        ('LEAVE.', True)])
        if ev == 'CRYPT':
            return ('A SEALED CRYPT', 'A TOMB WITH ITS SEAL HALF BROKEN. SOMETHING SCRATCHES '
                    'AT THE INSIDE OF THE LID.', [
                        ('OPEN IT: FIGHT. AN ELITE\'S SPOILS IF YOU WIN.', True),
                        ('SEARCH THE OFFERINGS: GAIN A POTION AND 30 GOLD.', True),
                        ('LEAVE.', True)])
        if ev == 'LIBRARY':
            return ('THE DROWNED LIBRARY', 'SODDEN BOOKS LINE THE WALLS. A FEW ARE STILL LEGIBLE, '
                    'IF YOU HAVE THE PATIENCE.', [
                        ('READ: CHOOSE ONE OF 4 CARDS.', True),
                        ('SLEEP: HEAL 33% OF YOUR MAX HP.', True),
                        ('LEAVE.', True)])
        return ('THE ASH ALTAR', 'AN ALTAR HEAPED WITH THE ASH OF OFFERINGS. FIRE STILL '
                'BREATHES SOMEWHERE BENEATH IT.', [
                    ('BURN AN OFFERING: REMOVE A CARD. GAIN 50 GOLD.', len(self.deck) > 1),
                    ('KNEEL: UPGRADE A CARD. LOSE 5 HP.', p.hp > 5 and any(c.upgradable for c in self.deck)),
                    ('LEAVE.', True)])

    def event_choose(self, i):
        title, text, opts = self.event_data()
        if not (0 <= i < len(opts)) or not opts[i][1]:
            self.sfx.play('no')
            return
        p = self.p
        ev = self.event
        res = None
        self.sfx.play('click')
        if i == len(opts) - 1:
            self.state = 'map'
            return
        if ev == 'STATUE':
            if i == 0:
                self.heal(p.maxhp // 4)
                res = 'THE STONE IS WARM. YOUR WOUNDS CLOSE.'
            else:
                self.gain_gold(85)
                self.deck.append(Card('GUILT'))
                res = 'THE STATUE STOPS WEEPING. YOU FEEL HER WATCH YOU LEAVE.'
        elif ev == 'FONT':
            if i == 0:
                self.lose_hp_out(12)
                r = self.random_relic()
                if r:
                    self.gain_relic(r)
                res = f'THE WATER GIVES UP ITS SECRET: {r}.' if r else 'THE BASIN IS EMPTY.'
            else:
                p.maxhp += 6
                p.hp += 6
                res = 'IT TASTES OF IRON. YOU FEEL STRONGER.'
        elif ev == 'PILGRIM':
            if i == 0:
                self.open_picker('REMOVE A CARD', lambda c: True, self.event_remove, cancel=False)
                return
            self.gain_gold(100)
            self.deck.append(Card('DOUBT'))
            res = 'HIS EYES FOLLOW YOU UNTIL THEY DO NOT.'
        elif ev == 'MIRROR':
            if i == 0:
                self.open_picker('DUPLICATE A CARD', lambda c: True, self.event_dup, cancel=False)
                return
            self.lose_hp_out(7)
            cands = [c for c in self.deck if c.upgradable]
            for c in random.sample(cands, min(2, len(cands))):
                c.up = True
            res = 'SHARDS FLY. SOME OF YOUR MEMORIES SHARPEN.'
        elif ev == 'DICE':
            if i == 0:
                bet = min(self.gold, 50)
                if random.random() < 0.5:
                    self.gold += bet
                    self.sfx.play('coin')
                    res = f'THE BONES FALL KIND. YOU WIN {bet} GOLD.'
                else:
                    self.gold -= bet
                    res = f'THE BONES FALL CRUEL. YOU LOSE {bet} GOLD.'
            else:
                self.lose_hp_out(6)
                if random.random() < 0.5:
                    c = Card(random.choice(POOL['rare']))
                    self.deck.append(c)
                    res = f'THE FIGURE NODS AND HANDS YOU {c.name}.'
                else:
                    res = 'THE FIGURE LAUGHS AND KEEPS YOUR BLOOD.'
        elif ev == 'CRYPT':
            if i == 0:
                self.start_combat(random.choice(ENCOUNTERS[self.act]['hard']), elite=True)
                return
            k = random.choice(list(POTIONS))
            got = self.gain_potion(k)
            self.gain_gold(30)
            res = f'YOU FIND {k} AND 30 GOLD.' if got else 'YOU FIND 30 GOLD. YOUR BELT IS FULL.'
        elif ev == 'LIBRARY':
            if i == 0:
                self.reward_lines = []
                self.reward_cards = self.card_choices(4)
                self.reward_next = 'map'
                self.state = 'reward'
                self.sel = 0
                return
            self.heal(p.maxhp // 3)
            res = 'YOU WAKE WITH INK ON YOUR FACE, RESTED.'
        elif ev == 'ALTAR':
            if i == 0:
                self.open_picker('BURN A CARD', lambda c: True, self.event_burn, cancel=False)
                return
            self.lose_hp_out(5)
            self.open_picker('UPGRADE A CARD', lambda c: c.upgradable, self.event_up,
                             cancel=False, preview_up=True)
            return
        self.event_result = res
        self.state = 'event_done'

    def lose_hp_out(self, n):
        self.p.hp = max(1, self.p.hp - n)
        self.sfx.play('hurt')

    def event_remove(self, c):
        self.deck.remove(c)
        self.event_result = 'YOU LISTEN UNTIL THE END. SOMETHING IN YOU IS LIGHTER.'
        self.state = 'event_done'

    def event_dup(self, c):
        self.deck.append(Card(c.key, c.up))
        self.event_result = f'THE MIRROR HANDS YOU A SECOND {c.name}.'
        self.state = 'event_done'

    def event_burn(self, c):
        self.deck.remove(c)
        self.gain_gold(50)
        self.event_result = f'{c.name} CURLS INTO ASH. COINS GLITTER IN THE EMBERS.'
        self.state = 'event_done'

    def event_up(self, c):
        c.up = True
        self.event_result = f'THE FIRE TEMPERS {c.key}.'
        self.state = 'event_done'

    # -------------------------------------------------------------- update
    def update(self):
        self.t += 1
        if self.msg_t:
            self.msg_t -= 1
        for f in self.floats:
            f[1] -= 0.35
            f[4] -= 1
        self.floats = [f for f in self.floats if f[4] > 0]
        if self.state == 'won' or self.state == 'dead':
            self.end_t += 1
        if self.state != 'combat' or self.paused:
            return
        units = [self.p] + self.enemies
        for u in units:
            u.shake = max(0, u.shake - 1)
            u.flash = max(0, u.flash - 1)
            u.lunge = max(0, u.lunge - 1)
        for e in self.enemies:
            if e.dead and e.die_t > 0:
                e.die_t -= 1
        if self.phase == 'enemy':
            self.ptimer -= 1
            if self.ptimer <= 0:
                while self.equeue and self.equeue[0].dead:
                    self.equeue.pop(0)
                if self.equeue:
                    self.enemy_act(self.equeue.pop(0))
                    self.ptimer = 26
                    if self.phase == 'enemy' and not self.alive():
                        self.phase = 'victory'
                        self.ptimer = 50
                elif self.phase == 'enemy':
                    self.start_player_turn()
        elif self.phase == 'victory':
            self.ptimer -= 1
            if self.ptimer <= 0 and not self.victory_done:
                self.victory_done = True
                self.win_combat()
        elif self.phase == 'defeat':
            self.ptimer -= 1
            if self.ptimer <= 0:
                self.state = 'dead'
                self.end_t = 0
        # hand animation
        for c, (x, y) in zip(self.hand, self.hand_layout()):
            if c.x is None:
                c.x, c.y = x, y
            c.x += (x - c.x) * 0.3
            c.y += (y - c.y) * 0.3

    # -------------------------------------------------------------- layout helpers
    def hand_layout(self):
        n = len(self.hand)
        if not n:
            return []
        span = min(n * (CW + 2) - 2, 296)
        step = (span - CW) / (n - 1) if n > 1 else 0
        x0 = 200 - span / 2
        hov = self.hand_hover()
        out = []
        for i, c in enumerate(self.hand):
            y = HAND_UP if (i == hov or c is self.sel) and self.drag is None else HAND_Y
            out.append((x0 + i * step, y))
        return out

    def hand_hover(self):
        if self.state != 'combat' or self.overlay:
            return None
        mx, my = self.mouse
        n = len(self.hand)
        if not n or my < HAND_UP:
            return None
        span = min(n * (CW + 2) - 2, 296)
        step = (span - CW) / (n - 1) if n > 1 else 0
        x0 = 200 - span / 2
        for i in range(n - 1, -1, -1):
            if x0 + i * step <= mx < x0 + i * step + CW:
                return i
        return None

    def enemy_at(self, pos):
        for e in self.alive():
            if e.rect().inflate(8, 16).collidepoint(pos):
                return e
        return None

    def potion_rect(self, i):
        return pygame.Rect(118 + i * 11, 1, 10, 10)

    def relic_rect(self, i):
        return pygame.Rect(156 + i * 10, 1, 9, 10)

    def end_rect(self):
        return pygame.Rect(352, 168, 46, 14)

    # -------------------------------------------------------------- input
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
            return
        if ev.type == pygame.MOUSEWHEEL and self.overlay == 'picker':
            self.scroll_picker(-ev.y * 20)
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
        if self.state in ('title', 'dead', 'won'):
            self.handle_end(ev)
            return
        if self.paused:
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    self.paused = False
                elif ev.key == pygame.K_q:
                    self.paused = False
                    self.state = 'title'
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                self.paused = False
            return
        if self.overlay == 'picker':
            self.handle_picker(ev)
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            if self.state == 'combat' and self.aiming:
                self.aiming = False
            elif self.state == 'combat' and (self.sel is not None or self.potsel is not None):
                self.sel = self.potsel = None
            else:
                self.paused = True
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_v and not (self.state == 'combat'):
            self.view_pile(self.deck, 'YOUR DECK')
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i in range(3):
                if self.potion_rect(i).collidepoint(ev.pos) and self.potions[i]:
                    self.select_potion(i)
                    return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3 and self.state != 'combat':
            for i in range(3):
                if self.potion_rect(i).collidepoint(ev.pos) and self.potions[i]:
                    self.potions[i] = None
                    self.sfx.play('click')
                    return
        getattr(self, 'handle_' + self.state.split('_')[0])(ev)

    def handle_end(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE and self.state == 'title':
                pygame.quit()
                sys.exit()
            if ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_e):
                if self.state == 'title':
                    self.new_run()
                elif self.end_t > 50:
                    self.state = 'title'
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.state == 'title':
                self.new_run()
            elif self.end_t > 50:
                self.state = 'title'

    def select_potion(self, i):
        k = self.potions[i]
        if k is None:
            return
        if self.state == 'combat' and self.phase == 'player' and POTIONS[k][0] == 'one':
            self.potsel = i
            self.sel = None
            a = self.alive()
            self.tsel = min(self.tsel, len(a) - 1) if a else 0
            self.sfx.play('click')
        else:
            self.use_potion(i)

    def keyboard_cycle(self, key, n):
        if key in (pygame.K_a, pygame.K_LEFT, pygame.K_w, pygame.K_UP):
            return -1
        if key in (pygame.K_d, pygame.K_RIGHT, pygame.K_s, pygame.K_DOWN, pygame.K_TAB):
            return 1
        return 0

    def is_confirm(self, key):
        return key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e)

    def handle_map(self, ev):
        opts = self.reachable()
        if not opts:
            return
        if ev.type == pygame.KEYDOWN:
            d = self.keyboard_cycle(ev.key, len(opts))
            if d:
                self.msel = (self.msel + d) % len(opts)
                self.sfx.play('click')
            elif self.is_confirm(ev.key):
                self.enter_node(opts[self.msel % len(opts)])
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for n in opts:
                x, y = self.node_xy(n)
                r = 12 if n == 'boss' else 7
                if abs(ev.pos[0] - x) <= r and abs(ev.pos[1] - y) <= r:
                    self.enter_node(n)
                    return

    def handle_combat(self, ev):
        if self.phase != 'player':
            return
        alive = self.alive()
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_SPACE:
                self.end_turn()
                return
            if k == pygame.K_q:
                self.view_pile(self.drawp, 'DRAW PILE')
                return
            if k == pygame.K_w:
                self.view_pile(self.disc, 'DISCARD PILE')
                return
            if k in (pygame.K_z, pygame.K_x, pygame.K_c):
                self.select_potion({pygame.K_z: 0, pygame.K_x: 1, pygame.K_c: 2}[k])
                return
            d = -1 if k in (pygame.K_a, pygame.K_LEFT) else 1 if k in (pygame.K_d, pygame.K_RIGHT) else 0
            if d:
                if (self.aiming or self.potsel is not None) and alive:
                    self.tsel = (self.tsel + d) % len(alive)
                elif self.hand:
                    if self.sel in self.hand:
                        i = (self.hand.index(self.sel) + d) % len(self.hand)
                    else:
                        i = min(self.kidx, len(self.hand) - 1) if d > 0 else max(0, min(self.kidx, len(self.hand)) - 1)
                    self.pick_card(self.hand[i])
                self.sfx.play('click')
                return
            if k in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm_play()
                return
            idx = None
            if pygame.K_1 <= k <= pygame.K_9:
                idx = k - pygame.K_1
            elif k == pygame.K_0:
                idx = 9
            if idx is not None and idx < len(self.hand):
                c = self.hand[idx]
                if self.sel is c:
                    self.confirm_play()
                else:
                    self.pick_card(c)
                    self.sfx.play('click')
            return
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 3:
                self.sel = self.potsel = None
                self.drag = None
                self.aiming = False
                return
            if ev.button != 1:
                return
            if self.end_rect().collidepoint(ev.pos):
                self.end_turn()
                return
            if pygame.Rect(0, 196, 26, 28).collidepoint(ev.pos):
                self.view_pile(self.drawp, 'DRAW PILE')
                return
            if pygame.Rect(374, 196, 26, 28).collidepoint(ev.pos):
                self.view_pile(self.disc, 'DISCARD PILE')
                return
            hov = self.hand_hover()
            if hov is not None:
                c = self.hand[hov]
                self.pick_card(c)
                self.drag = (c, ev.pos)
                self.sfx.play('click')
                return
            e = self.enemy_at(ev.pos)
            if self.potsel is not None:
                if e:
                    self.use_potion(self.potsel, e)
                return
            if self.sel is not None and ev.pos[1] < FIELD_Y:
                if self.needs_target(self.sel):
                    if e:
                        self.play_card(self.sel, e)
                else:
                    self.play_card(self.sel)
            return
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.drag:
            c, start = self.drag
            self.drag = None
            moved = abs(ev.pos[0] - start[0]) + abs(ev.pos[1] - start[1]) > 6
            if moved and ev.pos[1] < FIELD_Y and c in self.hand:
                if self.needs_target(c):
                    e = self.enemy_at(ev.pos)
                    if e:
                        self.play_card(c, e)
                else:
                    self.play_card(c)

    def confirm_play(self):
        alive = self.alive()
        if self.potsel is not None:
            if alive:
                self.use_potion(self.potsel, alive[self.tsel % len(alive)])
            return
        if self.sel is None or self.sel not in self.hand:
            if self.hand:
                self.pick_card(self.hand[min(self.kidx, len(self.hand) - 1)])
            return
        c = self.sel
        if self.needs_target(c) and len(alive) > 1 and not self.aiming:
            if not self.playable(c):
                self.play_card(c)   # explains why not
                return
            self.aiming = True
            self.tsel = min(self.tsel, len(alive) - 1)
            self.sfx.play('click')
            return
        t = alive[self.tsel % len(alive)] if alive and self.needs_target(c) else None
        i = self.hand.index(c)
        if self.play_card(c, t):
            self.kidx = i
        self.aiming = False

    def pick_card(self, c):
        self.sel = c
        self.potsel = None
        self.aiming = False
        self.kidx = self.hand.index(c)
        a = self.alive()
        if a:
            self.tsel = min(self.tsel, len(a) - 1)

    def handle_reward(self, ev):
        n = len(self.reward_cards)
        if ev.type == pygame.KEYDOWN:
            d = self.keyboard_cycle(ev.key, n + 1)
            if d:
                self.sel = (self.sel + d) % (n + 1)
                self.sfx.play('click')
            elif self.is_confirm(ev.key):
                self.take_reward(self.sel if self.sel < n else None)
            elif pygame.K_1 <= ev.key < pygame.K_1 + n:
                self.take_reward(ev.key - pygame.K_1)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, r in enumerate(self.reward_rects()):
                if r.collidepoint(ev.pos):
                    self.take_reward(i if i < n else None)
                    return

    def reward_rects(self):
        n = len(self.reward_cards)
        cw = CW * 2 if n <= 3 else int(CW * 1.5)
        ch = CH * 2 if n <= 3 else int(CH * 1.5)
        gap = 10
        x0 = (W - n * cw - (n - 1) * gap) // 2
        y0 = 34 if n <= 3 else 56
        rects = [pygame.Rect(x0 + i * (cw + gap), y0, cw, ch) for i in range(n)]
        rects.append(pygame.Rect(W // 2 - 24, 206, 48, 12))
        return rects

    def handle_bossrelic(self, ev):
        n = len(self.boss_choices)
        if ev.type == pygame.KEYDOWN:
            d = self.keyboard_cycle(ev.key, n + 1)
            if d:
                self.sel = (self.sel + d) % (n + 1)
                self.sfx.play('click')
            elif self.is_confirm(ev.key):
                self.pick_boss_relic(self.sel if self.sel < n else None)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, r in enumerate(self.boss_rects()):
                if r.collidepoint(ev.pos):
                    self.pick_boss_relic(i if i < n else None)
                    return

    def boss_rects(self):
        rects = [pygame.Rect(40, 60 + i * 34, 320, 30) for i in range(len(self.boss_choices))]
        rects.append(pygame.Rect(W // 2 - 24, 200, 48, 12))
        return rects

    def handle_rest(self, ev):
        if ev.type == pygame.KEYDOWN:
            d = self.keyboard_cycle(ev.key, 2)
            if d:
                self.sel = (self.sel + d) % 2
                self.sfx.play('click')
            elif self.is_confirm(ev.key):
                self.do_rest(self.sel)
            elif ev.key in (pygame.K_1, pygame.K_2):
                self.do_rest(ev.key - pygame.K_1)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, r in enumerate(self.rest_rects()):
                if r.collidepoint(ev.pos):
                    self.do_rest(i)

    def rest_rects(self):
        return [pygame.Rect(90 + i * 120, 90, 100, 60) for i in range(2)]

    def handle_shop(self, ev):
        n = len(self.shop)
        if ev.type == pygame.KEYDOWN:
            d = self.keyboard_cycle(ev.key, n + 1)
            if d:
                self.sel = (self.sel + d) % (n + 1)
                self.sfx.play('click')
            elif self.is_confirm(ev.key):
                if self.sel == n:
                    self.state = 'map'
                else:
                    self.buy(self.sel)
            elif ev.key == pygame.K_l:
                self.state = 'map'
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, r in enumerate(self.shop_rects()):
                if r.collidepoint(ev.pos):
                    self.buy(i)
                    return
            if self.leave_rect().collidepoint(ev.pos):
                self.state = 'map'

    def leave_rect(self):
        return pygame.Rect(W // 2 - 26, 200, 52, 12)

    def handle_chest(self, ev):
        if (ev.type == pygame.KEYDOWN and self.is_confirm(ev.key)) or \
                (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
            self.state = 'map'

    def event_rects(self):
        _, _, opts = self.event_data()
        return [pygame.Rect(40, 120 + i * 16, 320, 13) for i in range(len(opts))]

    def handle_event(self, ev):
        if self.state == 'event_done':
            if (ev.type == pygame.KEYDOWN and self.is_confirm(ev.key)) or \
                    (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
                self.state = 'map'
            return
        _, _, opts = self.event_data()
        if ev.type == pygame.KEYDOWN:
            d = self.keyboard_cycle(ev.key, len(opts))
            if d:
                self.sel = (self.sel + d) % len(opts)
                self.sfx.play('click')
            elif self.is_confirm(ev.key):
                self.event_choose(self.sel)
            elif pygame.K_1 <= ev.key < pygame.K_1 + len(opts):
                self.event_choose(ev.key - pygame.K_1)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, r in enumerate(self.event_rects()):
                if r.collidepoint(ev.pos):
                    self.event_choose(i)

    def scroll_picker(self, d):
        pk = self.picker
        rows = (len(pk['cards']) + 5) // 6
        mx = max(0, rows * 86 - 180)
        pk['scroll'] = max(0, min(mx, pk['scroll'] + d))

    def handle_picker(self, ev):
        pk = self.picker
        n = len(pk['cards'])
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_ESCAPE or (pk['pick'] is None and k in (pygame.K_v, pygame.K_q, pygame.K_w)):
                if pk['cancel']:
                    self.overlay = None
                return
            moves = {pygame.K_a: -1, pygame.K_LEFT: -1, pygame.K_d: 1, pygame.K_RIGHT: 1,
                     pygame.K_w: -6, pygame.K_UP: -6, pygame.K_s: 6, pygame.K_DOWN: 6}
            if k in moves and n:
                pk['sel'] = max(0, min(n - 1, pk['sel'] + moves[k]))
                row = pk['sel'] // 6
                top = row * 86
                if top - pk['scroll'] < 0:
                    pk['scroll'] = top
                elif top - pk['scroll'] > 100:
                    pk['scroll'] = top - 100
                self.sfx.play('click')
            elif self.is_confirm(k):
                self.picker_choose(pk['sel'])
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 3 and pk['cancel']:
                self.overlay = None
                return
            if ev.button != 1:
                return
            if pk['cancel'] and pygame.Rect(W // 2 - 26, 210, 52, 12).collidepoint(ev.pos):
                self.overlay = None
                return
            for i, r in enumerate(self.picker_rects()):
                if r.collidepoint(ev.pos) and 20 < ev.pos[1] < 206:
                    self.picker_choose(i)
                    return

    # -------------------------------------------------------------- drawing: cards
    def card_text(self, c, target=None):
        txt = c.raw_text()

        def rep(m):
            kind, i = m.group(1), int(m.group(2))
            base = c.v[i]
            if kind == 'D':
                if self.state == 'combat':
                    bonus = c.d['bonus'](self, c) if 'bonus' in c.d else 0
                    return str(self.calc_dmg(self.p, target, base + bonus))
                return str(base)
            if kind == 'B':
                return str(self.calc_blk(base)) if self.state == 'combat' else str(base)
            return str(base)
        return re.sub(r'\{([DB]?)(\d)\}', rep, txt)

    def render_card(self, c, target=None, playable=True):
        text = self.card_text(c, target)
        cost = c.cost
        key = (c.key, c.up, text, cost, playable)
        s = self.card_cache.get(key)
        if s is not None:
            return s
        if len(self.card_cache) > 400:
            self.card_cache.clear()
        s = pygame.Surface((CW, CH))
        s.fill(BLACK)
        rar = c.d['rar']
        edge = BLOOD if rar == 'rare' or c.type == 'curse' else BONE
        pygame.draw.rect(s, edge, s.get_rect(), 1)
        if rar in ('uncommon', 'rare'):
            pygame.draw.rect(s, edge, s.get_rect().inflate(-4, -4), 1)
        # art panel
        art = pygame.Rect(5, 20, CW - 10, 17)
        pygame.draw.rect(s, BONE, art)
        s.blit(dither_surface(art.w, art.h, True), art.topleft)
        pygame.draw.rect(s, BONE, art, 1)
        ic = {'atk': 'atk', 'skl': 'blk', 'pow': 'buf', 'status': 'deb', 'curse': 'elite'}[c.type]
        big = icon_surf(ic, 2, BLOOD if c.type in ('pow', 'curse') else BONE)
        s.blit(big, (CW // 2 - 9, 20 - 1))
        # cost
        if not c.d.get('unplay'):
            pygame.draw.circle(s, BLOOD if playable else BLACK, (7, 7), 6)
            pygame.draw.circle(s, BONE, (7, 7), 6, 1)
            draw_text(s, 'X' if cost == -1 else str(cost), 7, 5, 1, 'c', BONE, False)
        draw_text(s, TYPE_NAME[c.type], CW - 4, 4, 1, 'r', BONE if c.type != 'curse' else BLOOD, False)
        draw_text(s, c.name, CW // 2, 13, 1, 'c', BLOOD if c.up else BONE, False)
        for i, line in enumerate(wrap(text, 13)[:6]):
            draw_text(s, line, CW // 2, 41 + i * 6, 1, 'c', BONE, False)
        if not playable:
            s.blit(dither_surface(CW, CH), (0, 0))
        self.card_cache[key] = s
        return s

    def keyword_tips(self, c):
        txt = c.raw_text() + (' ' + 'ETHEREAL' if c.d.get('eth') else '')
        if c.cost == -1:
            txt += ' X '
        tips = [v for k, v in KEYWORDS.items() if k in txt]
        return tips[:4]

    # -------------------------------------------------------------- drawing
    def draw_panel(self, r, fill=BLACK, border=BONE):
        pygame.draw.rect(self.screen, fill, r)
        pygame.draw.rect(self.screen, border, r, 1)

    def draw_tip(self, x, y, lines, width=28):
        out = []
        for l in lines:
            out += wrap(l, width) + ['']
        out = out[:-1]
        w = max(len(l) for l in out) * 4 + 7 if out else 10
        h = len(out) * 7 + 5
        x = max(2, min(W - w - 2, x))
        y = max(2, min(H - h - 2, y))
        self.draw_panel(pygame.Rect(x, y, w, h))
        for i, l in enumerate(out):
            draw_text(self.screen, l, x + 4, y + 3 + i * 7, 1, 'l', BONE, False)

    def draw_topbar(self):
        s = self.screen
        s.fill(BLACK, (0, 0, W, 12))
        pygame.draw.line(s, BONE, (0, 12), (W, 12))
        draw_text(s, f'HP {self.p.hp}/{self.p.maxhp}', 4, 4, 1, 'l', BLOOD)
        draw_text(s, f'GOLD {self.gold}', 62, 4, 1, 'l', BONE)
        for i in range(3):
            r = self.potion_rect(i)
            k = self.potions[i]
            pygame.draw.rect(s, BONE, r, 1)
            if k:
                pygame.draw.rect(s, BLOOD if self.potsel == i else BONE, r.inflate(-4, -4))
                pygame.draw.rect(s, BLOOD, (r.x + 3, r.y + 3, 4, 4))
        for i, rl in enumerate(self.relics):
            r = self.relic_rect(i)
            if r.right > 362:
                break
            col = BLOOD if RELICS[rl][0] in ('boss', 'rare') else BONE
            pygame.draw.rect(s, col, r)
            draw_text(s, rl[0], r.centerx, r.y + 3, 1, 'c', BLACK, False)
        draw_text(s, f'F{self.floor_no}', 396, 4, 1, 'r', BONE)

    def topbar_tip(self):
        mx, my = self.mouse
        if my > 12:
            return None
        for i in range(3):
            if self.potion_rect(i).collidepoint(self.mouse) and self.potions[i]:
                k = self.potions[i]
                hint = 'CLICK OR Z/X/C TO DRINK.' if self.state == 'combat' else 'RIGHT CLICK TO DISCARD.'
                return [k, POTIONS[k][1], hint]
        for i, rl in enumerate(self.relics):
            if self.relic_rect(i).collidepoint(self.mouse):
                return [rl, RELICS[rl][1]]
        if mx < 56:
            return ['YOUR HEALTH.']
        if mx > 370:
            return [f'ACT {self.act + 1}, FLOOR {self.floor_no}. V VIEWS YOUR DECK ({len(self.deck)} CARDS).']
        return None

    def draw(self):
        s = self.screen
        s.fill(BLACK)
        st = self.state
        if st == 'title':
            self.draw_title()
        elif st in ('dead', 'won'):
            self.draw_end()
        else:
            getattr(self, 'draw_' + st.split('_')[0])()
            self.draw_topbar()
            if self.overlay == 'picker':
                self.draw_picker()
            tip = None if self.overlay else self.topbar_tip()
            if tip:
                self.draw_tip(self.mouse[0] - 40, 15, tip)
            if self.msg_t:
                draw_text(s, self.msg, W // 2, 118, 1, 'c', BLOOD)
            if self.paused:
                s.blit(self.dim2, (0, 0))
                draw_text(s, 'PAUSED', W // 2, 90, 3, 'c', BONE)
                draw_text(s, 'ESC RESUME    Q QUIT TO TITLE', W // 2, 120, 1, 'c', BONE)
        self.draw_cursor()

    def draw_cursor(self):
        mx, my = self.mouse
        pts = [(mx, my), (mx, my + 7), (mx + 2, my + 5), (mx + 5, my + 5)]
        pygame.draw.polygon(self.screen, BLACK, [(mx - 1, my - 2), (mx - 1, my + 9), (mx + 2, my + 7), (mx + 8, my + 6)])
        pygame.draw.polygon(self.screen, BONE, pts)

    def draw_title(self):
        s = self.screen
        for i in range(0, W, 8):
            h = 30 + int(12 * math.sin(i * 0.11 + self.t * 0.01))
            pygame.draw.line(s, BONE, (i, H), (i, H - h), 1) if i % 16 == 0 else None
        s.blit(self.dim, (0, 0))
        draw_text(s, 'RELIQUARY', W // 2, 40, 5, 'c', BONE)
        draw_text(s, 'A DECK OF BONES, A CATHEDRAL OF ASH', W // 2, 72, 1, 'c', BLOOD)
        ks = self.pspr[0]
        s.blit(ks, (W // 2 - ks.get_width() // 2, 88))
        lines = ['CLICK OR DRAG A CARD ONTO A FOE. RIGHT CLICK CANCELS.',
                 'A/D PICK A CARD, E CHOOSES; THEN A/D PICK A FOE, E PLAYS',
                 'SPACE END TURN  Q DRAW PILE  W DISCARD  Z/X/C POTIONS  V DECK',
                 'ESC PAUSE    F11 FULLSCREEN']
        for i, l in enumerate(lines):
            draw_text(s, l, W // 2, 146 + i * 9, 1, 'c', BONE)
        if (self.t // 30) % 2:
            draw_text(s, 'PRESS ENTER OR CLICK TO BEGIN', W // 2, 190, 1, 'c', BLOOD)
        stats = []
        if self.best:
            stats.append(f'HIGHEST FLOOR: {self.best}')
        if self.wins:
            stats.append(f'VICTORIES: {self.wins}')
        if stats:
            draw_text(s, '    '.join(stats), W // 2, 206, 1, 'c', BONE)

    def draw_end(self):
        s = self.screen
        won = self.state == 'won'
        draw_text(s, 'THE RELIQUARY IS YOURS' if won else 'YOU JOIN THE BONES', W // 2, 60, 3, 'c',
                  BONE if won else BLOOD)
        draw_text(s, f'FLOOR {self.floor_no}    ACT {self.act + 1}    DECK {len(self.deck)} CARDS',
                  W // 2, 96, 1, 'c', BONE)
        draw_text(s, f'RELICS: {len(self.relics)}', W // 2, 108, 1, 'c', BONE)
        if won:
            draw_text(s, 'THE PALE KING KNEELS. THE BELLS FALL SILENT.', W // 2, 124, 1, 'c', BONE)
        draw_text(s, f'HIGHEST FLOOR: {self.best}    VICTORIES: {self.wins}', W // 2, 140, 1, 'c', BONE)
        if self.end_t > 50 and (self.t // 30) % 2:
            draw_text(s, 'PRESS ENTER', W // 2, 170, 1, 'c', BLOOD)

    def draw_map(self):
        s = self.screen
        draw_text(s, f'ACT {self.act + 1}: {ACT_NAMES[self.act]}', W // 2, 17, 1, 'c', BLOOD)
        for a, b in self.edges:
            x0, y0 = self.node_xy(a)
            x1, y1 = self.node_xy(b)
            n = int(max(abs(x1 - x0), abs(y1 - y0)) / 3)
            on = a in self.visited and b in self.visited
            for i in range(2, n - 1):
                x = x0 + (x1 - x0) * i / n
                y = y0 + (y1 - y0) * i / n
                s.set_at((int(x), int(y)), BLOOD if on else BONE)
        for n in self.nodes:
            if n[0] == FLOORS - 1:
                x0, y0 = self.node_xy(n)
                x1, y1 = self.node_xy('boss')
                k = int(max(abs(x1 - x0), abs(y1 - y0)) / 3)
                for i in range(2, k - 3):
                    s.set_at((int(x0 + (x1 - x0) * i / k), int(y0 + (y1 - y0) * i / k)), BONE)
        reach = self.reachable()
        cur = reach[self.msel % len(reach)] if reach else None
        hover = None
        for n in sorted(self.nodes):
            x, y = self.node_xy(n)
            t = self.ntype[n]
            ic = self.icons_red[t] if n in self.visited else self.icons[t]
            if n in reach and (self.t // 20) % 2:
                pygame.draw.circle(s, BONE, (x, y), 7, 1)
            if n == cur:
                pygame.draw.circle(s, BLOOD, (x, y), 8, 1)
            s.blit(ic, (x - 4, y - 4))
            if abs(self.mouse[0] - x) <= 7 and abs(self.mouse[1] - y) <= 7:
                hover = t
        x, y = self.node_xy('boss')
        s.blit(self.boss_icon, (x - 9, y - 9))
        if 'boss' in reach:
            pygame.draw.circle(s, BLOOD if cur == 'boss' else BONE, (x, y), 13, 1)
        if abs(self.mouse[0] - x) <= 12 and abs(self.mouse[1] - y) <= 12:
            hover = 'boss'
        names = dict(fight='FOES', elite='ELITE: A DEADLIER FOE GUARDING A RELIC', rest='FIRE: REST OR HONE A CARD',
                     shop='MERCHANT', event='UNKNOWN', chest='RELIQUARY CHEST',
                     boss=f'BOSS: {ENCOUNTERS[self.act]["boss"][0]}')
        draw_text(s, 'A/D PICK A PATH  ENTER GO  V DECK' if not hover else names[hover], W // 2, 212, 1, 'c', BONE)
        x = 34
        for k in ('fight', 'elite', 'rest', 'shop', 'event', 'chest'):
            s.blit(self.icons[k], (x, 196))
            lbl = {'fight': 'FOES', 'elite': 'ELITE', 'rest': 'FIRE', 'shop': 'SHOP', 'event': 'UNKNOWN',
                   'chest': 'CHEST'}[k]
            draw_text(s, lbl, x + 11, 198, 1, 'l', BONE)
            x += 14 + len(lbl) * 4 + 18

    def draw_unit_bar(self, u, x, y, w):
        s = self.screen
        pygame.draw.rect(s, BONE, (x, y, w, 5), 1)
        fill = int((w - 2) * max(0, u.hp) / u.maxhp)
        s.fill(BLOOD, (x + 1, y + 1, fill, 3))
        label = f'{max(0, u.hp)}/{u.maxhp}'
        draw_text(s, label, x + w // 2, y + 7, 1, 'c', BONE)
        if u.block:
            r = pygame.Rect(x - 12, y - 2, 11, 9)
            pygame.draw.rect(s, BONE, r)
            draw_text(s, str(u.block), r.centerx, r.y + 2, 1, 'c', BLACK, False)
        sx = x
        sy = y + 14
        tips = []
        for k, n in u.st.items():
            lab = f'{STATUS[k][0]}{n}' if k not in ('barricade', 'envenom') else STATUS[k][0]
            wlab = len(lab) * 4 + 2
            if sx + wlab > x + w + 18:
                sx = x
                sy += 7
            debuff = STATUS[k][2] or (k in ('str', 'dex') and n < 0)
            draw_text(s, lab, sx, sy, 1, 'l', BLOOD if debuff else BONE)
            if pygame.Rect(sx - 1, sy - 1, wlab, 7).collidepoint(self.mouse):
                tips.append(STATUS[k][1].replace('THAT MUCH', str(n)).replace('THAT MANY', str(n)))
            sx += wlab + 2
        return tips

    def draw_combat(self):
        s = self.screen
        t = self.t
        # floor and pillars
        for x in range(0, W, 2):
            s.set_at((x, 113 + (x // 2) % 2), BONE)
        for px in (20, 128, 392):
            for y in range(14, 112, 2):
                s.set_at((px, y), BONE)
        tips = []
        # player
        p = self.p
        ox = (random.randint(-2, 2) if p.shake else 0) + (4 if p.lunge > 5 else 0)
        spr = self.pspr[1] if p.flash else self.pspr[0]
        s.blit(spr, (p.x - spr.get_width() // 2 + ox, p.y - spr.get_height()))
        tips += self.draw_unit_bar(p, p.x - 22, 118, 44)
        if pygame.Rect(p.x - 18, p.y - 44, 36, 44).collidepoint(self.mouse):
            tips.append(f'YOU. {self.p.hp}/{self.p.maxhp} HP' + (f', {p.block} BLOCK.' if p.block else '.'))
        # targeting
        sel = self.sel
        alive = self.alive()
        targeting = (sel is not None and self.needs_target(sel)) or self.potsel is not None
        tgt = None
        if targeting and alive:
            hov = self.enemy_at(self.mouse)
            tgt = alive[self.tsel % len(alive)] if self.aiming or not hov else hov
        # enemies
        for e in self.enemies:
            if e.dead and e.die_t <= 0:
                continue
            ox = (random.randint(-2, 2) if e.shake else 0) - (6 if e.lunge > 6 else 0)
            spr = e.spr[1] if e.flash else e.spr[0]
            r = e.rect().move(ox, 0)
            if e.dead:
                if (e.die_t // 3) % 2:
                    continue
                r = r.move(0, (40 - e.die_t) // 4)
            s.blit(spr, r.topleft)
            if e.dead:
                continue
            if e is tgt:
                pygame.draw.rect(s, BLOOD, r.inflate(6, 6), 1)
            tips += self.draw_unit_bar(e, e.x - 22, 118, 44)
            # intent
            if self.phase in ('player', 'enemy'):
                iy = r.y - 12 + int(math.sin(t * 0.08 + e.x) * 1.5)
                if self.has('HOLLOW CROWN'):
                    s.blit(self.icons['unk'], (e.x - 4, iy))
                else:
                    kinds, label = self.intent_info(e)
                    w = len(kinds) * 9 + (len(label) * 4 + 1 if label else 0)
                    ix = e.x - w // 2
                    for k in kinds:
                        s.blit(self.icons_red[k] if k == 'atk' else self.icons[k], (ix, iy))
                        ix += 9
                    if label:
                        draw_text(s, label, ix + 1, iy + 2, 1, 'l', BLOOD)
                if pygame.Rect(e.x - 20, iy - 2, 40, 12).collidepoint(self.mouse):
                    tips.append('INTENT HIDDEN.' if self.has('HOLLOW CROWN') else self.intent_desc(e))
            if r.collidepoint(self.mouse):
                tips.append(f'{e.key}. {e.hp}/{e.maxhp} HP' + (f', {e.block} BLOCK.' if e.block else '.'))
        # energy, piles, end turn
        ex, ey = 14, 134
        pygame.draw.circle(s, BLOOD, (ex, ey), 9)
        pygame.draw.circle(s, BONE, (ex, ey), 9, 1)
        draw_text(s, f'{self.energy}', ex, ey - 2, 1, 'c', BONE)
        if pygame.Rect(ex - 9, ey - 9, 18, 18).collidepoint(self.mouse):
            tips.append(f'ENERGY: {self.energy}. CARDS COST ENERGY TO PLAY.')
        for x, n, lab in ((2, len(self.drawp), 'DRAW'), (376, len(self.disc), 'DISC')):
            r = pygame.Rect(x, 198, 22, 26)
            self.draw_panel(r)
            draw_text(s, str(n), r.centerx, r.y + 6, 1, 'c', BONE)
            draw_text(s, lab, r.centerx, r.y + 15, 1, 'c', BONE)
            if r.collidepoint(self.mouse):
                tips.append(('DRAW PILE (Q)' if lab == 'DRAW' else 'DISCARD PILE (W)') + f': {n} CARDS. CLICK TO VIEW.')
        if self.exh:
            draw_text(s, f'EXHAUST {len(self.exh)}', 398, 188, 1, 'r', BONE)
        er = self.end_rect()
        if self.phase == 'player':
            hot = er.collidepoint(self.mouse)
            self.draw_panel(er, BLOOD if hot else BLACK)
            draw_text(s, 'END TURN', er.centerx, er.y + 5, 1, 'c', BONE, False)
            if hot:
                tips.append('END YOUR TURN (SPACE).')
        else:
            label = {'enemy': 'ENEMY TURN', 'victory': 'VICTORY', 'defeat': 'DEFEAT'}[self.phase]
            draw_text(s, label, er.right, er.y + 5, 1, 'r', BLOOD)
        if self.phase == 'player' and (self.aiming or self.potsel is not None):
            draw_text(s, 'A/D PICK A FOE    E PLAYS    ESC BACK', W // 2, 18, 1, 'c', BLOOD)
        elif self.turn == 1 and self.phase == 'player' and t % 60 < 40 and self.fights <= 1 and not self.elite \
                and self.act == 0:
            draw_text(s, 'DRAG A CARD ONTO A FOE, OR A/D TO PICK A CARD AND E TO PLAY', W // 2, 18, 1, 'c', BONE)
        # hand
        hov = self.hand_hover()
        layout = self.hand_layout()
        order = list(range(len(self.hand)))
        top = None
        if self.sel in self.hand:
            top = self.hand.index(self.sel)
        elif hov is not None:
            top = hov
        if top is not None:
            order.remove(top)
            order.append(top)
        for i in order:
            c = self.hand[i]
            if self.drag and self.drag[0] is c:
                continue
            surf = self.render_card(c, tgt if c is sel else None, self.playable(c) and self.phase == 'player')
            x, y = (c.x, c.y) if c.x is not None else layout[i]
            s.blit(surf, (int(x), int(y)))
            if c is sel:
                pygame.draw.rect(s, BLOOD, (int(x) - 1, int(y) - 1, CW + 2, CH + 2), 1)
            if i < 10:
                draw_text(s, str((i + 1) % 10), int(x) + CW // 2, int(y) - 7, 1, 'c', BONE)
        if self.drag:
            c = self.drag[0]
            mx, my = self.mouse
            if self.needs_target(c) and my < FIELD_Y:
                tg = self.enemy_at(self.mouse)
                surf = self.render_card(c, tg, self.playable(c))
                s.blit(surf, (mx - CW // 2, max(FIELD_Y - 20, my + 6)))
                pygame.draw.line(s, BLOOD, (mx, max(FIELD_Y - 20, my + 6)), (mx, my))
                if tg:
                    pygame.draw.rect(s, BLOOD, tg.rect().inflate(6, 6), 1)
            else:
                surf = self.render_card(c, None, self.playable(c))
                s.blit(surf, (mx - CW // 2, my - CH // 2))
        # card tips
        show = self.sel if self.sel in self.hand else (self.hand[hov] if hov is not None else None)
        if show is not None and not self.drag:
            kt = self.keyword_tips(show)
            if kt:
                idx = self.hand.index(show)
                x = layout[idx][0]
                tx = int(x) + CW + 4 if x < 260 else int(x) - 128
                self.draw_tip(tx, 132, kt, 30)
        # floats
        for f in self.floats:
            if f[4] % 6 < 5 or f[4] > 20:
                draw_text(s, f[2], int(f[0]), int(f[1]), 1, 'c', f[3])
        if tips and not self.drag:
            self.draw_tip(self.mouse[0] + 8, self.mouse[1] + 10, tips[:3])

    def draw_reward(self):
        s = self.screen
        draw_text(s, 'SPOILS', W // 2, 15, 1, 'c', BONE)
        if self.reward_lines:
            draw_text(s, '    '.join(self.reward_lines), W // 2, 24, 1, 'c', BLOOD)
        rects = self.reward_rects()
        n = len(self.reward_cards)
        hov = None
        for i, c in enumerate(self.reward_cards):
            r = rects[i]
            surf = pygame.transform.scale(self.render_card(c), r.size)
            s.blit(surf, r.topleft)
            if i == self.sel or r.collidepoint(self.mouse):
                pygame.draw.rect(s, BLOOD, r.inflate(4, 4), 1)
            if r.collidepoint(self.mouse):
                hov = c
        sk = rects[-1]
        self.draw_panel(sk, BLOOD if self.sel == n or sk.collidepoint(self.mouse) else BLACK)
        draw_text(s, 'SKIP', sk.centerx, sk.y + 4, 1, 'c', BONE, False)
        draw_text(s, 'CHOOSE A CARD FOR YOUR DECK.  A/D AND ENTER, OR CLICK', W // 2, 198 if n <= 3 else 186,
                  1, 'c', BONE)
        if hov:
            kt = self.keyword_tips(hov)
            if kt:
                self.draw_tip(self.mouse[0] + 8, self.mouse[1] + 8, kt)

    def draw_bossrelic(self):
        s = self.screen
        draw_text(s, 'A BOSS RELIC', W // 2, 22, 2, 'c', BLOOD)
        draw_text(s, 'CHOOSE ONE TO CARRY INTO THE NEXT ACT', W // 2, 40, 1, 'c', BONE)
        rects = self.boss_rects()
        for i, rl in enumerate(self.boss_choices):
            r = rects[i]
            hot = i == self.sel or r.collidepoint(self.mouse)
            self.draw_panel(r, BLACK, BLOOD if hot else BONE)
            draw_text(s, rl, r.x + 6, r.y + 5, 1, 'l', BLOOD)
            for j, l in enumerate(wrap(RELICS[rl][1], 76)):
                draw_text(s, l, r.x + 6, r.y + 14 + j * 7, 1, 'l', BONE)
        sk = rects[-1]
        self.draw_panel(sk, BLOOD if self.sel == len(self.boss_choices) or sk.collidepoint(self.mouse) else BLACK)
        draw_text(s, 'SKIP', sk.centerx, sk.y + 4, 1, 'c', BONE, False)

    def draw_rest(self):
        s = self.screen
        draw_text(s, 'A FIRE IN THE DARK', W // 2, 30, 2, 'c', BONE)
        # flame
        for i in range(40):
            a = random.random() * TAU
            rr = random.random() * 10
            x = W // 2 + int(math.cos(a) * rr * 0.6)
            y = 70 - int(abs(math.sin(a)) * rr * 1.4) + random.randint(-1, 1)
            s.set_at((x, y), BLOOD if rr > 5 else BONE)
        for i, ((name, desc, ok), r) in enumerate(zip(self.rest_options(), self.rest_rects())):
            hot = i == self.sel or r.collidepoint(self.mouse)
            self.draw_panel(r, BLACK, BLOOD if hot else BONE)
            draw_text(s, f'{i + 1} {name}', r.centerx, r.y + 8, 2, 'c', BONE if ok else BLOOD)
            for j, l in enumerate(wrap(desc if ok else 'THE BLACK CANDLE FORBIDS IT.' if i == 0 else 'NOTHING TO HONE.', 22)):
                draw_text(s, l, r.centerx, r.y + 28 + j * 7, 1, 'c', BONE)
        draw_text(s, 'A/D AND ENTER, OR CLICK', W // 2, 170, 1, 'c', BONE)

    def draw_shop(self):
        s = self.screen
        draw_text(s, 'THE BONE MERCHANT', W // 2, 17, 1, 'c', BLOOD)
        rects = self.shop_rects()
        tips = None
        for i, (item, r) in enumerate(zip(self.shop, rects)):
            kind, obj, price, sold = item
            hot = i == self.sel or r.collidepoint(self.mouse)
            if sold:
                self.draw_panel(r)
                draw_text(s, 'SOLD', r.centerx, r.centery - 2, 1, 'c', BONE)
                continue
            if kind == 'card':
                s.blit(self.render_card(obj), r.topleft)
            elif False:
                self.draw_panel(r)
                draw_text(s, 'SOLD', r.centerx, r.centery - 2, 1, 'c', BONE)
            else:
                self.draw_panel(r)
                name = {'relic': obj, 'potion': obj, 'remove': 'REMOVE A CARD'}[kind]
                for j, l in enumerate(wrap(name, 16)[:2]):
                    draw_text(s, l, r.centerx, r.y + 5 + j * 7, 1, 'c', BLOOD if kind == 'relic' else BONE)
                draw_text(s, {'relic': 'RELIC', 'potion': 'POTION', 'remove': 'SERVICE'}[kind],
                          r.centerx, r.y + 22, 1, 'c', BONE)
                if r.collidepoint(self.mouse) or i == self.sel:
                    desc = {'relic': lambda: RELICS[obj][1], 'potion': lambda: POTIONS[obj][1],
                            'remove': lambda: 'REMOVE A CARD FROM YOUR DECK FOR GOOD.'}[kind]()
                    tips = [name, desc]
            if True:
                col = BONE if self.gold >= price else BLOOD
                draw_text(s, f'{price}G', r.centerx, r.bottom + 2, 1, 'c', col)
            if hot:
                pygame.draw.rect(s, BLOOD, r.inflate(4, 4), 1)
            if kind == 'card' and r.collidepoint(self.mouse):
                kt = self.keyword_tips(obj)
                tips = kt or None
        lr = self.leave_rect()
        self.draw_panel(lr, BLOOD if self.sel == len(self.shop) or lr.collidepoint(self.mouse) else BLACK)
        draw_text(s, 'LEAVE [L]', lr.centerx, lr.y + 4, 1, 'c', BONE, False)
        draw_text(s, 'A/D AND ENTER, OR CLICK TO BUY', W // 2, 186, 1, 'c', BONE)
        if tips:
            self.draw_tip(self.mouse[0] + 8, self.mouse[1] + 8, tips)

    def draw_chest(self):
        s = self.screen
        draw_text(s, 'A RELIQUARY CHEST', W // 2, 40, 2, 'c', BONE)
        s.blit(icon_surf('chest', 4), (W // 2 - 18, 60))
        for i, l in enumerate(self.chest_lines):
            for j, ll in enumerate(wrap(l, 70)):
                draw_text(s, ll, W // 2, 110 + i * 12 + j * 7, 1, 'c', BLOOD if i == 0 else BONE)
        draw_text(s, 'PRESS ENTER OR CLICK', W // 2, 190, 1, 'c', BONE)

    def draw_event(self):
        s = self.screen
        title, text, opts = self.event_data()
        draw_text(s, title, W // 2, 26, 2, 'c', BLOOD)
        for i, l in enumerate(wrap(text, 70)):
            draw_text(s, l, W // 2, 50 + i * 8, 1, 'c', BONE)
        if self.state == 'event_done':
            for i, l in enumerate(wrap(self.event_result or '', 70)):
                draw_text(s, l, W // 2, 120 + i * 8, 1, 'c', BLOOD)
            draw_text(s, 'PRESS ENTER OR CLICK', W // 2, 180, 1, 'c', BONE)
            return
        for i, ((label, ok), r) in enumerate(zip(opts, self.event_rects())):
            hot = i == self.sel or r.collidepoint(self.mouse)
            self.draw_panel(r, BLOOD if hot and ok else BLACK, BONE if ok else BLOOD)
            draw_text(s, f'{i + 1}. {label}', r.x + 5, r.y + 4, 1, 'l', BONE if ok else BLOOD, False)

    def draw_picker(self):
        s = self.screen
        pk = self.picker
        s.blit(self.dim2, (0, 0))
        s.fill(BLACK, (0, 13, W, 12))
        draw_text(s, f'{pk["title"]} ({len(pk["cards"])})', W // 2, 16, 1, 'c', BLOOD)
        clip = pygame.Rect(0, 24, W, 182)
        s.set_clip(clip)
        hov = None
        for i, (c, r) in enumerate(zip(pk['cards'], self.picker_rects())):
            if r.bottom < 24 or r.top > 206:
                continue
            shown = Card(c.key, True) if pk['up'] and (i == pk['sel'] or r.collidepoint(self.mouse)) \
                and c.upgradable else c
            s.blit(self.render_card(shown), r.topleft)
            if i == pk['sel'] and pk['pick'] is not None or r.collidepoint(self.mouse):
                pygame.draw.rect(s, BLOOD, r.inflate(4, 4), 1)
            if r.collidepoint(self.mouse):
                hov = shown
        s.set_clip(None)
        s.fill(BLACK, (0, 207, W, 18))
        if pk['cancel']:
            r = pygame.Rect(W // 2 - 26, 210, 52, 12)
            self.draw_panel(r, BLOOD if r.collidepoint(self.mouse) else BLACK)
            draw_text(s, 'BACK [ESC]', r.centerx, r.y + 4, 1, 'c', BONE, False)
        if not pk['cards']:
            draw_text(s, 'EMPTY', W // 2, 100, 2, 'c', BONE)
        if hov is not None:
            kt = self.keyword_tips(hov)
            if kt:
                self.draw_tip(self.mouse[0] + 8, self.mouse[1] + 8, kt)

    # -------------------------------------------------------------- main loop
    def run(self):
        while True:
            for ev in pygame.event.get():
                self.handle(ev)
            self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(60)


if __name__ == '__main__':
    Game().run()
