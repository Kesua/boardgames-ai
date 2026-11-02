"""Recompute every number cited in games/forest_shuffle/notes.json from the current stats.json files and print the
English text each one should have. Run from the repository root after tools/build_site.py: python games/forest_shuffle/check_notes.py  (prints MISMATCH lines when notes differ)."""
import json, sys, re

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

R = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
G = R / "games" / "forest_shuffle"
st = {e: json.loads((G / "experiments" / e / "stats.json").read_text(encoding="utf-8")) for e in
      ["p2-v2fix-15m-mirror", "p2-v1-7.2m-mirror", "p4-v1-6.8m-mirror", "p2-v2fix-15m-vs-v1-7.2m"]}
cat = None
try:
    cat = json.loads((R / "site" / "data" / "forest_shuffle" / "game.json").read_text(encoding="utf-8"))["catalog"]["items"]
except Exception:
    pass
notes = (G / "notes.json").read_text(encoding="utf-8")

def r(v, d):  # JS Intl rounding (half away from zero) of v with d decimals
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(repr(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    return f"{q:,}" if d else f"{int(q):,}"
P = lambda v, d=0: r(v * 100, d) + " %"
PP = lambda v, d=1: ("+" if v > 0 else "−" if v < 0 else "") + r(abs(v * 100), d) + " pp"
E = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + r(abs(v), 2)
def item(e, k): return next(x for x in st[e]["items"] if x["item"] == k)
def arch(e, k): return next(x for x in st[e]["archetypes"] if x["archetype"] == k)
def fact(e, sec, lab): return next(f["value"] for f in st[e]["game"][sec]["facts"] if f["label"] == lab)
def row(e, sec, grp, key="win_rate"): return next(x[key] for x in st[e]["game"][sec]["rows"] if x["group"] == grp)
def lenbin(e, k, b, kind="items", key="item"): return next(x["win_lift"] for x in st[e]["length"][kind] if x[key] == k and x["bin"] == b)
def out(e): return st[e]["style"]["outcome"][0]
def fate(e, k, f):
    cards = {c["card"]: c for c in st[e]["cards"]}
    return sum(cards.get(c, {}).get(f, 0) for c in cat[k]["cards"]) if cat else None

N, O, F, V = "p2-v2fix-15m-mirror", "p2-v1-7.2m-mirror", "p4-v1-6.8m-mirror", "p2-v2fix-15m-vs-v1-7.2m"
checks = [
    # --- 2p new AI
    ("N Gentian lift", PP(item(N, "GENTIAN")["win_lift"])), ("N Gentian presence", P(item(N, "GENTIAN")["presence_rate"])),
    ("N Gentian ppc", r(item(N, "GENTIAN")["points_per_copy"], 1)), ("N Gentian edge", E(item(N, "GENTIAN")["winner_edge"])),
    ("N Phoebus", PP(item(N, "PHOEBUS_APOLLO")["win_lift"])), ("N SWF", PP(item(N, "SILVER_WASHED_FRITILLARY")["win_lift"])),
    ("N Marten presence", P(item(N, "BEECH_MARTEN")["presence_rate"])), ("N Marten ppc", r(item(N, "BEECH_MARTEN")["points_per_copy"], 1)),
    ("N Marten edge", E(item(N, "BEECH_MARTEN")["winner_edge"])),
    ("N Fallow lift", PP(item(N, "FALLOW_DEER")["win_lift"])), ("N Fallow ppc", r(item(N, "FALLOW_DEER")["points_per_copy"], 1)),
    ("N Fallow edge", E(item(N, "FALLOW_DEER")["winner_edge"])), ("N Bison", PP(item(N, "EUROPEAN_BISON")["win_lift"])),
    ("N Steinbock", PP(item(N, "STEINBOCK")["win_lift"])), ("N Wolf", PP(item(N, "WOLF")["win_lift"])), ("N Wolf ppc", r(item(N, "WOLF")["points_per_copy"], 1)),
    ("N StonePine symbol share", P(arch(N, "SWISS_PINE")["share"])), ("N StonePine symbol win", P(arch(N, "SWISS_PINE")["win_rate"])),
    ("N Stone Pine presence", P(item(N, "STONE_PINE")["presence_rate"])), ("N Stone Pine edge", E(item(N, "STONE_PINE")["winner_edge"])),
    ("N Stone Pine lift", PP(item(N, "STONE_PINE")["win_lift"])), ("N Stone Pine lift within chance (must be True)", str(abs(item(N, "STONE_PINE")["win_lift"]) <= 2 * item(N, "STONE_PINE")["win_lift_se"])),
    ("N saplings/player", r(out(N)["x_saplings"], 1)), ("N sapling forests", P(arch(N, "SAPLING")["share"])), ("N sapling win", P(arch(N, "SAPLING")["win_rate"])),
    ("N Beech presence", P(item(N, "BEECH")["presence_rate"])), ("N Beech edge", E(item(N, "BEECH")["winner_edge"])),
    ("N Beech symbol share", P(arch(N, "BEECH")["share"])), ("N Beech symbol win", P(arch(N, "BEECH")["win_rate"])),
    ("N Raccoon", PP(item(N, "RACCOON")["win_lift"])), ("N Raccoon presence", P(item(N, "RACCOON")["presence_rate"])), ("N Raccoon edge", E(item(N, "RACCOON")["winner_edge"])),
    ("N Sycamore", PP(item(N, "SYCAMORE")["win_lift"]) + " " + P(item(N, "SYCAMORE")["presence_rate"])),
    ("N Woodpecker", PP(item(N, "GREAT_SPOTTED_WOODPECKER")["win_lift"]) + " " + P(item(N, "GREAT_SPOTTED_WOODPECKER")["presence_rate"])),
    ("N Jay", PP(item(N, "EURASIAN_JAY")["win_lift"]) + " " + P(item(N, "EURASIAN_JAY")["presence_rate"])),
    ("N Oak paid / sapling / played", f"{fate(N, 'OAK', 'paid'):,} / {fate(N, 'OAK', 'as_sapling')} / {fate(N, 'OAK', 'played')}"),
    ("N Oak forests (card)", str(item(N, "OAK")["boards_with"])), ("N Oak symbol share/win", P(arch(N, "OAK")["share"]) + " / " + P(arch(N, "OAK")["win_rate"])),
    ("N seats", P(st[N]["seat_order"][0]["win_rate"], 1) + " : " + P(st[N]["seat_order"][1]["win_rate"], 1)),
    ("N turns", r(st[N]["meta"]["rounds_min"], 0) + "–" + r(st[N]["meta"]["rounds_max"], 0)),
    ("N winner by length", r(st[N]["length"]["bins"][0]["winner_score"], 0) + " → " + r(st[N]["length"]["bins"][-1]["winner_score"], 0)),
    ("N r2 deck/clearing/both", " / ".join(P(fact(N, "drivers", k), 1) for k in ("r2_deck",))),
    ("N clearing win:lose", P(fact(N, "clearing", "clearing_winners"), 1) + " : " + P(fact(N, "clearing", "clearing_losers"), 1)),
    ("N clearing share of turns", P(next(a["share"] for a in st[N]["style"]["action_mix"] if a["action"] == "DRAW_CLEARING"))),
    ("N wipes/game, win, lose", r(fact(N, "wipes", "wipes_per_game"), 1) + ", " + r(fact(N, "wipes", "wipes_winners"), 2) + ", " + r(fact(N, "wipes", "wipes_losers"), 2)),
    ("N hand left", r(out(N)["hand_left"], 1)),
    ("N 4p Beech edge", E(item(F, "BEECH")["winner_edge"])),
    # --- 2p original AI
    ("O saplings/player", r(out(O)["x_saplings"], 1)), ("O sapling forests / win", P(arch(O, "SAPLING")["share"]) + " / " + P(arch(O, "SAPLING")["win_rate"], 1)),
    ("O Red Deer", PP(item(O, "RED_DEER")["win_lift"]) + " " + E(item(O, "RED_DEER")["winner_edge"])),
    ("O Marten", PP(item(O, "BEECH_MARTEN")["win_lift"]) + " " + E(item(O, "BEECH_MARTEN")["winner_edge"])),
    ("O Wood Ant / Moss", PP(item(O, "WOOD_ANT")["win_lift"]) + " / " + PP(item(O, "MOSS")["win_lift"])),
    ("O Fallow / Wolf", PP(item(O, "FALLOW_DEER")["win_lift"]) + " " + E(item(O, "FALLOW_DEER")["winner_edge"]) + " / " + PP(item(O, "WOLF")["win_lift"])),
    ("O MapB/Gentian/Digitalis/Blackberries", " / ".join(PP(item(O, k)["win_lift"]) for k in ("MAP_BUTTERFLY", "GENTIAN", "DIGITALIS", "BLACKBERRIES"))),
    ("O Douglas symbol share/win", P(arch(O, "DOUGLAS_FIR")["share"]) + " / " + P(arch(O, "DOUGLAS_FIR")["win_rate"], 1)),
    ("O Douglas/Birch/Larch", " / ".join(PP(item(O, k)["win_lift"]) for k in ("DOUGLAS_FIR", "BIRCH", "EUROPEAN_LARCH"))),
    ("O VCB/Magpie/Fox/PennyBun/Hare", " / ".join(PP(item(O, k)["win_lift"]) for k in ("VIOLET_CARPENTER_BEE", "EURASIAN_MAGPIE", "RED_FOX", "PENNY_BUN", "EUROPEAN_HARE"))),
    ("O hand left", r(out(O)["hand_left"], 1)), ("O seats", P(st[O]["seat_order"][0]["win_rate"], 1) + " : " + P(st[O]["seat_order"][1]["win_rate"], 1)),
    ("O turns", r(st[O]["meta"]["rounds_min"], 0) + "–" + r(st[O]["meta"]["rounds_max"], 0)),
    ("O winner by length", r(st[O]["length"]["bins"][0]["winner_score"], 0) + " → " + r(st[O]["length"]["bins"][-1]["winner_score"], 0)),
    ("O r2", " / ".join(P(fact(O, "drivers", k), 1) for k in ("r2_deck", "r2_clearing", "r2_both"))),
    ("O clearing", P(fact(O, "clearing", "clearing_winners"), 1) + " : " + P(fact(O, "clearing", "clearing_losers"), 1)),
    ("O clearing 30-40 / <10 %", P(row(O, "clearing", 3), 1) + " / " + P(row(O, "clearing", 0), 1)),
    ("O wipes", r(fact(O, "wipes", "wipes_per_game"), 1) + ", " + r(fact(O, "wipes", "wipes_winners"), 2) + ", " + r(fact(O, "wipes", "wipes_losers"), 2)),
    ("O sapling by length", PP(lenbin(O, "SAPLING", 0, "archetypes", "archetype")) + " → " + PP(lenbin(O, "SAPLING", 4, "archetypes", "archetype"))),
    ("O Map Butterfly by length", PP(lenbin(O, "MAP_BUTTERFLY", 0)) + " → " + PP(lenbin(O, "MAP_BUTTERFLY", 4))),
    ("O Linden by length", PP(lenbin(O, "LINDEN", 0)) + " → " + PP(lenbin(O, "LINDEN", 4))),
    ("O Oak forests (card)", str(item(O, "OAK")["boards_with"])), ("O Beech presence/edge", P(item(O, "BEECH")["presence_rate"]) + " " + E(item(O, "BEECH")["winner_edge"])),
    ("O Gentian", PP(item(O, "GENTIAN")["win_lift"])),
    # --- 4p early AI
    ("F Fallow", PP(item(F, "FALLOW_DEER")["win_lift"]) + f" over {item(F, 'FALLOW_DEER')['boards_with']:,} edge " + E(item(F, "FALLOW_DEER")["winner_edge"])),
    ("F max edge card", max(st[F]["items"], key=lambda x: x["winner_edge"] or -9)["item"]),
    ("F Wolf/Roe/Red", " / ".join(PP(item(F, k)["win_lift"]) for k in ("WOLF", "ROE_DEER", "RED_DEER"))),
    ("F LT/MapB/Camberwell/Gentian", " / ".join(PP(item(F, k)["win_lift"]) for k in ("LARGE_TORTOISESHELL", "MAP_BUTTERFLY", "CAMBERWELL_BEAUTY", "GENTIAN"))),
    ("F StonePine symbol share/win", P(arch(F, "SWISS_PINE")["share"]) + " / " + P(arch(F, "SWISS_PINE")["win_rate"])),
    ("F baseline", P(st[F]["meta"]["baseline_win_rate"])),
    ("F Stone Pine card", P(item(F, "STONE_PINE")["presence_rate"]) + " " + PP(item(F, "STONE_PINE")["win_lift"]) + " " + E(item(F, "STONE_PINE")["winner_edge"])),
    ("F Steinbock/Blackberries/Digitalis", " / ".join(PP(item(F, k)["win_lift"]) for k in ("STEINBOCK", "BLACKBERRIES", "DIGITALIS"))),
    ("F sapling forests / win", P(arch(F, "SAPLING")["share"]) + " / " + P(arch(F, "SAPLING")["win_rate"], 1)), ("F saplings/player", r(out(F)["x_saplings"], 1)),
    ("F Gnat/Bechstein/BlackTrumpet/Blackthorn/Woodpecker", " / ".join(PP(item(F, k)["win_lift"]) for k in ("GNAT", "BECHSTEINS_BAT", "BLACK_TRUMPET", "BLACKTHORN", "GREAT_SPOTTED_WOODPECKER"))),
    ("F Oak/Douglas/HC symbol win", " / ".join(P(arch(F, k)["win_rate"]) + " (" + P(arch(F, k)["share"]) + ")" for k in ("OAK", "DOUGLAS_FIR", "HORSE_CHESTNUT"))),
    ("F seats", P(st[F]["seat_order"][0]["win_rate"], 1) + " : " + P(st[F]["seat_order"][-1]["win_rate"], 1)),
    ("F turns", r(st[F]["meta"]["rounds_min"], 0) + "–" + r(st[F]["meta"]["rounds_max"], 0)),
    ("F winner by length", r(st[F]["length"]["bins"][0]["winner_score"], 0) + " → " + r(st[F]["length"]["bins"][-1]["winner_score"], 0)),
    ("F r2", " / ".join(P(fact(F, "drivers", k), 1) for k in ("r2_deck", "r2_clearing", "r2_both"))),
    ("F clearing", P(fact(F, "clearing", "clearing_winners"), 1) + " : " + P(fact(F, "clearing", "clearing_losers"), 1)),
    ("F clearing groups 1/4/6/7", " / ".join(P(row(F, "clearing", k), 1) for k in (1, 4, 6, 7))),
    ("F wipes 0 / 3+", P(row(F, "wipes", 0), 1) + " / " + P(row(F, "wipes", 3), 1)),
    ("F Moss/Linden by length", PP(lenbin(F, "MOSS", 0)) + " → " + PP(lenbin(F, "MOSS", 4)) + " / " + PP(lenbin(F, "LINDEN", 0)) + " → " + PP(lenbin(F, "LINDEN", 4))),
    ("F Fallow by length", PP(lenbin(F, "FALLOW_DEER", 0)) + " → " + PP(lenbin(F, "FALLOW_DEER", 4))),
    ("F StonePine sym by length (min..max)", " .. ".join(PP(f(lenbin(F, "SWISS_PINE", b, "archetypes", "archetype") for b in range(5))) for f in (min, max))),
    ("F sapling by length (max..min)", " .. ".join(PP(f(lenbin(F, "SAPLING", b, "archetypes", "archetype") for b in range(5))) for f in (max, min))),
    # --- versus
    #("V new AI wins", P(next(x["win_rate"] for x in st[V]["results"] if x["agent"] == "model:p2-v2fix-15m"), 1)),
]
for name, val in checks:
    # a value counts as found when its numeric parts all appear in notes.json (English formatting)
    parts = [x.strip() for x in re.split(r" / | : | → | \.\. |, | over | edge |\(|\)| (?=[+−]?\d)", val) if x.strip() and re.search(r"\d", x)]
    # "+8.6 pp" must appear as such ("8.6 pp" after "+" or "(", or the bare number when it has no unit)
    # accepted forms: "+8.6 pp", "8.6 pp", "+12.7" (as in "from +12.7 to +16.8 pp"), "0.29" (as in "0.29 fewer")
    missing = [x for x in parts if not any(v in notes for v in (x, x.lstrip("+"), x.replace(" pp", ""), x.lstrip("+−").replace(" pp", "")))]
    print(("MISMATCH " if missing else "ok       ") + f"{name}: {val}" + (f"   (not in notes: {missing})" if missing else ""))
