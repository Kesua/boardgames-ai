/* boardgames.ai dashboard: a static single-page app over site/data (built by tools/build_site.py).
   Routes: #/                     home (all games)
           #/<game>[/<tab>[/<item>]][?p=2&v=new]   one game; tabs: discoveries strategy items boards style length
                                                    more compare lab                                        */
(function () {
  "use strict";
  const C = window.Charts;
  const S = { lang: "en", ui: {}, game: null, cache: {} };
  const $ = (sel, root) => (root || document).querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ------------------------------------------------------------------ data
  async function getJSON(url) {
    if (!S.cache[url]) S.cache[url] = fetch(url, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(url + " " + r.status); return r.json(); });
    return S.cache[url];
  }
  const loadIndex = () => getJSON("data/index.json");
  const loadGame = (slug) => getJSON(`data/${slug}/game.json`);
  const loadExp = (slug, id) => getJSON(`data/${slug}/exp/${id}.json`);

  // ------------------------------------------------------------------ text
  let UI = {};
  async function loadLang(lang) {
    UI = await getJSON(`i18n/${lang}.json`);
    if (lang !== "en") UI = Object.assign({}, await getJSON("i18n/en.json"), UI);
  }
  function t(key, vars) {
    let s = UI[key] ?? key;
    for (const k in vars || {}) s = s.split("{" + k + "}").join(vars[k]);
    return s;
  }
  const L = (obj) => (obj && typeof obj === "object" ? (obj[S.lang] ?? obj.en ?? "") : obj ?? "");
  function term(g, key) { const tt = g.manifest.terms || {}; return (tt[S.lang] || tt.en || {})[key] || t("term_" + key); }
  function itemName(g, key) {
    const i18n = g.i18n[S.lang] || g.i18n.en || {};
    const fromI18n = i18n.items && i18n.items[key] && i18n.items[key].name;
    if (fromI18n) return fromI18n;
    const card = g.catalog.cards && g.catalog.cards[key];
    if (card) return card.label;
    return String(key).toLowerCase().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  function tagName(g, kind, value) {
    const i18n = g.i18n[S.lang] || g.i18n.en || {};
    const m = (i18n.tags && i18n.tags[kind]) || {};
    if (m[value]) return m[value];
    if (kind === "archetype" || kind === "_arch") return archName(g, value);
    return t("v_" + value) !== "v_" + value ? t("v_" + value) : String(value).replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
  }
  function archName(g, value) {
    const i18n = g.i18n[S.lang] || g.i18n.en || {};
    if (i18n.archetypes && i18n.archetypes[value]) return i18n.archetypes[value];
    if (t("v_" + value) !== "v_" + value) return t("v_" + value);
    return tagName(g, g.manifest.archetype ? g.manifest.archetype.tag : "", value);
  }
  function agentName(g, raw) {
    if (!raw) return "";
    if (raw.startsWith("model:")) return modelLabel(g, raw.slice(6));
    return t("agent_" + raw);
  }
  function modelLabel(g, id) {
    const m = g.models[id];
    if (!m) return id;
    const steps = m.steps ? fmtSteps(m.steps) : "";
    return `${t(m.strength && m.strength.legacy ? "ai_original" : "ai_new")} (${steps})`;
  }

  // ------------------------------------------------------------------ numbers
  const nf = (d) => new Intl.NumberFormat(S.lang === "cs" ? "cs-CZ" : "en-GB", { minimumFractionDigits: d, maximumFractionDigits: d });
  const num = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? "–" : nf(d).format(v));
  const int = (v) => num(v, 0);
  const pct = (v, d = 0) => (v === null || v === undefined ? "–" : num(v * 100, d) + " %");
  const pp = (v, d = 1) => (v === null || v === undefined ? "–" : (v > 0 ? "+" : v < 0 ? "−" : "") + num(Math.abs(v * 100), d) + " " + t("pp"));
  const signed = (v, d = 2) => (v === null || v === undefined ? "–" : (v > 0 ? "+" : v < 0 ? "−" : "") + num(Math.abs(v), d));
  function fmtSteps(n) { return n >= 1e6 ? num(n / 1e6, n % 1e6 ? 1 : 0) + " " + t("million") : int(n); }
  function fmtBy(f, v) {
    switch (f) {
      case "pct": return pct(v, 1);
      case "pp": return pp(v);
      case "int": return int(v);
      case "num1": return num(v, 1);
      case "num2": return num(v, 2);
      case "decile": return `${v * 10}–${v * 10 + 10} %`;
      case "plus3": return v >= 3 ? "3+" : String(v);
      default: return v;
    }
  }

  // ------------------------------------------------------------------ routing
  function parseHash() {
    const h = location.hash.replace(/^#\/?/, "");
    const [path, qs] = h.split("?");
    const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
    const q = Object.fromEntries(new URLSearchParams(qs || ""));
    return { game: parts[0] || null, tab: parts[1] || "discoveries", item: parts[2] || null, q };
  }
  function link(game, tab, item, q) {
    const r = parseHash();
    const params = new URLSearchParams(Object.assign({}, game === r.game ? r.q : {}, q || {}));
    for (const [k, v] of [...params]) if (v === "" || v === undefined || v === null) params.delete(k);
    const s = params.toString();
    return "#/" + [game, tab, item].filter(Boolean).map(encodeURIComponent).join("/") + (s ? "?" + s : "");
  }

  async function render() {
    const r = parseHash();
    const main = $("#main");
    try {
      const index = await loadIndex();
      renderHeader(index, r);
      if (r.game === "how") { renderHow(main); return; }
      if (!r.game) { renderHome(main, index); return; }
      const meta = index.games.find((x) => x.slug === r.game);
      if (!meta) { main.innerHTML = `<p class="empty">${esc(t("not_found"))}</p>`; return; }
      const g = await loadGame(r.game);
      document.documentElement.style.setProperty("--accent", (g.manifest.theme || {}).accent || "#2c6e8f");
      await renderGame(main, g, r);
    } catch (e) {
      console.error(e);
      main.innerHTML = `<div class="card"><h2>${esc(t("error"))}</h2><p class="sub">${esc(e.message)}</p></div>`;
    }
    C.hideTip();
  }

  function renderHeader(index, r) {
    const sw = $("#game-switch");
    const hl = $("#howto-link");
    hl.textContent = t("how_read");
    hl.classList.toggle("on", r.game === "how");
    sw.innerHTML = `<a href="#/" class="${r.game ? "" : "on"}">${esc(t("all_games"))}</a>` + index.games.map((g) =>
      `<a href="#/${g.slug}" class="${r.game === g.slug ? "on" : ""}">${esc(g.name)}</a>`).join("");
    if (!r.game) {
      document.documentElement.style.removeProperty("--accent");
    }
    const gm = index.games.find((x) => x.slug === r.game);
    document.title = (r.game === "how" ? t("how_title") + " — " : gm ? gm.name + " — " : "") + "boardgames.ai";
    $("#foot").innerHTML = `${esc(t("footer", { date: index.generated }))} <a href="https://github.com/boardgames-ai/boardgames-ai">GitHub</a>`;
  }

  // ------------------------------------------------------------------ how to read the numbers
  function renderHow(main) {
    const terms = ["g_lift", "g_pp", "g_err", "g_edge", "g_presence", "g_points", "g_type", "g_mirror", "g_seed", "g_strength", "g_grey", "g_corr"];
    main.innerHTML = `<section class="hero"><div class="eyebrow">${esc(t("how_read"))}</div><h1>${esc(t("how_title"))}</h1>
      <p class="lede">${esc(t("how_lede"))}</p></section>
      <div class="card"><h2>${esc(t("how_example_h"))}</h2><p class="takeaway">${esc(t("how_example"))}</p></div>
      <div class="card section"><h2>${esc(t("glossary_h"))}</h2><dl class="gloss">${terms.map((k) => `<dt>${esc(t(k))}</dt><dd>${esc(t(k + "_d"))}</dd>`).join("")}</dl></div>
      <p class="caveat">${esc(t("caveat"))}</p>`;
  }

  // ------------------------------------------------------------------ home
  function renderHome(main, index) {
    main.innerHTML = `
      <section class="hero">
        <div class="eyebrow">${esc(t("home_eyebrow"))}</div>
        <h1>${esc(t("home_q"))}</h1>
        <p class="lede">${esc(t("home_lede"))}</p>
        <div class="steps">
          <div class="step"><h3>${esc(t("step1_t"))}</h3><p>${esc(t("step1"))}</p></div>
          <div class="step"><h3>${esc(t("step2_t"))}</h3><p>${esc(t("step2"))}</p></div>
          <div class="step"><h3>${esc(t("step3_t"))}</h3><p>${esc(t("step3"))}</p></div>
        </div>
      </section>
      <section class="section"><h2>${esc(t("games_h"))}</h2><p class="sub">${esc(t("games_sub"))}</p>
        <div class="grid cols-2" style="margin-top:12px">${index.games.map(gameCard).join("")}</div></section>
      <section class="section grid cols-2">
        <div class="card"><h2>${esc(t("add_h"))}</h2><p class="takeaway">${esc(t("add_text"))}</p>
          <ol class="clean" style="margin-top:10px">${["add_1", "add_2", "add_3", "add_4"].map((k) => `<li>${esc(t(k))}</li>`).join("")}</ol>
          <p style="margin-top:10px"><a href="https://github.com/boardgames-ai/boardgames-ai/blob/main/CONTRIBUTING.md">${esc(t("add_link"))}</a></p></div>
        <div class="card"><h2>${esc(t("trust_h"))}</h2><ul class="clean">${["trust_1", "trust_2", "trust_3", "trust_4"].map((k) => `<li>${esc(t(k))}</li>`).join("")}</ul></div>
      </section>
      <p class="caveat">${esc(t("caveat"))}</p>`;
  }
  function gameCard(g) {
    const hl = Object.entries(g.headline || {});
    const games = hl.reduce((a, [, h]) => a + h.games, 0);
    const counts = hl.map(([p]) => p).join(" · ");
    const status = hl.length ? (hl.some(([, h]) => h.finished) ? `<span class="pill ok">${esc(t("model_finished"))}</span>` : `<span class="pill warn">${esc(t("model_legacy"))}</span>`)
      : `<span class="pill">${esc(t("model_training"))}</span>`;
    return `<a class="card gcard" href="#/${g.slug}" style="--gaccent:${esc((g.theme || {}).accent || "")}">
      <div class="gtitle"><span class="emoji" aria-hidden="true">${esc((g.theme || {}).emoji || "🎲")}</span>
        <div><h2>${esc(g.name)}</h2><div class="sub">${esc([g.publisher, g.year].filter(Boolean).join(", "))}</div></div></div>
      <p>${esc(L(g.intro))}</p>
      <div class="kv"><div><b>${games ? int(games) : "–"}</b><span>${esc(t("games_analysed"))}</span></div>
        <div><b>${esc(counts || "–")}</b><span>${esc(t("player_counts"))}</span></div>
        <div><b>${int(g.models)}</b><span>${esc(t("models"))}</span></div></div>
      <div class="row">${status}<span class="sub">${esc(t("open_game"))} →</span></div></a>`;
  }

  // ------------------------------------------------------------------ game shell
  function sources(g, r) {
    const feat = g.manifest.featured || {};
    const pc = Object.keys(feat).sort((a, b) => a - b);
    const pFilter = r.q.p && feat[r.q.p] ? [r.q.p] : pc;
    const v = r.q.v || "new";
    const out = [];
    for (const p of pFilter) {
      const f = feat[p];
      const main = { key: p, players: +p, variant: "new", exp: f.main };
      const old = f.compare ? { key: p + "o", players: +p, variant: "old", exp: f.compare } : null;
      if (v === "old") out.push(old || main); else if (v === "both") out.push(main, ...(old ? [old] : [])); else out.push(main);
    }
    return out;
  }
  function srcLabel(g, s) {
    const pl = t("n_players", { n: s.players });
    const hasCompare = !!((g.manifest.featured || {})[String(s.players)] || {}).compare;
    if (!hasCompare) return pl;
    return `${pl} · ${t(s.variant === "old" ? "ai_original" : "ai_new")}`;
  }

  async function renderGame(main, g, r) {
    const m = g.manifest;
    const feat = m.featured || {};
    const hasCompare = Object.values(feat).some((f) => f.compare);
    const tabs = [["discoveries", t("tab_discoveries")], ["strategy", t("tab_strategy")], ["items", cap(term(g, "items"))],
      ["boards", cap(term(g, "boards"))], ["style", t("tab_style")]];
    const srcs = sources(g, r);
    const exps = await Promise.all(srcs.map((s) => loadExp(g.slug, s.exp)));
    if (!srcs.length) { renderNoData(main, g, r); return; }
    const anyLength = exps.some((e) => e.length);
    if (anyLength) tabs.push(["length", t("tab_length")]);
    if (exps.some((e) => e.game && Object.keys(e.game).length)) tabs.push(["more", t("tab_more", { game: m.name })]);
    if (hasCompare) tabs.push(["compare", t("tab_compare")]);
    tabs.push(["lab", t("tab_lab")]);
    const pcs = Object.keys(feat).sort((a, b) => a - b);
    const filters = (pcs.length > 1 || hasCompare) && !["lab"].includes(r.tab) ? `<div class="filters">
      ${pcs.length > 1 ? `<span class="lbl">${esc(t("players"))}</span><div class="seg">${[["", t("all")], ...pcs.map((p) => [p, p])].map(([v, lab]) =>
        `<button type="button" data-q="p" data-v="${v}" class="${(r.q.p || "") === v ? "on" : ""}">${esc(lab)}</button>`).join("")}</div>` : ""}
      ${hasCompare && r.tab !== "compare" ? `<span class="lbl">${esc(t("ai"))}</span><div class="seg">${[["", t("ai_new")], ["old", t("ai_original")], ["both", t("side_by_side")]].map(([v, lab]) =>
        `<button type="button" data-q="v" data-v="${v}" class="${(r.q.v || "") === v ? "on" : ""}">${esc(lab)}</button>`).join("")}</div>` : ""}
    </div>` : "";
    main.innerHTML = `<section class="ghead"><div class="title"><span class="emoji" style="font-size:30px" aria-hidden="true">${esc((m.theme || {}).emoji || "")}</span>
        <div><div class="eyebrow">${esc([m.publisher, m.year, m.designer].filter(Boolean).join(" · "))}</div><h1 style="font-size:clamp(26px,3.6vw,36px)">${esc(m.name)}</h1></div></div></section>
      <nav class="tabs" aria-label="${esc(t("sections"))}">${tabs.map(([k, lab]) => `<a href="${link(g.slug, k)}" class="${r.tab === k ? "on" : ""}">${esc(lab)}</a>`).join("")}</nav>
      ${filters}<div id="view"></div>`;
    main.querySelectorAll(".filters button").forEach((b) => b.addEventListener("click", () => {
      location.hash = link(g.slug, r.tab, r.item, { [b.dataset.q]: b.dataset.v });
    }));
    const view = $("#view");
    const ctx = { g, r, srcs, exps, many: srcs.length > 1 };
    const fn = { discoveries: vDiscoveries, strategy: vStrategy, items: r.item ? vProfile : vItems, boards: vBoards, style: vStyle,
                 length: vLength, more: vMore, compare: vCompare, lab: vLab }[r.tab] || vDiscoveries;
    await fn(view, ctx);
  }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  /* A game whose AI is still training: say so, show what is already there (rules, cards, training progress). */
  function renderNoData(main, g, r) {
    const m = g.manifest;
    const tab = r.tab === "lab" ? "lab" : "discoveries";
    main.innerHTML = `<section class="ghead"><div class="title"><span class="emoji" style="font-size:30px" aria-hidden="true">${esc((m.theme || {}).emoji || "")}</span>
        <div><div class="eyebrow">${esc([m.publisher, m.year, m.designer].filter(Boolean).join(" · "))}</div><h1 style="font-size:clamp(26px,3.6vw,36px)">${esc(m.name)}</h1></div></div></section>
      <nav class="tabs"><a href="${link(g.slug, "discoveries")}" class="${tab === "discoveries" ? "on" : ""}">${esc(t("tab_discoveries"))}</a>
        <a href="${link(g.slug, "lab")}" class="${tab === "lab" ? "on" : ""}">${esc(t("tab_lab"))}</a></nav><div id="view"></div>`;
    const view = $("#view");
    if (tab === "lab") { vLab(view, { g }); return; }
    view.innerHTML = `<section class="hero" style="padding-top:0"><h1>${esc(t("game_q", { game: m.name }))}</h1><p class="lede">${esc(L(m.intro))}</p></section>
      <div class="card"><h2>${esc(t("training_now_h"))}</h2><p class="takeaway">${esc(t("training_now", { n: Object.keys(g.catalog.items || {}).length, items: term(g, "items") }))}</p>
      <p style="margin-top:10px"><a href="${link(g.slug, "lab")}">${esc(t("tab_lab"))} →</a></p></div>`;
  }

  // ------------------------------------------------------------------ discoveries
  function vDiscoveries(view, { g, srcs, exps, many }) {
    const m = g.manifest;
    const tiles = [
      [t("t_games"), exps.map((e) => e.meta.games), int],
      [t("t_boards", { boards: term(g, "boards") }), exps.map((e) => e.meta.boards), int],
      [t("t_training"), srcs.map((s) => (g.models[g.experiments[s.exp].seats[0]] || {}).steps), (v) => (v ? fmtSteps(v) : "–")],
      [t("t_winner"), exps.map((e) => e.meta.winner_score), (v) => num(v, 0)],
      [t("t_best"), exps.map((e) => e.meta.best_score), int]];
    const notes = g.notes || {};
    const variant = (srcs[0] || {}).variant === "old" ? "compare" : "main";
    const findings = (notes.findings || []).filter((f) => f.variant === variant || (!f.variant && variant === "main"));
    const pcs = srcs.map((s) => s.key);
    view.innerHTML = `
      <section class="hero" style="padding-top:0">
        <h1>${esc(t("game_q", { game: m.name }))}</h1>
        <p class="lede">${esc(L(m.intro))} ${esc(t("game_lede_tail"))}</p></section>
      ${oneLine(g, srcs)}
      <div class="tiles">${tiles.map(([lab, vals, f]) => `<div class="tile"><div class="lab">${esc(lab)}</div><div class="vals">${vals.map((v, i) =>
        `<div class="v"><b>${esc(f(v))}</b><span>${esc(srcLabel(g, srcs[i], many))}</span></div>`).join("")}</div></div>`).join("")}</div>
      <section class="section"><h2>${esc(t("how_h"))}</h2>
        <div class="steps">
          <div class="step"><h3>${esc(t("step1_t"))}</h3><p>${esc(howLearn(g, srcs))}</p></div>
          <div class="step"><h3>${esc(t("step2_t"))}</h3><p>${esc(t("how_play", { games: int(exps[0] ? exps[0].meta.games : 0) }))}</p></div>
          <div class="step"><h3>${esc(t("step3_t"))}</h3><p>${esc(t("how_count", { boards: term(g, "boards"), items: term(g, "items") }))}</p></div></div></section>
      <section class="section"><h2>${esc(t("findings_h"))}</h2>
        ${findings.length ? `<div class="grid cols-3" style="margin-top:12px">${findings.map((f) => finding(g, f, pcs)).join("")}</div>`
          : `<p class="sub" style="margin-top:6px">${esc(t("findings_none"))}</p>`}
        ${autoFindings(g, srcs, exps)}
        <p class="caveat">${esc(notes.written ? t("findings_caveat", { date: notes.written }) : t("caveat"))}</p></section>`;
  }
  function oneLine(g, srcs) {
    const notes = (g.notes && g.notes.experiments) || {};
    const parts = srcs.map((s) => { const n = notes[s.exp]; const x = n ? n[S.lang] || n.en : null; return x && x.summary ? [s, x.summary] : null; }).filter(Boolean);
    if (!parts.length) return "";
    return `<div class="grid ${parts.length > 1 ? "cols-2" : ""}" style="margin-bottom:14px">${parts.map(([s, txt]) => `<div class="card oneline">
      <div class="who">${esc(t("plan_one_line"))} · ${esc(srcLabel(g, s))}</div><p>${esc(txt)}</p>
      <a href="${link(g.slug, "strategy", null, { p: String(s.players) })}">${esc(t("read_strategy"))} →</a></div>`).join("")}</div>`;
  }
  function howLearn(g, srcs) {
    const parts = srcs.filter((s) => s.variant === "new").map((s) => {
      const mid = g.experiments[s.exp].seats[0];
      const m = g.models[mid] || {};
      return t("how_learn_one", { steps: m.steps ? fmtSteps(m.steps) : "?", players: t("n_players", { n: s.players }) });
    });
    return t("how_learn", { list: parts.join(", ") });
  }
  function finding(g, f, pcs) {
    const x = f[S.lang] || f.en;
    const nums = pcs.filter((p) => !p.endsWith("o")).map((p) => [p, x["n" + p]]).filter(([, v]) => v);
    return `<article class="card finding"><h3>${esc(x.title)}</h3>
      ${nums.length ? `<div class="nums">${nums.map(([p, v]) => `<div><b>${esc(v)}</b><span>${esc(t("n_players", { n: p }))}</span></div>`).join("")}</div>` : ""}
      <p class="sub">${esc(x.label || "")}</p><p>${esc(x.text)}</p>${x.before ? `<p class="before">${esc(x.before)}</p>` : ""}
      ${f.link ? `<a href="${link(g.slug, f.link.replace(/^#/, ""))}">${esc(t("show_chart"))} →</a>` : ""}</article>`;
  }
  /* Data-driven takeaways shown under the written findings: always current, even before notes are written. */
  function autoFindings(g, srcs, exps) {
    const cards = [];
    exps.forEach((e, i) => {
      if (!e.items) return;
      const min = Math.max(30, e.meta.boards * 0.05);
      const ok = e.items.filter((r) => r.boards_with >= min);
      const best = ok.slice().sort((a, b) => b.win_lift - a.win_lift)[0];
      const worst = ok.slice().sort((a, b) => a.win_lift - b.win_lift)[0];
      const first = e.seat_order && e.seat_order[0];
      const lab = srcLabel(g, srcs[i], srcs.length > 1);
      if (best) cards.push([t("auto_best", { item: term(g, "item") }), itemName(g, best.item), pp(best.win_lift), lab, link(g.slug, "items", best.item)]);
      if (worst) cards.push([t("auto_worst", { item: term(g, "item") }), itemName(g, worst.item), pp(worst.win_lift), lab, link(g.slug, "items", worst.item)]);
      if (first) cards.push([t("auto_first"), pct(first.win_rate, 1), t("auto_first_sub", { base: pct(e.meta.baseline_win_rate, 0) }), lab, link(g.slug, "strategy")]);
    });
    if (!cards.length) return "";
    return `<h3 style="margin-top:22px">${esc(t("auto_h"))}</h3><p class="sub">${esc(t("auto_sub"))}</p>
      <div class="grid cols-4" style="margin-top:10px">${cards.map(([h, v, sub, lab, href]) => `<a class="card" href="${href}" style="text-decoration:none;color:inherit">
      <div class="eyebrow">${esc(h)}</div><div style="font-size:19px;font-weight:700;margin-top:4px">${esc(v)}</div>
      <div class="sub">${esc(sub)} · ${esc(lab)}</div></a>`).join("")}</div>`;
  }

  // ------------------------------------------------------------------ strategy
  function vStrategy(view, { g, srcs, exps, many }) {
    const notes = (g.notes && g.notes.experiments) || {};
    let html = "";
    srcs.forEach((s, i) => {
      const n = notes[s.exp];
      const x = n ? n[S.lang] || n.en : null;
      const e = exps[i];
      html += `<section class="section card"><div class="spread"><h2>${esc(srcLabel(g, s, true))}</h2>
        <span class="sub">${esc(t("based_on", { games: int(e.meta.games) }))}</span></div>
        ${x ? `<p class="lede" style="margin-top:8px">${esc(x.summary)}</p>
        <div class="grid cols-2" style="margin-top:8px"><div class="notes-block"><h3>${esc(t("works"))}</h3><ul class="clean">${(x.works || []).map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>
        <div class="notes-block"><h3>${esc(t("avoid"))}</h3><ul class="clean">${(x.avoid || []).map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div></div>
        ${x.order ? `<h3 style="margin-top:12px">${esc(t("order"))}</h3><p class="takeaway">${esc(x.order)}</p>` : ""}
        ${x.length ? `<h3 style="margin-top:12px">${esc(t("length"))}</h3><ul class="clean">${(Array.isArray(x.length) ? x.length : [x.length]).map((w) => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}`
        : `<p class="sub" style="margin-top:6px">${esc(t("notes_none"))}</p>`}
        <h3 style="margin-top:16px">${esc(t("help_hurt_h", { items: cap(term(g, "items")) }))}</h3>
        <p class="sub">${esc(t("lift_expl", { boards: term(g, "boards") }))} ${esc(t("min_boards", { n: minBoards(e), boards: term(g, "boards") }))}</p>
        <div id="help-${i}" style="margin-top:6px"></div>
        ${e.archetypes ? `<h3 style="margin-top:16px">${esc(cap(term(g, "archetypes")))}</h3><p class="sub">${esc(L((g.manifest.archetype || {}).rule))}</p><div id="arch-${i}"></div>` : ""}
        <h3 style="margin-top:16px">${esc(t("order"))}</h3><p class="sub">${esc(t("order_expl"))}</p><div id="seat-${i}"></div>
      </section>`;
    });
    view.innerHTML = html;
    srcs.forEach((s, i) => {
      const e = exps[i];
      const min = minBoards(e);
      const ok = e.items.filter((r) => r.boards_with >= min);
      const row = (r) => ({ label: itemName(g, r.item), value: r.win_lift, err: 2 * (r.win_lift_se || 0),
        tip: `<b>${esc(itemName(g, r.item))}</b><br>${esc(t("win_lift"))}: ${pp(r.win_lift)} (± ${pp(2 * (r.win_lift_se || 0)).replace(/^[+−]/, "")})<br>${esc(t("presence"))}: ${pct(r.presence_rate, 0)}<br>${esc(t("points_per", { item: term(g, "item") }))}: ${num(r.points_per_copy, 1)}${r.winner_edge !== null && r.winner_edge !== undefined ? `<br>${esc(t("winner_edge"))}: ${signed(r.winner_edge)}` : ""}` });
      const sorted = ok.slice().sort((a, b) => b.win_lift - a.win_lift);
      const pick = sorted.length > 20 ? sorted.slice(0, 10).concat(sorted.slice(-10)) : sorted;
      C.divergingBars($("#help-" + i), pick.map(row), { fmt: (v) => pp(v, 0) });
      if (e.archetypes) C.divergingBars($("#arch-" + i), e.archetypes.filter((r) => r.boards >= 20).map((r) => ({
        label: `${archName(g, r.archetype)} · ${pct(r.share, 0)}`, value: r.win_lift, err: 2 * (r.win_lift_se || 0),
        tip: `<b>${esc(archName(g, r.archetype))}</b><br>${esc(t("share_of", { boards: term(g, "boards") }))}: ${pct(r.share, 1)}<br>${esc(t("win_rate"))}: ${pct(r.win_rate, 1)}<br>${esc(t("win_lift"))}: ${pp(r.win_lift)}` })), { fmt: (v) => pp(v, 0), labelW: 230 });
      C.divergingBars($("#seat-" + i), e.seat_order.map((r) => ({ label: `${t("seat_n", { n: r.seat + 1 })} · ${pct(r.win_rate, 1)}`,
        value: r.win_rate - e.meta.baseline_win_rate, err: 2 * Math.sqrt(r.win_rate * (1 - r.win_rate) / r.seats),
        tip: `<b>${esc(t("seat_n", { n: r.seat + 1 }))}</b><br>${esc(t("win_rate"))}: ${pct(r.win_rate, 1)} (${esc(t("equal_share"))} ${pct(e.meta.baseline_win_rate, 0)})<br>${esc(t("mean_score"))}: ${num(r.mean_score, 1)}` })), { fmt: (v) => pp(v, 1) });
    });
  }
  const minBoards = (e) => Math.max(30, Math.round(e.meta.boards * 0.05));

  // ------------------------------------------------------------------ items list + profile
  function vItems(view, { g, srcs, exps }) {
    const e = exps[0], s = srcs[0];
    const min = minBoards(e);
    const cat = g.catalog.items || {};
    const tagKinds = Object.keys(g.manifest.tags || {});
    view.innerHTML = `<div class="spread"><div><h2>${esc(cap(term(g, "items")))}</h2><p class="sub">${esc(t("items_expl", { n: e.items.length, boards: term(g, "boards"), src: srcLabel(g, s, true) }))}</p></div>
      <div class="row"><input type="search" id="q" placeholder="${esc(t("search"))}" aria-label="${esc(t("search"))}">
      ${tagKinds.length ? `<select id="tagf" aria-label="${esc(t("filter"))}"><option value="">${esc(t("all"))}</option>${tagKinds.map((k) => {
        const vals = [...new Set(Object.values(cat).flatMap((it) => (it.tags && it.tags[k]) || []))].sort();
        return `<optgroup label="${esc(L(g.manifest.tags[k]))}">${vals.map((v) => `<option value="${esc(k + ":" + v)}">${esc(tagName(g, k, v))}</option>`).join("")}</optgroup>`;
      }).join("")}</select>` : ""}</div></div>
      <div class="table-wrap" style="margin-top:12px"><table><thead><tr>
        <th>${esc(cap(term(g, "item")))}</th><th class="num sort" data-k="presence_rate">${esc(t("presence"))}</th>
        <th class="num sort" data-k="win_lift">${esc(t("win_lift"))}</th><th class="num sort" data-k="points_per_copy">${esc(t("points_per", { item: term(g, "item") }))}</th>
        <th class="num sort" data-k="winner_edge">${esc(t("winner_edge"))}</th><th class="num sort" data-k="boards_with">${esc(cap(t("boards_with", { boards: term(g, "boards") })))}</th>
      </tr></thead><tbody id="rows"></tbody></table></div><p class="sub" style="margin-top:8px">${esc(t("grey_note", { n: min, boards: term(g, "boards") }))}</p>`;
    let key = "win_lift", dir = -1;
    const draw = () => {
      const q = $("#q").value.trim().toLowerCase();
      const tf = $("#tagf") ? $("#tagf").value : "";
      const rows = e.items.filter((r) => {
        if (q && !itemName(g, r.item).toLowerCase().includes(q)) return false;
        if (tf) { const [k, v] = tf.split(":"); const it = cat[r.item] || {}; if (!((it.tags || {})[k] || []).includes(v)) return false; }
        return true;
      }).sort((a, b) => ((b.boards_with >= min) - (a.boards_with >= min)) || dir * ((a[key] ?? -1e9) - (b[key] ?? -1e9)));
      const max = Math.max(...e.items.map((r) => Math.abs(r.win_lift)));
      $("#rows").innerHTML = rows.map((r) => `<tr class="${r.boards_with < min ? "dim" : ""}">
        <td class="namecell"><a href="${link(g.slug, "items", r.item)}">${esc(itemName(g, r.item))}</a></td>
        <td class="num">${pct(r.presence_rate, 0)}</td>
        <td class="num">${pp(r.win_lift)} <span class="minibar" style="width:${Math.round(40 * Math.abs(r.win_lift) / max)}px;background:${r.win_lift >= 0 ? "var(--pos)" : "var(--neg)"}"></span></td>
        <td class="num">${num(r.points_per_copy, 1)}</td><td class="num">${signed(r.winner_edge)}</td><td class="num">${int(r.boards_with)}</td></tr>`).join("")
        || `<tr><td colspan="6" class="muted">${esc(t("no_match"))}</td></tr>`;
    };
    view.querySelectorAll("th.sort").forEach((th) => th.addEventListener("click", () => { dir = key === th.dataset.k ? -dir : -1; key = th.dataset.k; draw(); }));
    $("#q").addEventListener("input", draw);
    if ($("#tagf")) $("#tagf").addEventListener("change", draw);
    draw();
  }

  function describeItem(g, key) {
    const i18n = (g.i18n[S.lang] || g.i18n.en || {}).items || {};
    const it = i18n[key] || {};
    const cat = (g.catalog.items || {})[key] || {};
    const lines = [];
    ["effect", "bonus", "scoring", "note"].forEach((k) => { if (it[k]) lines.push([t("d_" + k), it[k]]); });
    if (cat.power_text) lines.push([t("d_power"), cat.power_text]);
    return lines;
  }

  function vProfile(view, { g, r, srcs, exps }) {
    const key = r.item;
    const cat = (g.catalog.items || {})[key] || {};
    const attrs = (g.manifest.item_attributes || []).filter((a) => cat[a] !== undefined && cat[a] !== null && !(Array.isArray(cat[a]) && !cat[a].length));
    const fmtAttr = (a, v) => Array.isArray(v) ? v.map((x) => tagName(g, a, x)).join(", ") : typeof v === "boolean" ? (v ? t("yes") : t("no")) : (typeof v === "string" ? tagName(g, a, v) : v);
    const desc = describeItem(g, key);
    let html = `<p><a href="${link(g.slug, "items")}">← ${esc(t("all_items", { items: term(g, "items") }))}</a></p>
      <div class="card" style="margin-top:10px"><h2>${esc(itemName(g, key))}</h2>
        <div class="attrs" style="margin-top:8px">${attrs.map((a) => `<span class="pill">${esc(t("a_" + a))}: ${esc(fmtAttr(a, cat[a]))}</span>`).join("")}</div>
        ${desc.length ? `<div style="margin-top:10px">${desc.map(([k, v]) => `<p class="desc"><b>${esc(k)}:</b> ${esc(v)}</p>`).join("")}</div>` : ""}</div>
      <div class="grid cols-2" style="margin-top:14px">`;
    srcs.forEach((s, i) => {
      const e = exps[i];
      const st = e.items.find((x) => x.item === key);
      const cards = (cat.cards || [key]);
      const fate = e.cards ? e.cards.filter((c) => cards.includes(c.card)) : [];
      const fateNames = Object.keys(g.manifest.fate || {}).concat(["left_in_hand"]);
      const tot = Object.fromEntries(fateNames.map((k) => [k, fate.reduce((a, c) => a + (c[k] || 0), 0)]));
      const sum = Object.values(tot).reduce((a, b) => a + b, 0);
      html += `<div class="card"><h3>${esc(srcLabel(g, s, true))}</h3>${st ? `
        <div class="kv" style="margin-top:10px"><div><b>${pp(st.win_lift)}</b><span>${esc(t("win_lift"))}</span></div>
        <div><b>${pct(st.presence_rate, 0)}</b><span>${esc(t("presence"))}</span></div>
        <div><b>${num(st.points_per_copy, 1)}</b><span>${esc(t("points_per", { item: term(g, "item") }))}</span></div>
        <div><b>${signed(st.winner_edge)}</b><span>${esc(t("winner_edge"))}</span></div></div>
        <p class="sub" style="margin-top:8px">${esc(t("profile_expl", { win: pct(st.win_rate, 1), base: pct(e.meta.baseline_win_rate, 0), n: int(st.boards_with), boards: term(g, "boards") }))}</p>`
        : `<p class="sub">${esc(t("never_on_board", { boards: term(g, "boards") }))}</p>`}
        ${sum ? `<h3 style="margin-top:12px">${esc(t("fate_h"))}</h3><div id="fate-${i}"></div>` : ""}
        ${e.length ? `<h3 style="margin-top:12px">${esc(t("by_length"))}</h3><div id="len-${i}"></div>` : ""}</div>`;
    });
    view.innerHTML = html + "</div>";
    srcs.forEach((s, i) => {
      const e = exps[i];
      const cards = (cat.cards || [key]);
      const fate = e.cards ? e.cards.filter((c) => cards.includes(c.card)) : [];
      const fateNames = Object.keys(g.manifest.fate || {}).concat(["left_in_hand"]);
      const tot = fateNames.map((k) => fate.reduce((a, c) => a + (c[k] || 0), 0));
      if ($("#fate-" + i)) C.columns($("#fate-" + i), { x: fateNames.map((k) => L((g.manifest.fate_labels || {})[k]) || k), series: [{ name: t("cards_n"), values: tot }], fmt: int, height: 180 });
      if (e.length && $("#len-" + i)) {
        const bins = Object.fromEntries(e.length.bins.map((b) => [b.bin, b]));
        const pts = e.length.items.filter((x) => x.item === key).map((x) => ({ x: bins[x.bin].rounds_mean, y: x.win_lift, hollow: x.boards < 30,
          tip: `${esc(t("rounds_range", { a: num(bins[x.bin].rounds_min, 1), b: num(bins[x.bin].rounds_max, 1) }))}<br>${esc(t("win_lift"))}: ${pp(x.win_lift)}<br>${esc(term(g, "boards"))}: ${int(x.boards)}` }));
        C.lines($("#len-" + i), { series: [{ name: itemName(g, key), points: pts }], zero: true, yfmt: (v) => pp(v, 0), xfmt: (v) => num(v, 0), xlabel: t("rounds_per_player"), height: 200 });
      }
    });
  }

  // ------------------------------------------------------------------ boards
  function vBoards(view, { g, srcs, exps }) {
    const e = exps[0];
    const groups = { top: t("pos_top"), middle: t("pos_middle"), bottom: t("pos_bottom") };
    view.innerHTML = `<h2>${esc(t("boards_h", { boards: term(g, "boards") }))}</h2><p class="sub">${esc(t("boards_expl", { src: srcLabel(g, srcs[0], true) }))}</p>
      <div class="boards" style="margin-top:12px">${(e.samples || []).map((gm) => `<div class="card board">
        <div class="spread"><h3>${esc(groups[gm.position])} · ${esc(t("game_n", { n: gm.game_id }))}</h3><span class="sub">${esc(t("scores"))}: ${gm.scores.map(int).join(" : ")}</span></div>
        <div class="grid cols-2">${gm.boards.map((b) => drawBoard(g, b)).join("")}</div></div>`).join("")}</div>`;
  }
  function drawBoard(g, b) {
    const head = `<div class="spread"><b>${esc(t("seat_n", { n: b.seat + 1 }))}${b.win ? " · " + esc(t("winner")) : ""}</b><span class="sub">${int(b.score)} ${esc(t("points"))}</span></div>
      <div class="attrs">${Object.entries(b.breakdown).map(([k, v]) => `<span class="pill">${esc(L((g.manifest.score_categories || {})[k]) || k)}: ${int(v)}</span>`).join("")}</div>`;
    const items = b.items || [];
    const slots = new Set(items.map((x) => x.slot).filter((x) => x !== null && x !== undefined));
    const cross = [...slots].every((x) => ["TOP", "BOTTOM", "LEFT", "RIGHT"].includes(x));
    const byGroup = {};
    items.forEach((x) => { (byGroup[x.group] = byGroup[x.group] || []).push(x); });
    let body;
    if (cross) {
      body = `<div class="board-groups">${Object.keys(byGroup).sort((a, b2) => a - b2).map((gk) => {
        const its = byGroup[gk];
        const host = its.find((x) => x.slot === null || x.slot === undefined);
        const at = (pos) => its.filter((x) => x.slot === pos).map((x) => `<div class="bitem" title="${esc(itemName(g, x.item))}"><span>${esc(itemName(g, x.item))}</span><b>${int(x.points)}</b></div>`).join("");
        return `<div class="bgroup cross"><div class="c-top">${at("TOP")}</div><div class="c-left">${at("LEFT")}</div>
          <div class="c-host">${host ? `<div class="bitem"><span>${esc(itemName(g, host.item))}</span><b>${int(host.points)}</b></div>` : `<div class="bitem"><span>${esc(t("sapling"))}</span><b>0</b></div>`}</div>
          <div class="c-right">${at("RIGHT")}</div><div class="c-bottom">${at("BOTTOM")}</div></div>`;
      }).join("")}</div>`;
    } else {
      body = Object.keys(byGroup).map((gk) => `<div class="mat-row" style="margin-top:6px"><div class="rh">${esc(tagName(g, "habitat", gk))}</div>
        ${[0, 1, 2, 3, 4].map((c) => { const x = byGroup[gk].find((y) => y.slot === c); return x ? `<div class="slot filled"><div class="sn">${esc(itemName(g, x.item))}</div>
          <div class="sd">${int(x.points)} ${esc(t("points_short"))}${x.tags && x.tags.eggs ? ` · ${x.tags.eggs} 🥚` : ""}${x.tags && x.tags.tucked ? ` · ${x.tags.tucked} ${esc(t("tucked_short"))}` : ""}${x.tags && x.tags.cache ? ` · ${x.tags.cache} ${esc(t("cache_short"))}` : ""}</div></div>` : `<div class="slot"></div>`; }).join("")}</div>`).join("");
    }
    return `<div class="card flat">${head}<div style="margin-top:8px">${body}</div></div>`;
  }

  // ------------------------------------------------------------------ play style
  function vStyle(view, { g, srcs, exps }) {
    let html = "";
    srcs.forEach((s, i) => {
      html += `<section class="section card"><h2>${esc(srcLabel(g, s, true))}</h2>
        <div class="grid cols-2" style="margin-top:10px">
          <div><h3>${esc(t("action_mix"))}</h3><p class="sub">${esc(t("action_mix_expl"))}</p><div id="mix-${i}"></div></div>
          <div><h3>${esc(t("score_split"))}</h3><p class="sub">${esc(t("score_split_expl"))}</p><div id="split-${i}"></div></div>
          <div><h3>${esc(t("most_played", { items: term(g, "items") }))}</h3><div id="played-${i}"></div></div>
          <div><h3>${esc(t("most_points", { items: cap(term(g, "items")) }))}</h3><div id="points-${i}"></div></div>
          ${exps[i].style.optional_use && exps[i].style.optional_use.length ? `<div><h3>${esc(t("optional_h"))}</h3><p class="sub">${esc(t("optional_expl"))}</p><div id="opt-${i}"></div></div>` : ""}
        </div></section>`;
    });
    view.innerHTML = html;
    srcs.forEach((s, i) => {
      const st = exps[i].style;
      const acts = g.manifest.actions || {};
      const mix = st.action_mix.filter((r) => acts[r.action]);
      C.divergingBars($("#mix-" + i), mix.slice().sort((a, b) => b.share - a.share).map((r) => ({ label: L(acts[r.action]), value: r.share,
        tip: `<b>${esc(L(acts[r.action]))}</b><br>${pct(r.share, 1)} ${esc(t("of_turns"))}` })), { fmt: (v) => pct(v, 0), mag: true });
      const out = st.outcome[0] || {};
      const cats = Object.keys(g.manifest.score_categories || {});
      C.divergingBars($("#split-" + i), cats.map((k) => ({ label: L(g.manifest.score_categories[k]), value: out["b_" + k] || 0,
        tip: `<b>${esc(L(g.manifest.score_categories[k]))}</b><br>${num(out["b_" + k], 1)} ${esc(t("points"))}` })), { fmt: (v) => num(v, 0), mag: true });
      const top = (arr, k, n) => arr.slice().sort((a, b) => b[k] - a[k]).slice(0, n);
      C.divergingBars($("#played-" + i), top(st.items_played, "share", 10).map((r) => ({ label: itemName(g, r.item), value: r.share,
        tip: `<b>${esc(itemName(g, r.item))}</b><br>${pct(r.share, 1)} ${esc(t("of_plays"))}` })), { fmt: (v) => pct(v, 1), mag: true });
      C.divergingBars($("#points-" + i), top(st.points_by_item, "points_per_board", 10).map((r) => ({ label: itemName(g, r.item), value: r.points_per_board,
        tip: `<b>${esc(itemName(g, r.item))}</b><br>${num(r.points_per_board, 1)} ${esc(t("points_per_board", { board: term(g, "board") }))}` })), { fmt: (v) => num(v, 1), mag: true });
      if ($("#opt-" + i)) {
        const rows = st.optional_use.slice().sort((a, b) => a.use_rate - b.use_rate).slice(0, 12);
        const wname = (w) => (t("w_" + w) !== "w_" + w ? t("w_" + w) : w.replace(/_/g, " "));
        C.divergingBars($("#opt-" + i), rows.map((r) => ({ label: wname(r.what), value: r.use_rate,
          tip: `<b>${esc(wname(r.what))}</b><br>${esc(t("use_rate"))}: ${pct(r.use_rate, 1)}<br>${int(r.use)} / ${int(r.use + r.skip)}` })), { fmt: (v) => pct(v, 0), minMax: 1, mag: true });
      }
    });
  }

  // ------------------------------------------------------------------ game length
  function vLength(view, { g, srcs, exps }) {
    let html = "";
    srcs.forEach((s, i) => {
      if (!exps[i].length) return;
      html += `<section class="section card"><h2>${esc(srcLabel(g, s, true))}</h2>
        <p class="takeaway">${esc(t("length_expl", { a: num(exps[i].meta.rounds_min, 1), b: num(exps[i].meta.rounds_max, 1) }))}</p>
        <div class="grid cols-2" style="margin-top:10px"><div><h3>${esc(t("by_length_items", { items: cap(term(g, "items")) }))}</h3><p class="sub">${esc(t("by_length_expl"))}</p><div id="lenit-${i}"></div></div>
        <div><h3>${esc(t("hist_h"))}</h3><div id="hist-${i}"></div></div>
        ${exps[i].length.archetypes ? `<div><h3>${esc(t("by_length_items", { items: cap(term(g, "archetypes")) }))}</h3><div id="lenar-${i}"></div></div>` : ""}</div></section>`;
    });
    view.innerHTML = html;
    srcs.forEach((s, i) => {
      const ln = exps[i].length;
      if (!ln) return;
      const bins = Object.fromEntries(ln.bins.map((b) => [b.bin, b]));
      const mk = (key, name, rows) => ({ name, points: rows.map((x) => ({ x: bins[x.bin].rounds_mean, y: x.win_lift, hollow: x.boards < 30,
        tip: `<b>${esc(name)}</b><br>${esc(t("rounds_range", { a: num(bins[x.bin].rounds_min, 1), b: num(bins[x.bin].rounds_max, 1) }))}<br>${esc(t("win_lift"))}: ${pp(x.win_lift)}<br>${int(x.boards)} ${esc(term(g, "boards"))}` })) });
      C.lines($("#lenit-" + i), { series: ln.default_items.map((k) => mk(k, itemName(g, k), ln.items.filter((x) => x.item === k))), zero: true, yfmt: (v) => pp(v, 0), xfmt: (v) => num(v, 0), xlabel: t("rounds_per_player") });
      C.columns($("#hist-" + i), { x: ln.histogram.map((h) => h.rounds), series: [{ name: t("games"), values: ln.histogram.map((h) => h.games) }], fmt: int, height: 220 });
      if (ln.archetypes && $("#lenar-" + i)) {
        const keys = [...new Set(ln.archetypes.map((x) => x.archetype))].filter((k) => ln.archetypes.filter((x) => x.archetype === k && x.boards >= 30).length >= 3).slice(0, 6);
        C.lines($("#lenar-" + i), { series: keys.map((k) => mk(k, archName(g, k), ln.archetypes.filter((x) => x.archetype === k))), zero: true, yfmt: (v) => pp(v, 0), xfmt: (v) => num(v, 0), xlabel: t("rounds_per_player") });
      }
    });
  }

  // ------------------------------------------------------------------ game-specific sections (standard shapes)
  function secLabel(g, key) {
    const i18n = g.i18n[S.lang] || g.i18n.en || {};
    return (i18n.sections && i18n.sections[key]) || ((g.i18n.en || {}).sections || {})[key] || t(key) || key;
  }
  function vMore(view, { g, srcs, exps }) {
    let html = "";
    const keys = Object.keys((exps[0] && exps[0].game) || {});
    keys.forEach((k) => {
      const first = exps[0].game[k];
      html += `<section class="section card"><h2>${esc(secLabel(g, first.title))}</h2>${first.note ? `<p class="takeaway">${esc(secLabel(g, first.note))}</p>` : ""}
        <div class="grid ${srcs.length > 1 ? "cols-2" : ""}" style="margin-top:10px">${srcs.map((s, i) => `<div>${srcs.length > 1 ? `<h3>${esc(srcLabel(g, s, true))}</h3>` : ""}<div id="sec-${k}-${i}"></div></div>`).join("")}</div></section>`;
    });
    view.innerHTML = html || `<p class="empty">${esc(t("no_data"))}</p>`;
    keys.forEach((k) => srcs.forEach((s, i) => { const sec = exps[i].game && exps[i].game[k]; if (sec) drawShape(g, $(`#sec-${k}-${i}`), sec); }));
  }
  function drawShape(g, el, sec) {
    const facts = sec.facts ? `<div class="kv" style="margin-bottom:10px">${sec.facts.map((f) => `<div><b>${esc(fmtBy(f.format, f.value))}</b><span>${esc(secLabel(g, f.label))}</span></div>`).join("")}</div>` : "";
    el.innerHTML = facts + '<div class="plot"></div><div class="tbl"></div>';
    const plot = el.querySelector(".plot");
    const lab = (k) => secLabel(g, k);
    const cell = (c, v) => c.format === "category" ? L((g.manifest.score_categories || {})[v]) || v : c.format === "label" ? lab(v) : c.format === "text" ? v : fmtBy(c.format, v);
    if (sec.shape === "bars") {
      const MIN = 20;                                           // groups with fewer players are too noisy to plot
      const hidden = sec.rows.filter((r) => r[sec.bars] < MIN);
      sec = Object.assign({}, sec, { rows: sec.rows.filter((r) => r[sec.bars] >= MIN) });
      const xs = sec.rows.map((r) => fmtBy(sec.x_format, r[sec.x]));
      C.columns(plot, { x: xs, series: [{ name: lab(sec.line_label), values: sec.rows.map((r) => r[sec.line]),
        tips: sec.rows.map((r, i) => `<b>${esc(lab(sec.x_label))}: ${esc(xs[i])}</b><br>${esc(lab(sec.line_label))}: ${esc(fmtBy(sec.line_format, r[sec.line]))}<br>${esc(lab(sec.bar_label))}: ${int(r[sec.bars])}`) }],
        fmt: (v) => fmtBy(sec.line_format, v), baseline: sec.baseline, base_label: t("equal_share"), diverge: sec.baseline !== undefined, height: 220 });
      const small = el.querySelector(".tbl");
      small.innerHTML = `<p class="sub" style="margin-top:6px">${esc(lab(sec.bar_label))}: ${sec.rows.map((r, i) => `${esc(xs[i])}: ${int(r[sec.bars])}`).join(" · ")}${
        hidden.length ? ` · ${esc(t("hidden_small", { n: MIN }))}: ${hidden.map((r) => `${esc(fmtBy(sec.x_format, r[sec.x]))} (${int(r[sec.bars])})`).join(", ")}` : ""}</p>`;
    } else if (sec.shape === "grid") {
      C.grid(plot, { xEdges: sec.x_edges, yEdges: sec.y_edges, counts: sec.counts, xlabel: lab(sec.x_label), ylabel: lab(sec.y_label), unit: t("games") });
    } else if (sec.shape === "table") {
      if (sec.bars) {
        const cols = sec.columns;
        const xcol = cols.find((c) => c.key === sec.bars.x);
        C.columns(plot, { x: sec.rows.map((r) => cell(xcol, r[sec.bars.x])), series: sec.bars.series.map((sk) => ({ name: lab(sk), values: sec.rows.map((r) => r[sk]) })), fmt: (v) => num(v, 1), height: 220 });
      }
      const sortable = sec.rows.length > 12;
      el.querySelector(".tbl").innerHTML = `<div class="table-wrap" style="margin-top:10px;max-height:${sortable ? "420px" : "none"}"><table><thead><tr>${sec.columns.map((c) => `<th class="${["text", "category", "label"].includes(c.format) ? "" : "num"}">${esc(lab(c.label))}</th>`).join("")}</tr></thead>
        <tbody>${sec.rows.map((r) => `<tr>${sec.columns.map((c) => `<td class="${["text", "category", "label"].includes(c.format) ? "" : "num"}">${esc(cell(c, r[c.key]))}${c.format === "pp" && r[c.key + "_se"] ? ` <span class="muted">± ${esc(pp(2 * r[c.key + "_se"]).replace(/^[+−]/, ""))}</span>` : ""}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
  }

  // ------------------------------------------------------------------ comparison
  function vCompare(view, { g, r }) {
    const ps = Object.keys(g.compare || {}).filter((p) => !r.q.p || p === r.q.p);
    let html = `<h2>${esc(t("compare_h"))}</h2><p class="takeaway">${esc(t("compare_expl"))}</p>`;
    ps.forEach((p) => {
      const c = g.compare[p];
      const feat = g.manifest.featured[p];
      const newM = g.experiments[feat.main].seats[0], oldM = g.experiments[feat.compare].seats[0];
      html += `<section class="section card"><h2>${esc(t("n_players", { n: p }))}</h2>
        <p class="sub">${esc(modelLabel(g, newM))} ↔ ${esc(modelLabel(g, oldM))}</p>
        ${c.versus ? `<h3 style="margin-top:12px">${esc(t("versus_h"))}</h3><div class="kv" style="margin-top:6px">${c.versus.map((v) => `<div><b>${pct(v.win_rate, 1)}</b><span>${esc(agentName(g, v.agent))} · ${esc(t("mean_score"))} ${num(v.mean_score, 1)}</span></div>`).join("")}</div>` : ""}
        ${c.deals ? `<h3 style="margin-top:14px">${esc(t("deals_h"))}</h3><p class="sub">${esc(t("deals_expl", { n: int(c.deals.deals), new: num(c.deals.winner_new, 0), old: num(c.deals.winner_old, 0), share: pct(c.deals.new_higher, 0) }))}</p><div id="deals-${p}"></div><p class="sub" style="text-align:center">${esc(t("deals_axis"))}</p>` : ""}
        <h3 style="margin-top:14px">${esc(t("changes_h", { items: cap(term(g, "items")) }))}</h3><p class="sub">${esc(t("changes_expl"))}</p><div id="chg-${p}"></div>
        <h3 style="margin-top:14px">${esc(t("style_cmp_h"))}</h3><div class="table-wrap" style="margin-top:6px"><table><thead><tr><th></th><th class="num">${esc(t("ai_new"))}</th><th class="num">${esc(t("ai_original"))}</th></tr></thead><tbody>
        ${Object.keys(c.style.new).filter((k) => typeof c.style.new[k] === "number" && k !== "seats").map((k) => `<tr><td>${esc(styleLabel(g, k))}</td><td class="num">${esc(styleVal(k, c.style.new[k]))}</td><td class="num">${esc(styleVal(k, c.style.old[k]))}</td></tr>`).join("")}
        </tbody></table></div></section>`;
    });
    view.innerHTML = html;
    ps.forEach((p) => {
      const c = g.compare[p];
      if (c.deals) C.columns($("#deals-" + p), { x: c.deals.hist.map((h) => `${h.from}`), series: [{ name: t("deals"), values: c.deals.hist.map((h) => h.deals),
        tips: c.deals.hist.map((h) => `${esc(t("winner_diff", { a: h.from, b: h.to }))}<br><b>${int(h.deals)}</b> ${esc(t("deals"))}`) }], fmt: int, height: 200 });
      const clear = c.items.filter((x) => x.clear);
      const sel = clear.slice(0, 8).concat(clear.slice(-8).filter((x) => !clear.slice(0, 8).includes(x)));
      C.divergingBars($("#chg-" + p), sel.map((x) => ({ label: itemName(g, x.item), value: x.change, err: 2 * x.se,
        tip: `<b>${esc(itemName(g, x.item))}</b><br>${esc(t("ai_new"))}: ${pp(x.lift_new)}<br>${esc(t("ai_original"))}: ${pp(x.lift_old)}<br>${esc(t("change"))}: ${pp(x.change)} (± ${pp(2 * x.se).replace(/^[+−]/, "")})` })), { fmt: (v) => pp(v, 0) });
    });
  }
  function styleLabel(g, k) {
    if (k.startsWith("b_")) return L((g.manifest.score_categories || {})[k.slice(2)]) || k;
    if (k.startsWith("x_")) return L((g.manifest.seat_extras || {})[k.slice(2)]) || k;
    return t("st_" + k);
  }
  const styleVal = (k, v) => (["win_rate", "first_seat_win"].includes(k) || k.endsWith("_share") ? pct(v, 1) : num(v, 1));

  // ------------------------------------------------------------------ lab
  function vLab(view, { g }) {
    const models = Object.values(g.models);
    let html = `<h2>${esc(t("lab_h"))}</h2><p class="takeaway">${esc(t("lab_expl"))}</p>`;
    models.forEach((m, i) => {
      const st = m.strength || {};
      const status = st.finished ? `<span class="pill ok">${esc(t("model_finished"))}</span>` : st.legacy ? `<span class="pill warn">${esc(t("model_legacy"))}</span>` : `<span class="pill">${esc(t("model_unfinished"))}</span>`;
      html += `<section class="section card"><div class="spread"><h2>${esc(modelLabel(g, m.id))}</h2><div class="row">${status}<span class="pill">${esc(t("n_players", { n: m.players }))}</span><code>${esc(m.id)}</code></div></div>
        <div class="kv" style="margin-top:10px"><div><b>${m.steps ? fmtSteps(m.steps) : "–"}</b><span>${esc(t("t_training"))}</span></div>
          <div><b>${m.games ? int(m.games) : "–"}</b><span>${esc(t("training_games"))}</span></div><div><b>${m.hours ? num(m.hours, 1) + " h" : "–"}</b><span>${esc(t("hours"))}</span></div>
          <div><b>${m.size_mb ? num(m.size_mb, 1) + " MB" : "–"}</b><span>${esc(t("size"))}</span></div></div>
        <h3 style="margin-top:14px">${esc(t("strength_h"))}</h3><p class="sub">${esc(t("strength_expl"))}</p>
        <div class="table-wrap" style="margin-top:6px"><table><thead><tr><th>${esc(t("opponent"))}</th><th class="num">${esc(t("games"))}</th><th class="num">${esc(t("win_rate"))}</th><th class="num">${esc(t("margin"))}</th><th>${esc(t("required"))}</th></tr></thead><tbody>
        ${(st.games || []).map((x) => `<tr><td>${esc(x.label || x.opponent)}</td><td class="num">${int(x.games)}</td><td class="num">${pct(x.win, 1)}${x.win_se ? ` <span class="muted">± ${pct(2 * x.win_se, 1)}</span>` : ""}</td><td class="num">${x.margin !== undefined && x.margin !== null ? signed(x.margin, 1) : "–"}</td><td>${esc(!x.required ? "–" : x.required === "beats" ? t("req_beats") : t("req_atleast", { v: pct(parseFloat(x.required.slice(2)), 0) }))}${x.required ? ((x.required === "beats" ? x.win - 2 * (x.win_se || 0) > 0.5 : x.win >= parseFloat(x.required.slice(2))) ? " ✓" : " ✗") : ""}</td></tr>`).join("")}
        </tbody></table></div>${st.note ? `<p class="sub" style="margin-top:6px">${esc(st.note)}</p>` : ""}
        ${Object.keys(m.log_rows || {}).length ? `<h3 style="margin-top:14px">${esc(t("curve_h"))}</h3><p class="sub">${esc(t("curve_expl"))}</p><div id="curve-${i}"></div>` : ""}
        <details style="margin-top:12px"><summary>${esc(t("recipe_h"))}</summary><ol class="clean">${(m.recipe || []).map((x) => `<li><code>${esc(x)}</code></li>`).join("")}</ol>
          <p class="sub" style="margin-top:6px">sha256 <code>${esc((m.sha256 || "").slice(0, 16))}…</code> · ${esc(m.source || "")}</p></details></section>`;
    });
    html += `<section class="section"><h2>${esc(t("exp_h"))}</h2><p class="takeaway">${esc(t("exp_expl"))}</p><div class="grid cols-2" style="margin-top:10px">
      ${Object.values(g.experiments).map((x) => `<div class="card"><div class="spread"><h3><code>${esc(x.id)}</code></h3><span class="pill">${esc(t("kind_" + x.kind))}</span></div>
        <p class="sub" style="margin-top:6px">${esc(t("exp_line", { games: int(x.games), players: x.players, seed: x.seed }))}${x.made_by ? " · " + esc(x.made_by) : ""}</p>
        <p class="sub">${esc(t("seats"))}: ${x.seats.map((s) => esc(g.models[s] ? modelLabel(g, s) : t("agent_" + s))).join(" · ")}</p>
        <pre style="margin-top:8px">${esc(x.command)}</pre><pre style="margin-top:6px">python -m bgai.experiment --game ${esc(x.game)} --id ${esc(x.id)} --verify 20</pre></div>`).join("")}</div></section>
      <section class="section card"><h2>${esc(t("rights_h"))}</h2><pre style="margin-top:8px">${esc(g.rights || "")}</pre></section>`;
    view.innerHTML = html;
    models.forEach((m, i) => {
      const host = $("#curve-" + i);
      if (!host) return;
      let offset = 0;
      const series = { win_vs_ref: [], win_vs_greedy: [], win_vs_1m: [], win_vs_3m: [], win_vs_anchor: [] };
      Object.values(m.log_rows).forEach((rows) => {
        rows.forEach((row) => Object.keys(series).forEach((k) => { if (row[k] !== null && row[k] !== undefined) series[k].push({ x: row.steps / 1e6, y: row[k] }); }));
        void offset;
      });
      const shown = Object.entries(series).filter(([, pts]) => pts.length >= 2).map(([k, pts]) => ({ name: t("c_" + k), points: pts.map((q) => ({ ...q, tip: `<b>${esc(t("c_" + k))}</b><br>${num(q.x, 1)} ${esc(t("million"))} ${esc(t("steps"))}: ${pct(q.y, 1)}` })) }));
      C.lines(host, { series: shown, yfmt: (v) => pct(v, 0), xfmt: (v) => num(v, 0), xlabel: t("steps_m"), ymin: 0, ymax: 1, refs: [{ y: 1 / m.players, label: t("equal_share") }] });
    });
  }

  // ------------------------------------------------------------------ boot
  function setTheme(th) {
    if (th === "auto") document.documentElement.removeAttribute("data-theme"); else document.documentElement.setAttribute("data-theme", th);
    try { localStorage.setItem("theme", th); } catch (e) { /* storage blocked */ }
    const icon = { auto: "◐", light: "☀", dark: "☾" }[th];
    const b = $("#theme-btn");
    b.textContent = icon;
    b.title = t("theme_" + th);
    b.setAttribute("aria-label", t("theme_" + th));
  }
  async function setLang(lang) {
    S.lang = lang;
    try { localStorage.setItem("lang", lang); } catch (e) { /* storage blocked */ }
    document.documentElement.lang = lang;
    await loadLang(lang);
    $("#lang").innerHTML = ["en", "cs"].map((l) => `<button type="button" data-l="${l}" class="${l === lang ? "on" : ""}">${l.toUpperCase()}</button>`).join("");
    $("#lang").querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => { await setLang(b.dataset.l); render(); }));
  }
  async function boot() {
    let lang = "en", theme = "auto";
    try { lang = localStorage.getItem("lang") || ((navigator.language || "").startsWith("cs") ? "cs" : "en"); theme = localStorage.getItem("theme") || "auto"; } catch (e) { /* storage blocked */ }
    await setLang(lang);
    setTheme(theme);
    $("#theme-btn").addEventListener("click", () => {
      let cur = "auto";
      try { cur = localStorage.getItem("theme") || "auto"; } catch (e) { /* storage blocked */ }
      setTheme({ auto: "light", light: "dark", dark: "auto" }[cur]);
    });
    window.addEventListener("hashchange", () => { render(); window.scrollTo({ top: 0 }); });
    let rt = null, lastW = window.innerWidth;
    window.addEventListener("resize", () => {
      if (Math.abs(window.innerWidth - lastW) < 40) return;
      lastW = window.innerWidth;
      clearTimeout(rt);
      rt = setTimeout(() => { const y = window.scrollY; render().then(() => window.scrollTo({ top: y })); }, 250);
    });
    render();
  }
  boot();
})();
