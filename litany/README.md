# LITANY

A tiny dark-fantasy typing game. A hooded reciter kneels in a ritual circle while shades creep in from every side, each carrying a word. Speak the words, keep the candles lit.

```
python litany.py            # fullscreen
python litany.py --windowed
```

**How it plays:** type a word to banish its shade. Your first letter locks onto the nearest word starting with it (words on screen start with different letters whenever possible); every correct letter throws a spark that knocks the shade back. Wrong keys are ignored, but they break your combo. Backspace lets go of the locked word. Esc pauses, F11 toggles fullscreen.

- **Candles** are your lives: a shade that reaches the circle snuffs one. Every third wave relights one.
- **Blood-red words are wards:** finish one to banish every shade near you and drive the rest back.
- **Every fifth wave an elder shade** comes, slow and huge, carrying one long word.
- Waves grow longer, faster and wordier. Score is letters times your combo multiplier (up to x10), plus a bonus per word. WPM and accuracy are shown as you play; your best score is remembered.
