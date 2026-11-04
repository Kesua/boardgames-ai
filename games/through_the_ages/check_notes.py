"""Recompute every number cited in games/through_the_ages/notes.json from the current stats.json files (and the two
models' strength cards), rounded the way the site rounds, and print a MISMATCH line for each one the notes do not
contain, then check the claims in the text that depend on the data. Exit code 1 on any mismatch.
Run from the repository root: python games/through_the_ages/check_notes.py"""
import json, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
G = R / "games" / "through_the_ages"
E2, E4 = "p2-29m-mirror", "p4-24m-mirror"
ST = {e: json.loads((G / "experiments" / e / "stats.json").read_text(encoding="utf-8")) for e in (E2, E4)}
MODEL = {e: json.loads((G / "models" / e.rsplit("-", 1)[0] / "model.json").read_text(encoding="utf-8")) for e in (E2, E4)}
sys.path.insert(0, str(R))
from games.through_the_ages import SPEC  # noqa: E402
KIND = {k: v["kind"] for k, v in SPEC.catalog()["items"].items()}


def r(v, d):  # JS Intl rounding (half away from zero)
    q = Decimal(repr(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    return f"{q:,}" if d else f"{int(q):,}"


def fmt(v, kind):
    """n0/n1 number, p/p1 percent, pp percentage points (signed)."""
    sign = lambda x: "+" if x > 0 else "−" if x < 0 else ""
    return {"n0": lambda: r(v, 0), "n1": lambda: r(v, 1), "p": lambda: r(v * 100, 0) + " %",
            "p1": lambda: r(v * 100, 1) + " %", "pp": lambda: sign(v) + r(abs(v * 100), 1) + " pp"}[kind]()


item = lambda e, k: next(x for x in ST[e]["items"] if x["item"] == k)
tag = lambda e, k: next(x for x in ST[e]["tags"]["kind"] if x["value"] == k)
out = lambda e: ST[e]["style"]["outcome"][0]
common = lambda e: [x for x in ST[e]["items"] if x["presence_rate"] >= 0.05]
clear = lambda x: abs(x["win_lift"]) > 2 * x["win_lift_se"]
greedy = lambda e: next(g["win"] for g in MODEL[e]["strength"]["games"] if g["opponent"] == "greedy")


def values(e):
    """name -> (value, format) for every number the notes cite from experiment e."""
    it = lambda k: item(e, k)
    pp = lambda k: (it(k)["win_lift"], "pp")
    m, so, o, bins = ST[e]["meta"], ST[e]["seat_order"], out(e), ST[e]["length"]["bins"]
    v = {k: pp(k) for k in ("despotism_a", "democracy_iii", "theocracy_i", "johann_sebastian_bach_ii",
                            "himeji_castle_i", "eiffel_tower_ii", "louvre_museum_ii", "colosseum_a", "suez_canal_ii",
                            "printing_press_i", "historic_territory_ii", "vast_territory_i", "strategic_territory_ii",
                            "military_theory_iii", "drama_i")}
    v.update({"democracy_s": (it("democracy_iii")["presence_rate"], "p"), "theater": (tag(e, "theater")["win_lift"], "pp"),
              "theater_s": (tag(e, "theater")["presence_rate"], "p"), "drama_ppc": (it("drama_i")["points_per_copy"], "n1"),
              "science": (o["x_science_rating"], "n1"), "prod": (o["b_production"], "n1"), "events": (o["b_events"], "n1"),
              "military": (o["b_military"], "n1"), "score": (m["mean_score"], "n1"),
              "s0": (so[0]["win_rate"], "p1"), "sl": (so[-1]["win_rate"], "p1"), "base": (m["baseline_win_rate"], "p1"),
              "rmin": (m["rounds_min"], "n0"), "rmax": (m["rounds_max"], "n0"),
              "w0": (bins[0]["winner_score"], "n0"), "w4": (bins[-1]["winner_score"], "n0"),
              "greedy": (greedy(e), "p1")})
    if e == E2:
        v.update({k: pp(k) for k in ("republic_ii", "communism_iii", "monarchy_i", "fundamentalism_iii",
                                     "isaac_newton_ii", "bill_gates_iii", "johannes_gutenberg_i", "pyramids_a",
                                     "forbidden_city_i", "taj_mahal_i", "statue_of_liberty_ii", "great_wall_i",
                                     "inhabited_territory_i", "movies_iii", "opera_ii", "alfred_nobel_ii", "strategy_ii",
                                     "navigation_ii")})
        v.update({"library": (tag(e, "library")["win_lift"], "pp"),
                  "theocracy_s": (it("theocracy_i")["presence_rate"], "p"),
                  "fundamentalism_s": (it("fundamentalism_iii")["presence_rate"], "p"),
                  "despotism_s": (it("despotism_a")["presence_rate"], "p"),
                  "himeji_s": (it("himeji_castle_i")["presence_rate"], "p"),
                  "himeji_ppc": (it("himeji_castle_i")["points_per_copy"], "n1"),
                  "taj_ppc": (it("taj_mahal_i")["points_per_copy"], "n1"),
                  "bach_ppc": (it("johann_sebastian_bach_ii")["points_per_copy"], "n1"),
                  "historic_ppc": (it("historic_territory_ii")["points_per_copy"], "n1")})
    else:
        v.update({k: pp(k) for k in ("michelangelo_i", "nelson_mandela_iii", "acropolis_a", "computers_iii",
                                     "civil_service_iii", "international_red_cross_iii", "taj_mahal_i",
                                     "mechanized_agriculture_iii", "satellites_iii", "great_wall_i", "leonardo_da_vinci_i",
                                     "constitutional_monarchy_ii", "republic_ii", "monarchy_i", "forbidden_city_i",
                                     "hanging_gardens_a", "jan_zizka_i", "napoleon_bonaparte_ii")})
        v.update({"michelangelo_ppc": (it("michelangelo_i")["points_per_copy"], "n1"),
                  "taj_ppc": (it("taj_mahal_i")["points_per_copy"], "n1"),
                  "pp_s": (it("printing_press_i")["presence_rate"], "p")})
    return v


def claims(e):
    it = lambda k: item(e, k)
    top = sorted(common(e), key=lambda x: -x["win_lift"])
    pos = lambda *ks: all(clear(it(k)) and it(k)["win_lift"] > 0 for k in ks)
    neg = lambda *ks: all(clear(it(k)) and it(k)["win_lift"] < 0 for k in ks)
    govs = [x for x in ST[e]["items"] if KIND[x["item"]] == "government" and x["presence_rate"] >= 0.05]
    base = [("Despotism clearly goes with losing", neg("despotism_a")),
            ("Democracy and Theocracy clearly go with winning", pos("democracy_iii", "theocracy_i")),
            ("Bach, Eiffel Tower, Louvre, Historic Territory (II), Military Theory clearly go with winning",
             pos("johann_sebastian_bach_ii", "eiffel_tower_ii", "louvre_museum_ii", "historic_territory_ii", "military_theory_iii")),
            ("Colosseum and Suez Canal clearly go with losing", neg("colosseum_a", "suez_canal_ii")),
            ("theaters clearly go with winning", tag(e, "theater")["win_lift"] > 2 * tag(e, "theater")["win_lift_se"]),
            ("first and last seat within 2 standard errors of the average player",
             all(abs(ST[e]["seat_order"][s]["win_rate"] - ST[e]["meta"]["baseline_win_rate"]) <= 2 * (
                 ST[e]["seat_order"][s]["win_rate"] * (1 - ST[e]["seat_order"][s]["win_rate"]) / ST[e]["seat_order"][s]["seats"]) ** 0.5
                 for s in (0, -1))),
            ("events give most of the points beyond production", out(e)["b_events"] > (out(e)["score"] - out(e)["b_production"]) / 2),
            ("the winner's score rises with every length bin",
             all(a["winner_score"] < b["winner_score"] for a, b in zip(ST[e]["length"]["bins"], ST[e]["length"]["bins"][1:])))]
    if e == E2:
        wonders = [x for x in common(e) if KIND[x["item"]] == "wonder"]
        base += [("Himeji Castle has the largest win-rate difference of the cards in >= 5 % of civilizations", top[0]["item"] == "himeji_castle_i"),
                 ("Theocracy, Fundamentalism, Vast (I), Strategic (II), Inhabited (I) Territory, Movies, Opera, Nobel, Strategy, Navigation, Statue of Liberty, Great Wall clearly win",
                  pos("theocracy_i", "fundamentalism_iii", "vast_territory_i", "strategic_territory_ii", "inhabited_territory_i",
                      "movies_iii", "opera_ii", "alfred_nobel_ii", "strategy_ii", "navigation_ii", "statue_of_liberty_ii", "great_wall_i")),
                 ("Republic, Communism, Monarchy, Printing Press, Newton, Gates, Gutenberg, Pyramids, Forbidden City clearly lose",
                  neg("republic_ii", "communism_iii", "monarchy_i", "printing_press_i", "isaac_newton_ii", "bill_gates_iii",
                      "johannes_gutenberg_i", "pyramids_a", "forbidden_city_i")),
                 ("libraries clearly go with losing", tag(e, "library")["win_lift"] < -2 * tag(e, "library")["win_lift_se"]),
                 ("Taj Mahal has the most points per copy of the common wonders", max(wonders, key=lambda x: x["points_per_copy"])["item"] == "taj_mahal_i"),
                 ("Taj Mahal does not clearly go with winning", not (clear(it("taj_mahal_i")) and it("taj_mahal_i")["win_lift"] > 0))]
    else:
        others = [g for g in govs if g["item"] not in ("democracy_iii", "theocracy_i")]
        base += [("Michelangelo has the largest win-rate difference of the cards in >= 5 % of civilizations", top[0]["item"] == "michelangelo_i"),
                 ("every other final government goes with losing or does not clearly differ",
                  all(g["win_lift"] < 0 or not clear(g) for g in others)),
                 ("Michelangelo, Mandela, Acropolis, Red Cross, Himeji, Taj Mahal, Printing Press, Computers, Civil Service, Mech. Agriculture, Satellites, Vast (I), Strategic (II), Drama clearly win",
                  pos("michelangelo_i", "nelson_mandela_iii", "acropolis_a", "international_red_cross_iii", "himeji_castle_i",
                      "taj_mahal_i", "printing_press_i", "computers_iii", "civil_service_iii", "mechanized_agriculture_iii",
                      "satellites_iii", "vast_territory_i", "strategic_territory_ii", "drama_i")),
                 ("Great Wall, Leonardo, Constitutional Monarchy, Republic, Monarchy, Forbidden City, Hanging Gardens, Zizka, Napoleon clearly lose",
                  neg("great_wall_i", "leonardo_da_vinci_i", "constitutional_monarchy_ii", "republic_ii", "monarchy_i",
                      "forbidden_city_i", "hanging_gardens_a", "jan_zizka_i", "napoleon_bonaparte_ii"))]
    return base


def main():
    notes = json.loads((G / "notes.json").read_text(encoding="utf-8"))
    bad = 0
    for e in (E2, E4):
        V = values(e)
        # an experiment's numbers may appear in its own notes, in the findings or in the known limits
        text = json.dumps([notes["experiments"][e]["en"]] + [f["en"] for f in notes["findings"]] + [notes["limits"]["en"]], ensure_ascii=False)
        for name in V:
            s = fmt(*V[name])
            ok = s in text
            bad += not ok
            print(("ok       " if ok else "MISMATCH ") + f"{e} {name}: {s}")
        for name, ok in claims(e):
            bad += not ok
            print(("ok       " if ok else "MISMATCH ") + f"{e} claim: {name}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
