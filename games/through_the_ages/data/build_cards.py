"""Build games/through_the_ages/data/cards.json from independent card lists and check them against each other.

python games/through_the_ages/data/build_cards.py [inbox dir]   (default: inbox/through_the_ages)

Sources (downloads and extractions live in the git-ignored inbox, see SOURCES.md):
- A: Board Game Arena's typed card data, `bga/material.inc.php` (github.com/srussking/throughtheages @ 45b1c03).
- B: the printed base cards read from the card pictures `bga/cards_big.jpg` by a separate agent who never saw A,
  `list_B_base.json` (format: scratch FORMAT.md, copied into SOURCES.md).
- E: the expansion's new and rebalanced cards, `list_expansion.json`, gathered from the official expansion rulebook,
  CGE's designer notes pages and the fan wiki (sources per card inside the file).
Copy counts per player count come from A (B's pictures do not show them), checked against the rulebooks' totals.

The script fails on any disagreement between A and B that EXPECTED_DIFFS does not resolve with a reason, so a rebuild
can never silently change the data. Card texts are never stored; abilities are structured effects (card_effects.py).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from card_effects import BASE as BASE_EFFECTS  # noqa: E402
from php_array import read_assignment  # noqa: E402

AGES = ["A", "I", "II", "III"]
NUMERIC = ["science_cost", "revolution_cost", "resource_cost", "stage_costs", "urban_limit",
           "military_action_cost"]

# BGA spellings -> printed names (B)
NAME_FIXES = {
    "Calvarymen": "Cavalrymen",
    "Loss of Sovereignity": "Loss of Sovereignty",
    "Maximillien Robespierre": "Maximilien Robespierre",
    "J.S. Bach": "J. S. Bach",
    "Defense / Colonization": "Military Bonus",
    "Leonardo Da Vinci": "Leonardo da Vinci",
}
# B names unnamed bonus cards by their values
B_NAME_FIXES = {"Military bonus 2 / 1": "Military Bonus", "Military bonus 4 / 2": "Military Bonus",
                "Military bonus 6 / 3": "Military Bonus"}
# fan wiki (digital edition) names -> printed names
WIKI_ALIASES = {"Stock Pile": "Stockpile", "Development of Civil Life": "Development of Civilization",
                "Military Alliance": "Military Pact", "Space Flight": "First Space Flight",
                "Johann Sebastian Bach": "J. S. Bach", "Maximillien Robespierre": "Maximilien Robespierre",
                "Leonardo Da Vinci": "Leonardo da Vinci"}

# (name, age, field) -> (value used, reason). Filled while comparing; every entry is listed in SOURCES.md.
EXPECTED_DIFFS: dict = {
    ("Aggression: Plunder", "I", "military_action_cost"):
        (1, "B read 2 from the small picture; re-read at 4x zoom: one red token, like Raid I and Plunder II/III"),
}

KIND_A = {
    "Farm": "farm", "Mine": "mine", "Lab": "lab", "Temple": "temple", "Library": "library", "Theater": "theater",
    "Arena": "arena", "Infantry": "infantry", "Cavalry": "cavalry", "Artillery": "artillery",
    "Air Force": "air_force", "Govt": "government", "Civil": "special_civil", "Military": "special_military",
    "Colonization": "special_colonization", "Construction": "special_construction", "Leader": "leader",
    "Wonder": "wonder", "Action": "action", "Event": "event", "Territory": "territory",
    "Aggression": "aggression", "War": "war", "Pact": "pact", "Tactics": "tactic", "Bonus": "bonus",
}
MILITARY_KINDS = {"event", "territory", "aggression", "war", "pact", "tactic", "bonus"}


def norm(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", plain.lower().replace("&", "and"))


def _int(v):
    return v if isinstance(v, int) else None


def load_a(path: Path) -> dict:
    """BGA material.inc.php -> {(name, age): card in the common format}. Pact UI duplicates (no copies) dropped."""
    raw = read_assignment(path.read_text(encoding="utf-8"), "card_types")
    out = {}
    for bga_id, c in raw.items():
        copies = {"2": c["qt2"], "3": c["qt3"], "4": c["qt4"]}
        if c["category"] == "Pact" and not any(copies.values()):
            continue
        name = NAME_FIXES.get(c["name"], c["name"])
        kind = KIND_A[c["type"]]
        if kind == "aggression":
            name = "Aggression: " + name
        y = {}
        for src, dst in [("food", "food"), ("ress", "resources"), ("science", "science"), ("culture", "culture"),
                         ("strength", "strength"), ("CA", "civil_actions"), ("MA", "military_actions"),
                         ("colonize", "colonization")]:
            v = _int(c.get(src))
            if v:
                y[dst] = v
        h = _int(c.get("happy"))
        if h:
            y["happy" if h > 0 else "unhappy"] = abs(h)
        for col in ("blue", "yellow"):
            v = (c.get("tokendelta") or {}).get(col, 0)
            if v:  # signed: + adds tokens to the bank when the card enters play, - removes them
                y[f"{col}_tokens"] = v
        card = {
            "name": name, "age": c["age"], "deck": "military" if kind in MILITARY_KINDS else "civil", "kind": kind,
            "science_cost": c["techcost"] or None,
            "revolution_cost": c.get("techcostbon"),
            "resource_cost": c["resscost"] if isinstance(c["resscost"], int) and c["resscost"] else None,
            "stage_costs": c["resscost"] if isinstance(c["resscost"], list) else None,
            "yields": y,
            "urban_limit": c.get("buildinglimit"),
            "military_action_cost": c.get("MA") if kind in ("aggression", "war") else None,
            "tactic": None, "bonus": None, "copies": copies, "bga_id": bga_id,
        }
        if kind in ("aggression", "war"):
            card["yields"].pop("military_actions", None)
        if kind == "pact":  # side symbols A/B are part of the pact's effect, not one player's yields
            card["yields"] = {}
        if kind == "tactic":
            card["tactic"] = {"units": {"infantry": c.get("inf", 0), "cavalry": c.get("cav", 0),
                                        "artillery": c.get("arty", 0)},
                              "strength": c.get("artybon"), "outdated_strength": c.get("artybonplus") or None}
        if kind == "bonus":
            card["bonus"] = {"defense": c["def"], "colonization": c["colo"]}
        key = (name, c["age"])
        if key in out:
            raise SystemExit(f"duplicate card in A: {key}")
        out[key] = card
    return out


def load_list(path: Path) -> dict:
    out = {}
    for c in json.loads(path.read_text(encoding="utf-8")):
        c = dict(c, name=B_NAME_FIXES.get(c["name"], c["name"]))
        key = (c["name"], c["age"])
        if key in out:
            raise SystemExit(f"duplicate card in {path.name}: {key}")
        out[key] = c
    return out


def compare(a: dict, b: dict) -> list:
    """Field-by-field differences between A and B not covered by EXPECTED_DIFFS."""
    problems = []
    bn = {(norm(n), age): (n, age) for n, age in b}
    for key, ca in sorted(a.items(), key=lambda kv: (AGES.index(kv[0][1]), kv[0][0])):
        bk = bn.get((norm(key[0]), key[1]))
        if bk is None:
            problems.append(f"{key}: missing in B")
            continue
        cb = b[bk]
        fields = ["kind"] + NUMERIC + ["yields", "tactic", "bonus"]
        for f in fields:
            va, vb = ca.get(f), cb.get(f)
            if f == "yields":
                va, vb = dict(va or {}), {k: v for k, v in (vb or {}).items() if v}
                if ca["kind"] == "pact":
                    vb = {}
            if va != vb:
                exp = EXPECTED_DIFFS.get((key[0], key[1], f))
                if exp is None:
                    problems.append(f"{key} {f}: A={va} B={vb}")
        marks = {"": ca["copies"]["2"], "3+": ca["copies"]["3"] - ca["copies"]["2"],
                 "4": ca["copies"]["4"] - ca["copies"]["3"]}
        mb = cb.get("player_marking") or ""
        if ca["kind"] != "pact" and any(ca["copies"].values()) and not marks.get(mb):
            exp = EXPECTED_DIFFS.get((key[0], key[1], "player_marking"))
            if exp is None:
                problems.append(f"{key} player_marking: B={mb!r}, A copies {ca['copies']}")
    names_a = {(norm(n), age) for n, age in a}
    for (n, age) in b:
        if (norm(n), age) not in names_a:
            problems.append(f"{(n, age)}: in B, not in A")
    return problems


def check_membership(a: dict, wiki: dict) -> list:
    """Third source: the fan wiki's card list (names per age) must hold exactly the cards A gives copies."""
    listed = set()
    for cat, ages in wiki.items():
        if cat.startswith("_"):
            continue
        for age, names in ages.items():
            listed |= {(WIKI_ALIASES.get(n, n), age) for n in names}
    in_game = {k for k, c in a.items() if any(c["copies"].values()) and c["age"] != "A" or
               (c["age"] == "A" and c["bga_id"] not in STARTING_BGA_IDS)}
    in_game = {k for k in in_game if any(a[k]["copies"].values())}
    problems = [f"{k}: has copies in A, missing from the wiki list" for k in sorted(in_game - listed)]
    problems += [f"{k}: in the wiki list, no copies in A" for k in sorted(listed - in_game)]
    return problems


STARTING_BGA_IDS = {3, 6, 8, 29, 31, 34}  # Agriculture, Bronze, Despotism, Philosophy, Religion, Warriors (printed on the board)

# Expansion values decided between disagreeing sources: (name, age, field) -> (value, reason). Listed in SOURCES.md.
EXPANSION_DECISIONS: dict = {
    ("Transcontinental Railroad", "II", "stage_costs"):
        ([3, 3, 3, 3], "printed picture (fan wiki) and NamuWiki; the fan wiki text says 4/4/4/4"),
    ("Republic", "II", "revolution_cost"):
        (2, "fan wiki and the BoardGameGeek playtester overview; NamuWiki says 3; no picture found"),
    ("Professional Sports", "III", "resource_cost"):
        (8, "base printed value (A and B); the rebalance changes its strength only; fan wiki 7, NamuWiki 8"),
}
EXPANSION_FIELDS = ["kind", "science_cost", "revolution_cost", "resource_cost", "stage_costs", "urban_limit",
                    "yields"]


def compare_expansion(e: dict, p: dict) -> list:
    """Text list E against the printed pictures P (52 leaders and wonders)."""
    problems = []
    en = {(norm(n), age): (n, age) for n, age in e}
    for key, cp in p.items():
        ek = en.get((norm(key[0]), key[1]))
        if ek is None:
            problems.append(f"{key}: printed card missing in the text list")
            continue
        for f in EXPANSION_FIELDS:
            ve, vp = e[ek].get(f), cp.get(f)
            if f == "yields":
                ve, vp = {k: v for k, v in (ve or {}).items() if v}, {k: v for k, v in (vp or {}).items() if v}
            if ve != vp and (ek[0], ek[1], f) not in EXPANSION_DECISIONS:
                problems.append(f"{ek} {f}: text={ve} printed={vp}")
            elif (ek[0], ek[1], f) in EXPANSION_DECISIONS and EXPANSION_DECISIONS[(ek[0], ek[1], f)][0] != vp:
                problems.append(f"{ek} {f}: decision {EXPANSION_DECISIONS[(ek[0], ek[1], f)][0]} != printed {vp}")
    return problems
# Rebalanced copies (rules T15.2): the copy marked "4" becomes "3+"
REBALANCED_COPIES = {("Republic", "II"): {"2": 1, "3": 2, "4": 2},
                     ("Professional Sports", "III"): {"2": 1, "3": 2, "4": 2},
                     ("Military Theory", "III"): {"2": 1, "3": 2, "4": 2}}
# The rebalanced Bach is printed with his full name (expansion list); the card keeps one identity in the game
REBALANCED_NAMES = {("J. S. Bach", "II"): "Johann Sebastian Bach"}
CARD_FIELDS = ["science_cost", "revolution_cost", "resource_cost", "stage_costs", "yields", "urban_limit",
               "military_action_cost", "tactic", "bonus"]
KIND_ORDER = ["farm", "mine", "lab", "temple", "library", "theater", "arena", "infantry", "cavalry", "artillery",
              "air_force", "government", "special_civil", "special_military", "special_colonization",
              "special_construction", "leader", "wonder", "action", "event", "territory", "aggression", "war",
              "pact", "tactic", "bonus"]


def build(a: dict, e: dict) -> list:
    """Cards of the modelled game (base + expansion, rules T15) in the cards.json shape."""
    from card_effects import EXPANSION as EXP_EFFECTS
    cards = {}
    for key, c in a.items():
        if not any(c["copies"].values()):
            continue  # Light Cavalry: no copies in this edition (SOURCES.md)
        starting = c["bga_id"] in STARTING_BGA_IDS
        cards[key] = {"name": key[0], "age": key[1], "deck": c["deck"], "kind": c["kind"], "set": "base",
                      "starting": starting, "copies": None if starting else dict(c["copies"]),
                      **{f: c[f] for f in CARD_FIELDS}, "effect": BASE_EFFECTS.get(key)}
    for key, x in e.items():
        if x["name"].startswith("UNKNOWN"):
            continue  # left out by the maintainer's decision (SOURCES.md)
        vals = {f: EXPANSION_DECISIONS.get((key[0], key[1], f), (x.get(f),))[0] for f in CARD_FIELDS}
        if x["version"] == "rebalanced":
            base_key = next(k for k in cards if k[1] == key[1] and norm(REBALANCED_NAMES.get(k, k[0])) == norm(key[0]))
            card = cards.pop(base_key)
            card.update({k: v for k, v in vals.items() if v not in (None, {})})
            card["name"], card["set"] = key[0], "rebalanced"
            card["copies"] = REBALANCED_COPIES.get(base_key, card["copies"])
            card["effect"] = EXP_EFFECTS.get(key, card["effect"])
            cards[(key[0], key[1])] = card
        elif key in cards and x["kind"] in ("action", "bonus"):
            cards[key]["copies"] = {n: v + (1 if x["kind"] == "bonus" or n != "2" else 0)
                                    for n, v in cards[key]["copies"].items()}  # extra copy: bonus for all, action 3+
        else:
            cards[key] = {"name": key[0], "age": key[1], "deck": x["deck"], "kind": x["kind"], "set": "new",
                          "starting": False, "copies": {"2": 1, "3": 1, "4": 1}, **vals,
                          "effect": EXP_EFFECTS.get(key)}
            if x["kind"] == "pact":
                cards[key]["copies"] = {"2": 0, "3": 1, "4": 1}
    out = sorted(cards.values(), key=lambda c: (c["deck"] != "civil", AGES.index(c["age"]),
                                                KIND_ORDER.index(c["kind"]), c["name"]))
    for i, c in enumerate(out):
        c["id"] = i
        c["yields"] = c["yields"] or {}
    return [{"id": c.pop("id"), **c} for c in out]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    inbox = Path(argv[0]) if argv else HERE.parents[2] / "inbox" / "through_the_ages"
    a = load_a(inbox / "bga" / "material.inc.php")
    b = load_list(inbox / "list_B_base.json")
    e = load_list(inbox / "list_expansion.json")
    problems = compare(a, b)
    problems += check_membership(a, json.loads((inbox / "wiki_card_list_digital.json").read_text(encoding="utf-8")))
    problems += compare_expansion(e, load_list(inbox / "list_expansion_printed.json"))
    cards = build(a, e)
    problems += [f"{(c['name'], c['age'])}: no structured effect" for c in cards if c["effect"] is None and
                 c["kind"] in {"leader", "action", "event", "territory", "aggression", "war", "pact"}]
    if problems:
        print("\n".join(problems))
        print(f"{len(problems)} problem(s)")
        return 1
    (HERE / "cards.json").write_text(json.dumps(cards, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                     newline="\n")
    print(f"A and B agree on {len(a)} base cards, the expansion text list and the printed pictures on 52 cards; "
          f"wrote {len(cards)} cards to cards.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
