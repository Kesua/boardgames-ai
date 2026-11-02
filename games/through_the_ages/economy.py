"""Banks (T1.7, T1.8), statistics (T11), food and resources (T12): payment with change (choice C1), gaining,
production, corruption, consumption; culture and science points with the per-card culture book (PLAN section 7).

Statistics are pure functions of a player's cards in play and workers, cached per player and `Player.ver` (bumped by
`touch`). Anything that changes cards in play or workers must call `touch(p)`.
"""
from __future__ import annotations

from functools import lru_cache

from . import effects, military
from .cards import (EFFECT_TYPE, HOLDS_WORKERS, KIND, N_STATS, S_CIVIL, S_COLON, S_CULT, S_FOODB, S_HAPPY, S_MIL,
                    S_RESB, S_SCI, S_STR, S_UNHAPPY, STAT_YIELDS, TOKEN_VALUE, URBAN_LIMIT)


# ---------------------------------------------------------------------------------------------- tables (T1.7, T1.8)
def corruption(blue_bank: int) -> int:
    """T1.7: resources lost by blue tokens left in the blue bank (T1.9: above 16 counts as 11+)."""
    if blue_bank >= 11:
        return 0
    if blue_bank >= 6:
        return 2
    if blue_bank >= 1:
        return 4
    return 6


def pop_cost(yellow_bank: int):
    """T1.8: food cost of one population increase; None when the yellow bank is empty."""
    if yellow_bank >= 17:
        return 2
    if yellow_bank >= 13:
        return 3
    if yellow_bank >= 9:
        return 4
    if yellow_bank >= 5:
        return 5
    if yellow_bank >= 1:
        return 7
    return None


def consumption(yellow_bank: int) -> int:
    """T1.8: food consumed at the end of turn."""
    if yellow_bank >= 17:
        return 0
    if yellow_bank >= 13:
        return 1
    if yellow_bank >= 9:
        return 2
    if yellow_bank >= 5:
        return 3
    if yellow_bank >= 1:
        return 4
    return 6


def happy_required(yellow_bank: int) -> int:
    """T1.8: happy faces required."""
    if yellow_bank >= 17:
        return 0
    if yellow_bank >= 13:
        return 1
    if yellow_bank >= 11:
        return 2
    return 8 - (yellow_bank + 1) // 2           # 9-10 -> 3, 7-8 -> 4, 5-6 -> 5, 3-4 -> 6, 1-2 -> 7, 0 -> 8


# ---------------------------------------------------------------------------------------------- statistics (T11)
class Stats:
    """One player's statistics. `v` holds the raw sums by stat index (cards.S_*)."""
    __slots__ = ("v", "civil", "military", "culture", "science", "happiness", "strength", "strength_raw", "army",
                 "army_count", "colonization", "resource_bonus", "food_bonus", "urban_limit", "civil_limit_bonus",
                 "military_limit_bonus", "wonder_stages", "urban_discount", "culture_parts", "happy_parts",
                 "build_disc", "sci_disc", "gaudi", "gov_disc", "pop_discount", "ignore_discontent", "take_disc",
                 "no_wonder_surcharge")

    def __init__(self):
        self.v = [0] * N_STATS
        self.urban_limit = 0
        self.civil_limit_bonus = 0
        self.military_limit_bonus = 0
        self.wonder_stages = 1                 # stages per wonder action (T5.7; construction technologies)
        self.urban_discount = {}               # age -> resource discount on urban buildings of that age
        self.culture_parts = {}                # card -> signed culture contribution (PLAN C3)
        self.happy_parts = {}                  # card -> happy faces it gives (St. Peter's, Michelangelo, Joan)
        self.build_disc = {}                   # kind -> {age: resource discount} (Watt, Shakespeare)
        self.sci_disc = {}                     # kind -> {age: science discount} (Bach, Shakespeare, Watt, Colosseum)
        self.gaudi = None                      # Gaudi: urban kinds with a building (science discount per other kind)
        self.gov_disc = 0                      # Acropolis: science discount of a peaceful government change
        self.pop_discount = 0                  # Moses: food discount of a population increase
        self.ignore_discontent = 0             # Forbidden City: discontent workers counted 2 fewer
        self.take_disc = 0                     # Darwin: technology cards from the row cost 1 less (minimum 1)
        self.no_wonder_surcharge = False       # Michelangelo: no extra civil actions for completed wonders
        self.army_count = 0


def touch(p) -> None:
    p.ver += 1


def compute_stats(g, p) -> Stats:
    st = Stats()
    v = st.v
    parts = st.culture_parts
    happy = st.happy_parts
    workers = p.workers
    late = []
    for c in p.play_order:
        mult = workers.get(c, 0) if HOLDS_WORKERS[c] else 1
        if mult:
            for k, x in STAT_YIELDS[c]:
                v[k] += x * mult
                if k == S_CULT:
                    parts[c] = parts.get(c, 0) + x * mult
                elif k == S_HAPPY:
                    happy[c] = happy.get(c, 0) + x * mult
        t = EFFECT_TYPE[c]
        if t is not None:
            if t in effects.LATE_ORDER:
                late.append(c)
            else:
                effects.passive(g, p, c, st)
    for c in p.ruined:                                   # Ravages of Time: a ruined wonder produces 2 culture
        v[S_CULT] += 2
        parts[c] = parts.get(c, 0) + 2
    if p.homer_wonder is not None and p.homer_wonder in p.wonders:   # Homer tucked under a wonder: +1 happy face
        v[S_HAPPY] += 1
        happy[p.homer_wonder] = happy.get(p.homer_wonder, 0) + 1
    if late:                                             # effects that read other cards' happy faces, in order
        late.sort(key=lambda c: effects.LATE_ORDER.index(EFFECT_TYPE[c]))
        for c in late:
            effects.passive(g, p, c, st)
    effects.pact_and_war_passives(g, p, st)              # pacts the player is party to, wars it is in (T10)
    st.army, st.army_count = military.armies(p)          # T11.4
    if st.army_count:
        effects.after_armies(g, p, st)                   # Jan Zizka: culture per army
    st.urban_limit += URBAN_LIMIT[p.government] or 0
    st.civil = max(0, v[S_CIVIL])
    st.military = max(0, v[S_MIL])
    st.culture = max(0, v[S_CULT])                       # T11.2
    st.science = max(0, v[S_SCI])
    st.happiness = min(8, max(0, v[S_HAPPY] - v[S_UNHAPPY]))   # T11.5
    st.strength_raw = v[S_STR] + st.army
    st.strength = max(0, st.strength_raw)                # T11.3
    st.colonization = v[S_COLON]
    st.resource_bonus = v[S_RESB]
    st.food_bonus = v[S_FOODB]
    return st


def stats(g, seat: int) -> Stats:
    p = g.s.players[seat]
    hit = g._stats.get(seat)
    if hit is not None and hit[0] == p.ver:
        return hit[1]
    st = compute_stats(g, p)
    g._stats[seat] = (p.ver, st)
    return st


def civil_available(g, seat: int) -> int:
    p = g.s.players[seat]
    return max(0, stats(g, seat).civil - p.civil_spent) + p.temp_civil


def military_available(g, seat: int) -> int:
    p = g.s.players[seat]
    return max(0, stats(g, seat).military - p.military_spent) + p.temp_military


def spend_civil(p, n: int) -> None:
    """T11.6: temporary actions are spent first."""
    t = min(p.temp_civil, n)
    p.temp_civil -= t
    p.civil_spent += n - t


def spend_military(p, n: int) -> None:
    t = min(p.temp_military, n)
    p.temp_military -= t
    p.military_spent += n - t


def settle_totals(g, seat: int, before: tuple, revolution: bool = False) -> None:
    """T11.6: after cards entered/left play. A total that rises gives available actions (civil ones arrive spent
    after a revolution, T5.9); a total that falls removes spent actions first."""
    p = g.s.players[seat]
    st = stats(g, seat)
    dc, dm = st.civil - before[0], st.military - before[1]
    if revolution:
        p.civil_spent = st.civil
    elif dc < 0:
        p.civil_spent = max(0, p.civil_spent + dc)
    if dm < 0:
        p.military_spent = max(0, p.military_spent + dm)


def totals(g, seat: int) -> tuple:
    st = stats(g, seat)
    return st.civil, st.military


def discontent(g, seat: int) -> int:
    """T11.8: happy faces required minus happiness, if positive."""
    p = g.s.players[seat]
    st = stats(g, seat)
    return max(0, happy_required(p.yellow_bank) - st.happiness - st.ignore_discontent)


def pop_cost_for(g, seat: int, discount: int = 0):
    """Food cost of one population increase now (T1.8, Moses), None with an empty yellow bank."""
    cost = pop_cost(g.s.players[seat].yellow_bank)
    return None if cost is None else max(0, cost - stats(g, seat).pop_discount - discount)


def urban_workers(p, kind: str) -> int:
    return sum(p.workers.get(c, 0) for c in p.techs if KIND[c] == kind)


def civil_hand_limit(g, seat: int) -> int:
    st = stats(g, seat)
    return st.civil + st.civil_limit_bonus


def military_hand_limit(g, seat: int) -> int:
    st = stats(g, seat)
    return st.military + st.military_limit_bonus


# ---------------------------------------------------------------------------------------------- tokens (T12)
def kind_cards(p, kind: str) -> list:
    """Farm or mine technologies in play, highest token value first (values differ per age)."""
    return sorted((c for c in p.techs if KIND[c] == kind), key=lambda c: -TOKEN_VALUE[c])


def total(p, kind: str) -> int:
    """Food (kind 'farm') or resources (kind 'mine') a player has."""
    tok = p.tokens
    return sum(tok.get(c, 0) * TOKEN_VALUE[c] for c in p.techs if KIND[c] == kind)


def food(p) -> int:
    return total(p, "farm")


def resources(p) -> int:
    return total(p, "mine")


def _configs(values: tuple, target: int, i: int = 0):
    """Every token count vector over `values` (descending) whose value is exactly target."""
    if i == len(values) - 1:
        v = values[i]
        if target % v == 0:
            yield (target // v,)
        return
    v = values[i]
    for k in range(target // v, -1, -1):
        for rest in _configs(values, target - k * v, i + 1):
            yield (k,) + rest


def _feasible(orig: tuple, final: tuple, values: tuple) -> bool:
    """Can `final` token counts come from `orig` by returning tokens, moving tokens to lower-value cards and taking
    change (smaller tokens) from the bank (T12.3)? Tokens never move to a higher-value card."""
    pool = []                                   # spare value of tokens broken into smaller ones
    for i, v in enumerate(values):
        o, f = orig[i], final[i]
        keep = min(o, f)
        for _ in range(f - keep):
            best = -1
            for j, cap in enumerate(pool):
                if cap >= v and (best < 0 or cap < pool[best]):
                    best = j
            if best < 0:
                return False
            pool[best] -= v
        pool.extend([v] * (o - keep))
    return True


@lru_cache(maxsize=100000)
def plan_payment(values: tuple, orig: tuple, bank: int, amount: int):
    """T12.3, choice C1. Final token counts after paying `amount`. Tokens are returned to the bank, moved to a
    lower-value card (the token itself moves, paying the difference: no bank token needed) or broken into smaller
    tokens with change taken from the blue bank (each extra token comes from the bank).
    - Exact payment when possible, returning the most tokens to the bank, ties keeping higher-value tokens.
    - Otherwise paying more is allowed only if the payment leaves the blue bank empty (all bank tokens taken as
      change); the smallest such overpayment. None when the total is too low."""
    have = sum(v * c for v, c in zip(values, orig))
    if have < amount:
        return None
    n = sum(orig)
    best = None
    for f in _configs(values, have - amount):                     # exact payments
        nf = sum(f)
        if nf > n + bank or not _feasible(orig, f, values):
            continue
        key = (nf, tuple(-x for x in f))
        if best is None or key < best[0]:
            best = (key, f)
    if best is not None:
        return best[1]
    for target in range(have - amount - 1, -1, -1):              # overpay: bank must end empty (nf = n + bank)
        for f in _configs(values, target):
            if sum(f) == n + bank and _feasible(orig, f, values):
                return f
    for target in range(have - amount - 1, -1, -1):              # defensive (not reachable with a value-1 card)
        for f in _configs(values, target):
            if sum(f) <= n + bank and _feasible(orig, f, values):
                return f
    return tuple(0 for _ in values)


@lru_cache(maxsize=100000)
def plan_gain(values: tuple, bank: int, amount: int) -> tuple:
    """T12.2: tokens to add for gaining `amount` with as few tokens as possible from a bank of `bank` tokens; if the
    bank cannot make it, the largest amount below it that it can make."""
    for target in range(amount, -1, -1):
        best = None
        for f in _configs(values, target):
            nf = sum(f)
            if nf <= bank and (best is None or nf < best[0]):
                best = (nf, f)
        if best is not None:
            return best[1]
    return tuple(0 for _ in values)


def _set_tokens(p, cards: list, counts: tuple) -> None:
    old = sum(p.tokens.get(c, 0) for c in cards)
    for c, k in zip(cards, counts):
        if k:
            p.tokens[c] = k
        else:
            p.tokens.pop(c, None)
    p.blue_bank += old - sum(counts)


def pay(p, kind: str, amount: int) -> int:
    """Pay food/resources (T12.3, choice C1). Returns the amount actually paid (more than asked only when exact
    change is impossible). The caller checked that the player can pay."""
    if amount <= 0:
        return 0
    cards = kind_cards(p, kind)
    values = tuple(TOKEN_VALUE[c] for c in cards)
    orig = tuple(p.tokens.get(c, 0) for c in cards)
    final = plan_payment(values, orig, p.blue_bank, amount)
    if final is None:
        raise ValueError(f"P{p.seat} cannot pay {amount} {kind}")
    _set_tokens(p, cards, final)
    return sum(v * (o - f) for v, o, f in zip(values, orig, final))


def lose(p, kind: str, amount: int) -> int:
    """Lose food/resources: like paying, but losing more than you have loses everything (T12.3). Returns the
    amount the player had to lose that was missing (0 when fully lost)."""
    if amount <= 0:
        return 0
    have = total(p, kind)
    if have >= amount:
        pay(p, kind, amount)
        return 0
    cards = kind_cards(p, kind)
    _set_tokens(p, cards, tuple(0 for _ in cards))
    return amount - have


def gain(p, kind: str, amount: int) -> int:
    """Gain food/resources (T12.2). Returns the amount gained."""
    if amount <= 0:
        return 0
    cards = kind_cards(p, kind)
    values = tuple(TOKEN_VALUE[c] for c in cards)
    add = plan_gain(values, p.blue_bank, amount)
    for c, k in zip(cards, add):
        if k:
            p.tokens[c] = p.tokens.get(c, 0) + k
    p.blue_bank -= sum(add)
    return sum(v * k for v, k in zip(values, add))


def produce(p, kind: str) -> int:
    """T12.6 / T12.8: one token per worker on each farm (mine); with too few tokens in the bank the highest levels
    are filled first. Returns the value produced."""
    out = 0
    for c in kind_cards(p, kind):
        k = min(p.workers.get(c, 0), p.blue_bank)
        if k:
            p.tokens[c] = p.tokens.get(c, 0) + k
            p.blue_bank -= k
            out += k * TOKEN_VALUE[c]
    return out


def produce_step(g, seat: int, kind: str) -> None:
    """Food ('farm') or resource ('mine') production of one player (T12.6, T12.8, T15.6): one token per worker, the
    extra tokens of Machu Picchu / Transcontinental Railroad on their farms and mines, then all production bonuses
    summed (gained, or lost if negative)."""
    p = g.s.players[seat]
    produce(p, kind)
    for c in effects.extra_token_cards(g, p, kind):
        if p.blue_bank > 0:
            p.tokens[c] = p.tokens.get(c, 0) + 1
            p.blue_bank -= 1
    bonus = production_bonus(g, seat, kind)
    if bonus > 0:
        gain(p, kind, bonus)
    elif bonus < 0:
        lose(p, kind, -bonus)


def production_bonus(g, seat: int, kind: str) -> int:
    """T15.6 production bonuses (symbols, texts, pacts) + Ashoka's bonus for the colours in the civil hand."""
    st = stats(g, seat)
    return (st.food_bonus if kind == "farm" else st.resource_bonus) + effects.hand_bonus(g, seat, kind)


def output(g, seat: int, kind: str, bonuses: bool = True) -> int:
    """Food or resource production of one player now: workers, extra tokens and (with `bonuses`) production
    bonuses."""
    p = g.s.players[seat]
    out = sum(p.workers.get(c, 0) * TOKEN_VALUE[c] for c in p.techs if KIND[c] == kind)
    out += sum(TOKEN_VALUE[c] for c in effects.extra_token_cards(g, p, kind))
    return out + (production_bonus(g, seat, kind) if bonuses else 0)


# ---------------------------------------------------------------------------------------------- points (T12.4)
def add_culture(p, amount: int, category: str, card=None) -> int:
    """Score (or lose, never below 0) culture points; books the actual change. Returns it."""
    if amount < 0:
        amount = -min(p.culture, -amount)
    if amount:
        p.culture += amount
        key = (category, card)
        p.culture_book[key] = p.culture_book.get(key, 0) + amount
    return amount


def add_science(p, amount: int) -> int:
    if amount < 0:
        amount = -min(p.science, -amount)
    p.science += amount
    return amount


def book_culture_rating(g, seat: int) -> int:
    """End-of-turn culture (T3.6): the culture rating, booked to its sources (PLAN C3). When the rating is clipped
    at 0 nothing is scored, so nothing is booked."""
    p = g.s.players[seat]
    st = stats(g, seat)
    if st.culture <= 0:
        return 0
    if sum(st.culture_parts.values()) != st.culture:
        add_culture(p, st.culture, "production", None)     # defensive: parts do not explain the rating
        return st.culture
    for c, x in st.culture_parts.items():
        if x:
            p.culture += x
            key = ("production", c)
            p.culture_book[key] = p.culture_book.get(key, 0) + x
    return st.culture

