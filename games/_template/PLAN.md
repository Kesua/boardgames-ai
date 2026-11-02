# <Game name> — engine plan (plan-engine skill)

1. Kit parts used, and why any part is not used
2. State (plain data, so clone() is a pickle)
3. Turn flow as decisions (kind, deciding seat, answers)
4. Action numbering (CodecBuilder segments)
5. Optional vs mandatory, per decision
6. Effects: one handler per effect type; timing order
7. Scoring: breakdowns() categories, tiebreaks(), tableau() rows; scores are higher-is-better
8. What the agent observes (encoder): private, public, hidden
9. Recording: record_info fields; forced moves (drain_forced)
10. Game length: fixed or variable
11. Risks: the rules most likely to be implemented wrong and how each is tested
