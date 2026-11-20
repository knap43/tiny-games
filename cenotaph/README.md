# CENOTAPH

A tiny dark-fantasy turn-based tactical roguelike in the spirit of Hoplite, on a square grid with no diagonals: you and every foe move and strike only along rows and columns. Descend twelve depths of the cenotaph and take its Heart. Every foe strikes in a fixed, readable pattern, so each turn is a small positioning puzzle.

```
python cenotaph.py            # fullscreen
python cenotaph.py --windowed
```

**Moving is attacking:**
- **Strike:** step into a foe next to you; you stay where you are.
- **Lunge:** step straight toward a foe two tiles away (needs your spear in hand).
- **1 Leap:** jump straight up to 2 tiles, over anything, to a free tile. Recharges over a few turns.
- **2 Throw spear:** kill the first foe in a straight line up to 3 tiles. Walk over the spear to take it back; without it you cannot lunge.
- **3 Bash:** shove a foe next to you away and stun it. Into a chasm, it falls; into a wall, it is stunned longer.

**Controls:** WASD/arrows (or the numpad) to move, Space to wait. 1/2/3 pick an ability, then click a target or steer the cursor and press Enter (Esc cancels). With the mouse: click a tile next to you to move, click a foe next to you to strike, click further along a row or column to leap, right click a foe to throw. Esc pauses, F11 toggles fullscreen.

**Reading the board:** red marks show every tile some foe would strike on its next action; hover a foe to see its reach alone, or hover anything for a description. Foes act after you, so killing one before it acts removes its threat.

**Foes:** ghouls (strike the four tiles next to them), bone archers (rows and columns, 2-5 tiles, never point-blank), cultists (rows and columns up to 7, resting a turn after), grave-robbers (lob a bomb that bursts after your next move in a cross, hurting foes too) and revenants (two wounds, slow).

**Boons:** each staircase grants one of three: more hearts, healing, a longer or quicker leap, a stronger or quicker bash, a longer throw, a spear that flies back, bloodlust (three kills in a turn heals) or a leap that stuns on landing. Your deepest descent is remembered.
