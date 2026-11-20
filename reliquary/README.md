# RELIQUARY

A tiny dark-fantasy roguelike deck builder in the spirit of Slay the Spire, in black, bone and blood. Climb three acts of a ruined cathedral (the Catacombs, the Drowned Nave, the Pale Throne), each a branching map that ends in a boss. Win fights with a deck of cards, take new cards as spoils, and gather relics that bend the rules.

```
python reliquary.py            # fullscreen
python reliquary.py --windowed
```

**Combat:** each turn you draw 5 cards and have 3 energy. Attacks deal damage, skills mostly give block (which soaks damage until your next turn), and powers last for the whole fight. Every foe shows its intent above its head: the damage it will deal, or a shield, buff or debuff icon. Hover anything (intents, status effects, cards, relics, potions) to read what it does.

**Controls:**
- **Mouse:** drag a card onto a foe, or anywhere above the hand for untargeted cards. You can also click a card, then click its target. Right click cancels.
- **Keys:** A/D (or the arrows, or 1-9 and 0) move through your hand and E chooses a card. If it needs a target and there are several foes, A/D then move through the foes and E plays it; Esc steps back. Space ends the turn, Q and W show the draw and discard piles, Z/X/C drink a potion, and V views your deck outside combat.
- Menus: A/D and Enter, or click. Esc pauses or cancels, F11 toggles fullscreen.

**The map:** foes, elites (harder, and they guard a relic), fires (rest to heal 30%, or hone a card to upgrade it), the bone merchant (cards, relics, potions, card removal), chests, and unknown rooms holding events with choices.

**Status effects:** strength, dexterity, weak (deal 25% less), vulnerable (take 50% more), frail (25% less block), poison, thorns, veil (each hit deals at most 1), and the foes' own rituals, rage, iron skin and wards.

**Cards:** about 50, from Cleave and Twin Cut to Whirl, Catalyst, Dark Rite, Barricade and Wraith Form, plus status cards foes force on you (Slime, Burn, Dazed, Wound) and curses from bad bargains. After each act's boss you choose a boss relic, most of which grant extra energy at a price. Your highest floor and victories are remembered.
