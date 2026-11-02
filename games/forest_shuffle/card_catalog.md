# Forest Shuffle card catalog (base + Woodland Edge + Alpine)

Transcribed from the BoardGameArena card sheets and the base-game reference cards, cross-checked against
[soldag/forest-shuffle-scoring](https://github.com/soldag/forest-shuffle-scoring) (all 368 card halves match in species, position and tree symbol).
Machine-readable version: `forest_shuffle/data/cards.json`.

**Deck: 233 cards** = 80 trees + 12 shrubs + 72 top/bottom + 66 left/right + 3 winter. Plus 14 reference cards and 5 caves = 252 components.

Tree symbol abbreviations: Li=Linden, Oa=Oak, SF=Silver Fir, Bi=Birch, Be=Beech, Sy=Sycamore, DF=Douglas Fir, HC=Horse Chestnut, AL=Alpine Larch, SP=Swiss Pine

## Trees (base)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Linden | Tree | 1 | - | - | 3 if no other forest has more Linden (ties ok), else 1 | ties count as most; Violet Carpenter Bee adds to the count |
| Oak | Tree | 2 | - | extra turn | 10 if all 8 tree species in forest (no saplings) |  |
| Silver Fir | Tree | 2 | - | place 1 Pawed Animal from hand free (no effect/bonus) | 2 per card attached to this tree |  |
| Birch | Tree | 0 | draw 1 | - | 1 |  |
| Beech | Tree | 1 | draw 1 | - | 5 if ≥4 Beech in forest |  |
| Sycamore | Tree | 2 | - | - | 1 per Tree (saplings included) |  |
| Douglas Fir | Tree | 2 | - | extra turn | 5 |  |
| Horse Chestnut | Tree | 1 | - | - | set: 1/2/3/4/5/6/7 → 1/4/9/16/25/36/49 total | 7+ scores 49; Violet Carpenter Bee adds to the count |

## Trees (Alpine)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| European Larch | Tree, Alps | 1 | - | place 1 Alps from hand free (no effect/bonus) | 3 | tree species Alpine Larch |
| Stone Pine | Tree, Alps | 2 | draw 1 | draw 1 | 1 per Alps (includes itself) | tree species Swiss Pine |

## Shrubs (Woodland Edge)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Elderberry | Shrub, Woodland Edge | 2 | PERMANENT: whenever you play a Plant → draw 1 | place 1 Plant from hand free (no effect/bonus) | 0 |  |
| Common Hazel | Shrub, Woodland Edge | 2 | PERMANENT: whenever you play a Bat → draw 1 | place 1 Bat from hand free (no effect/bonus) | 0 |  |
| Blackthorn | Shrub, Woodland Edge | 2 | PERMANENT: whenever you play a Butterfly → draw 1 | place 1 Butterfly from hand free (no effect/bonus) | 0 |  |

## Top halves (base)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Great Spotted Woodpecker | Bird | 1 | draw 1 | - | 10 if no other forest has more Tree (ties ok), else 0 | saplings included; ties count; Violet Carpenter Bee adds |
| Chaffinch | Bird | 1 | - | - | 5 if on a Beech |  |
| Large Tortoiseshell | Insect, Butterfly | 0 | - | - | butterfly set: 1..7 different → 0/3/6/12/20/35/55 |  |
| Camberwell Beauty | Insect, Butterfly | 0 | - | - | butterfly set: 1..7 different → 0/3/6/12/20/35/55 |  |
| Purple Emperor | Insect, Butterfly | 0 | - | - | butterfly set: 1..7 different → 0/3/6/12/20/35/55 |  |
| Silver-Washed Fritillary | Insect, Butterfly | 0 | - | - | butterfly set: 1..7 different → 0/3/6/12/20/35/55 |  |
| Peacock Butterfly | Insect, Butterfly | 0 | - | - | butterfly set: 1..7 different → 0/3/6/12/20/35/55 |  |
| Red Squirrel | Pawed Animal | 0 | - | - | 5 if on a Oak |  |
| Bullfinch | Bird | 1 | - | - | 2 per Insect |  |
| Tawny Owl | Bird | 2 | draw 1 | draw 2 | 5 |  |
| Eurasian Jay | Bird | 1 | extra turn | - | 3 |  |
| Goshawk | Bird | 2 | - | - | 3 per Bird |  |

## Bottom halves (base)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Penny Bun | Mushroom | 2 | PERMANENT: whenever you play a card in TOP slot of a tree → draw 1 | - | 0 |  |
| Parasol Mushroom | Mushroom | 2 | PERMANENT: whenever you play a card in BOTTOM slot of a tree → draw 1 | - | 0 |  |
| Chanterelle | Mushroom | 2 | PERMANENT: whenever you play a Tree → draw 1 | - | 0 |  |
| Fly Agaric | Mushroom | 2 | PERMANENT: whenever you play a Pawed Animal → draw 1 | - | 0 |  |
| Mole | Pawed Animal | 2 | immediately play any number of cards paying their cost | - | 0 |  |
| Blackberries | Plant | 0 | - | - | 2 per Plant |  |
| Wild Strawberries | Plant | 0 | - | - | 10 if all 8 tree species in forest (no saplings) |  |
| Tree Ferns | Plant | 1 | draw 1 | - | 6 per Amphibian |  |
| Common Toad | Amphibian | 0 | - | - | 5 if it shares its slot with another Common Toad | slot sharing with Common Toad (max 2) |
| Tree Frog | Amphibian | 0 | - | - | 5 per Gnat |  |
| Fire Salamander | Amphibian | 1 | - | place 1 Pawed Animal from hand free (no effect/bonus) | set: 1/2/3 → 5/15/25 total |  |
| Hedgehog | Pawed Animal | 1 | - | draw 1 | 2 per Butterfly |  |
| Fireflies | Insect | 0 | - | - | set: 1/2/3/4 → 0/10/15/20 total |  |
| Moss | Plant | 0 | - | - | 10 if ≥10 trees (saplings incl.) |  |
| Wood Ant | Insect | 1 | - | - | 2 per card in a BOTTOM slot of a tree |  |
| Stag Beetle | Insect | 2 | - | place 1 Bird from hand free (no effect/bonus) | 1 per Pawed Animal |  |
| Pond Turtle | Amphibian | 2 | draw 1 | - | 5 |  |

## Left/right halves (base)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| European Hare | Pawed Animal | 0 | - | - | 1 per European Hare (Mountain Hare counts as European Hare) | slot sharing with European Hare |
| European Badger | Pawed Animal | 1 | - | place 1 Pawed Animal from hand free (no effect/bonus) | 2 |  |
| Greater Horseshoe Bat | Bat | 1 | - | - | 5 if ≥3 different Bat |  |
| Red Fox | Pawed Animal | 2 | draw 1 per European Hare | - | 2 per European Hare |  |
| Raccoon | Pawed Animal | 1 | put any number of hand cards in cave, draw equal number | - | 0 |  |
| Wild Boar | Clovenhoofed Animal | 2 | - | - | 10 if ≥1 Squeaker in forest |  |
| Brown Long-Eared Bat | Bat | 1 | - | - | 5 if ≥3 different Bat |  |
| Roe Deer | Clovenhoofed Animal, Deer | 2 | - | draw 1 | 3 per card showing this card's tree symbol |  |
| Barbastelle Bat | Bat | 1 | - | - | 5 if ≥3 different Bat |  |
| Brown Bear | Pawed Animal | 3 | put all cards from clearing into cave | draw 1 then extra turn | 0 |  |
| Beech Marten | Pawed Animal | 1 | draw 1 | - | 5 per fully occupied tree |  |
| Red Deer | Clovenhoofed Animal, Deer | 2 | - | place 1 Deer from hand free (no effect/bonus) | 1 per Plant or Tree |  |
| Lynx | Pawed Animal | 1 | - | - | 10 if ≥1 Roe Deer in forest |  |
| Gnat | Insect | 0 | place any Bat from hand free (no effect/bonus) | - | 1 per Bat |  |
| Violet Carpenter Bee | Insect | 1 | - | - | 0 | the tree it occupies counts as one additional tree of its species (Linden, Beech, Horse Chestnut sets; Moss and Woodpecker tree counts). Not for Sycamore/Red Deer per-tree counts. |
| Fallow Deer | Clovenhoofed Animal, Deer | 2 | - | draw 2 | 3 per Clovenhoofed Animal |  |
| European Fat Dormouse | Pawed Animal | 1 | - | - | 15 if a Bat also occupies this tree |  |
| Bechstein's Bat | Bat | 1 | - | - | 5 if ≥3 different Bat |  |
| Wolf | Pawed Animal | 3 | draw 1 per Deer | extra turn | 5 per Deer |  |
| Squeaker | Clovenhoofed Animal | 0 | - | - | 1 |  |

## Top halves (Woodland Edge)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Map Butterfly | Insect, Butterfly, Woodland Edge | 0 | - | - | butterfly set: 1..7 different → 0/3/6/12/20/35/55 |  |
| Eurasian Magpie | Bird, Woodland Edge | 1 | take 1 from clearing to hand | put 2 cards from clearing into cave | 3 |  |
| Nightingale | Bird, Woodland Edge | 1 | - | extra turn | 5 if on a shrub |  |
| Barn Owl | Bird, Woodland Edge | 2 | extra turn (if ≥1 Bat) | - | 3 per Bat |  |

## Bottom halves (Woodland Edge)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Digitalis | Plant, Woodland Edge | 0 | - | - | different Plant: 1/2/3/4/5+ → 1/3/6/10/15 | 5+ scores 15 |
| Stinging Nettle | Plant, Woodland Edge | 0 | - | - | 2 per Butterfly | any number of butterflies may share the top slot of its tree/shrub |
| Great Green Bush-Cricket | Insect, Woodland Edge | 1 | place 1 Bird from hand free (no effect/bonus) | - | 1 per Insect |  |
| Water Vole | Pawed Animal, Woodland Edge | 2 | immediately play any number of hand cards as saplings | extra turn | 0 |  |

## Left/right halves (Woodland Edge)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Wild Boar (♀) | Clovenhoofed Animal, Woodland Edge | 2 | remove all clearing cards from game | place 1 Squeaker from hand free (no effect/bonus) | 10 per Squeaker |  |
| Bee Swarm | Insect, Woodland Edge | 1 | put all Plant/Shrub/Tree cards from clearing into cave | - | 1 per Plant |  |
| European Bison | Clovenhoofed Animal, Woodland Edge | 3 | extra turn | - | 2 per card showing Beech/Oak |  |
| European Wildcat | Pawed Animal, Woodland Edge | 1 | take 1 from clearing to hand | - | 1 per Woodland Edge card (itself included) | corrected 2026-11-02 (was 1 per Bird); official card appendix + 2 implementations |
| Common Pipistrelle | Bat, Woodland Edge | 1 | - | - | 5 if ≥3 different Bat |  |
| Crane Fly | Insect, Woodland Edge | 1 | place any Bat from hand free (no effect/bonus) | take all Bat from clearing to hand | 1 per Bat |  |
| European Polecat | Pawed Animal, Woodland Edge | 2 | - | extra turn | 10 if it is the only dweller on its tree/shrub |  |

## Top halves (Alpine)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Phoebus Apollo | Insect, Butterfly, Alps | 0 | - | - | butterfly set: 1..7 different → 0/3/6/12/20/35/55 |  |
| Golden Eagle | Bird, Alps | 1 | - | - | 1 per Pawed Animal or Amphibian |  |
| Bearded Vulture | Bird, Alps | 1 | put 2 cards from clearing into cave | - | 1 per card in cave |  |
| Common Raven | Bird, Alps | 1 | draw 1 | - | 5 |  |

## Bottom halves (Alpine)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Black Trumpet | Mushroom, Alps | 2 | PERMANENT: whenever you play a Alps → draw 1 | - | 0 |  |
| Edelweiss | Plant, Alps | 1 | draw 1 | draw 1 | 3 |  |
| Blueberry | Plant, Alps | 1 | place 1 Amphibian from hand free (no effect/bonus) | - | 2 per different Bird |  |
| Alpine Newt | Amphibian, Alps | 1 | - | place 1 Alps from hand free (no effect/bonus) then place 1 Insect from hand free (no effect/bonus) | 2 per Insect |  |
| Gentian | Plant, Alps | 0 | place 1 Butterfly from hand free (no effect/bonus) | - | 3 per Butterfly |  |

## Left/right halves (Alpine)

| Species | Types | Cost | Effect | Bonus (pay with matching symbol) | Scoring | Notes |
|---|---|---|---|---|---|---|
| Alpine Marmot | Pawed Animal, Alps | 1 | - | - | 3 per different Plant |  |
| Chamois | Clovenhoofed Animal, Alps | 1 | - | - | 3 per card showing this card's tree symbol |  |
| Capercaillie | Bird, Alps | 1 | place 1 Plant from hand free (no effect/bonus) | - | 1 per Plant |  |
| Mountain Hare | Pawed Animal, Alps | 0 | - | - | 1 per European Hare | counts as European Hare; does not share slots |
| Steinbock | Clovenhoofed Animal, Alps | 3 | extra turn | - | 10 |  |
| Savi's Pipistrelle | Bat, Alps | 1 | - | - | 5 if ≥3 different Bat |  |

## Physical cards

Every card in the deck. Split cards list `visible half : tree symbol` for each half; the count is the number of identical copies.

### Base game

**Trees / shrubs** (66 cards)

- `BT001` Linden [Li] ×9
- `BT002` Oak [Oa] ×7
- `BT003` Silver Fir [SF] ×6
- `BT004` Birch [Bi] ×10
- `BT005` Beech [Be] ×10
- `BT006` Sycamore [Sy] ×6
- `BT007` Douglas Fir [DF] ×7
- `BT008` Horse Chestnut [HC] ×11

**Top / bottom** (48 cards)

- `BV001` top: Great Spotted Woodpecker [Li] | bottom: Penny Bun [DF]
- `BV002` top: Chaffinch [Sy] | bottom: Parasol Mushroom [SF]
- `BV003` top: Large Tortoiseshell [Be] | bottom: Mole [Sy]
- `BV004` top: Camberwell Beauty [HC] | bottom: Chanterelle [Bi]
- `BV005` top: Purple Emperor [Li] | bottom: Fly Agaric [Oa]
- `BV006` top: Silver-Washed Fritillary [Oa] | bottom: Blackberries [Be]
- `BV007` top: Red Squirrel [Oa] | bottom: Wild Strawberries [Bi]
- `BV008` top: Bullfinch [SF] | bottom: Tree Ferns [Li]
- `BV009` top: Tawny Owl [Sy] | bottom: Common Toad [DF]
- `BV010` top: Eurasian Jay [HC] | bottom: Tree Ferns [SF]
- `BV011` top: Goshawk [Oa] | bottom: Common Toad [Sy]
- `BV012` top: Bullfinch [DF] | bottom: Parasol Mushroom [HC]
- `BV013` top: Camberwell Beauty [Bi] | bottom: Tree Frog [Oa]
- `BV014` top: Peacock Butterfly [Li] | bottom: Common Toad [Be]
- `BV015` top: Purple Emperor [Bi] | bottom: Tree Frog [Oa]
- `BV016` top: Red Squirrel [Be] | bottom: Fire Salamander [Li]
- `BV017` top: Tawny Owl [Bi] | bottom: Penny Bun [DF]
- `BV018` top: Eurasian Jay [Sy] | bottom: Fly Agaric [SF]
- `BV019` top: Great Spotted Woodpecker [DF] | bottom: Wild Strawberries [Sy]
- `BV020` top: Goshawk [SF] | bottom: Hedgehog [HC]
- `BV021` top: Large Tortoiseshell [Sy] | bottom: Mole [Oa]
- `BV022` top: Peacock Butterfly [HC] | bottom: Fireflies [Be]
- `BV023` top: Peacock Butterfly [Oa] | bottom: Chanterelle [SF]
- `BV024` top: Silver-Washed Fritillary [Be] | bottom: Moss [Li]
- `BV025` top: Eurasian Jay [Bi] | bottom: Fireflies [DF]
- `BV026` top: Chaffinch [Be] | bottom: Common Toad [SF]
- `BV027` top: Red Squirrel [HC] | bottom: Fireflies [Sy]
- `BV028` top: Red Squirrel [DF] | bottom: Common Toad [HC]
- `BV029` top: Peacock Butterfly [SF] | bottom: Hedgehog [Oa]
- `BV030` top: Bullfinch [DF] | bottom: Hedgehog [Be]
- `BV031` top: Large Tortoiseshell [SF] | bottom: Blackberries [Bi]
- `BV032` top: Camberwell Beauty [Sy] | bottom: Fireflies [Li]
- `BV033` top: Purple Emperor [HC] | bottom: Moss [DF]
- `BV034` top: Silver-Washed Fritillary [Oa] | bottom: Blackberries [SF]
- `BV035` top: Tawny Owl [Be] | bottom: Wild Strawberries [Sy]
- `BV036` top: Eurasian Jay [Bi] | bottom: Tree Ferns [HC]
- `BV037` top: Great Spotted Woodpecker [Li] | bottom: Common Toad [Oa]
- `BV038` top: Goshawk [SF] | bottom: Wood Ant [Be]
- `BV039` top: Chaffinch [Sy] | bottom: Stag Beetle [Bi]
- `BV040` top: Bullfinch [DF] | bottom: Tree Frog [Li]
- `BV041` top: Large Tortoiseshell [SF] | bottom: Fire Salamander [DF]
- `BV042` top: Camberwell Beauty [Sy] | bottom: Pond Turtle [Bi]
- `BV043` top: Purple Emperor [HC] | bottom: Pond Turtle [Sy]
- `BV044` top: Silver-Washed Fritillary [Oa] | bottom: Fire Salamander [HC]
- `BV045` top: Tawny Owl [Be] | bottom: Stag Beetle [Sy]
- `BV046` top: Chaffinch [Bi] | bottom: Wood Ant [Be]
- `BV047` top: Great Spotted Woodpecker [Li] | bottom: Wood Ant [Bi]
- `BV048` top: Goshawk [DF] | bottom: Moss [Li]

**Left / right** (44 cards)

- `BH001` left: European Hare [Li] | right: European Badger [DF]
- `BH002` left: European Hare [Oa] | right: Greater Horseshoe Bat [Li]
- `BH003` left: European Hare [SF] | right: Red Fox [Oa]
- `BH004` left: Raccoon [DF] | right: European Hare [Sy]
- `BH005` left: Wild Boar [Sy] | right: European Hare [SF]
- `BH006` left: Brown Long-Eared Bat [Sy] | right: European Hare [Li]
- `BH007` left: Raccoon [SF] | right: Roe Deer [Be]
- `BH008` left: Brown Long-Eared Bat [Sy] | right: European Badger [DF]
- `BH009` left: Barbastelle Bat [HC] | right: Wild Boar [Oa]
- `BH010` left: Brown Bear [Li] | right: Raccoon [SF]
- `BH011` left: Beech Marten [Sy] | right: Brown Bear [HC]
- `BH012` left: Red Deer [Li] | right: Brown Bear [Be]
- `BH013` left: Barbastelle Bat [SF] | right: Beech Marten [HC]
- `BH014` left: Lynx [DF] | right: European Hare [Bi]
- `BH015` left: Wild Boar [Bi] | right: Beech Marten [Oa]
- `BH016` left: European Badger [HC] | right: Gnat [Oa]
- `BH017` left: Red Fox [Li] | right: Violet Carpenter Bee [DF]
- `BH018` left: Wild Boar [Sy] | right: Roe Deer [HC]
- `BH019` left: Fallow Deer [Li] | right: Wild Boar [DF]
- `BH020` left: Fallow Deer [Li] | right: Roe Deer [Bi]
- `BH021` left: Red Deer [SF] | right: Fallow Deer [Sy]
- `BH022` left: Violet Carpenter Bee [DF] | right: Lynx [Be]
- `BH023` left: European Fat Dormouse [Be] | right: Barbastelle Bat [Oa]
- `BH024` left: Greater Horseshoe Bat [Be] | right: European Fat Dormouse [DF]
- `BH025` left: Red Fox [Li] | right: Wolf [SF]
- `BH026` left: European Fat Dormouse [SF] | right: Brown Long-Eared Bat [Be]
- `BH027` left: Bechstein's Bat [Be] | right: European Fat Dormouse [Oa]
- `BH028` left: Gnat [Bi] | right: Violet Carpenter Bee [DF]
- `BH029` left: Wolf [DF] | right: Gnat [HC]
- `BH030` left: Roe Deer [Li] | right: Squeaker [Sy]
- `BH031` left: Bechstein's Bat [Oa] | right: Wolf [SF]
- `BH032` left: Roe Deer [SF] | right: Lynx [Li]
- `BH033` left: Beech Marten [Be] | right: Bechstein's Bat [Bi]
- `BH034` left: European Hare [Be] | right: Red Deer [HC]
- `BH035` left: Wolf [Sy] | right: Greater Horseshoe Bat [Li]
- `BH036` left: Squeaker [HC] | right: Red Deer [Oa]
- `BH037` left: Red Fox [Be] | right: Squeaker [Oa]
- `BH038` left: Lynx [DF] | right: Raccoon [Bi]
- `BH039` left: Squeaker [Oa] | right: Lynx [SF]
- `BH040` left: European Hare [Bi] | right: Beech Marten [HC]
- `BH041` left: Lynx [HC] | right: Red Fox [DF]
- `BH042` left: European Hare [Bi] | right: Red Deer [HC]
- `BH043` left: Violet Carpenter Bee [SF] | right: European Hare [Sy]
- `BH044` left: European Badger [HC] | right: Fallow Deer [Bi]

**Winter** ×3

### Woodland Edge

**Trees / shrubs** (12 cards)

- `WT001` Elderberry [Li] ×1
- `WT002` Elderberry [Sy] ×1
- `WT003` Elderberry [Bi] ×1
- `WT004` Elderberry [Oa] ×1
- `WT005` Common Hazel [HC] ×1
- `WT006` Common Hazel [Oa] ×1
- `WT007` Common Hazel [Be] ×1
- `WT008` Common Hazel [Bi] ×1
- `WT009` Blackthorn [DF] ×1
- `WT010` Blackthorn [Bi] ×1
- `WT011` Blackthorn [SF] ×1
- `WT012` Blackthorn [Sy] ×1

**Top / bottom** (12 cards)

- `WV001` top: Map Butterfly [Li] | bottom: Digitalis [DF]
- `WV002` top: Map Butterfly [Sy] | bottom: Stinging Nettle [Bi]
- `WV003` top: Map Butterfly [Oa] | bottom: Great Green Bush-Cricket [SF]
- `WV004` top: Map Butterfly [SF] | bottom: Water Vole [Sy]
- `WV005` top: Eurasian Magpie [Be] | bottom: Digitalis [Bi]
- `WV006` top: Eurasian Magpie [SF] | bottom: Stinging Nettle [HC]
- `WV007` top: Eurasian Magpie [Bi] | bottom: Great Green Bush-Cricket [Be]
- `WV008` top: Nightingale [Be] | bottom: Digitalis [Sy]
- `WV009` top: Nightingale [Oa] | bottom: Stinging Nettle [Sy]
- `WV010` top: Nightingale [HC] | bottom: Water Vole [Be]
- `WV011` top: Barn Owl [Bi] | bottom: Digitalis [Oa]
- `WV012` top: Barn Owl [Sy] | bottom: Great Green Bush-Cricket [Oa]

**Left / right** (12 cards)

- `WH001` left: Wild Boar (♀) [Bi] | right: Bee Swarm [Sy]
- `WH002` left: European Bison [Oa] | right: Wild Boar (♀) [Sy]
- `WH003` left: Wild Boar (♀) [SF] | right: European Wildcat [HC]
- `WH004` left: Common Pipistrelle [Li] | right: Squeaker [SF]
- `WH005` left: Squeaker [HC] | right: Crane Fly [Be]
- `WH006` left: European Polecat [SF] | right: Squeaker [DF]
- `WH007` left: Bee Swarm [Be] | right: Common Pipistrelle [Sy]
- `WH008` left: European Wildcat [Oa] | right: Bee Swarm [Bi]
- `WH009` left: Common Pipistrelle [Bi] | right: European Bison [Be]
- `WH010` left: European Bison [Be] | right: European Polecat [Sy]
- `WH011` left: Crane Fly [Bi] | right: European Polecat [Oa]
- `WH012` left: European Wildcat [Sy] | right: Crane Fly [Oa]

### Alpine

**Trees / shrubs** (14 cards)

- `AT001` European Larch [AL] ×7
- `AT002` Stone Pine [SP] ×7

**Top / bottom** (12 cards)

- `AV001` top: Phoebus Apollo [SP] | bottom: Black Trumpet [AL]
- `AV002` top: Phoebus Apollo [DF] | bottom: Edelweiss [SP]
- `AV003` top: Phoebus Apollo [AL] | bottom: Blueberry [Bi]
- `AV004` top: Phoebus Apollo [SF] | bottom: Alpine Newt [SP]
- `AV005` top: Golden Eagle [Be] | bottom: Black Trumpet [SP]
- `AV006` top: Bearded Vulture [SF] | bottom: Gentian [AL]
- `AV007` top: Golden Eagle [AL] | bottom: Alpine Newt [DF]
- `AV008` top: Common Raven [AL] | bottom: Gentian [Be]
- `AV009` top: Common Raven [DF] | bottom: Blueberry [SP]
- `AV010` top: Bearded Vulture [AL] | bottom: Alpine Newt [SF]
- `AV011` top: Bearded Vulture [SP] | bottom: Edelweiss [AL]
- `AV012` top: Golden Eagle [SF] | bottom: Gentian [SP]

**Left / right** (10 cards)

- `AH001` left: Alpine Marmot [Be] | right: Chamois [SP]
- `AH002` left: Alpine Marmot [AL] | right: Capercaillie [DF]
- `AH003` left: Mountain Hare [SF] | right: Alpine Marmot [SP]
- `AH004` left: Steinbock [AL] | right: Alpine Marmot [Bi]
- `AH005` left: Chamois [AL] | right: Capercaillie [Be]
- `AH006` left: Mountain Hare [AL] | right: Chamois [DF]
- `AH007` left: Savi's Pipistrelle [SF] | right: Steinbock [SP]
- `AH008` left: Capercaillie [AL] | right: Savi's Pipistrelle [SP]
- `AH009` left: Capercaillie [SP] | right: Steinbock [DF]
- `AH010` left: Savi's Pipistrelle [AL] | right: Mountain Hare [SP]

## Verification notes

- Species, half position, tree symbol and copy counts of all 368 halves agree with soldag/forest-shuffle-scoring.
- Costs were read from the cards. soldag differs on four: Horse Chestnut (card 1, soldag 2), Crane Fly (1 vs 2), Gentian (0 vs 1), Wood Ant (1 vs 0). The card images were taken as authoritative.
- Butterfly tables printed on base cards stop at 5 species; Phoebus Apollo shows 6 (35) and Map Butterfly 7 (55). One shared table applies.
- Rulebook clarifications folded in: Mountain Hare counts as European Hare but never shares a slot; Oak and Wild Strawberries still need 8 species with Alpine; Stinging Nettle refers to its own host; Water Vole saplings reveal clearing cards; Bee Swarm, Bearded Vulture, Eurasian Magpie and Brown Bear resolve after payment.
- Violet Carpenter Bee (reference card 13): adds 1 to the host tree's species count for Linden, Beech and Horse Chestnut scoring and to the tree count for Moss and Great Spotted Woodpecker. It scores 0 itself.
