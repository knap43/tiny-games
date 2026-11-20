# CENOTAPH

A tiny dark-fantasy turn-based tactical roguelike in the spirit of Hoplite, on a square grid. Descend twelve depths of the cenotaph and take its Heart. Every foe strikes in a fixed, readable pattern, so each turn is a small positioning puzzle.

```
python cenotaph.py            # fullscreen
python cenotaph.py --windowed
```

**Moving is attacking:**
- **Stab:** step from one tile next to a foe to another tile still next to it.
- **Lunge:** step straight toward a foe two tiles away (needs your spear in hand).
- **1 Leap:** jump to a free tile up to 2 away (stabs still count). Recharges over a few turns.
- **2 Throw spear:** kill the first foe in a straight line up to 3 tiles. Walk over the spear to take it back; without it you cannot lunge.
- **3 Bash:** shove a foe next to you away and stun it. Into a chasm, it falls; into a wall, it is stunned longer.

**Controls:** WASD/arrows plus Q E Z C for diagonals (or the numpad) to move, Space to wait. 1/2/3 pick an ability, then click a target or steer the cursor and press Enter (Esc cancels). With the mouse: click a tile next to you to move, click a foe next to you to bash, click further out to leap, right click a foe to throw. Esc pauses, F11 toggles fullscreen.

**Reading the board:** red marks show every tile some foe would strike on its next action; hover a foe to see its reach alone, or hover anything for a description. Foes act after you, so killing one before it acts removes its threat.

**Foes:** ghouls (strike any adjacent tile), bone archers (straight and diagonal lines, 2-5 tiles, never point-blank), cultists (rows and columns up to 7, resting a turn after), grave-robbers (lob a bomb that bursts after your next move, 3x3, hurting foes too) and revenants (two wounds, slow).

**Boons:** each staircase grants one of three: more hearts, healing, a longer or quicker leap, a stronger or quicker bash, a longer throw, a spear that flies back, bloodlust (three kills in a turn heals) or a leap that stuns on landing. Your deepest descent is remembered.
