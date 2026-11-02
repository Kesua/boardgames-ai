/* Small SVG charts with hover tooltips. One y-axis per chart, thin marks, text in ink colours, series colours in fixed
   order (--s1..--s8), diverging blue/red around a neutral zero, sequential blue for grids. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const tip = () => document.getElementById("tip");

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function text(parent, x, y, s, cls, anchor) {
    const t = el("text", { x, y, class: cls || "lab", "text-anchor": anchor || "start" }, parent);
    t.textContent = s;
    return t;
  }
  function showTip(ev, html) {
    const t = tip();
    t.innerHTML = html;
    t.hidden = false;
    const pad = 14, w = t.offsetWidth, h = t.offsetHeight;
    let x = ev.clientX + pad, y = ev.clientY + pad;
    if (x + w > window.innerWidth - 8) x = ev.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = ev.clientY - h - pad;
    t.style.left = Math.max(8, x) + "px";
    t.style.top = Math.max(8, y) + "px";
  }
  function hideTip() { tip().hidden = true; }
  function hover(node, html) {
    node.addEventListener("mousemove", (e) => showTip(e, typeof html === "function" ? html() : html));
    node.addEventListener("mouseleave", hideTip);
    node.addEventListener("focus", (e) => { const r = node.getBoundingClientRect(); showTip({ clientX: r.right, clientY: r.top }, typeof html === "function" ? html() : html); });
    node.addEventListener("blur", hideTip);
  }
  /* Charts draw at the container's real width, so text keeps its size on every screen (redrawn on resize). */
  function widthOf(container) { return Math.max(300, Math.floor(container.getBoundingClientRect().width) || 640); }
  function svgBox(container, w, h) {
    container.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "chart";
    container.appendChild(wrap);
    const svg = el("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, role: "img" }, wrap);
    return { wrap, svg };
  }
  function niceTicks(lo, hi, n) {
    if (lo === hi) { lo -= 1; hi += 1; }
    const span = hi - lo, step0 = span / Math.max(1, n);
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= step0) || step0;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }
  const color = (i) => `var(--s${(i % 8) + 1})`;
  // axis labels: whole-number ticks drop trailing zero decimals ("20.0" -> "20", "4,0 %" -> "4 %"), never a thousands
  // separator ("3,000" stays): only the page language's decimal mark counts. The formatter also gets the decimals the
  // tick step needs (0.05 -> 2), so it can keep ticks distinct ("0.05 0.10", not "0.1 0.1").
  const tickText = (fmt, t, ticks) => {
    const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : 1, dec = Math.max(0, Math.ceil(-Math.log10(step) - 1e-9));
    const s = String(fmt ? fmt(t, dec) : t);
    const re = document.documentElement.lang === "cs" ? /,0+(?=[^0-9]*$)/ : /\.0+(?=[^0-9]*$)/;
    return ticks.every((v) => Number.isInteger(v)) ? s.replace(re, "") : s;
  };
  /* A label in at most three lines of about maxCh characters (split at spaces), the last shortened with "…" if needed. */
  function wrapLines(label, maxCh) {
    const words = String(label).split(" "), out = [];
    while (words.length && out.length < 3) {
      let a = words.shift();
      while (words.length && (a + " " + words[0]).length <= maxCh) a += " " + words.shift();
      out.push(a);
    }
    if (words.length) out[2] += " " + words.join(" ");
    return out.map((x) => (x.length > maxCh + 2 ? x.slice(0, maxCh) + "…" : x));
  }

  /* Horizontal bars around zero (polarity): rows [{label, value, tip, dim}]. Positive = --pos, negative = --neg.
     o.mag: plain magnitudes (shares, points) in one hue. The axis only covers the signs present. */
  function divergingBars(container, rows, o) {
    o = o || {};
    const W = widthOf(container);
    // phones: the name goes above its bar, so the bar gets the whole width
    const stacked = W < 500, rowH = stacked ? 40 : 24, barTop = stacked ? 19 : 5, barH = 14, top = 6, h = top + rows.length * rowH + 24;
    const labelW = stacked ? 0 : Math.min(o.labelW || 200, Math.round(W * 0.38));
    const { svg } = svgBox(container, W, h);
    // the axis covers every uncertainty range, so no range line is cut at the plot edge
    const max = Math.max(1e-9, ...rows.map((r) => Math.abs(r.value) + (r.err || 0)), o.minMax || 0);
    const anyNeg = rows.some((r) => r.value < 0), anyPos = rows.some((r) => r.value > 0);
    const plotW = W - labelW - 72;
    const x0 = labelW + 8 + (anyNeg && anyPos ? plotW / 2 : anyNeg ? plotW : 0);
    const half = anyNeg && anyPos ? plotW / 2 : plotW;
    const clipX = (x) => Math.max(labelW + 4, Math.min(W - 4, x));
    const g = el("g", { class: "grid" }, svg);
    const dt = niceTicks(anyNeg ? -max : 0, anyPos || !anyNeg ? max : 0, 4);
    dt.forEach((t) => {
      const x = x0 + (t / max) * half;
      el("line", { x1: x, x2: x, y1: top, y2: h - 22 }, g);
      text(svg, x, h - 6, tickText(o.fmt, t, dt), "lab", "middle");
    });
    rows.forEach((r, i) => {
      const y = top + i * rowH;
      // labels that do not fit are shortened (about 6.6 px per character at this font size)
      const maxCh = Math.max(6, Math.floor(((stacked ? W : labelW) - 4) / 6.6));
      const full = String(r.label), cut = full.lastIndexOf(" · "), tail = cut > 0 ? full.slice(cut) : "", head = cut > 0 ? full.slice(0, cut) : full;
      const lab = full.length > maxCh ? head.slice(0, Math.max(3, maxCh - tail.length - 1)) + "…" + tail : full;   // keep a " · 58 %" ending
      const t = stacked ? text(svg, 2, y + 14, lab, "name", "start") : text(svg, labelW, y + rowH / 2 + 4, lab, "name", "end");
      if (lab !== r.label) el("title", {}, t).textContent = r.label;
      if (r.dim) t.setAttribute("opacity", ".55");
      const v = r.value, x = v >= 0 ? x0 : x0 + (v / max) * half, w = Math.max(1.5, Math.abs(v / max) * half), cy = y + barTop + barH / 2;
      // a bar whose uncertainty range crosses zero is drawn pale: the effect may be nothing
      const unclear = r.err && Math.abs(v) <= r.err;
      const fill = o.mag ? "var(--accent)" : v >= 0 ? "var(--pos)" : "var(--neg)", pale = r.dim || unclear;
      const bar = el("rect", { x, y: y + barTop, width: w, height: barH, rx: 4, class: pale ? "mark pale" : "mark", style: pale ? `--c:${fill}` : null,
                               fill, opacity: r.dim ? .45 : unclear ? .3 : 1 }, svg);
      let right = v >= 0 ? x + w : x0;   // right end of what is drawn on the positive side of zero
      if (r.err) {
        const ex1 = clipX(x0 + ((v - r.err) / max) * half), ex2 = clipX(x0 + ((v + r.err) / max) * half);
        const wk = { stroke: "var(--ink-2)", "stroke-width": 1.5 };
        el("line", Object.assign({ x1: ex1, x2: ex2, y1: cy, y2: cy }, wk), svg);
        el("line", Object.assign({ x1: ex1, x2: ex1, y1: cy - 4, y2: cy + 4 }, wk), svg);
        el("line", Object.assign({ x1: ex2, x2: ex2, y1: cy - 4, y2: cy + 4 }, wk), svg);
        right = Math.max(right, ex2);
      }
      // the value sits right of the bar and its range line (negative bar: right of zero, or of a range crossing it), never over them
      text(svg, Math.min(right + 5, W - 58), cy + 4, o.vfmt ? o.vfmt(v) : o.fmt ? o.fmt(v) : v, "val", "start");
      const hit = el("rect", { x: 0, y, width: W, height: rowH, class: "hit", tabindex: 0 }, svg);
      if (r.tip) hover(hit, r.tip);
      svg.insertBefore(hit, bar);
    });
    el("line", { x1: x0, x2: x0, y1: top, y2: h - 22, class: "zero" }, svg);
  }

  /* Vertical bars, one series or grouped: {x:[labels], series:[{name, values, tips}], fmt, baseline, base_label} */
  function columns(container, spec) {
    const W = widthOf(container), maxCh = Math.max(6, Math.floor(((W - 70) / Math.max(1, spec.x.length) - 4) / 6));
    const nl = spec.allLabels ? Math.max(1, ...spec.x.map((lab) => wrapLines(lab, maxCh).length)) : 1;   // long names wrap onto more lines
    const H = (spec.height || 240) + (spec.xlabel ? 16 : 0) + (nl - 1) * 13, L = spec.ylabel ? 60 : 46, R = 10, T = 12, B = 34 + (spec.xlabel ? 16 : 0) + (nl - 1) * 13;
    const { wrap, svg } = svgBox(container, W, H);
    const all = spec.series.flatMap((s) => s.values).filter((v) => v !== null && v !== undefined);
    let lo = Math.min(0, ...all), hi = Math.max(0, ...all, spec.baseline ?? 0);
    if (spec.diverge && spec.baseline !== undefined) {
      // bars hang from the baseline, so the axis only needs to cover the values and the baseline
      lo = Math.min(spec.baseline, ...all); hi = Math.max(spec.baseline, ...all);
      // at least ±(minSpan) around the baseline, so small noisy differences also look small
      const span = spec.minSpan || 0; lo = Math.min(lo, spec.baseline - span); hi = Math.max(hi, spec.baseline + span);
      const pad = (hi - lo) * 0.08 || 0.05; lo = Math.max(0, lo - pad); hi = hi + pad;
    }
    const ticks = niceTicks(lo, hi, 4);
    // the axis ends on a labelled tick, so the tallest bar never sticks out above the last number
    if (ticks.length > 1 && hi > ticks[ticks.length - 1] + 1e-9 && !spec.diverge) ticks.push(+(ticks[ticks.length - 1] + ticks[1] - ticks[0]).toFixed(10));
    lo = Math.min(lo, ticks[0]); hi = Math.max(hi, ticks[ticks.length - 1]);
    const y = (v) => T + (H - T - B) * (1 - (v - lo) / (hi - lo || 1));
    const g = el("g", { class: "grid" }, svg);
    ticks.forEach((t) => { el("line", { x1: L, x2: W - R, y1: y(t), y2: y(t) }, g); text(svg, L - 6, y(t) + 4, tickText(spec.tickFmt || spec.fmt, t, ticks), "lab", "end"); });
    const n = spec.x.length, k = spec.series.length, band = (W - L - R) / n, gap = 2;
    const bw = Math.max(3, Math.min(42, (band - 10) / k - gap));
    spec.x.forEach((lab, i) => {
      const cx = L + band * i + band / 2;
      const every = spec.allLabels ? 1 : Math.ceil(n / Math.max(1, Math.floor((W - L - R) / 70)));
      if (i % every === 0 && lab !== "") {
        if (spec.allLabels) wrapLines(lab, maxCh).forEach((line, li) => { const tt = text(svg, cx, H - B + 16 + li * 13, line, "lab", "middle"); if (line.endsWith("…")) el("title", {}, tt).textContent = lab; });
        else text(svg, cx, H - B + 16, String(lab).length > 14 && band < 90 ? String(lab).slice(0, 12) + "…" : lab, "lab", "middle");
      }
      spec.series.forEach((s, j) => {
        const v = s.values[i];
        if (v === null || v === undefined) return;
        const base = spec.diverge ? spec.baseline : 0;
        const x = cx - (k * (bw + gap)) / 2 + j * (bw + gap);
        const y1 = y(Math.max(v, base)), y2 = y(Math.min(v, base));
        const fill = spec.diverge ? (v >= base ? "var(--pos)" : "var(--neg)") : (s.color || color(j));
        const pale = s.dims && s.dims[i];
        el("rect", { x, y: y1, width: bw, height: Math.max(1.5, y2 - y1), rx: 3, fill, class: pale ? "mark pale" : "mark", style: pale ? `--c:${fill}` : null, opacity: pale ? .35 : 1 }, svg);
        const hit = el("rect", { x: x - 2, y: T, width: bw + 4, height: H - T - B, class: "hit", tabindex: 0 }, svg);
        hover(hit, (s.tips && s.tips[i]) || `<b>${lab}</b><br>${s.name}: ${spec.fmt ? spec.fmt(v) : v}`);
      });
    });
    if (lo <= 0 && hi >= 0) el("line", { x1: L, x2: W - R, y1: y(0), y2: y(0), class: "zero" }, svg);
    axisTitles(svg, W, H, L, R, T, B, spec);
    if (spec.baseline !== undefined && spec.baseline !== 0) {
      el("line", { x1: L, x2: W - R, y1: y(spec.baseline), y2: y(spec.baseline), stroke: "var(--ink-3)", "stroke-dasharray": "4 4" }, svg);
      if (spec.base_label) text(svg, W - R, y(spec.baseline) - 5, spec.base_label, "lab", "end");
    }
    if (k > 1) legend(wrap, spec.series.map((s, j) => ({ name: s.name, color: s.color || color(j) })));
  }

  /* Lines: {series:[{name, points:[{x,y,tip,hollow}]}], xfmt, yfmt, zero, xlabel} */
  function lines(container, spec) {
    const W = widthOf(container), H = spec.height || 260, L = 46, R = 14, T = 16, B = 36;
    const { wrap, svg } = svgBox(container, W, H);
    spec.series = spec.series.map((s) => Object.assign({}, s, { points: s.points.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)) }))
      .filter((s) => s.points.length);
    const pts = spec.series.flatMap((s) => s.points);
    if (!pts.length) { container.innerHTML = '<p class="sub">No data.</p>'; return; }
    let xlo = Math.min(...pts.map((p) => p.x), spec.xmin ?? Infinity), xhi = Math.max(...pts.map((p) => p.x), spec.xmax ?? -Infinity);
    let ylo = Math.min(...pts.map((p) => p.y), spec.zero ? 0 : Infinity), yhi = Math.max(...pts.map((p) => p.y), spec.zero ? 0 : -Infinity);
    if (spec.ymin !== undefined) ylo = Math.min(ylo, spec.ymin);
    if (spec.ymax !== undefined) yhi = Math.max(yhi, spec.ymax);
    const yt = niceTicks(ylo, yhi, 4); ylo = Math.min(ylo, yt[0]); yhi = Math.max(yhi, yt[yt.length - 1]);
    const xt = niceTicks(xlo, xhi, 6);
    const X = (v) => L + (W - L - R) * ((v - xlo) / (xhi - xlo || 1));
    const Y = (v) => T + (H - T - B) * (1 - (v - ylo) / (yhi - ylo || 1));
    const g = el("g", { class: "grid" }, svg);
    yt.forEach((t) => { el("line", { x1: L, x2: W - R, y1: Y(t), y2: Y(t) }, g); text(svg, L - 6, Y(t) + 4, tickText(spec.yfmt, t, yt), "lab", "end"); });
    xt.filter((t) => t >= xlo && t <= xhi).forEach((t) => text(svg, X(t), H - B + 16, spec.xfmt ? spec.xfmt(t) : t, "lab", "middle"));
    if (spec.xlabel) text(svg, (L + W - R) / 2, H - 4, spec.xlabel, "lab", "middle");
    if (spec.zero) el("line", { x1: L, x2: W - R, y1: Y(0), y2: Y(0), class: "zero" }, svg);
    (spec.refs || []).forEach((r) => {
      el("line", { x1: L, x2: W - R, y1: Y(r.y), y2: Y(r.y), stroke: "var(--ink-3)", "stroke-dasharray": "4 4" }, svg);
      text(svg, W - R, Y(r.y) - 5, r.label, "lab", "end");
    });
    spec.series.forEach((s, j) => {
      const c = s.color || color(j);
      const p = s.points.slice().sort((a, b) => a.x - b.x);
      if (p.length > 1) el("path", { d: p.map((q, i) => (i ? "L" : "M") + X(q.x).toFixed(1) + " " + Y(q.y).toFixed(1)).join(""),
                                     fill: "none", stroke: c, "stroke-width": 2, "stroke-linejoin": "round" }, svg);
      p.forEach((q) => {
        const dot = el("circle", { cx: X(q.x), cy: Y(q.y), r: p.length > 40 ? 2.2 : 4, fill: q.hollow ? "var(--surface)" : c,
                                   stroke: c, "stroke-width": 2, class: "mark" }, svg);
        const hit = el("circle", { cx: X(q.x), cy: Y(q.y), r: 10, class: "hit", tabindex: p.length > 40 ? -1 : 0 }, svg);
        hover(hit, q.tip || `<b>${s.name}</b><br>${spec.yfmt ? spec.yfmt(q.y) : q.y}`);
        void dot;
      });
    });
    if (spec.series.length > 1) legend(wrap, spec.series.map((s, j) => ({ name: s.name, color: s.color || color(j) })));
  }

  /* Count grid (heatmap, sequential): {xEdges, yEdges, counts[x][y], xlabel, ylabel} */
  function grid(container, spec) {
    const W = widthOf(container), H = 300, L = 60, R = 10, T = 10, B = 40;
    const { wrap, svg } = svgBox(container, W, H);
    const nx = spec.counts.length, ny = spec.counts[0].length;
    const max = Math.max(1, ...spec.counts.flat());
    const cw = (W - L - R) / nx, ch = (H - T - B) / ny;
    const ramp = ["--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5", "--seq-6", "--seq-7"];
    for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) {
      const v = spec.counts[i][j];
      const x = L + i * cw, y = T + (ny - 1 - j) * ch;
      const step = v ? ramp[Math.min(6, Math.floor((Math.sqrt(v / max)) * 6.999))] : null;
      const r = el("rect", { x: x + 1, y: y + 1, width: cw - 2, height: ch - 2, rx: 3, fill: step ? `var(${step})` : "var(--surface-2)", tabindex: v ? 0 : -1 }, svg);
      hover(r, `${spec.xlabel}: ${spec.xEdges[i]}–${spec.xEdges[i + 1]}<br>${spec.ylabel}: ${spec.yEdges[j]}–${spec.yEdges[j + 1]}<br><b>${v}</b> ${spec.unit || ""}`);
    }
    for (let i = 0; i <= nx; i += Math.max(1, Math.ceil(nx / 10))) text(svg, L + i * cw, H - B + 14, spec.xEdges[i], "lab", "middle");
    for (let j = 0; j <= ny; j += Math.max(1, Math.ceil(ny / 6))) text(svg, L - 6, T + (ny - j) * ch + 4, spec.yEdges[j], "lab", "end");
    text(svg, (L + W - R) / 2, H - 4, spec.xlabel, "lab", "middle");
    axisTitles(svg, W, H, L, R, T, B, { ylabel: spec.ylabel });
    if (spec.legendLo) {
      const d = document.createElement("div");
      d.className = "legend";
      d.innerHTML = `<span>${spec.legendLo}</span>${ramp.map((c) => `<i style="background:var(${c});margin:0"></i>`).join("")}<span style="margin-left:6px">${spec.legendHi}</span>`;
      wrap.appendChild(d);
    }
  }
  /* Axis titles: x under the tick labels, y rotated along the left edge. */
  function axisTitles(svg, W, H, L, R, T, B, spec) {
    if (spec.xlabel) text(svg, (L + W - R) / 2, H - 4, spec.xlabel, "lab", "middle");
    if (spec.ylabel) {
      const tt = text(svg, 0, 0, spec.ylabel, "lab", "middle");
      tt.setAttribute("transform", `translate(12 ${(T + H - B) / 2}) rotate(-90)`);
    }
  }

  function legend(wrap, items) {
    const d = document.createElement("div");
    d.className = "legend";
    items.forEach((it) => { const s = document.createElement("span"); s.innerHTML = `<i style="background:${it.color}"></i>`; s.appendChild(document.createTextNode(it.name)); d.appendChild(s); });
    wrap.appendChild(d);
  }

  window.Charts = { divergingBars, columns, lines, grid, legend, color, hover, hideTip };
})();
