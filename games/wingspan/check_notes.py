"""Recompute every number cited in games/wingspan/notes.json from the current stats.json, rounded the way the site
rounds, and print a MISMATCH line for each one the notes do not contain (English and Czech text).
Run from the repository root: python games/wingspan/check_notes.py"""
import json, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
E = "p2-28m-mirror"
st = json.loads((R / "games" / "wingspan" / "experiments" / E / "stats.json").read_text(encoding="utf-8"))
notes = json.loads((R / "games" / "wingspan" / "notes.json").read_text(encoding="utf-8"))
text = {lang: json.dumps([notes["experiments"][E][lang]] + [f[lang] for f in notes["findings"]], ensure_ascii=False)
        for lang in ("en", "cs")}


def r(v, d, cs):  # JS Intl rounding (half away from zero); Czech uses a decimal comma
    q = Decimal(repr(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    s = f"{q:,}" if d else f"{int(q):,}"
    return s.replace(",", " ").replace(".", ",") if cs else s


item = lambda k: next(x for x in st["items"] if x["item"] == k)
arch = lambda k: next(x for x in st["archetypes"] if x["archetype"] == k)
G = st["game"]
mix = {x["category"]: x for x in G["score_mix"]["rows"]}
goals = G["goals"]["rows"]
act = {(x["round"], x["who"]): x for x in G["actions"]["rows"]}
bonus = {x["card"]: x for x in G["bonus"]["rows"]}
fact = lambda sec, lab: next(f["value"] for f in G[sec]["facts"] if f["label"] == lab)
birds = {x["birds"]: x for x in G["birds"]["rows"]}
seat = st["seat_order"]
# (name, value, kind): kind n = number with 1 decimal, p = percent, p1 = percent with 1 decimal, pp = percentage points
checks = [("goals winners", mix["goals"]["winners"], "n"), ("goals others", mix["goals"]["others"], "n"),
          ("goals round 1", goals[0]["winners"], "n"), ("goals round 1 others", goals[0]["others"], "n"),
          ("goals round 4", goals[3]["winners"], "n"), ("goals round 4 others", goals[3]["others"], "n"),
          ("eggs winners", mix["eggs"]["winners"], "n"), ("eggs others", mix["eggs"]["others"], "n"),
          ("tucked winners", mix["tucked"]["winners"], "n"), ("tucked others", mix["tucked"]["others"], "n"),
          ("bird points winners", mix["birds"]["winners"], "n"), ("bird points others", mix["birds"]["others"], "n"),
          ("bonus points winners", mix["bonus"]["winners"], "n"), ("bonus points others", mix["bonus"]["others"], "n"),
          ("Barn Swallow", item("BARN_SWALLOW")["win_lift"], "pp"), ("Barn Swallow presence", item("BARN_SWALLOW")["presence_rate"], "p"),
          ("Purple Martin", item("PURPLE_MARTIN")["win_lift"], "pp"), ("American Robin", item("AMERICAN_ROBIN")["win_lift"], "pp"),
          ("Bushtit", item("BUSHTIT")["win_lift"], "pp"),
          ("birds winners", fact("birds", "birds_winners"), "n"), ("birds others", fact("birds", "birds_others"), "n"),
          ("wins with 6 birds", birds[6]["win_rate"], "p"), ("wins with 8 birds", birds[8]["win_rate"], "p"),
          ("wins with 10 birds", birds[10]["win_rate"], "p"),
          ("Falconer", bonus["Falconer"]["win_lift"], "pp"), ("Falconer holders", bonus["Falconer"]["holders"], "i"),
          ("Omnivore Expert", bonus["Omnivore Expert"]["win_lift"], "pp"), ("Enclosure Builder", bonus["Enclosure Builder"]["win_lift"], "pp"),
          ("Passerine Specialist", bonus["Passerine Specialist"]["win_lift"], "pp"),
          ("Peregrine Falcon", item("PEREGRINE_FALCON")["win_lift"], "pp"), ("Cooper's Hawk", item("COOPER_S_HAWK")["win_lift"], "pp"), ("Omnivore holders", bonus["Omnivore Expert"]["holders"], "i"),
          ("forest mats share", arch("forest")["share"], "p"), ("forest mats wins", arch("forest")["win_rate"], "p"),
          ("forest mats difference", arch("forest")["win_lift"], "pp"),
          ("grassland mats share", arch("grassland")["share"], "p"), ("grassland mats wins", arch("grassland")["win_rate"], "p"),
          ("last round food winners", act[(4, "winners")]["GAIN_FOOD"], "p"), ("last round food others", act[(4, "others")]["GAIN_FOOD"], "p"),
          ("last round eggs winners", act[(4, "winners")]["LAY_EGGS"], "p"), ("last round eggs others", act[(4, "others")]["LAY_EGGS"], "p"),
          ("first seat wins", seat[0]["win_rate"], "p1"), ("second seat wins", seat[1]["win_rate"], "p1")]
# claims in the text that depend on the data
lifts = sorted((x for x in st["items"] if x["presence_rate"] >= 0.05), key=lambda x: -x["win_lift"])
claims = [("Barn Swallow has the largest win-rate difference of birds on >= 5 % of mats", lifts[0]["item"] == "BARN_SWALLOW"),
          ("round goals are the biggest gap of any scoring category",
           max(mix, key=lambda c: mix[c]["winners"] - mix[c]["others"]) == "goals"),
          ("winners lead in every round", all(g["winners"] > g["others"] for g in goals)),
          ("Falconer and Omnivore Expert are clear (> 2 standard errors)",
           all(bonus[c]["win_lift"] > 2 * bonus[c]["win_lift_se"] for c in ("Falconer", "Omnivore Expert"))),
          ("Enclosure Builder and Passerine Specialist clearly lose (> 2 standard errors)",
           all(bonus[c]["win_lift"] < -2 * bonus[c]["win_lift_se"] for c in ("Enclosure Builder", "Passerine Specialist"))),
          ("4 of the top 10 birds tuck from the hand (Barn Swallow, Purple Martin, American Robin, Bushtit)",
           sorted(x["item"] for x in lifts[:10] if x["item"] in ("BARN_SWALLOW", "PURPLE_MARTIN", "AMERICAN_ROBIN", "BUSHTIT")) ==
           ["AMERICAN_ROBIN", "BARN_SWALLOW", "BUSHTIT", "PURPLE_MARTIN"]),
          ("grassland and wetland mats do not clearly differ",
           abs(arch("grassland")["win_rate"] - arch("wetland")["win_rate"]) < 2 * (arch("grassland")["win_lift_se"] ** 2 + arch("wetland")["win_lift_se"] ** 2) ** 0.5),
          ("forest mats clearly lose (> 2 standard errors)", arch("forest")["win_lift"] < -2 * arch("forest")["win_lift_se"])]
bad = 0
for lang in ("en", "cs"):
    cs = lang == "cs"
    for name, v, kind in checks:
        s = {"n": lambda: r(v, 1, cs), "i": lambda: r(v, 0, cs), "p": lambda: r(v * 100, 0, cs) + " %",
             "p1": lambda: r(v * 100, 1, cs) + " %",
             "pp": lambda: ("+" if v > 0 else "−" if v < 0 else "") + r(abs(v * 100), 1, cs) + (" p. b." if cs else " pp")}[kind]()
        ok = s in text[lang]
        bad += not ok
        print(("ok       " if ok else "MISMATCH ") + f"{lang} {name}: {s}")
for name, ok in claims:
    bad += not ok
    print(("ok       " if ok else "MISMATCH ") + f"claim: {name}")
sys.exit(1 if bad else 0)
