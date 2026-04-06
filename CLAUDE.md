# Zurich Zebras Optimizer — Project Context for Claude

## Role
Claude is project manager and lead developer for this codebase. John (the user) is the owner and domain expert. See `memory/MEMORY.md` for persistent context about John's preferences and past decisions.

---

## What This Project Does

Daily lineup optimizer for four Ottoneu Daily 5x5 Roto teams in League 1077:

| Team ID | Name |
| :--- | :--- |
| 7582 | Zurich Zebras (primary) |
| 7587 | Ghost Ride the WHIP |
| 7581 | Austin Waves |
| 7641 | LawDog |

The system scrapes Ottoneu rosters, enriches them with ATC/Steamer projections, applies context-aware daily multipliers (matchup, park, weather, platoon, BvP, batting order), and solves a linear programming problem to select the optimal 13-slot lineup. Output is JSON deployed to GitHub Pages via Actions.

---

## Architecture

```
Ottoneu Roster (harvester.py)
    ↓ FGID extraction
build_crosswalk.py → player_id_crosswalk.json   ← MLB IDs for all players, all teams
    ↓
fetch_statcast.py → projections-steamer.json
                  → projections-atc.json
                  → statcast_*.json
    ↓
enricher.py         ← merges roster + projections → base Score
    ↓
daily_engine.py     ← applies daily multipliers (projection-system-agnostic ID resolution)
    ↓
optimizer.py        ← SciPy LP solver, 13 slots
    ↓
update_web_data.py  → lineup_TEAMID_{steamer|atc}_{today|tomorrow}.json
                    → pitchers_TEAMID_{steamer|atc}_{today|tomorrow}.json
```

**Key invariant**: MLB ID resolution in `daily_engine.py` uses only the Ottoneu roster (Name + Team + FGID). It never reads `xMLBAMID` from projections. A player's roster status is independent of which projection system is loaded.

---

## Player ID Resolution Chain

`gameday_harvester.GameDayHarvester.get_mlb_id()` resolves in this order:

1. **FGID crosswalk** (`player_id_crosswalk.json`) — instant, most reliable
2. **MLB Stats API name search** (`statsapi.lookup_player`) + **`_team_matches()`** team verification — checks both `currentTeam.id` and `currentTeam.parentOrgId` (catches minor leaguers in parent org system)
3. **MiLB sport ID fallback** — repeats search across sport IDs 11–16 (AAA→Rookie) with same team verification
4. **Pybaseball fallback** — last resort, no team verification; picks most recently active player

**Critical**: Always run `_team_matches()` when `team_abb` is provided, even for single results. `statsapi.lookup_player("luis pena")` returns Luis Severino (nickname "Peña") as a false positive. Team verification catches this.

**`OTTONEU_TO_MLB`** in `crosswalks.py` is an explicit dict (not auto-reversed) — important because several Ottoneu abbreviations map to different MLB Stats API abbreviations (SFG→SF, CHW→CWS, KCR→KC, etc.).

---

## Hitter Scoring (V3 Algorithm)

### Base Score
```
((R + HR + RBI + SB × 1.5) / PA × 100) + (AVG × 89)
```
- SB × 1.5: category scarcity in 5x5 Roto
- AVG × 89: consistent H/PA denominator (AVG × 0.89 AB/PA ratio)

### Daily Multipliers (applied in `daily_engine._process_daily_multipliers`)
All multipliers compound multiplicatively. Total is capped at **+35% / −30%** before final score.

| Factor | Constants | Notes |
| :--- | :--- | :--- |
| Batting order | `ORDER_MULTIPLIERS` | ±10% spread (1→+10%, 9→−9%) |
| SP skill (ERA-based) | `ERA_FACTOR_MIN/MAX = 0.80/1.20`, neutral = 4.00 | |
| Dynamic platoon | Career OPS vs LHP/RHP from MLB API | Preferred over static |
| Static platoon | `PLATOON_ADVANTAGE_BONUS=1.07`, `PLATOON_LL=0.90`, `PLATOON_RR=0.97`, `SWITCH=1.03` | Fallback only |
| BvP | Min **25 PA**; ±3–8% | Reduced from old ±15% |
| Park factor | `park_factors.get_park_multiplier()` | |
| Wind | `WIND_SPEED_MODERATE=10`, `WIND_SPEED_STRONG=20` | ±5–10% |
| SB environment | Sprint speed gated (≥27.5 ft/s); `SB_CATCHER_MULT=0.02`, `SB_PITCHER_MULT=0.04` | Small; applies to full score not just SB term — known debt, see TODO.md |
| xwOBA / Barrel% | Informational only — no multiplier | Double-counting risk with projections |
| Compounding cap | `DAILY_MULT_MAX=1.35`, `DAILY_MULT_MIN=0.70` | Applied before final score |

**Removed in V3**: Superstar Shield (xwOBA floor protection), heat penalty, xwOBA/Barrel% score multipliers.

### Minors Detection
Step 2 in scoring loop: checks `mlb_statuses[mlb_id]['is_minors']` from `get_player_statuses()`.
Step 2b fallback: `row.get('IsMinors') is True` from Ottoneu roster (only fires if `mlb_id` is None).
Step 3: active roster check — if team is playing, player not in matchups, and not confirmed MLB, flag as minors.

---

## Pitcher Scoring (V1 Algorithm)

```
PitcherScore = BaseScore × Park × Weather × StatCast × Agg BvP × Opp Power
```
Base: `(K/9 × 0.4) + (5.0 − ERA) + (1.5 − WHIP) × 2.0`

---

## Recency Blending (StatCast)

| Month | Prior Season | Current Season |
| :--- | :--- | :--- |
| April | 100% | 0% |
| May | 70% | 30% |
| June | 40% | 60% |
| July+ | 0% | 100% |

Controlled by `config.RECENCY_WEIGHTS` and `get_recency_weight(target_date)`.

---

## Execution Order (Important)

In `update_web_data.py`, jobs are ordered **STEAMER before ATC** for each team and date. This matters because STEAMER often resolves MLB IDs that ATC can't (some players absent from ATC projections). Once STEAMER populates the crosswalk, ATC reads it.

```python
hitter_jobs = [
    ("steamer", today, ...),
    ("atc",     today, ...),
    ("steamer", tomorrow, ...),
    ("atc",     tomorrow, ...),
]
```

---

## GitHub Actions

Two workflows in `.github/workflows/`:

**`daily_refresh.yml`** (4 AM UTC):
1. Checkout `*.json` from gh-pages (feeds `fetch_if_missing` in fetch_statcast.py)
2. `fetch_statcast.py` — projections + StatCast datasets
3. `build_crosswalk.py` — resolve MLB IDs for all roster players
4. `update_web_data.py --skip-ai` — lineup JSON
5. Deploy to gh-pages

**`hourly_optimizer.yml`** (hourly, 8 AM–9 PM ET):
1. Checkout `*.json` from gh-pages (includes crosswalk)
2. `update_web_data.py` — lineup JSON + AI narrative
3. Deploy to gh-pages

Both workflows share `concurrency: group: gh-pages-deploy` to prevent race conditions.

---

## Key Files

| File | Role |
| :--- | :--- |
| `config.py` | **Single source of truth** for all scoring constants. Change values here, not in engine code. |
| `player_id_crosswalk.json` | FGID → MLB ID map. Built by `build_crosswalk.py`, read by `gameday_harvester.py`. |
| `projections-steamer.json` | Steamer full-season projections |
| `projections-atc.json` | ATC full-season projections |
| `crosswalks.py` | Team abbreviation mappings. `OTTONEU_TO_MLB` is an explicit dict — do not auto-reverse. |
| `TODO.md` | Feature backlog |

---

## Operational Commands

```bash
# Daily data prep
uv run python fetch_statcast.py
uv run python build_crosswalk.py
uv run python build_crosswalk.py --force     # after trade deadline
uv run python build_crosswalk.py --report    # inspect crosswalk

# Run optimizer
uv run python main.py
uv run python main.py --projection atc
uv run python pitcher_optimizer.py

# Generate all team JSON (web dashboard)
uv run python update_web_data.py --skip-ai

# Backtesting
uv run python backtester.py 2025-07-04
uv run python pitcher_backtester.py 2025-07-04
uv run python batch_backtester.py

# Free agent scouting
uv run python scout.py --pa 50
uv run python fa_backtester.py 2025-07-04

# Local web server
python -m http.server 8000
```

---

## Design Decisions & Pitfalls

- **Do not use `xMLBAMID` from projections for MLB ID resolution.** It works for STEAMER but breaks for ATC and any player absent from projections. Always use `get_mlb_id()` with the roster FGID.
- **`_id_crosswalk` is a class-level variable** on `GameDayHarvester`. All instances share it within a process. This is intentional — STEAMER's resolved IDs are immediately available to ATC.
- **`OTTONEU_TO_MLB` must remain an explicit dict.** Auto-reversing `MLB_TO_OTTONEU` produces wrong mappings where multiple MLB abbreviations point to the same Ottoneu code (SFG→SF vs SFN→SFG).
- **Single-result `statsapi.lookup_player` results are NOT trusted unconditionally.** `_team_matches()` must run when `team_abb` is provided. Severino's nickname "Peña" causes false positives on "luis pena" searches.
- **`DO_NOT_SIT`** in `config.py` lists players who should never be benched when starting in MLB (keyed by team_id). Update when the roster changes.
