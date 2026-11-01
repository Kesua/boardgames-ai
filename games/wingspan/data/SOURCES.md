# Where the Wingspan card data comes from, and how it was checked

`birds.json` (180 birds) and `bonus_cards.json` (26 bonus cards, 8 goal tiles) hold card **data** only: names,
numbers, icons and each power as a structured effect. They hold no printed card text and no art. The dashboard shows
an own-words description generated from the structured effect (`describe.power_text`).

## Sources

| | Source | Used for |
|---|---|---|
| A | Wingsearch app data, github.com/navarog/wingsearch, `src/assets/data/master.json`, `bonus.json` (newest printing wording) | the data itself |
| B | BoardGameGeek "Wingspan card list" spreadsheet by TawnyFrogmouth (2020 snapshot in github.com/coolbutuseless/wingspan, `data-raw/wingspan-card-lists-20201118.xlsx`, sheet "Core") | field-by-field check of A |
| C | Wingspan fan wiki, wingspan.miraheze.org, one page per bird | third, independent check of every bird |
| D | Two independent rules researchers (rules.md, sources section) | bonus-card tiers and the decisions D3–D6 |

## How to rebuild

```bash
python games/wingspan/data/build_cards.py <master.json> <bonus.json> <wingspan-card-lists-20201118.xlsx>
```

The script parses every power from **both** A's and B's wording into a structured effect and fails if they differ,
compares every field (points, habitats, food cost, "/" costs, wild icons, nest, egg limit, wingspan, power colour,
predator and flocking icons), and compares our bonus-card word matches with both sources' per-bird flags.
`tests/test_rules.py::test_bonus_cards` and `tests/test_data.py` pin the results.

## Results of the checks

- **A vs B, 180 birds:** all fields agree except:
  - American Redstart egg limit: A 2, B 4 → **2** (C agrees with A).
  - Power wording of the cowbirds and Yellow-Billed Cuckoo ("a bird" vs "another bird" with a bowl nest): equivalent,
    because none of the three can be its own target (the cowbirds have no nest, the cuckoo is a platform bird).
  - Star nests are called "wild" in both files and mapped to `star`.
- **Bonus-card words:** our word lists match both sources' flags except Canvasback (Anatomist "back" is a European
  expansion word, rules.md D6) and Tufted Titmouse (A only; "tuft" is an Americas expansion word).
- **Bonus-card tiers:** agree with A and B except Photographer 6+ birds (6, rules.md D3) and Backyard Birder 7+
  birds (6, D4).
- **C (fan wiki), 180 birds:** 177 agree on every field and the meaning of the power. Three differences:
  - Mississippi Kite and Northern Harrier predator icon: the wiki's field is blank, but its 12 and 5 birds with the
    identical power carry the icon → the wiki page is incomplete; A and B are right.
  - Northern Mockingbird food: A and B give invertebrate + fruit, the wiki seed + invertebrate. Kept **A and B**
    (two sources against one hand-edited page); flagged as the one open data question.
  - Eastern Screech-Owl wingspan (51 cm) and egg limit (2) are missing on the wiki; A and B agree on them.
