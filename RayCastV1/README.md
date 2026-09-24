# Echo Room

A first-person laser sonar for a blind user. The walls are invisible: every scan fires thousands of lasers, and each hit lights up briefly when its echo returns.

Open `index.html` in a browser. No install or server needed.

## Controls

| Key | Action |
|---|---|
| Mouse | Look around (click the view first, Esc releases) |
| E / left click | Scan (hold to keep scanning) |
| W S / ↑ ↓ | Walk forward / back |
| A D | Side-step |
| ← → | Turn |
| R F | Look up / down |
| Space / Shift | Fly up / down |
| X | Look level |
| Tab | Big map |
| C | Colour by surface / distance |
| T | Speak last scan summary |
| M | Reveal everything (tester mode) |

## Map

`map.png` is the level (it is also embedded in `index.html`). Colours:

- black: walls (4 m, floor to roof)
- green: room walls
- blue: door (fixed, 2.1 m)
- red: low obstacles (0.8 m)

Use "Load map image…" in the side panel to try your own map with the same colours.
