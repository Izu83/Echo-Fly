// Ready-made maps for both tasks. Every one can be edited further with the painter.
(function (root) {
  "use strict";
  const { emptyMap } = root.CWS;

  function painter(m) {
    const set = (x, y, v = 1) => { if (x >= 0 && y >= 0 && x < m.w && y < m.h) m.grid[y * m.w + x] = v; };
    const rect = (x0, y0, x1, y1, v = 1) => { for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) set(x, y, v); };
    const border = () => { rect(0, 0, m.w - 1, 0); rect(0, m.h - 1, m.w - 1, m.h - 1); rect(0, 0, 0, m.h - 1); rect(m.w - 1, 0, m.w - 1, m.h - 1); };
    return { rect, border };
  }

  function make(task, draw, markers) {
    const m = emptyMap(task);
    draw(painter(m), m);
    Object.assign(m, markers);
    return m;
  }

  const PRESETS = {
    walk: {
      "Open room": () => make("walk", (p) => p.border(),
        { start: { x: 5.5, y: 20, heading: 0 }, goal: { x: 58.5, y: 20 } }),
      "Pillars": () => make("walk", (p) => {
        p.border();
        for (let y = 5, row = 0; y < 36; y += 8, row++) for (let x = 12 + (row % 2) * 4; x < 58; x += 8) p.rect(x, y, x + 1, y + 1);
      }, { start: { x: 4.5, y: 22, heading: 0 }, goal: { x: 59.5, y: 22 } }),
      "Wall in the way": () => make("walk", (p) => { p.border(); p.rect(31, 10, 32, 29); },
        { start: { x: 6.5, y: 22, heading: 0 }, goal: { x: 57.5, y: 18 } }),
      "Two rooms": () => make("walk", (p) => { p.border(); p.rect(31, 1, 32, 25); p.rect(31, 32, 32, 38); },
        { start: { x: 6.5, y: 8, heading: 0.3 }, goal: { x: 56.5, y: 10 } }),
      "Zigzag": () => make("walk", (p) => { p.border(); p.rect(16, 1, 17, 28); p.rect(32, 11, 33, 38); p.rect(48, 1, 49, 28); },
        { start: { x: 5.5, y: 6, heading: 1.2 }, goal: { x: 58.5, y: 6 } }),
    },
    carry: {
      "Open floor": () => make("carry", (p) => p.border(),
        { start: { x: 5.5, y: 32, heading: 0 }, pickup: { x: 32, y: 8 }, drop: { x: 58.5, y: 32 } }),
      "Warehouse": () => make("carry", (p) => {
        p.border();
        for (const y of [9, 18, 27]) { p.rect(14, y, 26, y + 1); p.rect(36, y, 50, y + 1); }
      }, { start: { x: 4.5, y: 20, heading: 0 }, pickup: { x: 43, y: 14 }, drop: { x: 20, y: 32 } }),
      "Fetch from next room": () => make("carry", (p) => { p.border(); p.rect(31, 1, 32, 16); p.rect(31, 24, 32, 38); },
        { start: { x: 8.5, y: 30, heading: -0.4 }, pickup: { x: 52, y: 12 }, drop: { x: 8.5, y: 8 } }),
      "Pillar field": () => make("carry", (p) => {
        p.border();
        for (let x = 10; x < 58; x += 7) for (let y = 5; y < 36; y += 7) if ((x + y) % 2 === 0) p.rect(x, y, x + 1, y + 1);
      }, { start: { x: 4.5, y: 35, heading: -0.6 }, pickup: { x: 58, y: 5 }, drop: { x: 5.5, y: 5.5 } }),
    },
  };

  root.CWS.PRESETS = PRESETS;
})(typeof window !== "undefined" ? window : globalThis);
