# Standard shapes for game-specific statistics

A game's `summary.py` returns `{section_key: shape}`; the dashboard draws every shape without game code. All text is
keys into the game's `i18n/<lang>.json` → `"sections"`. Numbers are plain JSON numbers.

| Shape | Fields | Drawn as |
|---|---|---|
| `table` | `columns: [{key, label, format}]`, `rows: [...]`, optional `bars: {x, series: [keys]}` | optional grouped columns, then the table |
| `bars` | `x`, `x_format`, `bars` (count field), `line` (rate field), `line_format`, `baseline`, `x_label`, `bar_label`, `line_label`, `rows` | the rate as bars around the baseline (one axis); counts listed below; groups under 20 hidden and named |
| `grid` | `x_edges`, `y_edges`, `counts[x][y]`, `x_label`, `y_label` | count heatmap (sequential blue) |
| any | `title`, `note`, optional `facts: [{label, value, format}]` | heading, explanation, number tiles |

Formats: `pct` (0.123 → 12.3 %), `pp` (win lift, ±), `int`, `num1`, `num2`, `decile` (group 3 → 30–40 %), `plus3`
(3 → "3+"), `text` (as is), `label` (a section key), `category` (a score category from the manifest).
A `pp` column may carry `<key>_se` in each row; the table shows ± 2 standard errors.
Never put two different measures on two y-axes; show the second measure as a table, facts or a second section.
