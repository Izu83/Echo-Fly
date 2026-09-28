// Small line charts drawn on a canvas, with a crosshair + tooltip on hover. No libraries, works offline.
//
//   const c = new LineChart(canvas, tipDiv, { yMin, yMax, yFmt, xFmt, xName, zero, empty })
//   c.set([{ name, color, pts: [[x, y], ...], dots, faint }])      then c.draw()
(function (root) {
  "use strict";

  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function niceStep(span, count) {
    const raw = span / Math.max(1, count), mag = 10 ** Math.floor(Math.log10(raw)), f = raw / mag;
    return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag;
  }

  // keep at most `n` points per series: for each bucket the point farthest from the bucket's mean
  // (so short spikes, like a dopamine burst, survive)
  function thin(pts, n) {
    if (pts.length <= n) return pts;
    const out = [], per = pts.length / n;
    for (let b = 0; b < n; b++) {
      const lo = Math.floor(b * per), hi = Math.min(pts.length, Math.floor((b + 1) * per));
      let mean = 0;
      for (let i = lo; i < hi; i++) mean += pts[i][1];
      mean /= hi - lo;
      let best = pts[lo];
      for (let i = lo; i < hi; i++) if (Math.abs(pts[i][1] - mean) > Math.abs(best[1] - mean)) best = pts[i];
      out.push(best);
    }
    return out;
  }

  class LineChart {
    constructor(canvas, tip, opts = {}) {
      this.c = canvas; this.ctx = canvas.getContext("2d"); this.tip = tip;
      this.o = { yFmt: (v) => String(Math.round(v)), xFmt: (v) => String(Math.round(v)), xName: "", empty: "No data yet", ...opts };
      this.series = [];
      this.hoverX = null;
      canvas.addEventListener("pointermove", (e) => {
        const r = canvas.getBoundingClientRect();
        this.hoverPx = e.clientX - r.left;
        this.draw();
      });
      canvas.addEventListener("pointerleave", () => { this.hoverPx = null; this.tip.hidden = true; this.draw(); });
    }

    set(series) { this.series = series; }

    draw() {
      const c = this.c, ctx = this.ctx, dpr = window.devicePixelRatio || 1;
      const W = c.clientWidth, H = c.clientHeight;
      if (!W || !H) return;
      if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const text2 = css("--muted"), grid = css("--grid-line") || "#262d38", font = "11px system-ui, sans-serif";
      ctx.font = font;

      const all = this.series.flatMap((s) => s.pts);
      if (!all.length) {
        ctx.fillStyle = text2; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(this.o.empty, W / 2, H / 2);
        this.geom = null;
        return;
      }
      let x0 = Math.min(...all.map((p) => p[0])), x1 = Math.max(...all.map((p) => p[0]));
      if (x1 === x0) x1 = x0 + 1;
      let y0 = this.o.yMin ?? Math.min(0, ...all.map((p) => p[1])), y1 = this.o.yMax ?? Math.max(...all.map((p) => p[1]));
      if (this.o.yMax == null) { const st = niceStep(y1 - y0 || 1, 4); y1 = Math.ceil(y1 / st) * st || st; }
      if (y1 === y0) y1 = y0 + 1;

      const L = 40, R = 10, T = 10, B = 20;
      const pw = W - L - R, ph = H - T - B;
      const X = (v) => L + ((v - x0) / (x1 - x0)) * pw, Y = (v) => T + (1 - (v - y0) / (y1 - y0)) * ph;
      this.geom = { X, Y, x0, x1, L, R, W, pw };

      // grid + y ticks
      const ys = niceStep(y1 - y0, 4);
      ctx.strokeStyle = grid; ctx.lineWidth = 1; ctx.fillStyle = text2; ctx.textAlign = "right"; ctx.textBaseline = "middle";
      for (let v = Math.ceil(y0 / ys) * ys; v <= y1 + 1e-9; v += ys) {
        const y = Math.round(Y(v)) + 0.5;
        ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(L + pw, y); ctx.stroke();
        ctx.fillText(this.o.yFmt(v), L - 6, y);
      }
      if (this.o.zero && y0 < 0 && y1 > 0) {
        ctx.strokeStyle = text2; ctx.beginPath(); ctx.moveTo(L, Math.round(Y(0)) + 0.5); ctx.lineTo(L + pw, Math.round(Y(0)) + 0.5); ctx.stroke();
      }
      // x ticks
      const xs = niceStep(x1 - x0, Math.max(2, Math.floor(pw / 80)));
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      for (let v = Math.ceil(x0 / xs) * xs; v <= x1 + 1e-9; v += xs) ctx.fillText(this.o.xFmt(v), X(v), T + ph + 5);

      // series
      const maxPts = Math.max(50, Math.floor(pw * 1.5));
      for (const s of this.series) {
        const pts = thin(s.pts, maxPts);
        if (s.dots) {
          ctx.fillStyle = s.color; ctx.globalAlpha = s.faint ? 0.35 : 0.9;
          const r = pts.length > 150 ? 1.5 : 2.5;
          for (const [x, y] of pts) { ctx.beginPath(); ctx.arc(X(x), Y(y), r, 0, Math.PI * 2); ctx.fill(); }
          ctx.globalAlpha = 1;
          continue;
        }
        ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.globalAlpha = s.faint ? 0.4 : 1;
        ctx.beginPath();
        pts.forEach(([x, y], i) => (i ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y))));
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // hover: crosshair on the nearest x, values in the tooltip
      if (this.hoverPx == null || this.hoverPx < L || this.hoverPx > L + pw) { this.tip.hidden = true; return; }
      const hx = x0 + ((this.hoverPx - L) / pw) * (x1 - x0);
      const rows = [];
      let snapX = null;
      for (const s of this.series) {
        if (!s.pts.length || s.noTip) continue;
        let best = s.pts[0];
        for (const p of s.pts) if (Math.abs(p[0] - hx) < Math.abs(best[0] - hx)) best = p;
        if (snapX == null || Math.abs(best[0] - hx) < Math.abs(snapX - hx)) snapX = best[0];
        rows.push([s, best]);
      }
      if (snapX == null) { this.tip.hidden = true; return; }
      ctx.strokeStyle = text2; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(Math.round(X(snapX)) + 0.5, T); ctx.lineTo(Math.round(X(snapX)) + 0.5, T + ph); ctx.stroke();
      ctx.setLineDash([]);
      for (const [s, p] of rows) {
        ctx.fillStyle = s.color; ctx.strokeStyle = css("--floor"); ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 4, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
      this.tip.hidden = false;
      this.tip.innerHTML = `<b>${this.o.xName} ${this.o.xFmt(snapX)}</b>` + rows.map(([s, p]) =>
        `<div><i style="background:${s.color}"></i>${s.name}<span>${s.fmt ? s.fmt(p) : this.o.yFmt(p[1])}</span></div>`).join("");
      const tw = this.tip.offsetWidth, left = X(snapX) + 12 + tw > W ? X(snapX) - 12 - tw : X(snapX) + 12;
      this.tip.style.left = `${Math.max(0, left)}px`;
      this.tip.style.top = "6px";
    }
  }

  // running statistic over the last `n` values, one output per input
  function rolling(values, n, fn) {
    const out = [];
    for (let i = 0; i < values.length; i++) {
      const win = values.slice(Math.max(0, i - n + 1), i + 1).filter((v) => v != null);
      out.push(win.length ? fn(win) : null);
    }
    return out;
  }
  const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;
  const median = (a) => { const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

  root.CWS_CHARTS = { LineChart, rolling, mean, median };
})(window);
