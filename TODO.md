# Zurich Zebras Optimizer — Feature Backlog

---

## 🔍 Free Agent Scouting Dashboard (Major Initiative)

A separate web front-end and backend pipeline focused entirely on identifying
roster upgrade opportunities. Distinct value proposition from the lineup optimizer:
the optimizer answers "who do I start today?" — the scout answers "who should I
add to my roster?"

### What it needs to do
- Surface all available free agents in League 1077, ranked by long-term Roto value
- Enrich each player with advanced StatCast metrics beyond what projections capture:
  exit velocity, xwOBA, barrel rate, hard-hit rate, sprint speed, K% and BB% trends
- Show trajectory signals — is a player trending up or down relative to projection?
  (current-season StatCast vs prior-season baseline, same recency blending logic)
- Flag players whose underlying quality (xwOBA, barrel rate) significantly outpaces
  their projection — a key signal for breakout candidates being undervalued
- Filter by position eligibility, handedness, upcoming schedule strength

### Data pipeline
- Extend `player_id_crosswalk.json` to cover free agents (not just rostered players)
- `scout_harvester.py` already fetches the FA pool from FanGraphs API
- `statcast_harvester.py` already has cached per-player StatCast data keyed by MLB ID
- New `scout_engine.py` to compute a composite "Acquisition Value" score
- New JSON output (e.g., `scout_data.json`) deployed to gh-pages on a daily schedule

### Frontend
- Separate `scout.html` page linked from the main dashboard
- Filterable, sortable table: position, hand, team, upcoming schedule tier
- Player detail cards: projection vs StatCast quality, trend sparkline, 3-day history
- Highlight "hidden gem" tier: players with elite StatCast but modest projection

### Key StatCast signals for acquisition value (not just daily context)
| Metric | Why it matters |
| :--- | :--- |
| xwOBA (season) | Best single-number contact quality indicator |
| Barrel rate | Power upside signal independent of HR luck |
| Hard-hit rate (95+ mph) | More stable than barrel rate at smaller samples |
| Sprint speed | SB ceiling; correlates with IF hit rate too |
| Chase rate / whiff rate | Plate discipline sustainability signal |
| xBA − BA | Positive = due for average regression upward |
| xSLG − SLG | Positive = power being suppressed by sequencing |

---

Items here are not yet designed or scoped. They represent directions worth exploring,
roughly ordered by expected impact within each section.

---

## StatCast / Baseball Savant Data Enrichment

Now that `player_id_crosswalk.json` provides a reliable MLB ID for every Ottoneu
roster player, these Savant endpoints can be added to `fetch_statcast.py` and
consumed by the daily engine.

- [ ] **Sprint speed by season** — already partially used; pull per-season data so
      the recency blending curve applies to speed the same way it does to xwOBA
- [ ] **Barrel rate by season** — add as a minor scoring signal for power hitters;
      currently informational only, could justify a small multiplier once backtested
- [ ] **Catch probability / OAA (Outs Above Average)** — defensive metric for
      outfielders; useful for DFS-style context, less relevant for Roto
- [ ] **Expected stats by count** — xBA, xSLG, xwOBA split by ball-strike count;
      could inform BvP-style adjustments when pitcher is a high-strikeout arm
- [ ] **Hard-hit rate / exit velocity** — complement to barrel rate; useful for
      identifying hitters making loud contact even without HR results
- [ ] **Chase rate / whiff rate** — contact quality context for hitters facing
      high-swing-and-miss pitchers; could strengthen the opposing pitcher modifier
- [ ] **Pop time by season** — already used; extend to pull historical seasons
      rather than just current year

---

## Backtesting Framework

Agreed during algorithm review: implement a rigorous backtest before making further
multiplier tuning decisions.

- [ ] **Historical lineup simulator** — given a past date and roster state, run the
      engine and compare recommended lineup to actual production
- [ ] **Multiplier sensitivity analysis** — vary one multiplier at a time (±10%)
      and measure impact on start/bench accuracy across a full season
- [ ] **Factor attribution** — for each factor (platoon, BvP, order, park, weather),
      measure its independent contribution to prediction lift
- [ ] **Head-to-head vs. flat projection baseline** — how much does the daily engine
      improve over just starting whoever has the highest raw projection score?
- [ ] **Cross-projection-system agreement** — flag players where STEAMER and ATC
      disagree significantly; these are high-uncertainty starts

---

## Player ID Crosswalk Improvements

- [ ] **Trade handling** — detect when a player's team on Ottoneu differs from the
      crosswalk's stored team; flag for re-resolution rather than serving stale data
- [ ] **Name change / alias table** — maintain a small manual override table for
      players whose legal name differs from their common name (e.g., accents, Jr./Sr.)
- [ ] **FGID-less player handling** — some minor leaguers have no FanGraphs link on
      Ottoneu; fall back to a name+team+DOB fingerprint for stable identification
- [ ] **Crosswalk health report in CI** — after `build_crosswalk.py` runs, emit a
      summary of unresolved players as a workflow annotation so failures are visible

---

## Scoring Algorithm

- [ ] **Refactor SB environment to apply only to the SB term** — currently the
      catcher pop time and pitcher hold multipliers apply to the full score; the
      correct fix is to adjust only the SB component of the base formula
- [ ] **Pitcher fatigue / rest days** — factor in days since last outing and pitch
      count from most recent start; a pitcher on 3 days rest is meaningfully different
- [ ] **Ballpark-specific platoon splits** — some parks amplify handedness effects
      (e.g., short porches); could extend park factors to be split-aware
- [ ] **Relief pitcher context** — if a team's bullpen is elite/poor, adjust SP score
      downward/upward slightly for expected inherited run context

---

## Roster & Lineup Intelligence

- [ ] **Injury report integration** — pull MLB injury transactions daily so IL moves
      appear in the optimizer before Ottoneu processes them
- [ ] **Day-of-game scratch detection** — watch for late lineup changes posted to
      the MLB API and re-run the optimizer if a key starter is scratched
- [ ] **Multi-day outlook** — surface players whose next 3-day schedule is
      particularly favorable or unfavorable (opponent quality, park, weather trend)

---

## Infrastructure

- [ ] **Crosswalk included in hourly workflow** — currently only rebuilt daily;
      consider a lightweight "verify and patch" step in the hourly run for same-day
      call-ups that wouldn't appear until the next daily refresh
- [ ] **Structured logging to JSON** — machine-readable run logs would make it easier
      to detect patterns in resolution failures across runs
