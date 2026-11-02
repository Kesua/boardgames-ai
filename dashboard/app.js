/* boardgames.ai dashboard: a static single-page app over site/data (built by tools/build_site.py).
   Routes: #/                     home (all games)
           #/how[?t=<term>]       how to read the numbers (glossary)
           #/<game>[/<tab>[/<item>]][?p=2&v=old]   one game; tabs: discoveries strategy items boards style length
                                                    more compare lab                                        */
(function () {
  "use strict";
  const C = window.Charts;
  const S = { lang: "en", g: null, cache: {} };
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
  /* t(key, vars): {T:term} / {Tc:term} insert the current game's words (manifest "terms", e.g. forests / lesích),
     falling back to the generic term_<name> strings; then {var} placeholders are filled. */
  function t(key, vars) {
    if (key === "n_players" && vars && +vars.n >= 5 && has("n_players_many")) key = "n_players_many";   // Czech: 2–4 hráči, 5 hráčů
    let s = UI[key] ?? (/^Tc?:\w+$/.test(key) ? "{" + key + "}" : key);
    s = s.replace(/\{T(c?):(\w+)\}/g, (_, c, k) => (c ? cap(term(S.g, k)) : term(S.g, k)));
    // a value that ends with "." (e.g. "+8,5 p. b.") swallows the template's own full stop after it
    for (const k in vars || {}) s = s.split("{" + k + "}.").join(String(vars[k]).endsWith(".") ? vars[k] : vars[k] + ".").split("{" + k + "}").join(vars[k]);
    return s;
  }
  const has = (key) => UI[key] !== undefined;
  const cap = (s) => String(s).charAt(0).toUpperCase() + String(s).slice(1);
  const L = (obj) => (obj && typeof obj === "object" ? (obj[S.lang] ?? obj.en ?? "") : obj ?? "");
  function term(g, key) {
    // the game's own word in this language, else the generic word in this language, else the game's English word
    const tt = (g && g.manifest.terms) || {};
    const own = (tt[S.lang] || {})[key];
    if (own !== undefined) return own;
    if (has("term_" + key)) return UI["term_" + key];
    return (tt.en || {})[key] ?? key;
  }
  const gi18n = (g) => g.i18n[S.lang] || g.i18n.en || {};
  function itemName(g, key) {
    const fromI18n = (gi18n(g).items || {})[key];
    if (fromI18n && fromI18n.name) return fromI18n.name;
    const card = g.catalog.cards && g.catalog.cards[key];
    if (card) return card.label;
    return String(key).toLowerCase().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  function tagName(g, kind, value) {
    const m = ((gi18n(g).tags || {})[kind]) || {};
    if (m[value]) return m[value];
    if (kind === "archetype" || kind === "_arch") return archName(g, value);
    return has("v_" + value) ? t("v_" + value) : String(value).replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
  }
  function archName(g, value) {
    const a = gi18n(g).archetypes || {};
    if (a[value]) return a[value];
    if (has("v_" + value)) return t("v_" + value);
    return tagName(g, g.manifest.archetype ? g.manifest.archetype.tag : "", value);
  }
  function fmtDate(s) {
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}:\d{2}))?/.exec(s || "");
    if (!m) return s || "";
    const d = +m[3], mo = +m[2];
    const day = S.lang === "cs" ? `${d}. ${mo}. ${m[1]}` : `${d} ${t("month_" + mo)} ${m[1]}`;
    return m[4] ? `${day}, ${m[4]}` : day;
  }
  /* The game's name, in Czech etc. with its local title: "Wingspan (česky Na křídlech)" (manifest name_local). */
  const gameName = (m) => m.name + ((m.name_local || {})[S.lang] ? ` (${t("name_local", { name: m.name_local[S.lang] })})` : "");
  /* Every item exists once (one card per item): "copies" mean nothing, so per-copy wording and columns are dropped. */
  function unique(g) {
    if (g._unique === undefined) g._unique = Object.entries(g.catalog.items || {}).every(([k, it]) => (it.cards || [k]).length === 1
      && (((g.catalog.cards || {})[(it.cards || [k])[0]] || {}).count || 1) === 1);
    return g._unique;
  }
  const pointsLabel = (g) => t(unique(g) ? "points_per_unique" : "points_per");
  /* Food cost from a catalog "food" object {type: n} (+ wild, alternative): "1× fish + 1× seed" or "fish or seed". */
  function foodText(g, it) {
    const alt = it.alternative, parts = Object.entries(it.food).map(([k, n]) => (alt ? "" : n + "× ") + tagName(g, "food", k));
    if (it.wild) parts.push(it.wild + "× " + tagName(g, "food", "wild"));
    return parts.length ? parts.join(alt ? " " + t("or") + " " : " + ") : "0";
  }
  /* "?" next to a measure: opens its line on the How to read page. */
  const help = (k) => `<a class="qlink" href="#/how?t=${k}" title="${esc(t(k + "_d"))}" aria-label="${esc(t("what_is", { x: t(k) }))}">?</a>`;

  // ------------------------------------------------------------------ who played: trained model or baseline agent
  function modelRole(g, id) {
    for (const f of Object.values(g.manifest.featured || {})) {
      if (!f.compare) continue;
      if ((g.experiments[f.compare] || {}).seats && g.experiments[f.compare].seats[0] === id) return "original";
      if ((g.experiments[f.main] || {}).seats && g.experiments[f.main].seats[0] === id) return "new";
    }
    const st = (g.models[id] || {}).strength || {};
    return st.finished ? "finished" : "early";
  }
  /* seat id -> {model, finished, role, label} */
  function seatInfo(g, id) {
    const m = g.models[id];
    if (!m) return { model: false, finished: false, role: "baseline", id, label: has("agent_" + id) ? t("agent_" + id) : id };
    const st = m.strength || {};
    return { model: true, finished: !!st.finished, legacy: !!(st.legacy || m.legacy), role: modelRole(g, id), id, steps: m.steps, players: m.players,
             label: t("ai_" + modelRole(g, id)) };
  }
  const expSeat = (g, expId) => seatInfo(g, ((g.experiments[expId] || {}).seats || [])[0]);
  function modelLabel(g, id) {
    const m = g.models[id];
    if (!m) return has("agent_" + id) ? t("agent_" + id) : id;
    return `${t("ai_" + modelRole(g, id))} · ${t("n_players", { n: m.players })}`;
  }
  function agentName(g, raw) {
    if (!raw) return "";
    if (raw.startsWith("model:")) return modelLabel(g, raw.slice(6));
    return has("agent_" + raw) ? t("agent_" + raw) : raw;
  }

  // ------------------------------------------------------------------ numbers
  const nf = (d) => new Intl.NumberFormat(S.lang === "cs" ? "cs-CZ" : "en-GB", { minimumFractionDigits: d, maximumFractionDigits: d });
  const num = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? "–" : nf(d).format(v));
  const int = (v) => num(v, 0);
  // a share above 0 that would round to 0 shows as "<1 %" (or "<0.1 %"), so a card that appears never reads as absent
  const pct = (v, d = 0) => (v === null || v === undefined ? "–" : v > 0 && v * 100 < 0.5 * Math.pow(10, -d) ? "<" + num(Math.pow(10, -d), d) + " %" : num(v * 100, d) + " %");
  const pp = (v, d = 1) => (v === null || v === undefined ? "–" : (Math.abs(v * 100) < 0.5 * Math.pow(10, -d) ? "" : v > 0 ? "+" : "−") + num(Math.abs(v * 100), d) + " " + t("pp"));
  const signed = (v, d = 2) => (v === null || v === undefined ? "–" : (Math.abs(v) < 0.5 * Math.pow(10, -d) ? "" : v > 0 ? "+" : "−") + num(Math.abs(v), d));
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
    const params = new URLSearchParams(Object.assign({}, game === r.game ? r.q : {}, { s: "" }, q || {}));
    for (const [k, v] of [...params]) if (v === "" || v === undefined || v === null) params.delete(k);
    const s = params.toString();
    return "#/" + [game, tab, item].filter(Boolean).map(encodeURIComponent).join("/") + (s ? "?" + s : "");
  }

  async function render() {
    const r = parseHash();
    const main = $("#main");
    try {
      const index = await loadIndex();
      S.g = null;
      renderHeader(index, r);
      if (r.game === "how") { await renderHow(main, index, r); return; }
      if (!r.game) { renderHome(main, index); return; }
      const meta = index.games.find((x) => x.slug === r.game);
      if (!meta) { main.innerHTML = `<p class="empty">${esc(t("not_found"))}</p>`; return; }
      const g = await loadGame(r.game);
      S.g = g;
      document.documentElement.style.setProperty("--accent", (g.manifest.theme || {}).accent || "#2c6e8f");
      await renderGame(main, g, r);
    } catch (e) {
      console.error(e);
      main.innerHTML = `<div class="card"><h2>${esc(t("error"))}</h2><p class="sub">${esc(e.message)}</p></div>`;
    } finally {
      C.hideTip();
      markScroll(main);
    }
  }
  /* Tables and the tab bar that are wider than the screen fade out at the right edge until scrolled to the end;
     a wide table also gets a line saying it scrolls. The active tab is scrolled into view. */
  function markScroll(root) {
    root.querySelectorAll(".table-wrap, .tabs").forEach((w) => {
      if (w.scrollWidth <= w.clientWidth + 2) return;
      const upd = () => w.classList.toggle("end", w.scrollLeft + w.clientWidth >= w.scrollWidth - 4);
      w.classList.add("more");
      if (w.classList.contains("tabs")) {
        const on = w.querySelector(".on"), x = on ? on.getBoundingClientRect().left - w.getBoundingClientRect().left : 0;
        if (on && x + on.offsetWidth > w.clientWidth) w.scrollLeft = x - 24;
      }
      else if (!(w.previousElementSibling && w.previousElementSibling.classList.contains("scroll-hint"))) w.insertAdjacentHTML("beforebegin", `<p class="sub scroll-hint">${esc(t("scroll_hint"))}</p>`);
      w.addEventListener("scroll", upd, { passive: true });
      upd();
    });
  }

  function renderHeader(index, r) {
    const sw = $("#game-switch");
    const hl = $("#howto-link");
    hl.textContent = t("how_read");
    hl.classList.toggle("on", r.game === "how");
    sw.innerHTML = `<a href="#/" class="${r.game ? "" : "on"}">${esc(t("all_games"))}</a>` + index.games.map((g) =>
      `<a href="#/${g.slug}" class="${r.game === g.slug ? "on" : ""}">${esc(g.name)}</a>`).join("");
    if (!r.game || r.game === "how") document.documentElement.style.removeProperty("--accent");
    const gm = index.games.find((x) => x.slug === r.game);
    document.title = (r.game === "how" ? t("how_title") + " — " : gm ? gm.name + " — " : "") + "boardgames.ai";
    $("#foot").innerHTML = `${esc(t("footer", { date: fmtDate(index.generated) }))} <a href="https://github.com/boardgames-ai/boardgames-ai">GitHub</a>`;
  }

  // ------------------------------------------------------------------ how to read the numbers
  const GLOSSARY = ["g_lift", "g_pp", "g_err", "g_unclear", "g_edge", "g_presence", "g_points", "g_points_board", "g_type", "g_turns",
                    "g_mirror", "g_strength", "g_early", "g_greedy", "g_paired", "g_steps", "g_million", "g_ref", "g_margin", "g_rank", "g_grey",
                    "g_corr", "g_explains", "g_seed"];
  /* The worked example uses real numbers from the first game that has data, so it always matches the card pages. */
  async function howExample(index) {
    const gm = index.games.find((x) => x.slug === "forest_shuffle" && Object.keys(x.headline || {}).length) || index.games.find((x) => Object.keys(x.headline || {}).length);
    if (!gm) return null;
    const g = await loadGame(gm.slug);
    const p = Object.keys(gm.headline).sort((a, b) => a - b)[0];
    const e = await loadExp(gm.slug, gm.headline[p].experiment);
    const min = minBoards(e);
    const it = e.items.find((x) => x.item === "GENTIAN" && x.boards_with >= min) || e.items.filter((x) => x.boards_with >= min).sort((a, b) => b.win_lift - a.win_lift)[0];
    if (!it) return null;
    return { g, p, e, it };
  }
  async function renderHow(main, index, r) {
    const ex = await howExample(index).catch(() => null);
    let example = "";
    if (ex) {
      S.g = ex.g;
      example = `<div class="card"><h2>${esc(t("how_example_h"))}</h2><p class="takeaway">${esc(t("how_example", {
        item: itemName(ex.g, ex.it.item), lift: pp(ex.it.win_lift), lift2: pp(ex.it.win_lift, 2), win: pct(ex.it.win_rate, 2), base: pct(ex.e.meta.baseline_win_rate, 2),
        even: pct(1 / ex.e.meta.players, 0), players: t("n_players", { n: ex.p }), game: ex.g.manifest.name }))}</p>
        <p style="margin-top:8px"><a href="${link(ex.g.manifest.slug, "items", ex.it.item, { p: ex.p })}">${esc(t("how_example_link", { item: itemName(ex.g, ex.it.item) }))} →</a></p></div>`;
    }
    const gameGloss = [];
    for (const gm of index.games) {
      const g = await loadGame(gm.slug).catch(() => null);
      const gl = g && g.manifest.glossary;
      if (gl && gl.length) gameGloss.push(`<div class="card section"><h2>${esc(t("game_words", { game: g.manifest.name }))}</h2><dl class="gloss">${gl.map((x) =>
        `<dt>${esc(L(x.term))}</dt><dd>${esc(L(x.text))}</dd>`).join("")}</dl></div>`);
    }
    S.g = null;
    main.innerHTML = `<section class="hero"><div class="eyebrow">${esc(t("how_read"))}</div><h1>${esc(t("how_title"))}</h1>
      <p class="lede">${esc(t("how_lede"))}</p></section>
      ${example}
      <div class="card section"><h2>${esc(t("glossary_h"))}</h2><dl class="gloss">${GLOSSARY.map((k) => `<dt id="${k}">${esc(t(k))}</dt><dd>${esc(t(k + "_d"))}</dd>`).join("")}</dl></div>
      ${gameGloss.join("")}
      <p class="caveat">${esc(t("caveat"))}</p>`;
    if (r.q.t && document.getElementById(r.q.t)) {
      const dt = document.getElementById(r.q.t);
      dt.classList.add("hl");
      if (dt.nextElementSibling) dt.nextElementSibling.classList.add("hl");
      setTimeout(() => dt.scrollIntoView({ block: "center" }), 30);
    }
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
        <div class="card"><h2>${esc(t("trust_h"))}</h2><ul class="clean">${["trust_1", "trust_2", "trust_3", "trust_4"].map((k) => `<li>${esc(t(k))}</li>`).join("")}</ul>
          <p style="margin-top:10px"><a href="#/how">${esc(t("how_title"))} →</a></p></div>
        <div class="card"><h2>${esc(t("add_h"))}</h2><p class="takeaway">${esc(t("add_text"))}</p>
          <ol class="clean" style="margin-top:10px">${["add_1", "add_2", "add_3", "add_4"].map((k) => `<li>${esc(t(k))}</li>`).join("")}</ol>
          <p style="margin-top:10px"><a href="https://github.com/boardgames-ai/boardgames-ai/blob/main/CONTRIBUTING.md">${esc(t("add_link"))}</a></p></div>
      </section>
      <p class="caveat">${esc(t("caveat"))}</p>`;
  }
  function gameCard(g) {
    const hl = Object.entries(g.headline || {}).sort((a, b) => a[0] - b[0]);
    const games = hl.reduce((a, [, h]) => a + h.games, 0);
    const counts = hl.map(([p]) => p).join(" · ");
    // one status per player count: who played those games (finished AI, early AI, or a simple baseline player)
    const status = hl.length ? hl.map(([p, h]) => {
      const pl = t("n_players", { n: p });
      if (h.kind === "baseline") return `<span class="pill">${esc(t("status_baseline", { players: pl }))}</span>`;
      return h.finished ? `<span class="pill ok">${esc(t("status_finished", { players: pl }))}</span>`
        : `<span class="pill warn">${esc(t("status_early", { players: pl }))}</span>`;
    }).join("") : `<span class="pill">${esc(t(g.ai_status === "training" ? "model_training" : "model_none"))}</span>`;
    // count the current AI of each player count; older AIs kept for comparison are named apart
    const cur = hl.filter(([, h]) => h.kind === "model"), done = cur.filter(([, h]) => h.finished).length, older = (g.models || 0) - cur.length;
    return `<a class="card gcard" href="#/${g.slug}" style="--gaccent:${esc((g.theme || {}).accent || "")}">
      <div class="gtitle"><span class="emoji" aria-hidden="true">${esc((g.theme || {}).emoji || "🎲")}</span>
        <div><h2>${esc(g.name)}</h2><div class="sub">${esc([g.publisher, g.year].filter(Boolean).join(", "))}</div></div></div>
      <p>${esc(L(g.intro))}</p>
      <div class="kv"><div><b>${games ? int(games) : "–"}</b><span>${esc(t("games_analysed"))}</span></div>
        <div><b>${esc(counts || "–")}</b><span>${esc(t("player_counts"))}</span></div>
        <div><b>${cur.length ? esc(t("x_of_y", { x: int(done), y: int(cur.length) })) : "–"}</b><span>${esc(t("models_finished"))}${older > 0 ? `<br>${esc(t("models_extra", { n: int(older) }))}` : ""}</span></div></div>
      <div class="row">${status}<span class="sub">${esc(t("open_game"))} →</span></div></a>`;
  }

  // ------------------------------------------------------------------ game shell
  const SINGLE = ["items", "boards"];          // tabs that show one player count at a time
  function sources(g, r) {
    const feat = g.manifest.featured || {};
    const pc = Object.keys(feat).sort((a, b) => a - b);
    const single = SINGLE.includes(r.tab) && !r.item;
    const pFilter = r.q.p && feat[r.q.p] ? [r.q.p] : single ? pc.slice(0, 1) : pc;
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
  function srcInfo(g, s) { return expSeat(g, s.exp); }
  function srcLabel(g, s) {
    const pl = t("n_players", { n: s.players });
    const who = srcInfo(g, s);
    if (who.role === "finished") return pl;
    return `${pl} · ${who.label}`;
  }
  /* A source is tentative when its games were not played by a finished AI. */
  const tentative = (g, s) => !srcInfo(g, s).finished;
  const srcHead = (g, s) => (tentative(g, s) ? esc(t("n_players", { n: s.players })) + tentPill(g, s) : esc(srcLabel(g, s)));
  function tentPill(g, s) { return tentative(g, s) ? ` <span class="pill warn">${esc(t(srcInfo(g, s).role === "original" ? "pill_original" : srcInfo(g, s).role === "baseline" ? "pill_baseline" : "pill_tentative"))}</span>` : ""; }
  /* Why a model is not finished, from its strength card: the first required test it failed. */
  function whyEarly(g, id) {
    const m = g.models[id] || {}, st = m.strength || {};
    if (st.legacy || m.legacy) return t("why_legacy");
    const r = (st.games || []).find((x) => x.required && !(x.required === "beats" ? x.win - 2 * (x.win_se || 0) > 0.5
      : x.win >= parseFloat(x.required.slice(2))));
    if (!r) return t("why_untested");
    if (r.required !== "beats") return t("why_min", { who: t(has("agent_" + r.opponent) ? "agent_" + r.opponent : "why_older").toLowerCase(),
      win: pct(r.win, 1), need: pct(parseFloat(r.required.slice(2))) });
    return t("why_beats", { win: pct(r.win, 1) });
  }
  function tentNote(g, srcs) {
    const seen = new Set();
    const notes = srcs.filter((s) => tentative(g, s)).map((s) => {
      const who = srcInfo(g, s);
      const key = who.role === "original" ? "tent_original" : who.role === "baseline" ? "tent_baseline" : "tent_early";
      if (seen.has(key + s.players)) return "";
      seen.add(key + s.players);
      return `<div class="notice"><b>${esc(t(key + "_h", { players: t("n_players", { n: s.players }) }))}</b> ${esc(t(key, { players: t("n_players", { n: s.players }), agent: who.label.toLowerCase(), why: key === "tent_early" ? whyEarly(g, who.id) : "" }))}
        <a href="${link(g.slug, who.role === "original" ? "compare" : "lab")}">${esc(t(who.role === "original" ? "tab_compare" : "tab_lab"))} →</a></div>`;
    }).join("");
    return notes;
  }

  async function renderGame(main, g, r) {
    const m = g.manifest;
    const feat = m.featured || {};
    const hasCompare = Object.values(feat).some((f) => f.compare);
    const tabs = [["discoveries", t("tab_discoveries")], ["strategy", t("tab_strategy")], ["items", t("Tc:items")],
      ["boards", t("Tc:boards")], ["style", t("tab_style")]];
    const srcs = sources(g, r);
    const exps = await Promise.all(srcs.map((s) => loadExp(g.slug, s.exp)));
    if (!srcs.length) { renderNoData(main, g, r); return; }
    const anyLength = exps.some((e) => e.length);
    if (anyLength) tabs.push(["length", t("tab_length")]);
    if (exps.some((e) => e.game && Object.keys(e.game).length)) tabs.push(["more", t("tab_more", { game: m.name })]);
    if (hasCompare) tabs.push(["compare", t("tab_compare")]);
    tabs.push(["lab", t("tab_lab")]);
    const pcs = Object.keys(feat).sort((a, b) => a - b);
    const single = SINGLE.includes(r.tab) && !r.item;
    const pSel = r.q.p && feat[r.q.p] ? r.q.p : single ? pcs[0] : "";
    // the AI switch only matters for player counts that have two AIs to compare
    const cmpPcs = (pSel ? [pSel] : pcs).filter((p) => feat[p].compare);
    const showAi = cmpPcs.length && !["compare", "lab"].includes(r.tab);
    const showP = pcs.length > 1 && r.tab !== "lab";
    const pOpts = (single ? [] : [["", t("all")]]).concat(pcs.map((p) => [p, p]));
    const filters = showP || showAi ? `<div class="filters">
      ${showP ? `<span class="lbl">${esc(t("players"))}</span><div class="seg">${pOpts.map(([v, lab]) =>
        `<button type="button" data-q="p" data-v="${v}" class="${pSel === v ? "on" : ""}">${esc(lab)}</button>`).join("")}</div>` : ""}
      ${showAi ? `<span class="lbl">${esc(cmpPcs.length < (pSel ? 1 : pcs.length) ? t("ai_for", { players: cmpPcs.map((p) => t("n_players", { n: p })).join(", ") }) : t("ai"))}</span><div class="seg">${[["", t("ai_new")], ["old", t("ai_original")], ["both", t("side_by_side")]].map(([v, lab]) =>
        `<button type="button" data-q="v" data-v="${v}" class="${(r.q.v || "") === v ? "on" : ""}">${esc(lab)}</button>`).join("")}</div>` : ""}
    </div>` : "";
    main.innerHTML = `<section class="ghead"><div class="title"><span class="emoji" style="font-size:30px" aria-hidden="true">${esc((m.theme || {}).emoji || "")}</span>
        <div><div class="eyebrow">${esc([m.publisher, m.year, m.designer].filter(Boolean).join(" · "))}</div><h1 style="font-size:clamp(26px,3.6vw,36px)">${esc(gameName(m))}</h1></div></div></section>
      <nav class="tabs" aria-label="${esc(t("sections"))}">${tabs.map(([k, lab]) => `<a href="${link(g.slug, k)}" class="${r.tab === k ? "on" : ""}">${esc(lab)}</a>`).join("")}</nav>
      ${filters}${["lab", "compare"].includes(r.tab) ? "" : tentNote(g, srcs)}<div id="view"></div>`;
    main.querySelectorAll(".filters button").forEach((b) => b.addEventListener("click", () => {
      location.hash = link(g.slug, r.tab, r.item, { [b.dataset.q]: b.dataset.v });
    }));
    const view = $("#view");
    const ctx = { g, r, srcs, exps, many: srcs.length > 1 };
    const fn = { discoveries: vDiscoveries, strategy: vStrategy, items: r.item ? vProfile : vItems, boards: vBoards, style: vStyle,
                 length: vLength, more: vMore, compare: vCompare, lab: vLab }[r.tab] || vDiscoveries;
    await fn(view, ctx);
  }

  /* A game whose AI is still training: say so, show what is already there (rules, cards, training progress). */
  function renderNoData(main, g, r) {
    const m = g.manifest;
    const tab = r.tab === "lab" ? "lab" : "discoveries";
    main.innerHTML = `<section class="ghead"><div class="title"><span class="emoji" style="font-size:30px" aria-hidden="true">${esc((m.theme || {}).emoji || "")}</span>
        <div><div class="eyebrow">${esc([m.publisher, m.year, m.designer].filter(Boolean).join(" · "))}</div><h1 style="font-size:clamp(26px,3.6vw,36px)">${esc(gameName(m))}</h1></div></div></section>
      <nav class="tabs"><a href="${link(g.slug, "discoveries")}" class="${tab === "discoveries" ? "on" : ""}">${esc(t("tab_discoveries"))}</a>
        <a href="${link(g.slug, "lab")}" class="${tab === "lab" ? "on" : ""}">${esc(t("tab_lab"))}</a></nav><div id="view"></div>`;
    const view = $("#view");
    if (tab === "lab") { vLab(view, { g, r }); return; }
    view.innerHTML = `<section class="hero" style="padding-top:0"><h1>${esc(t("game_q", { game: m.name }))}</h1><p class="lede">${esc(L(m.intro))}</p></section>
      <div class="card"><h2>${esc(t(m.ai_status === "training" ? "training_now_h" : "engine_ready_h"))}</h2><p class="takeaway">${esc(t(m.ai_status === "training" ? "training_now" : "engine_ready", { n: Object.keys(g.catalog.items || {}).length }))}</p>
      <p style="margin-top:10px"><a href="${link(g.slug, "lab")}">${esc(t("tab_lab"))} →</a></p></div>`;
  }

  // ------------------------------------------------------------------ discoveries
  function vDiscoveries(view, { g, srcs, exps }) {
    const m = g.manifest;
    // games the AI played against itself while learning (from the model card of the AI in the first seat)
    const learnGames = srcs.map((src) => ((g.models[((g.experiments[src.exp] || {}).seats || [])[0]] || {}).games));
    const tiles = [
      ...(learnGames.every((v) => v) ? [[t("t_learn_games"), learnGames, int]] : []),
      [t("t_games"), exps.map((e) => e.meta.games), int],
      [t("t_boards"), exps.map((e) => e.meta.boards), int],
      [t("t_winner"), exps.map((e) => e.meta.winner_score), (v) => num(v, 0)]];
    const notes = g.notes || {};
    const variant = (srcs[0] || {}).variant === "old" ? "compare" : "main";
    const findings = (notes.findings || []).filter((f) => f.variant === variant || (!f.variant && variant === "main"));
    view.innerHTML = `
      <section class="hero" style="padding-top:0">
        <h1>${esc(t("game_q", { game: m.name }))}</h1>
        <p class="lede">${esc(L(m.intro))} ${esc(t("game_lede_tail"))}</p>
        ${m.edition_note ? `<p class="sub">${esc(L(m.edition_note))}</p>` : ""}</section>
      ${oneLine(g, srcs)}
      <section class="section"><h2>${esc(t("findings_h"))}</h2>
        ${findings.length ? `<div class="grid cols-3" style="margin-top:12px">${findings.map((f) => finding(g, f, srcs)).join("")}</div>`
          : `<p class="sub" style="margin-top:6px">${esc(t("findings_none"))}</p>`}
        ${autoFindings(g, srcs, exps)}
        <p class="caveat">${esc(gameCaveat(g, srcs))}${limits(g).length ? ` <a href="${link(g.slug, "lab", null, { s: "limits" })}">${esc(t("limits_link"))} →</a>` : ""}</p></section>
      <section class="section"><h2>${esc(t("how_h"))}</h2>
        <div class="steps">
          <div class="step"><h3>${esc(t("step1_t"))}</h3><p>${esc(howLearn(g, srcs))}</p></div>
          <div class="step"><h3>${esc(t("step2_t"))}</h3><p>${esc(howPlay(g, srcs, exps))}</p></div>
          <div class="step"><h3>${esc(t("step3_t"))}</h3><p>${esc(t("how_count"))}</p></div></div>
        <div class="tiles" style="margin-top:12px">${tiles.map(([lab, vals, f]) => `<div class="tile"><div class="lab">${esc(lab)}</div><div class="vals">${vals.map((v, i) =>
          `<div class="v"><b>${esc(f(v))}</b><span>${esc(srcLabel(g, srcs[i]))}</span></div>`).join("")}</div></div>`).join("")}</div></section>`;
  }
  /* The caveat under the findings: honest about AIs that have not passed their strength test. */
  function gameCaveat(g, srcs) {
    const notes = g.notes || {};
    if (srcs.length && srcs.every((s) => tentative(g, s))) return t("caveat_early");
    const early = [...new Set(srcs.filter((s) => tentative(g, s)).map((s) => t("n_players", { n: s.players })
      + (srcInfo(g, s).role === "original" ? ` (${srcInfo(g, s).label.toLowerCase()})` : "")))];
    const base = notes.written ? t("findings_caveat", { date: fmtDate(notes.written) }) : t("caveat_game");
    return early.length ? base + " " + t("caveat_some_early", { players: early.join(", ") }) : base;
  }
  /* Known limits written in notes.json ("limits": {en: [...], cs: [...]}), shown in the Lab and linked from Discoveries. */
  const limits = (g) => { const x = L((g.notes || {}).limits); return Array.isArray(x) ? x : []; };
  function oneLine(g, srcs) {
    const notes = (g.notes && g.notes.experiments) || {};
    const parts = srcs.map((s) => { const n = notes[s.exp]; const x = n ? n[S.lang] || n.en : null; return x && x.summary ? [s, x] : null; }).filter(Boolean);
    if (!parts.length) return "";
    return `<div class="grid ${parts.length > 1 ? "cols-2" : ""}" style="margin-bottom:14px">${parts.map(([s, x]) => `<div class="card oneline${tentative(g, s) ? " tent" : ""}">
      <div class="who">${esc(t("plan_one_line"))} · ${srcHead(g, s)}</div><p>${esc(x.summary)}</p>
      ${checklist(x, tentative(g, s))}
      <a href="${link(g.slug, "strategy", null, { p: String(s.players) })}">${esc(t("read_strategy"))} →</a></div>`).join("")}</div>`;
  }
  function checklist(x, tent) {
    if (!x.do && !x.dont) return "";
    return `<p class="sub" style="margin-top:8px">${esc(t(tent ? "check_expl_early" : "check_expl"))}</p><div class="check">${x.do ? `<div><h3>${esc(t("do_h"))}</h3><ul class="clean do">${x.do.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>` : ""}
      ${x.dont ? `<div><h3>${esc(t("dont_h"))}</h3><ul class="clean dont">${x.dont.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>` : ""}</div>`;
  }
  function howLearn(g, srcs) {
    const seen = new Set();
    const parts = srcs.map((s) => srcInfo(g, s)).filter((w) => !seen.has(w.id) && seen.add(w.id));
    const models = parts.filter((w) => w.model);
    const base = parts.filter((w) => !w.model);
    const out = [];
    if (models.length) out.push(t("how_learn", { list: models.map((w) => t((g.models[w.id] || {}).games ? "how_learn_games" : "how_learn_one", { steps: w.steps ? fmtSteps(w.steps) : "?", games: int((g.models[w.id] || {}).games), players: t("n_players", { n: w.players }), who: w.label })).join("; ") }));
    if (base.length) out.push(t("how_learn_base", { who: base.map((w) => w.label.toLowerCase()).join(", ") }));
    return out.join(" ");
  }
  function howPlay(g, srcs, exps) {
    return srcs.map((s, i) => {
      const rec = g.experiments[s.exp] || {};
      const seats = rec.seats || [];
      const who = srcInfo(g, s);
      const vars = { games: int(exps[i].meta.games), players: t("n_players", { n: s.players }), who: who.label };
      if (seats.length && seats.some((x) => x !== seats[0])) return t("how_play_versus", Object.assign(vars, { list: [...new Set(seats)].map((x) => seatInfo(g, x).label).join(" + ") }));
      if (!who.model) return t("how_play_base", vars);
      return t(who.finished ? "how_play" : "how_play_early", vars);
    }).join(" ");
  }
  function notesLink(g, f) {
    // notes links are "tab" or "tab/ITEM" (old "#tab&x=y" forms are cut to the tab)
    const raw = String(f.link || "").replace(/^#\/?/, "").split(/[&?]/)[0];
    const [tab, item] = raw.split("/");
    return link(g.slug, tab, item || null);
  }
  function finding(g, f, srcs) {
    const x = f[S.lang] || f.en;
    const seenP = new Set();   // one number per player count (side by side shows the same count twice)
    const nums = srcs.filter((s) => !seenP.has(s.players) && seenP.add(s.players)).map((s) => [s, x["n" + s.players]]).filter(([, v]) => v && v !== "–");
    return `<article class="card finding"><h3>${esc(x.title)}</h3>
      ${nums.length ? `<div class="nums">${nums.map(([s, v]) => `<div><b>${esc(v)}${String(v).includes(t("pp")) ? " " + help("g_pp") : ""}</b><span>${esc(t("n_players", { n: s.players }))}${tentative(g, s) ? ` · <em class="warn-ink">${esc(t(srcInfo(g, s).role === "original" ? "pill_original" : srcInfo(g, s).role === "baseline" ? "pill_baseline" : "pill_tentative"))}</em>` : ""}</span></div>`).join("")}</div>` : ""}
      <p class="sub">${esc(x.label || "")}</p><p>${esc(x.text)}</p>${x.before ? `<p class="before">${esc(x.before)}</p>` : ""}
      ${f.link ? `<a href="${notesLink(g, f)}">${esc(t("show_chart"))} →</a>` : ""}</article>`;
  }
  /* Data-driven takeaways shown under the written findings: always current, even before notes are written. */
  function autoFindings(g, srcs, exps) {
    const cards = [];
    exps.forEach((e, i) => {
      if (!e.items) return;
      const min = minBoards(e);
      const ok = e.items.filter((r) => r.boards_with >= min);
      const best = ok.slice().sort((a, b) => b.win_lift - a.win_lift)[0];
      const worst = ok.slice().sort((a, b) => a.win_lift - b.win_lift)[0];
      const first = e.seat_order && e.seat_order[0];
      const s = srcs[i];
      const tent = tentative(g, s) ? t(srcInfo(g, s).role === "original" ? "pill_original" : srcInfo(g, s).role === "baseline" ? "pill_baseline" : "pill_tentative") : "";
      const lab = tent ? t("n_players", { n: s.players }) : srcLabel(g, s);   // the warning pill names the AI
      const q = { p: String(s.players), v: s.variant === "old" ? "old" : "" };
      if (best) cards.push([t("auto_best"), itemName(g, best.item), t("auto_lift", { lift: pp(best.win_lift), share: pct(best.presence_rate, 0) }), lab, link(g.slug, "items", best.item, q), tent]);
      if (worst) cards.push([t("auto_worst"), itemName(g, worst.item), t("auto_lift", { lift: pp(worst.win_lift), share: pct(worst.presence_rate, 0) }), lab, link(g.slug, "items", worst.item, q), tent]);
      // within chance: the first seat's difference from the average player is inside 2 standard errors (n = seats)
      const chance = first && Math.abs(first.win_rate - e.meta.baseline_win_rate) <= 2 * Math.sqrt(first.win_rate * (1 - first.win_rate) / first.seats);
      if (first) cards.push([t("auto_first"), pct(first.win_rate, 1), t("auto_first_sub", { base: pct(e.meta.baseline_win_rate, 1) }) + (chance ? "; " + t("auto_first_chance") : ""), lab, link(g.slug, "strategy", null, q), tent]);
    });
    if (!cards.length) return "";
    return `<h3 style="margin-top:22px">${esc(t("auto_h"))}</h3><p class="sub">${esc(t("auto_sub", { n: "" }))}</p>
      <div class="grid cols-4" style="margin-top:10px">${cards.map(([h, v, sub, lab, href, tent]) => `<a class="card autocard${tent ? " tent" : ""}" href="${href}">
      <div class="eyebrow">${esc(h)}</div><div class="big">${esc(v)}</div>
      <div class="sub">${esc(sub)}</div><div class="sub">${esc(lab)}${tent ? ` · <span class="warn-ink">${esc(tent)}</span>` : ""}</div></a>`).join("")}</div>`;
  }

  // ------------------------------------------------------------------ strategy
  function liftRows(g, e, list) {
    return list.map((r) => ({ label: `${itemName(g, r.item)} · ${pct(r.presence_rate, 0)}`, value: r.win_lift, err: 2 * (r.win_lift_se || 0),
      tip: `<b>${esc(itemName(g, r.item))}</b><br>${esc(t("win_lift"))}: ${pp(r.win_lift)} (± ${pp(2 * (r.win_lift_se || 0)).replace(/^[+−]/, "")})<br>${esc(t("tip_win", { win: pct(r.win_rate, 1), base: pct(e.meta.baseline_win_rate, 1) }))}<br>${esc(t("presence"))}: ${pct(r.presence_rate, 0)} ${esc(t("of_boards"))}<br>${esc(pointsLabel(g))}: ${ppcText(e, r)}${noPoints(e, r) ? ` (${esc(t("points_none"))})` : ""}${!unique(g) && r.winner_edge !== null && r.winner_edge !== undefined ? `<br>${esc(t("winner_edge"))}: ${signed(r.winner_edge)}` : ""}` }));
  }
  function vStrategy(view, { g, srcs, exps }) {
    const notes = (g.notes && g.notes.experiments) || {};
    let html = "";
    srcs.forEach((s, i) => {
      const n = notes[s.exp];
      const x = n ? n[S.lang] || n.en : null;
      const e = exps[i];
      html += `<section class="section card${tentative(g, s) ? " tent" : ""}"><div class="spread"><h2>${srcHead(g, s)}</h2>
        <span class="sub">${esc(t("based_on", { games: int(e.meta.games) }))}</span></div>
        ${x ? `<p class="lede" style="margin-top:8px">${esc(x.summary)}</p>${checklist(x, tentative(g, s))}
        <h3 style="margin-top:16px">${esc(t("numbers_behind"))}</h3>
        <div class="grid cols-2" style="margin-top:4px"><div class="notes-block"><h3>${esc(t("works"))}</h3><ul class="clean">${(x.works || []).map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>
        <div class="notes-block"><h3>${esc(t(tentative(g, s) ? "avoid_plain" : "avoid"))}</h3><ul class="clean">${(x.avoid || []).map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div></div>
        ${x.order ? `<h3 style="margin-top:12px">${esc(t("order"))}</h3><p class="takeaway">${esc(x.order)}</p>` : ""}
        ${x.length ? `<h3 style="margin-top:12px">${esc(t("length"))}</h3><ul class="clean">${(Array.isArray(x.length) ? x.length : [x.length]).map((w) => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}`
        : `<p class="sub" style="margin-top:6px">${esc(t("notes_none"))}</p>`}
        <h3 style="margin-top:20px">${esc(t("help_hurt_h"))} ${help("g_lift")}</h3>
        <p class="sub">${esc(t("lift_expl"))} ${help("g_err")} ${esc(t("min_boards", { n: int(minBoards(e)) }))}</p>
        <div id="help-${i}" style="margin-top:6px"></div>
        ${e.archetypes ? `<h3 style="margin-top:20px">${esc(t("Tc:archetypes"))} ${help("g_type")}</h3><p class="sub">${esc(L((g.manifest.archetype || {}).rule))} ${esc(t("arch_expl"))}</p><div id="arch-${i}"></div>` : ""}
        <h3 style="margin-top:20px">${esc(t("order"))}</h3><p class="sub">${esc(t("order_expl", { base: pct(e.meta.baseline_win_rate, 2) }))}</p><div id="seat-${i}"></div>
      </section>`;
    });
    view.innerHTML = html;
    srcs.forEach((s, i) => {
      const e = exps[i];
      const min = minBoards(e);
      const ok = e.items.filter((r) => r.boards_with >= min);
      const sorted = ok.slice().sort((a, b) => b.win_lift - a.win_lift);
      const pick = sorted.length > 20 ? sorted.slice(0, 10).concat(sorted.slice(-10)) : sorted;
      C.divergingBars($("#help-" + i), liftRows(g, e, pick), { fmt: (v) => pp(v, 0), vfmt: (v) => pp(v, 1), labelW: 230 });
      if (e.archetypes) C.divergingBars($("#arch-" + i), e.archetypes.filter((r) => r.boards >= 20).map((r) => ({
        label: `${archName(g, r.archetype)} · ${pct(r.share, 0)}`, value: r.win_lift, err: 2 * (r.win_lift_se || 0),
        tip: `<b>${esc(archName(g, r.archetype))}</b><br>${esc(t("share_of"))}: ${pct(r.share, 1)}<br>${esc(t("win_rate"))}: ${pct(r.win_rate, 1)}<br>${esc(t("win_lift"))}: ${pp(r.win_lift)} (± ${pp(2 * (r.win_lift_se || 0)).replace(/^[+−]/, "")})` })), { fmt: (v) => pp(v, 0), vfmt: (v) => pp(v, 1), labelW: 230 });
      C.divergingBars($("#seat-" + i), e.seat_order.map((r) => ({ label: `${t("seat_n", { n: r.seat + 1 })} · ${pct(r.win_rate, 1)}`,
        value: r.win_rate - e.meta.baseline_win_rate, err: 2 * Math.sqrt(r.win_rate * (1 - r.win_rate) / r.seats),
        tip: `<b>${esc(t("seat_n", { n: r.seat + 1 }))}</b><br>${esc(t("win_rate"))}: ${pct(r.win_rate, 1)} (${esc(t("avg_player"))} ${pct(e.meta.baseline_win_rate, 2)})<br>${esc(t("mean_score"))}: ${num(r.mean_score, 1)}` })), { fmt: (v) => pp(v, 1) });
    });
  }
  const minBoards = (e) => Math.max(30, Math.round(e.meta.boards * 0.05));
  /* Points per copy; exactly 0 on a commonly played card means its points are counted on another card: "–". */
  const noPoints = (e, r) => r.points_per_copy === 0 && r.boards_with >= minBoards(e);
  const ppcText = (e, r) => (noPoints(e, r) ? "–" : num(r.points_per_copy, 1));

  // ------------------------------------------------------------------ items list + profile
  function vItems(view, { g, srcs, exps }) {
    const e = exps[0], s = srcs[0];
    const min = minBoards(e);
    const cat = g.catalog.items || {};
    const tagKinds = Object.keys(g.manifest.tags || {});
    const nRare = e.items.filter((r) => r.boards_with < min).length;
    const edge = !unique(g), ncol = edge ? 6 : 5;
    view.innerHTML = `<div class="spread"><div><h2>${esc(t("Tc:items"))} · ${srcHead(g, s)}</h2><p class="sub">${esc(t("items_expl", { n: int(e.items.length) + (g.manifest.items_note ? ` (${L(g.manifest.items_note)})` : "") }))} ${help("g_lift")}</p></div>
      <div class="row"><input type="search" id="q" placeholder="${esc(t("search"))}" aria-label="${esc(t("search"))}">
      ${tagKinds.length ? `<select id="tagf" aria-label="${esc(t("filter"))}">${tagKinds.map((k) => {
        const vals = [...new Set(Object.values(cat).flatMap((it) => (it.tags && it.tags[k]) || []))].sort((a, b) => tagName(g, k, a).localeCompare(tagName(g, k, b)));
        return `<option value="">${esc(t("filter_all", { what: L(g.manifest.tags[k]) }))}</option><optgroup label="${esc(L(g.manifest.tags[k]))}">${vals.map((v) => `<option value="${esc(k + ":" + v)}">${esc(tagName(g, k, v))}</option>`).join("")}</optgroup>`;
      }).join("")}</select>` : ""}</div></div>
      <div class="table-wrap" style="margin-top:12px"><table class="items"><thead><tr>
        <th>${esc(t("Tc:item"))}</th><th class="num sort" data-k="win_lift">${esc(t("win_lift"))} ${help("g_lift")}</th>
        <th class="num sort" data-k="presence_rate">${esc(t("presence"))} ${help("g_presence")}</th>
        <th class="num sort" data-k="points_per_copy">${esc(pointsLabel(g))} ${help("g_points")}</th>
        ${edge ? `<th class="num sort" data-k="winner_edge">${esc(t("winner_edge"))} ${help("g_edge")}</th>` : ""}<th class="num sort" data-k="boards_with">${esc(t("boards_with"))}</th>
      </tr></thead><tbody id="rows"></tbody></table></div><p class="sub" style="margin-top:8px">${esc(t("grey_note", { n: int(min) }))}</p>`;
    let key = "win_lift", dir = -1, open = false;
    view.querySelectorAll("th .qlink").forEach((a) => a.addEventListener("click", (ev) => ev.stopPropagation()));
    const draw = () => {
      const q = $("#q").value.trim().toLowerCase();
      const tf = $("#tagf") ? $("#tagf").value : "";
      const rows = e.items.filter((r) => {
        if (q && !itemName(g, r.item).toLowerCase().includes(q)) return false;
        if (tf) { const [k, v] = tf.split(":"); const it = cat[r.item] || {}; if (!((it.tags || {})[k] || []).includes(v)) return false; }
        return true;
      }).sort((a, b) => dir * ((a[key] ?? -1e9) - (b[key] ?? -1e9)));
      const ok = rows.filter((r) => r.boards_with >= min), rare = rows.filter((r) => r.boards_with < min);
      const max = Math.max(1e-9, ...e.items.filter((r) => r.boards_with >= min).map((r) => Math.abs(r.win_lift)));
      const row = (r, dim) => `<tr class="${dim ? "dim" : ""}">
        <td class="namecell"><a href="${link(g.slug, "items", r.item)}">${esc(itemName(g, r.item))}</a></td>
        <td class="num">${pp(r.win_lift)} ${dim ? `<span class="minibar none"></span>` : `<span class="minibar${Math.abs(r.win_lift) > 2 * (r.win_lift_se || 0) ? "" : " pale"}" style="width:${Math.max(2, Math.round(40 * Math.min(1, Math.abs(r.win_lift) / max)))}px;--c:${r.win_lift >= 0 ? "var(--pos)" : "var(--neg)"}"></span>`}</td>
        <td class="num">${pct(r.presence_rate, 0)}</td>
        <td class="num"${noPoints(e, r) ? ` title="${esc(t("points_none"))}"` : ""}>${ppcText(e, r)}</td>${edge ? `<td class="num">${signed(r.winner_edge)}</td>` : ""}<td class="num">${int(r.boards_with)}</td></tr>`;
      const showRare = open || q || tf;
      $("#rows").innerHTML = (ok.map((r) => row(r, false)).join("")
        + (rare.length ? `<tr class="group"><td colspan="${ncol}"><button type="button" class="linkbtn" id="rare-btn" aria-expanded="${showRare ? "true" : "false"}">${esc(t(showRare ? "rare_hide" : "rare_show", { n: rare.length, min: int(min) }))}</button></td></tr>` : "")
        + (showRare ? rare.map((r) => row(r, true)).join("") : ""))
        || `<tr><td colspan="${ncol}" class="muted">${esc(t("no_match"))}</td></tr>`;
      const rb = $("#rare-btn");
      if (rb) rb.addEventListener("click", () => { open = !open; draw(); });
      void nRare;
    };
    view.querySelectorAll("th.sort").forEach((th) => th.addEventListener("click", () => { dir = key === th.dataset.k ? -dir : -1; key = th.dataset.k; draw(); }));
    $("#q").addEventListener("input", draw);
    if ($("#tagf")) $("#tagf").addEventListener("change", draw);
    draw();
  }

  function describeItem(g, key) {
    const it = (gi18n(g).items || {})[key] || {};
    const cat = (g.catalog.items || {})[key] || {};
    const lines = [];
    ["effect", "bonus", "scoring", "note"].forEach((k) => { if (it[k]) lines.push([t("d_" + k), it[k]]); });
    if (cat.power_text && S.lang === "en") lines.push([t("d_power"), cat.power_text]);
    return lines;
  }
  function verdict(e, st) {
    const min = minBoards(e);
    if (!st) return ["none", t("verdict_never")];
    if (st.boards_with < min) return ["none", t("verdict_rare", { n: int(st.boards_with), min: int(min) })];
    const err = 2 * (st.win_lift_se || 0);
    // under 3 standard errors: among many compared items one or two such results are expected by chance
    const maybe = Math.abs(st.win_lift) < 1.5 * err, rare = st.presence_rate < 0.15;
    if (maybe && st.win_lift - err > 0) return ["pos", t("verdict_pos_maybe")];
    if (maybe && st.win_lift + err < 0) return ["neg", t("verdict_neg_maybe") + (rare ? " " + t("verdict_rare_hint") : "")];
    if (st.win_lift - err > 0.02) return ["pos", t("verdict_pos")];
    if (st.win_lift + err < -0.02) return ["neg", t(rare ? "verdict_neg_rare" : "verdict_neg")];
    if (st.win_lift - err > 0) return ["pos", t("verdict_pos_small")];
    if (st.win_lift + err < 0) return ["neg", t("verdict_neg_small")];
    return ["none", t("verdict_none")];
  }

  function vProfile(view, { g, r, srcs, exps }) {
    const key = r.item;
    const cat = (g.catalog.items || {})[key] || {};
    const attrs = (g.manifest.item_attributes || []).filter((a) => cat[a] !== undefined && cat[a] !== null && !(Array.isArray(cat[a]) && !cat[a].length));
    const fmtAttr = (a, v) => a.startsWith("food") && cat.food && typeof cat.food === "object" ? foodText(g, cat) : Array.isArray(v) ? v.map((x) => tagName(g, a, x)).join(", ") : typeof v === "boolean" ? (v ? t("yes") : t("no")) : (typeof v === "string" ? tagName(g, a, v) : v);
    const desc = describeItem(g, key);
    let html = `<p><a href="${link(g.slug, "items")}">← ${esc(t("all_items"))}</a></p>
      <div class="card" style="margin-top:10px"><h2>${esc(itemName(g, key))}</h2>
        <div class="attrs" style="margin-top:8px">${attrs.map((a) => `<span class="pill">${esc(t("a_" + a))}: ${esc(fmtAttr(a, cat[a]))}</span>`).join("")}</div>
        ${desc.length ? `<div style="margin-top:10px">${desc.map(([k, v]) => `<p class="desc"><b>${esc(k)}:</b> ${esc(v)}</p>`).join("")}</div>` : ""}</div>
      <div class="grid cols-2" style="margin-top:14px">`;
    srcs.forEach((s, i) => {
      const e = exps[i];
      const st = e.items.find((x) => x.item === key);
      const [vk, vtext] = verdict(e, st);
      html += `<div class="card${tentative(g, s) ? " tent" : ""}"><h3>${srcHead(g, s)}</h3>
        <p class="verdict ${vk}">${esc(vtext)}</p>${st && st.boards_with >= minBoards(e) ? `
        <div class="kv" style="margin-top:10px"><div><b>${pp(st.win_lift)}</b><span>${esc(t("win_lift"))} ${help("g_lift")}</span></div>
        <div><b>${pct(st.presence_rate, 0)}</b><span>${esc(t("presence"))} ${help("g_presence")}</span></div>
        <div><b>${ppcText(e, st)}</b><span>${esc(pointsLabel(g))} ${help("g_points")}${noPoints(e, st) ? `<br>${esc(t("points_none"))}` : ""}</span></div>
        ${unique(g) ? "" : `<div><b>${signed(st.winner_edge)}</b><span>${esc(t("winner_edge"))} ${help("g_edge")}</span></div>`}</div>
        <p class="sub" style="margin-top:8px">${esc(t("profile_expl", { win: pct(st.win_rate, 2), base: pct(e.meta.baseline_win_rate, 2), lift: pp(st.win_lift, 2), err: pp(2 * (st.win_lift_se || 0)).replace(/^[+−]/, ""), n: int(st.boards_with) }))}</p>`
        : ""}
        <div id="fate-${i}"></div>
        ${e.length && st && st.boards_with >= minBoards(e) ? `<div id="lenwrap-${i}"><h3 style="margin-top:14px">${esc(t("by_length"))}</h3><p class="sub">${esc(t("by_length_card"))}</p><div id="len-${i}"></div></div>` : ""}</div>`;
    });
    view.innerHTML = html + "</div>";
    // same x range for every player count, so the charts can be compared
    const allBins = exps.flatMap((e) => (e.length ? e.length.bins : []));
    const xmin = allBins.length ? Math.min(...allBins.map((b) => b.rounds_mean)) : undefined, xmax = allBins.length ? Math.max(...allBins.map((b) => b.rounds_mean)) : undefined;
    srcs.forEach((s, i) => {
      const e = exps[i];
      const cards = (cat.cards || [key]);
      const fate = e.cards ? e.cards.filter((c) => cards.includes(c.card)) : [];
      const fateNames = Object.keys(g.manifest.fate || {}).concat(["left_in_hand"]);
      const tot = fateNames.map((k) => fate.reduce((a, c) => a + (c[k] || 0), 0) / e.meta.games);   // average per game
      const copies = cards.reduce((a, c) => a + (((g.catalog.cards || {})[c] || {}).count || 0), 0);
      const host = $("#fate-" + i);
      if (tot.some((v) => v)) {
        host.innerHTML = `<h3 style="margin-top:14px">${esc(t("fate_h"))}</h3><p class="sub">${esc(t("fate_expl", { games: int(e.meta.games), n: copies ? int(copies) : "–" }))} ${esc(L(g.manifest.fate_note))}</p><div class="plot"></div>`;
        C.columns(host.querySelector(".plot"), { x: fateNames.map((k) => L((g.manifest.fate_labels || {})[k]) || k), series: [{ name: t("cards_n"), values: tot }], fmt: (v) => num(v, 2), tickFmt: (v, d) => num(v, Math.max(1, d || 0)), height: 190, ylabel: t("cards_n"), allLabels: true });
      }
      if (e.length && $("#len-" + i)) {
        const bins = Object.fromEntries(e.length.bins.map((b) => [b.bin, b]));
        const pts = e.length.items.filter((x) => x.item === key).map((x) => ({ x: bins[x.bin].rounds_mean, y: x.win_lift, hollow: x.boards < 30,
          tip: `${esc(t("rounds_range", { a: num(bins[x.bin].rounds_min, 0), b: num(bins[x.bin].rounds_max, 0) }))}<br>${esc(t("win_lift"))}: ${pp(x.win_lift)}<br>${esc(t("Tc:boards"))}: ${int(x.boards)}` }));
        if (pts.length < 2) { $("#lenwrap-" + i).remove(); return; }
        C.lines($("#len-" + i), { series: [{ name: itemName(g, key), points: pts }], zero: true, yfmt: (v) => pp(v, 0), xfmt: (v) => num(v, 0), xlabel: t("rounds_per_player"), height: 200, xmin, xmax });
      }
    });
  }

  // ------------------------------------------------------------------ boards
  function vBoards(view, { g, srcs, exps }) {
    const e = exps[0];
    const groups = { top: t("pos_top"), middle: t("pos_middle"), bottom: t("pos_bottom") };
    view.innerHTML = `<h2>${esc(t("boards_h"))} · ${srcHead(g, srcs[0])}</h2><p class="sub">${esc(t("boards_expl"))} ${esc(L(g.manifest.boards_note))}</p>
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
        ${[0, 1, 2, 3, 4].map((c) => { const x = byGroup[gk].find((y) => y.slot === c); return x ? `<div class="slot filled"><div class="sn"${(gi18n(g).items || {})[x.item] ? "" : ' lang="en"'}>${esc(itemName(g, x.item))}</div>
          <div class="sd">${int(x.points)} ${esc(t("points_short"))}${x.tags && x.tags.eggs ? ` · ${x.tags.eggs} 🥚` : ""}${x.tags && x.tags.tucked ? ` · ${x.tags.tucked} ${esc(t("tucked_short"))}` : ""}${x.tags && x.tags.cache ? ` · ${x.tags.cache} ${esc(t("cache_short"))}` : ""}</div></div>` : `<div class="slot"></div>`; }).join("")}</div>`).join("");
    }
    return `<div class="card flat">${head}<div style="margin-top:8px">${body}</div></div>`;
  }

  // ------------------------------------------------------------------ play style
  function vStyle(view, { g, srcs, exps }) {
    let html = "";
    srcs.forEach((s, i) => {
      const out = (exps[i].style.outcome || [])[0] || {};
      const facts = [[t("st_score"), num(out.score, 0)], [t("t_winner"), num(exps[i].meta.winner_score, 0)], [t("st_hand_left"), num(out.hand_left, 1)]]
        .concat(Object.keys(g.manifest.seat_extras || {}).filter((k) => out["x_" + k] !== undefined).map((k) => [t("st_count", { what: L(g.manifest.seat_extras[k]) }), num(out["x_" + k], 1)]));
      html += `<section class="section card${tentative(g, s) ? " tent" : ""}"><h2>${srcHead(g, s)}</h2>
        <p class="sub" style="margin-top:6px">${esc(t("style_facts"))}</p>
        <div class="kv" style="margin-top:6px">${facts.map(([k, v]) => `<div><b>${esc(v)}</b><span>${esc(k)}</span></div>`).join("")}</div>
        <div class="grid cols-2" style="margin-top:14px">
          <div><h3>${esc(t("action_mix"))}</h3><p class="sub">${esc(t("action_mix_expl"))}</p><div id="mix-${i}"></div></div>
          <div><h3>${esc(t("score_split"))}</h3><p class="sub">${esc(t("score_split_expl"))}</p><div id="split-${i}"></div></div>
          <div><h3>${esc(t("most_played"))}</h3><p class="sub">${esc(t("most_played_expl"))}</p><div id="played-${i}"></div></div>
          <div><h3>${esc(t("most_points"))} ${help("g_points_board")}</h3><p class="sub">${esc(t("most_points_expl"))}</p><div id="points-${i}"></div></div>
          ${exps[i].style.optional_use && exps[i].style.optional_use.length ? `<div><h3>${esc(t("optional_h"))}</h3><p class="sub">${esc(t("optional_expl"))} ${esc(L(g.manifest.optional_note))}</p><div id="opt-${i}"></div></div>` : ""}
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
        tip: `<b>${esc(itemName(g, r.item))}</b><br>${num(r.points_per_board, 1)} ${esc(t("points_per_board"))}` })), { fmt: (v) => num(v, 1), mag: true });
      if ($("#opt-" + i)) {
        const rows = st.optional_use.slice().sort((a, b) => a.use_rate - b.use_rate).slice(0, 12);
        const optNames = gi18n(g).optional || {};
        const wname = (w) => optNames[w] || (has("w_" + w) ? t("w_" + w) : w.replace(/_/g, " "));
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
      html += `<section class="section card${tentative(g, s) ? " tent" : ""}"><h2>${srcHead(g, s)}</h2>
        <p class="takeaway">${esc(t("length_expl", { a: num(exps[i].meta.rounds_min, 0), b: num(exps[i].meta.rounds_max, 0) }))} ${help("g_turns")}</p>
        <p class="takeaway">${esc(t("length_score", { lo: num(exps[i].length.bins[0].winner_score, 0), hi: num(exps[i].length.bins[exps[i].length.bins.length - 1].winner_score, 0) }))}</p>
        <div class="grid cols-2" style="margin-top:10px"><div><h3>${esc(t("by_length_items"))}</h3><p class="sub">${esc(t("by_length_expl"))}</p><div id="lenit-${i}"></div></div>
        <div><h3>${esc(t("hist_h"))}</h3><p class="sub">${esc(t("hist_expl"))}</p><div id="hist-${i}"></div></div>
        ${exps[i].length.archetypes ? `<div><h3>${esc(t("by_length_arch"))}</h3><p class="sub">${esc(t("by_length_arch_expl"))}</p><div id="lenar-${i}"></div></div>` : ""}</div></section>`;
    });
    view.innerHTML = html;
    srcs.forEach((s, i) => {
      const ln = exps[i].length;
      if (!ln) return;
      const bins = Object.fromEntries(ln.bins.map((b) => [b.bin, b]));
      const mk = (key, name, rows) => ({ name, points: rows.map((x) => ({ x: bins[x.bin].rounds_mean, y: x.win_lift, hollow: x.boards < 30,
        tip: `<b>${esc(name)}</b><br>${esc(t("rounds_range", { a: num(bins[x.bin].rounds_min, 0), b: num(bins[x.bin].rounds_max, 0) }))}<br>${esc(t("win_lift"))}: ${pp(x.win_lift)}<br>${int(x.boards)} ${esc(t("T:boards"))}` })) });
      C.lines($("#lenit-" + i), { series: ln.default_items.map((k) => mk(k, itemName(g, k), ln.items.filter((x) => x.item === k))), zero: true, yfmt: (v) => pp(v, 0), xfmt: (v) => num(v, 0), xlabel: t("rounds_per_player") });
      // two turns per bar: whole and half turns per player would otherwise alternate tall and short bars
      const h2 = {};
      ln.histogram.forEach((h) => { const k = Math.floor(h.rounds / 2) * 2; h2[k] = (h2[k] || 0) + h.games; });
      const hk = Object.keys(h2).map(Number).sort((a, b) => a - b);
      C.columns($("#hist-" + i), { x: hk.map((k) => `${k}–${k + 1}`), series: [{ name: t("games"), values: hk.map((k) => h2[k]),
        tips: hk.map((k) => `${esc(t("rounds_range", { a: k, b: k + 1 }))}<br><b>${int(h2[k])}</b> ${esc(t("games"))}`) }], fmt: int, height: 220, xlabel: t("rounds_per_player"), ylabel: t("n_games") });
      if (ln.archetypes && $("#lenar-" + i)) {
        const share = Object.fromEntries((exps[i].archetypes || []).map((a) => [a.archetype, a.share]));
        const keys = [...new Set(ln.archetypes.map((x) => x.archetype))].filter((k) => (share[k] || 0) >= 0.05 && ln.archetypes.filter((x) => x.archetype === k && x.boards >= 30).length >= 3)
          .sort((a, b) => share[b] - share[a]).slice(0, 6);
        C.lines($("#lenar-" + i), { series: keys.map((k) => mk(k, archName(g, k), ln.archetypes.filter((x) => x.archetype === k))), zero: true, yfmt: (v) => pp(v, 0), xfmt: (v) => num(v, 0), xlabel: t("rounds_per_player") });
      }
    });
  }

  // ------------------------------------------------------------------ game-specific sections (standard shapes)
  function secLabel(g, key) {
    return (gi18n(g).sections || {})[key] || ((g.i18n.en || {}).sections || {})[key] || t(key) || key;
  }
  function vMore(view, { g, srcs, exps }) {
    let html = "";
    const keys = Object.keys((exps[0] && exps[0].game) || {});
    keys.forEach((k) => {
      const first = exps[0].game[k];
      html += `<section class="section card"><h2>${esc(secLabel(g, first.title))}</h2>${first.note ? `<p class="takeaway">${esc(secLabel(g, first.note))}</p>` : ""}
        <div class="grid ${srcs.length > 1 ? "cols-2" : ""}" style="margin-top:10px">${srcs.map((s, i) => `<div>${srcs.length > 1 ? `<h3>${srcHead(g, s)}</h3>` : ""}<div id="sec-${k}-${i}"></div></div>`).join("")}</div></section>`;
    });
    view.innerHTML = html || `<p class="empty">${esc(t("no_data"))}</p>`;
    keys.forEach((k) => srcs.forEach((s, i) => { const sec = exps[i].game && exps[i].game[k]; if (sec) drawShape(g, $(`#sec-${k}-${i}`), sec, s.players); }));
  }
  function drawShape(g, el, sec, players) {
    // the average place is always about 1.5 with 2 players: hide that column there
    if (players === 2 && sec.columns) sec = Object.assign({}, sec, { columns: sec.columns.filter((c) => c.key !== "mean_rank") });
    const facts = sec.facts ? `<div class="kv" style="margin-bottom:10px">${sec.facts.map((f) => `<div><b>${esc(fmtBy(f.format, f.value))}</b><span>${esc(secLabel(g, f.label))}</span></div>`).join("")}</div>` : "";
    const after = sec.facts_note || (secLabel(g, sec.title + "_after") !== sec.title + "_after" ? secLabel(g, sec.title + "_after") : "");
    el.innerHTML = facts + (after ? `<p class="sub" style="margin:-4px 0 10px">${esc(after)}</p>` : "") + '<div class="plot"></div><div class="tbl"></div>';
    const plot = el.querySelector(".plot");
    const lab = (k) => secLabel(g, k);
    const cell = (c, v) => c.format === "category" ? L((g.manifest.score_categories || {})[v]) || v : c.format === "label" ? lab(v) : c.format === "text" ? v : fmtBy(c.format, v);
    if (sec.shape === "bars") {
      const MIN = 20;                                           // groups with fewer players are too noisy to plot
      const hidden = sec.rows.filter((r) => r[sec.bars] < MIN);
      sec = Object.assign({}, sec, { rows: sec.rows.filter((r) => r[sec.bars] >= MIN) });
      const xs = sec.rows.map((r) => fmtBy(sec.x_format, r[sec.x]));
      const FEW = 200;                                          // groups below this are drawn pale
      C.columns(plot, { x: xs, series: [{ name: lab(sec.line_label), values: sec.rows.map((r) => r[sec.line]), dims: sec.rows.map((r) => r[sec.bars] < FEW),
        tips: sec.rows.map((r, i) => `<b>${esc(lab(sec.x_label))}: ${esc(xs[i])}</b><br>${esc(lab(sec.line_label))}: ${esc(fmtBy(sec.line_format, r[sec.line]))}<br>${esc(lab(sec.bar_label))}: ${int(r[sec.bars])}`) }],
        fmt: (v) => fmtBy(sec.line_format, v).replace(/,0 %|\.0 %/, " %"), baseline: sec.baseline, base_label: t("equal_share"), diverge: sec.baseline !== undefined, minSpan: 0.1, height: 220,
        xlabel: lab(sec.x_label), ylabel: lab(sec.line_label) });
      const small = el.querySelector(".tbl");
      small.innerHTML = `<p class="sub" style="margin-top:6px">${esc(t("bars_expl", { few: int(FEW) }))} ${esc(lab(sec.bar_label))}: ${sec.rows.map((r, i) => `${esc(xs[i])}: ${int(r[sec.bars])}`).join(" · ")}${
        hidden.length ? ` · ${esc(t("hidden_small", { n: MIN }))}: ${hidden.map((r) => `${esc(fmtBy(sec.x_format, r[sec.x]))} (${int(r[sec.bars])})`).join(", ")}` : ""}</p>`;
    } else if (sec.shape === "grid") {
      C.grid(plot, { xEdges: sec.x_edges, yEdges: sec.y_edges, counts: sec.counts, xlabel: lab(sec.x_label), ylabel: lab(sec.y_label), unit: t("games"),
                     legendLo: t("grid_few"), legendHi: t("grid_many") });
    } else if (sec.shape === "table") {
      if (sec.bars) {
        const cols = sec.columns;
        const xcol = cols.find((c) => c.key === sec.bars.x);
        C.columns(plot, { x: sec.rows.map((r) => cell(xcol, r[sec.bars.x])), series: sec.bars.series.map((sk) => ({ name: lab(sk), values: sec.rows.map((r) => r[sk]) })), fmt: (v) => num(v, 1), height: 220 });
      }
      const sortable = sec.rows.length > 12;
      // a row whose difference could be chance (its range crosses 0) is greyed, as in the bar charts
      const unclearRow = (s, r) => s.columns.some((c) => c.format === "pp" && r[c.key + "_se"] !== undefined && Math.abs(r[c.key]) <= 2 * r[c.key + "_se"]);
      el.querySelector(".tbl").innerHTML = `<div class="table-wrap" style="margin-top:10px;max-height:${sortable ? "420px" : "none"}"><table><thead><tr>${sec.columns.map((c) => `<th class="${["text", "category", "label"].includes(c.format) ? "" : "num"}">${esc(lab(c.label))}</th>`).join("")}</tr></thead>
        <tbody>${sec.rows.map((r) => `<tr class="${unclearRow(sec, r) ? "dim" : ""}">${sec.columns.map((c) => `<td class="${["text", "category", "label"].includes(c.format) ? "" : "num"}">${esc(cell(c, r[c.key]))}${c.format === "pp" && r[c.key + "_se"] ? ` <span class="muted">± ${esc(pp(2 * r[c.key + "_se"]).replace(/^[+−]/, ""))}</span>` : ""}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
  }

  // ------------------------------------------------------------------ comparison
  function vCompare(view, { g, r }) {
    const ps = Object.keys(g.compare || {}).filter((p) => !r.q.p || p === r.q.p);
    let html = `<h2>${esc(t("compare_h"))}</h2><p class="takeaway">${esc(t("compare_expl"))}</p>`;
    if (!ps.length) html += `<p class="sub" style="margin-top:8px">${esc(t("compare_none", { players: t("n_players", { n: r.q.p }) }))}</p>`;
    ps.forEach((p) => {
      const c = g.compare[p];
      const feat = g.manifest.featured[p];
      const newM = g.experiments[feat.main].seats[0], oldM = g.experiments[feat.compare].seats[0];
      const vNew = (c.versus || []).find((v) => v.agent === "model:" + newM);
      const lab = (g.models[newM] || {}).strength ? ((g.models[newM].strength.games || []).find((x) => x.opponent === oldM) || null) : null;
      html += `<section class="section card"><h2>${esc(t("n_players", { n: p }))}</h2>
        <p class="sub">${esc(modelLabel(g, newM))} ↔ ${esc(modelLabel(g, oldM))}</p>
        ${c.versus ? `<h3 style="margin-top:12px">${esc(t("versus_h"))}</h3><div class="kv" style="margin-top:6px">${c.versus.map((v) => `<div><b>${pct(v.win_rate, 1)}</b><span>${esc(t("versus_wins", { who: agentName(g, v.agent) }))} · ${esc(t("mean_score"))} ${num(v.mean_score, 0)}</span></div>`).join("")}</div>
          ${vNew ? `<p class="sub" style="margin-top:6px">${esc(t("versus_expl", { games: int(((g.experiments[feat.versus] || {}).games) || 0), win: pct(vNew.win_rate, 1) }))}${lab ? " " + esc(t("versus_lab", { win: pct(lab.win, 1), games: int(lab.games) })) : ""}</p>` : ""}` : ""}
        ${c.deals ? `<h3 style="margin-top:14px">${esc(t("deals_h"))}</h3><p class="sub">${esc(t("deals_expl", { n: int(c.deals.deals), new: num(c.deals.winner_new, 0), old: num(c.deals.winner_old, 0), share: pct(c.deals.new_higher, 0) }))}</p>
          <p class="takeaway" style="margin-top:6px">${esc(t(vNew ? "deals_why" : "deals_why_short", { vs: vNew ? num(vNew.mean_score, 0) : "" }))}</p><div id="deals-${p}"></div>` : ""}
        <h3 style="margin-top:14px">${esc(t("changes_h"))} ${help("g_lift")}</h3><p class="sub">${esc(t("changes_expl"))}</p><div id="chg-${p}"></div>
        <h3 style="margin-top:14px">${esc(t("style_cmp_h"))}</h3><p class="sub">${esc(t("style_cmp_expl"))}</p><div class="table-wrap" style="margin-top:6px"><table><thead><tr><th></th><th class="num">${esc(t("ai_new"))}</th><th class="num">${esc(t("ai_original"))}</th></tr></thead><tbody>
        ${Object.keys(c.style.new).filter((k) => typeof c.style.new[k] === "number" && !["seats", "win_rate"].includes(k)).map((k) => `<tr><td>${esc(styleLabel(g, k))}</td><td class="num">${esc(styleVal(k, c.style.new[k]))}</td><td class="num">${esc(styleVal(k, c.style.old[k]))}</td></tr>`).join("")}
        </tbody></table></div></section>`;
    });
    view.innerHTML = html;
    ps.forEach((p) => {
      const c = g.compare[p];
      if (c.deals) C.columns($("#deals-" + p), { x: c.deals.hist.map((h) => (h.from % 100 === 0 ? (h.from > 0 ? "+" : h.from < 0 ? "−" : "") + Math.abs(h.from) : "")),
        series: [{ name: t("deals"), values: c.deals.hist.map((h) => h.deals),
        tips: c.deals.hist.map((h) => `${esc(t("winner_diff", { a: h.from, b: h.to }))}<br><b>${int(h.deals)}</b> ${esc(t("deals"))}`) }], fmt: int, height: 200,
        xlabel: t("deals_axis"), ylabel: t("deals"), allLabels: true });
      const clear = c.items.filter((x) => x.clear);
      const sel = clear.slice(0, 8).concat(clear.slice(-8).filter((x) => !clear.slice(0, 8).includes(x)));
      const bare = (v) => pp(v).replace(" " + t("pp"), "");
      C.divergingBars($("#chg-" + p), sel.map((x) => ({ label: `${itemName(g, x.item)} · ${bare(x.lift_old)} → ${pp(x.lift_new)}`, value: x.change, err: 2 * x.se,
        tip: `<b>${esc(itemName(g, x.item))}</b><br>${esc(t("ai_new"))}: ${pp(x.lift_new)}<br>${esc(t("ai_original"))}: ${pp(x.lift_old)}<br>${esc(t("change"))}: ${pp(x.change)} (± ${pp(2 * x.se).replace(/^[+−]/, "")})` })), { fmt: (v) => pp(v, 0), vfmt: (v) => pp(v, 1), labelW: 330 });
    });
  }
  function styleLabel(g, k) {
    if (k.startsWith("b_")) return t("st_points_from", { what: L((g.manifest.score_categories || {})[k.slice(2)]) || k });
    if (k.startsWith("x_")) return t("st_count", { what: L((g.manifest.seat_extras || {})[k.slice(2)]) || k });
    return t("st_" + k);
  }
  const styleVal = (k, v) => (["win_rate", "first_seat_win"].includes(k) || k.endsWith("_share") ? pct(v, 1) : num(v, k === "winner_score" ? 0 : 1));

  // ------------------------------------------------------------------ lab
  function oppLabel(g, x, players) {
    if (has("agent_" + x.opponent)) return t("agent_" + x.opponent);
    if (g.models[x.opponent]) return modelLabel(g, x.opponent);
    const m = /ppo_(\d+)(\.zip)?$/.exec(x.opponent || "");
    // the strength card's own label says whether the AI trained against that checkpoint ("never trained against")
    const seen = x.label && /trained against/i.test(x.label) && !/never/i.test(x.label);
    if (m) return t(seen ? "opp_trained" : x.opponent.includes("/") ? "opp_other_run" : "opp_own_early", { steps: fmtSteps(+m[1]), even: pct(1 / players, 0) });
    return x.label || x.opponent;
  }
  // by player count, the finished AI first
  const labOrder = (g) => Object.values(g.models).sort((a, b) => a.players - b.players || ((b.strength || {}).finished ? 1 : 0) - ((a.strength || {}).finished ? 1 : 0));
  function labSummary(g) {
    const models = labOrder(g);
    if (!models.length && !limits(g).length) return "";
    const lim = limits(g);
    return `<div class="card section"><h3>${esc(t("lab_summary_h"))}</h3><ul class="clean">${models.map((m) => {
      const role = modelRole(g, m.id);
      return `<li>${esc(t("lab_sum_" + role, { players: t("n_players", { n: m.players }), why: role === "early" ? whyEarly(g, m.id) : "" }))}</li>`;
    }).join("")}</ul>${lim.length ? `<h3 id="limits" style="margin-top:14px">${esc(t("limits_h"))}</h3><ul class="clean">${lim.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}</div>`;
  }
  function vLab(view, { g, r }) {
    const models = labOrder(g);
    const mi = gi18n(g).models || {};
    let html = `<h2>${esc(t("lab_h"))}</h2><p class="takeaway">${esc(t("lab_expl"))}</p>${labSummary(g)}`;
    models.forEach((m, i) => {
      const st = m.strength || {};
      const status = st.finished ? `<span class="pill ok">${esc(t("model_finished"))}</span>` : `<span class="pill warn">${esc(t(st.legacy || m.legacy ? "model_legacy" : "model_unfinished"))}</span>`;
      const note = (mi[m.id] || {}).note || (S.lang === "en" ? st.note : "") || "";
      html += `<section class="section card"><div class="spread"><h2>${esc(modelLabel(g, m.id))}</h2><div class="row">${status}<code>${esc(m.id)}</code></div></div>
        <div class="kv" style="margin-top:10px"><div><b>${m.steps ? fmtSteps(m.steps) : "–"}</b><span>${esc(t("t_training"))} ${help("g_steps")}</span></div>
          <div><b>${m.games ? int(m.games) : "–"}</b><span>${esc(t("training_games"))}</span></div><div><b>${m.hours ? num(m.hours, 1) + " h" : "–"}</b><span>${esc(t("hours"))}</span></div>
          <div><b>${m.size_mb ? num(m.size_mb, 1) + " MB" : "–"}</b><span>${esc(t("size"))}</span></div></div>
        <h3 style="margin-top:14px">${esc(t("strength_h"))} ${help("g_strength")}</h3><p class="sub">${esc(t("strength_expl", { even: pct(1 / m.players, 0) }))}</p>
        <div class="table-wrap" style="margin-top:6px"><table><thead><tr><th>${esc(t("opponent"))}</th><th class="num">${esc(t("games_col"))}</th><th class="num">${esc(t("win_rate"))}</th><th class="num">${esc(t("margin"))}</th><th>${esc(t("required"))}</th></tr></thead><tbody>
        ${(st.games || []).map((x) => `<tr><td>${esc(oppLabel(g, x, m.players))}</td><td class="num">${int(x.games)}${x.games < 30 ? ` <span class="muted">(${esc(t("few_games"))})</span>` : ""}</td><td class="num">${pct(x.win, 1)}${x.win_se ? ` <span class="muted">± ${pct(2 * x.win_se, 1)}</span>` : ""}</td><td class="num">${x.margin !== undefined && x.margin !== null ? signed(x.margin, 0) : "–"}</td><td>${esc(!x.required ? "–" : x.required === "beats" ? t("req_beats") : t("req_atleast", { v: pct(parseFloat(x.required.slice(2)), 0) }))}${x.required ? ((x.required === "beats" ? x.win - 2 * (x.win_se || 0) > 0.5 : x.win >= parseFloat(x.required.slice(2))) ? " ✓" : " ✗") : ""}</td></tr>`).join("")}
        </tbody></table></div>${note ? `<p class="sub" style="margin-top:6px">${esc(note)}</p>` : ""}
        ${Object.keys(m.log_rows || {}).length ? `<h3 style="margin-top:14px">${esc(t("curve_h"))}</h3><p class="sub">${esc(t("curve_expl"))}</p><div id="curve-${i}"></div>` : ""}
        <details style="margin-top:12px"><summary>${esc(t("recipe_h"))}</summary><ol class="clean">${(m.recipe || []).map((x) => `<li><code>${esc(x)}</code></li>`).join("")}</ol>
          <p class="sub" style="margin-top:6px">sha256 <code>${esc((m.sha256 || "").slice(0, 16))}…</code> · ${esc(m.source || "")}</p></details></section>`;
    });
    html += `<section class="section"><h2>${esc(t("exp_h"))}</h2><p class="takeaway">${esc(t("exp_expl"))}</p>${Object.keys(g.experiments).length ? "" : `<p class="sub" style="margin-top:6px">${esc(t("exp_none"))}</p>`}<div class="grid cols-2" style="margin-top:10px">
      ${Object.values(g.experiments).map((x) => `<div class="card"><div class="spread"><h3><code>${esc(x.id)}</code></h3><span class="pill">${esc(t("kind_" + x.kind))}</span></div>
        <p class="sub" style="margin-top:6px">${esc(t("exp_line", { games: int(x.games), players: t("n_players", { n: x.players }), seed: x.seed }))}</p>
        <p class="sub">${esc(t("seats"))}: ${x.seats.map((s) => esc(seatInfo(g, s).model ? modelLabel(g, s) : seatInfo(g, s).label)).join(" · ")}</p>
        <details style="margin-top:6px"><summary>${esc(t("commands_h"))}</summary><pre style="margin-top:8px">${esc(x.command)}</pre><pre style="margin-top:6px">python -m bgai.experiment --game ${esc(x.game)} --id ${esc(x.id)} --verify 20</pre></details></div>`).join("")}</div></section>
      <section class="section card"><h2>${esc(t("rights_h"))}</h2><pre style="margin-top:8px">${esc(g.rights || "")}</pre></section>`;
    view.innerHTML = html;
    models.forEach((m, i) => {
      const host = $("#curve-" + i);
      if (!host) return;
      const series = { win_vs_ref: [], win_vs_greedy: [], win_vs_1m: [], win_vs_3m: [], win_vs_anchor: [] };
      Object.values(m.log_rows).forEach((rows) => {
        rows.forEach((row) => Object.keys(series).forEach((k) => { if (row[k] !== null && row[k] !== undefined) series[k].push({ x: row.steps / 1e6, y: row[k] }); }));
      });
      const shown = Object.entries(series).filter(([, pts]) => pts.length >= 2).map(([k, pts]) => ({ name: t("c_" + k), points: pts.map((q) => ({ ...q, tip: `<b>${esc(t("c_" + k))}</b><br>${num(q.x, 1)} ${esc(t("million"))} ${esc(t("steps"))}: ${pct(q.y, 1)}` })) }));
      C.lines(host, { series: shown, yfmt: (v) => pct(v, 0), xfmt: (v) => num(v, 0), xlabel: t("steps_m"), ymin: 0, ymax: 1, refs: [{ y: 1 / m.players, label: t("equal_share") }] });
    });
    const to = r && r.q.s && document.getElementById(r.q.s);   // e.g. ?s=limits from the Discoveries caveat
    if (to) setTimeout(() => to.scrollIntoView({ block: "start" }), 30);
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
    const sk = $(".skip"); if (sk) sk.textContent = t("skip");
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
    window.addEventListener("hashchange", () => { window.scrollTo({ top: 0 }); render(); });
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
