"""Game state as plain data (PLAN.md section 2): clone() is a pickle, so no functions, sets or open handles here.
Sets are avoided on purpose (iteration order of str sets changes between processes); lists keep entry order."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bgai.kit import DecisionStack, Deck, TextLog

from .cards import AGRICULTURE, BRONZE, DESPOTISM, PHILOSOPHY, RELIGION, WARRIORS

ROW_SIZE = 13
LEADER_PROXY = 1000          # civil deck entry 1000 + k: leader proxy k (T15.9); 2000 + k: wonder proxy k
WONDER_PROXY = 2000


@dataclass
class Player:
    seat: int
    # banks and workers (T1.5, T2.3)
    blue_bank: int = 16
    yellow_bank: int = 18
    pool: int = 1                                   # unused workers
    blue_owned: int = 16                            # blue tokens this player owns (bank + cards + wonder): conservation
    yellow_owned: int = 25                          # yellow tokens (bank + pool + workers)
    workers: dict = field(default_factory=dict)     # card -> workers (farm, mine, urban, unit technologies)
    tokens: dict = field(default_factory=dict)      # card -> blue tokens (food on farms, resources on mines)
    # cards in play
    techs: list = field(default_factory=list)       # farm/mine/urban/unit technologies, entry order
    government: int = DESPOTISM
    specials: dict = field(default_factory=dict)    # special kind -> card
    leader: Optional[int] = None
    leaders_taken: list = field(default_factory=list)   # ages of leaders taken (T4.5)
    wonders: list = field(default_factory=list)     # completed wonders, entry order
    ruined: list = field(default_factory=list)      # ruined wonders (Ravages of Time, stage 2)
    unfinished: Optional[list] = None               # [card, stages paid, blue tokens on it]
    colonies: list = field(default_factory=list)
    tactic: Optional[int] = None                    # the tactic the marker is on (own exclusive or common), T6.4
    exclusive_tactic: Optional[int] = None          # tactic played on this or the previous turn, in own area (T3.3)
    pact: Optional[list] = None                     # own-area pact [card, partner seat, owner side "A"/"B"/None]
    wars: list = field(default_factory=list)        # declared wars [card, target seat] (T9.4)
    forfeit_politics: int = 0                       # political actions given up (International Agreement)
    hand_at_resign: Optional[list] = None           # civil + military hand when resigning (seat_extra)
    play_order: list = field(default_factory=list)  # every card in play that has symbols or effects, entry order
    left_play: list = field(default_factory=list)   # leaders and wonders that left play (kept for the tableau)
    # hands
    civil_hand: list = field(default_factory=list)
    military_hand: list = field(default_factory=list)
    taken_this_phase: list = field(default_factory=list)   # T5.10
    # actions (T11.6): only spent counts are stored, totals come from the cards in play
    civil_spent: int = 0
    military_spent: int = 0
    temp_civil: int = 0
    temp_military: int = 0
    temp: dict = field(default_factory=dict)        # purpose -> temporary food/resources/science (T12.9)
    # points
    science: int = 0
    culture: int = 0
    culture_book: dict = field(default_factory=dict)    # (category, card|None) -> culture points (PLAN section 7)
    flags: dict = field(default_factory=dict)       # per-turn flags, cleared at the end of the turn
    resigned_order: Optional[int] = None
    ver: int = 0                                    # bumped on every change the statistics depend on
    # civil card states (stage 3)
    used: list = field(default_factory=list)        # once-per-game abilities used (Catherine, Coubertin)
    reminders: int = 0                              # Hippocrates' yellow reminders above the government (box tokens)
    homer_wonder: Optional[int] = None              # completed wonder Homer is tucked under (+1 happy face)
    louvre_tokens: int = 0                          # blue tokens kept on the Louvre (owned, not resources)
    saladin: Optional[int] = None                   # Saladin's mode: 0 = +2 strength, 1 = +1 civil action
    kept_tactics: list = field(default_factory=list)    # Sun Tzu: replaced exclusive tactics kept in own area
    tactic_boost: Optional[int] = None              # marker on Sun Tzu's marked tactic (this id): +1 per army
    peek: Optional[list] = None                     # Ian Fleming: [seat, its military hand when looked at]
    fleming_last: Optional[int] = None              # Ian Fleming: the player looked at on the previous turn

    @staticmethod
    def new(seat: int) -> "Player":
        p = Player(seat)
        # T1.5 / T2.3: printed starting technologies and the 6 starting workers
        p.techs = [AGRICULTURE, BRONZE, PHILOSOPHY, RELIGION, WARRIORS]
        p.workers = {WARRIORS: 1, AGRICULTURE: 2, BRONZE: 2, PHILOSOPHY: 1, RELIGION: 0}
        p.play_order = [DESPOTISM, AGRICULTURE, BRONZE, PHILOSOPHY, RELIGION, WARRIORS]
        return p


@dataclass
class State:
    players: list
    start_seat: int
    age: str = "A"
    round: int = 0                                  # current round (1-based); after the game: rounds played
    turn_seat: int = 0
    turns: int = 0                                  # turns completed, all players together
    last_round: Optional[int] = None
    round_first: int = 0                            # first seat of the current round (T14.1 with resignations)
    phase: str = "setup"                            # start / politics / actions / end
    row: list = field(default_factory=lambda: [None] * ROW_SIZE)
    civil_deck: Deck = field(default_factory=Deck)
    military_deck: Deck = field(default_factory=Deck)
    military_discard: list = field(default_factory=list)     # current age only (T6.5, D7)
    age_a_unused: list = field(default_factory=list)          # Age A military cards set aside (T2.5)
    current_events: list = field(default_factory=list)        # [card, preparer|None(, known_by, peeked_by)], 0 = top
    future_events: list = field(default_factory=list)
    past_events: list = field(default_factory=list)
    common_tactics: list = field(default_factory=list)
    resolving: list = field(default_factory=list)             # military cards being resolved (events, attacks)
    game_end_eval: bool = False                               # T14.2 evaluation running (ties: starting player)
    selection: dict = field(default_factory=dict)             # age -> {"leaders": [...], "wonders": [...]} (T15.4)
    removed_civil: list = field(default_factory=list)         # civil cards that left the game
    removed_military: list = field(default_factory=list)
    civil_created: int = 0                                    # physical civil cards put into decks so far
    military_created: int = 0
    proxies_created: int = 0
    proxies_used: int = 0
    resigned: int = 0
    nobel_prize: Optional[int] = None                         # Alfred Nobel beside the culture track (card id)
    olympics: Optional[list] = None                           # [owner seat, Coubertin card] while the Games run
    sun_tzu_tactic: Optional[list] = None                     # [tactic Sun Tzu lies under, seat whose exclusive
                                                              #  tactic it still is | None once common] (D32)
    tasks: list = field(default_factory=list)
    decisions: DecisionStack = field(default_factory=DecisionStack)
    log: TextLog = field(default_factory=TextLog)
    forced: list = field(default_factory=list)
    game_over: bool = False
