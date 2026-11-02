"""Recompute every number cited in games/forest_shuffle/notes.json from the current stats.json files, rounded the way
the site rounds, and print a MISMATCH line for each one the notes do not contain (English and Czech text), then check
the claims in the text that depend on the data. Exit code 1 on any mismatch.
Run from the repository root: python games/forest_shuffle/check_notes.py"""
import json, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
G = R / "games" / "forest_shuffle"
E2, E4 = "p2-v2fix-15m-mirror", "p4-v2fix-9m-mirror"
ST = {e: json.loads((G / "experiments" / e / "stats.json").read_text(encoding="utf-8")) for e in (E2, E4)}
DATA = json.loads((G / "data" / "cards.json").read_text(encoding="utf-8"))
CARDS = DATA["cards"]
EXPANSION = {k: sp["expansion"] for k, sp in DATA["species"].items()}


def r(v, d, cs):  # JS Intl rounding (half away from zero); Czech uses a decimal comma and a space for thousands
    q = Decimal(repr(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    s = f"{q:,}" if d else f"{int(q):,}"
    return s.replace(",", " ").replace(".", ",") if cs else s


def fmt(v, kind, cs):
    """n0/n1 number, i integer, p/p1 percent, pp percentage points (signed), e/ea copies (signed / without sign)."""
    sign = lambda x: "+" if x > 0 else "−" if x < 0 else ""
    return {"n0": lambda: r(v, 0, cs), "n1": lambda: r(v, 1, cs), "i": lambda: r(v, 0, cs),
            "p": lambda: r(v * 100, 0, cs) + " %", "p1": lambda: r(v * 100, 1, cs) + " %",
            "pp": lambda: sign(v) + r(abs(v * 100), 1, cs) + (" p. b." if cs else " pp"),
            "e": lambda: sign(v) + r(abs(v), 2, cs), "ea": lambda: r(abs(v), 2, cs)}[kind]()


item = lambda e, k: next(x for x in ST[e]["items"] if x["item"] == k)
arch = lambda e, k: next(x for x in ST[e]["archetypes"] if x["archetype"] == k)
fact = lambda e, sec, lab: next(f["value"] for f in ST[e]["game"][sec]["facts"] if f["label"] == lab)
out = lambda e: ST[e]["style"]["outcome"][0]
act = lambda e, a: next(x["share"] for x in ST[e]["style"]["action_mix"] if x["action"] == a)
common = lambda e: [x for x in ST[e]["items"] if x["presence_rate"] >= 0.05]
clear = lambda x: abs(x["win_lift"]) > 2 * x["win_lift_se"]
lifts = lambda e: sorted(common(e), key=lambda x: -x["win_lift"])
seat_clear = lambda e, s: abs(ST[e]["seat_order"][s]["win_rate"] - ST[e]["meta"]["baseline_win_rate"]) > 2 * (
    ST[e]["seat_order"][s]["win_rate"] * (1 - ST[e]["seat_order"][s]["win_rate"]) / ST[e]["seat_order"][s]["seats"]) ** 0.5


def fate(e, species, what):
    """How often the tree cards of a species were played / played as a sapling / paid away in experiment e."""
    rows = {c["card"]: c for c in ST[e]["cards"]}
    return sum(rows.get(c["id"], {}).get(what, 0) for c in CARDS if c["layout"] == "WOODY_PLANT" and c["species"] == species)


BUTTERFLY = {"GENTIAN", "STINGING_NETTLE", "PHOEBUS_APOLLO", "SILVER_WASHED_FRITILLARY", "MAP_BUTTERFLY",
             "CAMBERWELL_BEAUTY", "LARGE_TORTOISESHELL", "PEACOCK_BUTTERFLY", "PURPLE_EMPEROR"}
TREES = ("LINDEN", "OAK", "SILVER_FIR", "BIRCH", "BEECH", "SYCAMORE", "DOUGLAS_FIR", "HORSE_CHESTNUT",
         "EUROPEAN_LARCH", "STONE_PINE")


def values(e):
    """name -> (value, format) for every number the notes cite from experiment e."""
    it = lambda k: item(e, k)
    pp = lambda k: (it(k)["win_lift"], "pp")
    m, so = ST[e]["meta"], ST[e]["seat_order"]
    v = {"gen": pp("GENTIAN"), "fd": pp("FALLOW_DEER"), "fd_ppc": (it("FALLOW_DEER")["points_per_copy"], "n1"),
         "fd_e": (it("FALLOW_DEER")["winner_edge"], "ea"), "fd_es": (it("FALLOW_DEER")["winner_edge"], "e"),
         "stb": pp("STEINBOCK"), "rav": pp("COMMON_RAVEN"), "edw": pp("EDELWEISS"), "df": pp("DOUGLAS_FIR"),
         "be": pp("BEECH"), "be_s": (it("BEECH")["presence_rate"], "p"), "rac": pp("RACCOON"), "syc": pp("SYCAMORE"),
         "wp": pp("GREAT_SPOTTED_WOODPECKER"),
         "sp_s": (arch(e, "SWISS_PINE")["share"], "p"), "sp_w": (arch(e, "SWISS_PINE")["win_rate"], "p1"),
         "oak_pl": (fate(e, "OAK", "played"), "i"), "hc_pl": (fate(e, "HORSE_CHESTNUT", "played"), "i"),
         "sap": (out(e)["x_saplings"], "n1"), "games": (m["games"], "i"),
         "s0": (so[0]["win_rate"], "p1"), "sl": (so[-1]["win_rate"], "p1"), "base": (m["baseline_win_rate"], "p1"),
         "tmin": (m["rounds_min"], "n0"), "tmax": (m["rounds_max"], "n0"),
         "w0": (ST[e]["length"]["bins"][0]["winner_score"], "n0"), "w4": (ST[e]["length"]["bins"][-1]["winner_score"], "n0"),
         "r2d": (fact(e, "drivers", "r2_deck"), "p1"),
         "cw": (fact(e, "clearing", "clearing_winners"), "p1"), "cl": (fact(e, "clearing", "clearing_losers"), "p1"),
         "ct": (act(e, "DRAW_CLEARING"), "p"), "wipes": (fact(e, "wipes", "wipes_per_game"), "n1"),
         "wc": (it("EUROPEAN_WILDCAT")["presence_rate"], "p1")}
    if e == E2:
        v.update({"gen_s": (it("GENTIAN")["presence_rate"], "p"), "gen_ppc": (it("GENTIAN")["points_per_copy"], "n1"),
                  "net": pp("STINGING_NETTLE"), "pa": pp("PHOEBUS_APOLLO"), "swf": pp("SILVER_WASHED_FRITILLARY"),
                  "mb": pp("MAP_BUTTERFLY"), "cb": pp("CAMBERWELL_BEAUTY"), "newt": pp("ALPINE_NEWT"),
                  "eb": pp("EUROPEAN_BISON"), "wolf": pp("WOLF"),
                  "bm": pp("BEECH_MARTEN"), "bm_s": (it("BEECH_MARTEN")["presence_rate"], "p"),
                  "bm_ppb": (it("BEECH_MARTEN")["points_per_board"], "n1"), "bm_e": (it("BEECH_MARTEN")["winner_edge"], "ea"),
                  "spc_s": (it("STONE_PINE")["presence_rate"], "p"),
                  "be_ea": (it("BEECH")["winner_edge"], "ea"), "be_ppc": (it("BEECH")["points_per_copy"], "n1"),
                  "bes_s": (arch(e, "BEECH")["share"], "p"), "bes_w": (arch(e, "BEECH")["win_rate"], "p"),
                  "jay": pp("EURASIAN_JAY"), "owl": pp("TAWNY_OWL"), "lar": pp("EUROPEAN_LARCH"),
                  "rac_s": (it("RACCOON")["presence_rate"], "p"), "rac_e": (it("RACCOON")["winner_edge"], "ea"),
                  "sf_pl": (fate(e, "SILVER_FIR", "played"), "i"), "li_pl": (fate(e, "LINDEN", "played"), "i"),
                  "pay4": (sum(fate(e, k, "paid") for k in ("SILVER_FIR", "OAK", "HORSE_CHESTNUT", "LINDEN")), "i"),
                  "sp_pl": (fate(e, "STONE_PINE", "played"), "i"), "be_pl": (fate(e, "BEECH", "played"), "i")})
    else:
        clr = {x["group"]: x["win_rate"] for x in ST[e]["game"]["clearing"]["rows"]}
        v.update({"stb_s": (it("STEINBOCK")["presence_rate"], "p"), "cha": pp("CHAMOIS"), "bb": pp("BLACKBERRIES"),
                  "pt": pp("POND_TURTLE"), "gen_s": (it("GENTIAN")["presence_rate"], "p"),
                  "bf_max": (max(it(k)["presence_rate"] for k in BUTTERFLY - {"GENTIAN", "STINGING_NETTLE"}), "p"),
                  "c0": (clr[0], "p1"), "c3": (clr[3], "p1"),
                  "pay2": (sum(fate(e, k, "paid") for k in ("OAK", "HORSE_CHESTNUT")), "i")})
    return v


def claims(e):
    it = lambda k: item(e, k)
    top = lifts(e)
    pos = lambda *ks: all(clear(it(k)) and it(k)["win_lift"] > 0 for k in ks)
    neg = lambda *ks: all(clear(it(k)) and it(k)["win_lift"] < 0 for k in ks)
    rare = lambda *ks: all(fate(e, k, "played") < 0.01 * (fate(e, k, "played") + fate(e, k, "paid") + fate(e, k, "as_sapling")) for k in ks)
    best_arch = max((a for a in ST[e]["archetypes"] if a["share"] >= 0.02), key=lambda a: a["win_rate"])["archetype"]
    base = [("Stone Pine symbol forests clearly win more", arch(e, "SWISS_PINE")["win_lift"] > 2 * arch(e, "SWISS_PINE")["win_lift_se"]),
            ("Stone Pine symbol forests have the highest win rate of the forest types in >= 2 % of forests", best_arch == "SWISS_PINE"),
            ("Fallow Deer clearly goes with winning", pos("FALLOW_DEER")),
            ("Beech, Raccoon, Sycamore, Douglas Fir and Great Spotted Woodpecker clearly go with losing",
             neg("BEECH", "RACCOON", "SYCAMORE", "DOUGLAS_FIR", "GREAT_SPOTTED_WOODPECKER")),
            ("Oak and Horse Chestnut are planted in under 1 % of their uses", rare("OAK", "HORSE_CHESTNUT")),
            ("first seat clearly above the average player",
             seat_clear(e, 0) and ST[e]["seat_order"][0]["win_rate"] > ST[e]["meta"]["baseline_win_rate"])]
    if e == E2:
        base += [("Gentian has the largest win-rate difference of the cards in >= 5 % of forests", top[0]["item"] == "GENTIAN"),
                 ("6 of the 12 cards that go most with winning are butterflies or score per butterfly",
                  sum(x["item"] in BUTTERFLY for x in top[:12]) == 6),
                 ("Alpine Newt is among the top 12", "ALPINE_NEWT" in [x["item"] for x in top[:12]]),
                 ("all butterfly cards cited clearly go with winning",
                  pos("GENTIAN", "STINGING_NETTLE", "PHOEBUS_APOLLO", "SILVER_WASHED_FRITILLARY", "MAP_BUTTERFLY", "CAMBERWELL_BEAUTY", "ALPINE_NEWT")),
                 ("European Bison, Steinbock, Wolf, Beech Marten clearly go with winning", pos("EUROPEAN_BISON", "STEINBOCK", "WOLF", "BEECH_MARTEN")),
                 ("Beech Marten brings the most points per forest of any card",
                  max(ST[e]["items"], key=lambda x: x["points_per_board"])["item"] == "BEECH_MARTEN"),
                 ("Beech Marten has the largest winner edge", max(ST[e]["items"], key=lambda x: x["winner_edge"] or -9)["item"] == "BEECH_MARTEN"),
                 ("Beech has the largest shortfall (most negative winner edge)", min(ST[e]["items"], key=lambda x: x["winner_edge"] or 9)["item"] == "BEECH"),
                 ("Stone Pine is the tree in most forests",
                  max((x for x in ST[e]["items"] if x["item"] in TREES), key=lambda x: x["presence_rate"])["item"] == "STONE_PINE"),
                 ("Stone Pine and Beech are the two trees planted most", sorted(TREES, key=lambda k: -fate(e, k, "played"))[:2] == ["STONE_PINE", "BEECH"]),
                 ("Silver Fir and Linden are planted in under 1 % of their uses", rare("SILVER_FIR", "LINDEN")),
                 ("Beech symbol forests clearly win less", arch(e, "BEECH")["win_lift"] < -2 * arch(e, "BEECH")["win_lift_se"]),
                 ("every fixed-point card cited clearly goes with losing (Common Raven and Edelweiss too)",
                  neg("EURASIAN_JAY", "COMMON_RAVEN", "TAWNY_OWL", "DOUGLAS_FIR", "EUROPEAN_LARCH", "EDELWEISS")),
                 ("clearing share of winners and losers within 1 point",
                  abs(fact(e, "clearing", "clearing_winners") - fact(e, "clearing", "clearing_losers")) < 0.01)]
    else:
        clr = {x["group"]: x for x in ST[e]["game"]["clearing"]["rows"]}
        p0, p3 = clr[0]["win_rate"], clr[3]["win_rate"]
        so = [x["win_rate"] for x in ST[e]["seat_order"]]
        base += [("Steinbock has the largest win-rate difference of the cards in >= 5 % of forests", top[0]["item"] == "STEINBOCK"),
                 ("Fallow Deer has the largest winner edge", max(ST[e]["items"], key=lambda x: x["winner_edge"] or -9)["item"] == "FALLOW_DEER"),
                 ("5 of the 7 cards that go most with winning are Alpine cards", sum(EXPANSION[x["item"]] == "alpine" for x in top[:7]) == 5),
                 ("Steinbock, Common Raven, Edelweiss, Chamois and Blackberries clearly go with winning",
                  pos("STEINBOCK", "COMMON_RAVEN", "EDELWEISS", "CHAMOIS", "BLACKBERRIES")),
                 ("Pond Turtle clearly goes with losing", neg("POND_TURTLE")),
                 ("Gentian does not clearly differ from the average", not clear(it("GENTIAN"))),
                 ("every butterfly is in under 5 % of forests",
                  max(it(k)["presence_rate"] for k in BUTTERFLY - {"GENTIAN", "STINGING_NETTLE"}) < 0.05),
                 ("winners take a smaller share of their draws from the clearing",
                  fact(e, "clearing", "clearing_winners") < fact(e, "clearing", "clearing_losers")),
                 ("under 10 % of draws from the clearing clearly wins more than 30-40 %",
                  p0 - p3 > 2 * (p0 * (1 - p0) / clr[0]["seats"] + p3 * (1 - p3) / clr[3]["seats"]) ** 0.5),
                 ("the win rate falls with every seat", all(a > b for a, b in zip(so, so[1:]))),
                 ("last seat clearly below the average player", seat_clear(e, len(so) - 1) and so[-1] < ST[e]["meta"]["baseline_win_rate"])]
    return base


def main():
    notes = json.loads((G / "notes.json").read_text(encoding="utf-8"))
    bad = 0
    for e, n in ((E2, "n2"), (E4, "n4")):
        V = values(e)
        for lang in ("en", "cs"):
            cs = lang == "cs"
            # an experiment's numbers may appear in its own notes, in the findings or in the known limits
            text = json.dumps([notes["experiments"][e][lang]] + [f[lang] for f in notes["findings"]] + [notes["limits"][lang]], ensure_ascii=False)
            for name in V:
                s = fmt(*V[name], cs)
                ok = s in text
                bad += not ok
                print(("ok       " if ok else "MISMATCH ") + f"{e} {lang} {name}: {s}")
        for name, ok in claims(e):
            bad += not ok
            print(("ok       " if ok else "MISMATCH ") + f"{e} claim: {name}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
