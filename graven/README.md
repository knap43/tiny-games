# GRAVEN

A tiny dark-fantasy top-down roguelike. One Python file, no assets: sprites are drawn in code and sounds are synthesized at startup. Palette: black, bone and blood.

```sh
python graven.py   # needs pygame (pacman -S python-pygame)
```

**Controls:** WASD move · mouse aim · LMB strike · RMB cast · Space/Shift roll · F drink vial · E take item · M map · Esc pause · F11 fullscreen/window

Torchlight carves dithered pools out of total darkness; enemies' red eyes give them away. Melee swings deflect enemy bolts back at their casters. Find weapons and spell tomes in reliquaries, collect souls (XP and mana) to earn boons, and face a boss every third level: The Hollow King, or in even-numbered areas The Ossuary Wyrm, a bone serpent that burrows under you and erupts in a ring of shards.

**Weapon boons:** besides the general boons, level-ups can offer a boon for any weapon, which only works while you wield it: sword (every third combo swing is a double-damage finisher), daggers (every second swing throws one), spear (tip hits deal double), greataxe (kills burst in blood), scythe (kills heal), warhammer (every swing sends a shockwave). Boons for the weapon in your hand turn up more often. Damage numbers float off every hit, bone-white normally and blood-red for critical hits (spear tip strikes and sword finishers).

**Spells:** firebolt, hexfan, bone spear, soul leech (homing, can heal), warding ring (blasts foes away and breaks bolts), soulfire, blood nova (costs HP), sunder beam (charges for a second, then pierces everything in a line), spectral blades (orbit you for six seconds).
