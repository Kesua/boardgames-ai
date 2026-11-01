"""Build games/wingspan/data/cards.json from two independent card lists and check them against each other.

python games/wingspan/data/build_cards.py <wingsearch master.json> <wingsearch bonus.json> <BGG card list .xlsx>

Source A: Wingsearch app data (github.com/navarog/wingsearch, src/assets/data/master.json, bonus.json), newest
printing wording. Source B: the BoardGameGeek "Wingspan card list" spreadsheet (TawnyFrogmouth, 2020 snapshot via
github.com/coolbutuseless/wingspan, data-raw/wingspan-card-lists-20201118.xlsx, sheet "Core").
The downloads are not committed (see SOURCES.md). The script fails on any disagreement that SOURCES.md does not
resolve explicitly, so a rebuild can never silently change the data.

Power texts are NOT stored (they are the publisher's text). Each power is parsed into a structured effect by
`parse_power`; both sources' wordings must parse to the same effect. The dashboard shows an own-words description
generated from the effect (describe.py).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FOODS = ["invertebrate", "seed", "fish", "fruit", "rodent"]
HABITATS = ["forest", "grassland", "wetland"]
NESTS = ["bowl", "cavity", "ground", "platform", "star"]

# Resolved differences between the sources (rules.md W15)
OVERRIDES = {
    "American Redstart": {"egg_limit": 2},          # A=2, B=4; fan wiki: 2
}


def _norm(t: str) -> str:
    t = t.replace("“", '"').replace("”", '"').replace("�", '"').replace("’", "'")
    t = re.sub(r"\s+", " ", t.strip().lower())
    return t


def parse_power(color: str, text: str):
    """Text of either source -> structured effect dict (or None for no power)."""
    color = (color or "").lower()
    if not text or text == "nan":
        return None
    t = _norm(text)
    f = r"\[(invertebrate|seed|fish|fruit|rodent)\]"
    m = re.fullmatch(r"all players gain (?:1|a) " + f + r" from the supply\.", t)
    if m:
        return {"type": "all_gain_supply", "food": m.group(1)}
    m = re.fullmatch(r"all players lay 1 \[egg\] on any 1 \[(\w+)\] bird\. you may lay 1 \[egg\] on 1 additional \[\1\] bird\.", t)
    if m:
        return {"type": "all_lay_nest", "nest": m.group(1)}
    m = re.fullmatch(r"discard 1 \[egg\] from any of your other birds to gain (\d) \[wild\] from the supply\.", t)
    if m:
        return {"type": "egg_for_wild", "count": int(m.group(1))}
    if re.fullmatch(r"discard 1 \[egg\] to draw 2 \[card\]\.", t):
        return {"type": "egg_for_cards", "count": 2}
    m = re.fullmatch(r"discard (?:1 |a )?" + f + r" to tuck 2 \[card\] from the deck behind this bird\.", t)
    if m:
        return {"type": "food_for_tucks", "food": m.group(1), "count": 2}
    m = re.fullmatch(r"draw (\d) \[card\]\.(?: if you do, discard 1 \[card\] from your hand at the end of your turn\.)?", t)
    if m:
        return {"type": "draw", "count": int(m.group(1)), "discard_end": 1 if "discard" in t else 0}
    if re.fullmatch(r"all players draw 1 \[card\] from the deck\.", t):
        return {"type": "all_draw_deck"}
    if re.fullmatch(r"each player gains 1 \[die\] from the birdfeeder, starting with the player of your choice\.", t):
        return {"type": "each_gain_die"}
    m = re.fullmatch(r"gain 1 " + f + r"(?: or (?:1 )?" + f + r")? from the birdfeeder,? (?:\()?if (?:available|there is one)(?:\))?\.(?: you may cache it on this (?:bird|card)\.)?", t)
    if m:
        foods = [m.group(1)] + ([m.group(2)] if m.group(2) else [])
        return {"type": "gain_feeder", "foods": foods, "may_cache": "cache" in t}
    if re.fullmatch(r"gain 1 \[(?:die|wild)\] from the birdfeeder\.", t):
        return {"type": "gain_feeder", "foods": list(FOODS), "may_cache": False}
    m = re.fullmatch(r"gain (\d) " + f + r" from the supply\.", t)
    if m:
        return {"type": "gain_supply", "foods": [m.group(2)], "count": int(m.group(1)), "cache": False}
    m = re.fullmatch(r"(?:cache 1 " + f + r" from the supply on this bird|gain 1 " + f + r" from the supply and cache it on this card)\.", t)
    if m:
        return {"type": "gain_supply", "foods": [m.group(1) or m.group(2)], "count": 1, "cache": True}
    if re.fullmatch(r"if this bird is to the right of all other birds in its habitat, move it to another habitat\.", t):
        return {"type": "move"}
    m = re.fullmatch(r"lay 1 \[egg\] on (this|any) bird\.", t)
    if m:
        return {"type": "lay_egg", "target": m.group(1)}
    m = re.fullmatch(r"look at a \[card\] from the deck\. if (?:less than |<)(\d+) ?cm, tuck it behind this bird\. if not, discard it\.", t)
    if m:
        return {"type": "hunt_card", "below": int(m.group(1))}
    m = re.fullmatch(r"player\(s\) with (?:the )?fewest (?:birds in their \[(\w+)\]|\[(\w+)\] birds)(?::)? (draw 1 \[card\]|gain 1 \[die\] from birdfeeder)\.", t)
    if m:
        return {"type": "fewest_" + ("draw" if "draw" in m.group(3) else "die"), "habitat": m.group(1) or m.group(2)}
    if re.fullmatch(r"repeat 1 \[predator\] power in this habitat\.", t):
        return {"type": "repeat", "predator_only": True}
    if re.fullmatch(r"repeat a brown power on (?:one )?(?:an)?other bird in this habitat\.", t):
        return {"type": "repeat", "predator_only": False}
    m = re.fullmatch(r"roll all dice not in birdfeeder\. if any are (?:a )?" + f + r", (?:cache 1 \[\1\] from the supply on this bird|gain 1 \[\1\] and cache it on this card)\.", t)
    if m:
        return {"type": "hunt_dice", "food": m.group(1)}
    if re.fullmatch(r"trade 1 \[wild\] for any other (?:type|\[wild\]) from the supply\.", t):
        return {"type": "trade_food"}
    m = re.fullmatch(r"tuck (?:1|a) \[card\] from your hand behind this bird\. if you do, (.*)\.", t)
    if m:
        rest = m.group(1)
        if rest == "draw 1 [card]":
            then = {"type": "draw", "count": 1, "discard_end": 0}
        elif re.fullmatch(r"(?:you may )?(?:also )?lay 1 \[egg\] on this bird", rest):
            then = {"type": "lay_egg", "target": "this"}
        elif rest == "lay 1 [egg] on any bird":
            then = {"type": "lay_egg", "target": "any"}
        else:
            mm = re.fullmatch(r"gain 1 " + f + r"(?: or (?:1 )?" + f + r")? from the supply", rest)
            if not mm:
                raise ValueError(f"unparsed tuck follow-up: {text!r}")
            then = {"type": "gain_supply", "foods": [mm.group(1)] + ([mm.group(2)] if mm.group(2) else []),
                    "count": 1, "cache": False}
        return {"type": "tuck_hand", "then": then}
    # pink
    m = re.fullmatch(r"when another player plays a(?: bird in their)? \[(\w+)\](?: bird)?, (.*)\.", t)
    if m:
        rest = m.group(2)
        mm = re.fullmatch(r"gain 1 " + f + r" from the supply", rest)
        then = ({"type": "gain_supply", "foods": [mm.group(1)], "count": 1, "cache": False} if mm else
                {"type": "tuck_hand", "then": None} if rest == "tuck 1 [card] from your hand behind this bird" else None)
        if then is None:
            raise ValueError(f"unparsed pink play: {text!r}")
        return {"type": "pink_play", "habitat": m.group(1), "then": then}
    m = re.fullmatch(r'when another player takes the "lay eggs" action, (?:this bird lays|lay) 1 \[egg\] on (another bird|a bird) with a \[(\w+)\] nest\.', t)
    if m:
        return {"type": "pink_lay_eggs", "nest": m.group(2), "other": m.group(1) == "another bird"}
    if re.fullmatch(r'when another player takes the "gain food" action, if they gain any number of \[rodent\], (?:cache 1 \[rodent\] from the supply on this bird|also gain 1 \[rodent\] from the supply and cache it on this card)\.', t):
        return {"type": "pink_gain_food_rodent"}
    if re.fullmatch(r"when another player's (?:\[predator\] )?predator succeeds, gain 1 \[die\] from the birdfeeder\.|when another player's \[predator\] succeeds, gain 1 \[die\] from the birdfeeder\.", t):
        return {"type": "pink_predator"}
    # white
    if t == "draw 2 new bonus cards and keep 1.":
        return {"type": "draw_bonus"}
    if t.startswith("draw [card] equal to the number of players +1"):
        return {"type": "oystercatcher"}
    if t == "draw the 3 face-up [card] in the bird tray.":
        return {"type": "take_tray"}
    m = re.fullmatch(r"gain all " + f + r" that are in the birdfeeder\.", t)
    if m:
        return {"type": "gain_all_feeder", "food": m.group(1)}
    m = re.fullmatch(r"lay 1 \[egg\] on each of your birds with a \[(\w+)\] nest\.", t)
    if m:
        return {"type": "lay_each_nest", "nest": m.group(1)}
    m = re.fullmatch(r"play an? (?:additional|second) bird in (?:your \[(\w+)\](?: or \[(\w+)\])?|this bird's habitat)\. pay its normal cost\.", t)
    if m:
        if m.group(2) or m.group(1) is None:
            return {"type": "play_another", "habitat": "this"}
        return {"type": "play_another", "habitat": m.group(1)}
    raise ValueError(f"unparsed power ({color}): {text!r}")


# ---------------- bonus-card word lists (base game) ----------------
ANATOMIST = ["beak", "belly", "bill", "breast", "cap", "chin", "collar", "crest", "crown", "eye", "face", "head",
             "neck", "rump", "shoulder", "tail", "throat", "wing"]
CARTOGRAPHER = ["american", "atlantic", "baltimore", "california", "canada", "carolina", "chihuahuan", "eastern",
                "inca", "mississippi", "mountain", "northern", "prairie", "sandhill", "savannah", "western"]
PHOTOGRAPHER = ["ash", "black", "blue", "bronze", "brown", "cerulean", "chestnut", "ferruginous", "gold", "gray",
                "green", "indigo", "lazuli", "purple", "red", "rose", "roseate", "ruby", "ruddy", "rufous", "snowy",
                "violet", "white", "yellow"]
# word forms that count (adjective endings and compounds); anything else containing the letters does not
SUFFIXES = ["", "s", "ed", "ied", "d", "en", "ped", "ned", "ated"]
COMPOUND_PARTS = {"bluebird": ["blue"], "blackbird": ["black"], "goldeneye": ["gold", "eye"], "goldfinch": ["gold"],
                  "spoonbill": ["bill"], "waxwing": ["wing"], "yellowthroat": ["yellow", "throat"],
                  "redstart": ["red"], "whitestart": ["white"], "bobwhite": ["white"], "redhead": ["red", "head"],
                  "yellowlegs": ["yellow"], "blackcap": ["black", "cap"], "canvasback": [], "bushtit": [],
                  "bufflehead": ["head"], "redpoll": ["red"], "greenshank": ["green"], "crossbill": ["bill"],
                  "grosbeak": ["beak"], "loggerhead": ["head"], "burrowing": [], "trumpeter": []}
# Known flag differences that are not errors: expansion words in the sources' per-bird flags (rules.md D6).
EXPECTED_FLAG_DIFFS = {("Canvasback", "Anatomist", "A"), ("Canvasback", "Anatomist", "B"),
                       ("Tufted Titmouse", "Anatomist", "A")}


def name_words(name: str, words: list) -> list:
    """Listed words found in a common name (whole words with their adjective endings, or listed compounds)."""
    found = []
    for tok in re.split(r"[\s\-]+", name.lower()):
        tok = tok.replace("'s", "")
        if tok in COMPOUND_PARTS:
            found += [w for w in COMPOUND_PARTS[tok] if w in words]
            continue
        for w in words:
            stem = w[:-1] if w.endswith("y") else w
            forms = [w + s for s in SUFFIXES] + ([stem + "ied"] if w.endswith("y") else [])
            if w == "gold":
                forms.append("golden")
            if w == "bronze":
                forms.append("bronzed")
            if tok in forms:
                found.append(w)
    return sorted(set(found))


def historian(name: str) -> bool:
    return "'s " in name or name.endswith("'s")


def _equivalent(a, ea, eb) -> bool:
    """Wording changes between printings that cannot change play: "lay on a bird with a [nest]" vs "on another bird
    with a [nest]" when the power bird itself never has that nest (cowbirds have none, the cuckoo is a platform)."""
    if ea and eb and ea["type"] == eb["type"] == "pink_lay_eggs" and ea["nest"] == eb["nest"]:
        own = (a.get("Nest type") or "none").lower()
        return own not in (ea["nest"], "wild", "star")
    return False


def build(master_path, bonus_path, xlsx_path):
    import pandas as pd
    master = json.loads(Path(master_path).read_text(encoding="utf-8"))
    a_core = {b["Common name"].strip(): b for b in master if b["Set"] == "core"}
    sheet = pd.read_excel(xlsx_path, sheet_name="Core")
    sheet = sheet[sheet["Common name"].notna()]
    key = lambda s: re.sub(r"[\s\-]+", " ", s.strip().lower())
    b_core = {key(r["Common name"]): r.to_dict() for _, r in sheet.iterrows()}
    assert len(a_core) == 180 and len(b_core) == 180, (len(a_core), len(b_core))
    problems = []
    birds = []

    def num(x):
        return 0 if x is None or (isinstance(x, float) and x != x) else int(x)

    for idx, name in enumerate(sorted(a_core)):
        a = a_core[name]
        b = b_core[key(name)]
        eff_a = parse_power(a["Color"], a["Power text"])
        eff_b = parse_power(str(b["Color"]), str(b["Power text"]))
        if eff_a != eff_b and not _equivalent(a, eff_a, eff_b):
            problems.append(f"{name}: effect A {eff_a} != B {eff_b}")
        habitats = [h for h in HABITATS if a.get(h.title()) == "X"]
        cost = {f: num(a.get(f.title())) for f in FOODS}
        cost = {f: n for f, n in cost.items() if n}
        nest = (a.get("Nest type") or "none").lower()
        nest = "star" if nest == "wild" else nest
        bird = {
            "id": idx, "name": name, "scientific": a["Scientific name"], "points": num(a["Victory points"]),
            "habitats": habitats, "nest": nest if nest in NESTS else "none",
            "egg_limit": num(a["Egg limit"]), "wingspan": num(a["Wingspan"]) if a["Wingspan"] not in ("*", None) else 0,
            "food": cost, "wild": num(a.get("Wild (food)")), "alternative": a.get("/ (food cost)") == "/",
            "food_total": num(a["Total food cost"]),
            "color": (a["Color"] or "none").lower(), "predator": a.get("Predator") == "X",
            "flocking": a.get("Flocking") == "X", "swift_start": a.get("Swift Start") == "X", "power": eff_a,
            "words": {"anatomist": name_words(name, ANATOMIST), "cartographer": name_words(name, CARTOGRAPHER),
                      "photographer": name_words(name, PHOTOGRAPHER), "historian": historian(name)},
        }
        bird.update(OVERRIDES.get(name, {}))
        # field-by-field check against source B
        checks = {"points": num(b["Victory points"]), "egg_limit": num(b["Egg capacity"]),
                  "wingspan": num(b["Wingspan"]) if str(b["Wingspan"]) != "*" else 0,
                  "habitats": [h for h in HABITATS if b.get(h.title()) == "X"],
                  "food": {f: num(b.get(f.title())) for f in FOODS if num(b.get(f.title()))},
                  "wild": num(b.get("Wild (food)")), "food_total": num(b["Total food cost"]),
                  "color": str(b["Color"]).lower() if str(b["Color"]) != "nan" else "none",
                  "predator": b.get("Predator") == "X", "flocking": b.get("Flocking") == "X",
                  "alternative": str(b.get("/ (food cost)")).lower() in ("x", "/"),
                  "nest": {"wild": "star", "nan": "none"}.get(str(b["Nest type"]).lower(), str(b["Nest type"]).lower())}
        for k, v in checks.items():
            if bird[k] != v and not (name in OVERRIDES and k in OVERRIDES[name]):
                problems.append(f"{name}: {k} A {bird[k]!r} != B {v!r}")
        # bonus-card word flags: our lists vs both sources' flags (expansion words make a few differ; listed)
        for card, words_key in (("Anatomist", "anatomist"), ("Cartographer", "cartographer"),
                                ("Photographer", "photographer"), ("Historian", "historian")):
            ours = bool(bird["words"][words_key])
            for src, flag in (("A", a.get(card) == "X"), ("B", b.get(card) == "X")):
                if ours != flag and (name, card, src) not in EXPECTED_FLAG_DIFFS:
                    problems.append(f"{name}: {card} ours={ours} {src}={flag}")
        birds.append(bird)

    bonus_raw = json.loads(Path(bonus_path).read_text(encoding="utf-8"))
    return birds, [x for x in bonus_raw if x.get("Set") == "core" and "Fan Made" not in x["Bonus card"]], problems


if __name__ == "__main__":
    birds, bonus_raw, problems = build(*sys.argv[1:4])
    print(f"{len(birds)} birds, {len(bonus_raw)} bonus cards")
    for p in problems:
        print("CHECK:", p)
    out = Path(__file__).with_name("birds.json")
    out.write_text(json.dumps(birds, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", out)
