# Zurich Zebras Ottoneu Optimizer

A daily lineup optimization and backtesting framework for four Ottoneu teams in League 1077. Maximizes 5x5 Roto efficiency by projecting daily player performance from real-time matchups, StatCast peripherals, and historical BvP data.

## 🚀 Quick Start

### 1. Installation
```bash
uv sync
```

### 2. Prepare Data (once per day)
Fetch StatCast datasets, projections, and resolve player ID crosswalk:
```bash
uv run python fetch_statcast.py
uv run python build_crosswalk.py
```

### 3. Generate Today's Optimal Lineup
```bash
uv run python main.py
```

### 4. Evaluate Starting Pitchers
```bash
uv run python pitcher_optimizer.py
```

---

## 🧪 Backtesting & Algorithm Validation

These tools run manually against historical data to evaluate and tune the scoring algorithm. They are not part of the automated daily pipeline.

### `backtester.py` — Single-Date Hitter Simulation
Runs the optimizer against a past date and compares the recommended lineup to actual MLB box scores. Useful for spot-checking algorithm decisions and validating that start/bench calls were correct.

```bash
uv run python backtester.py 2025-07-04
uv run python backtester.py 2025-07-04 --projection atc
```

Output includes: predicted score vs actual 5x5 production for each started and benched player, with live game status if run against today.

### `pitcher_backtester.py` — Single-Date Pitcher Simulation
Same concept applied to starting pitchers — compares projected pitcher efficiency scores to actual K, ERA, and WHIP results for a given date.

```bash
uv run python pitcher_backtester.py 2025-07-04
```

### `batch_backtester.py` — Season-Wide Accuracy Audit
Runs 50 randomly sampled dates from the 2025 season and aggregates start/bench accuracy across all five Roto categories (R, HR, RBI, SB, AVG). Produces a summary of how often the algorithm started the more productive player.

```bash
uv run python batch_backtester.py                    # 50 random dates, Steamer
uv run python batch_backtester.py --projection atc   # same with ATC
```

Use this before and after tuning multipliers in `config.py` to measure whether a change improves aggregate accuracy.

---

## 🚀 Projection System Selection

The optimizer supports two projection baselines, toggled with `--projection`:

- **Steamer (`--projection steamer`)**: Default. Aggressive on breakout candidates.
- **ATC (`--projection atc`)**: Ariel Theoretical Composite. Weighted average of multiple systems; reduces outlier variance.

```bash
uv run python main.py --projection atc
uv run python backtester.py --projection atc
uv run python batch_backtester.py --projection atc
uv run python scout.py --projection atc
```

---

## 🧠 The Zebras Algorithm (V3)

### Hitter Efficiency

A hitter's daily score starts from their full-season projection, scaled to per-game:

```
Base Score = ((R + HR + RBI + SB × 1.5) / PA × 100) + (AVG × 89)
```

- SB weighted **1.5×** for category scarcity
- AVG coefficient **89** = consistent H/PA denominator (AVG × 0.89 AB/PA)

Context-aware multipliers are then applied. The **total multiplier is capped at +35% / −30%** to prevent compounding extremes.

| Factor | Condition | Impact |
| :--- | :--- | :--- |
| **Batting Order** | Position 1–9 | **+10% to −9%** |
| **SP Skill** | ERA-based, 4.00 neutral | **±20% max** |
| **Dynamic Platoon** | Career OPS vs LHP/RHP (MLB API) | **±15% max** |
| **Static Platoon** | Fallback when splits unavailable | **+7% / −3% to −10%** |
| **BvP** | Career OPS vs this SP (min **25 PA**) | **±3% to ±8%** |
| **Park Factor** | Statcast venue run environment | **varies** |
| **Wind Out** | ≥10 MPH blowing out | **+5% to +10%** |
| **Wind In** | ≥10 MPH blowing in | **−5% to −10%** |
| **SB Environment** | Sprint speed ≥27.5 ft/s only | **±2–4%** |
| **xwOBA / Barrel%** | Elite thresholds | **Informational only** |
| **Total cap** | All factors combined | **+35% / −30%** |

### Pitcher Efficiency (V1)

```
PitcherScore = BaseScore × Park × Weather × StatCast × Agg BvP × Opp Power
```

Base Score: `(K/9 × 0.4) + (5.0 − ERA) + (1.5 − WHIP) × 2.0`

### Lineup Pending Logic

When a team hasn't posted its official lineup:
- Player marked **"Pending"** with order displayed as **"X\*"**
- Historical last-started batting position is used
- Appropriate order multiplier applied; fallback is #5

---

## 📊 Score Tiers

#### Hitter Tiers
| Score | Color | Tier |
| :--- | :--- | :--- |
| **90+** | Green | Elite — top hitter, weak pitcher, hitter's park |
| **60–89** | Sky/Blue | Strong play |
| **40–59** | Yellow | Marginal — starts only if no better option |
| **< 40** | Muted | Below Zebras Floor — benched to preserve game caps |

#### Pitcher Tiers
| Score | Tier |
| :--- | :--- |
| **7.0+** | Elite start |
| **5.0–6.5** | Strong start |
| **3.0–4.5** | Streamer / baseline |
| **< 2.5** | Avoid |

---

## 🔑 Player ID Crosswalk

All downstream processes (daily engine, StatCast lookups, future Baseball Savant enrichment) rely on a pre-built FGID → MLB ID crosswalk, stored in `player_id_crosswalk.json`.

```bash
uv run python build_crosswalk.py             # resolve new/unknown players only
uv run python build_crosswalk.py --force     # re-resolve all (use after trade deadline)
uv run python build_crosswalk.py --report    # inspect current contents
```

The crosswalk is rebuilt daily by GitHub Actions before the optimizer runs.

---

## 🔍 Free Agent Scouting

These tools help identify roster upgrade opportunities within League 1077. They run manually on demand and are not part of the automated pipeline.

### `scout_harvester.py` — Refresh Free Agent Pool
Fetches all available free agents in League 1077 from the FanGraphs API and saves them to `free_agents.json`. Run this first before using the scout.

```bash
uv run python scout_harvester.py
```

### `scout.py` — Rank Available Free Agents
Loads the free agent pool, projects each player using the Zebras efficiency score, enriches with StatCast metrics, and ranks by projected value. Use this to find pickups your current roster is missing.

```bash
uv run python scout.py --pa 50                   # min 50 PA (filters out small samples)
uv run python scout.py --pa 30 --projection atc  # ATC projections, lower PA floor
```

### `fa_backtester.py` — Audit Free Agent Performance
For a given historical date, fetches all free agents, projects them using the daily engine, and compares projections to actual box score results. Useful for identifying which free agents the algorithm would have correctly flagged as high-value adds.

```bash
uv run python fa_backtester.py 2025-07-04
```

> **Note:** A dedicated scouting web front-end is planned — see `TODO.md`. The goal is a separate dashboard that surfaces free agent opportunities using advanced StatCast metrics (xwOBA, barrel rate, sprint speed, hard-hit rate) beyond what the daily optimizer exposes.

---

## 🌐 Automated Web Dashboard

Zero-cost static dashboard hosted on GitHub Pages.

**Features:** Multi-projection toggle (ATC / Steamer), Today / Tomorrow views, pitcher cards, AI analyst (Google Gemini), live game status. Lineup scores are color-coded by tier (green / sky / yellow). Each player's score breakdown is displayed as color-coded chips — green for positive multipliers, red for penalties, slate for informational context. Fully responsive: card layout on mobile, table on desktop.

**Architecture:**
- **Daily (4 AM UTC)**: `fetch_statcast.py` → `build_crosswalk.py` → `update_web_data.py --skip-ai` → deploy to gh-pages
- **Hourly (8 AM–9 PM ET)**: `update_web_data.py` → deploy to gh-pages

**Local development:**
```bash
uv run python update_web_data.py --skip-ai
python -m http.server 8000
# open http://localhost:8000
```

---

## 🛠 Project Structure

| File | Purpose |
| :--- | :--- |
| `main.py` | Entry point — daily hitter optimization |
| `pitcher_optimizer.py` | Entry point — daily pitcher optimization |
| `update_web_data.py` | Generate all team/projection JSON views |
| `build_crosswalk.py` | Pre-build FGID → MLB ID crosswalk for all teams |
| `fetch_statcast.py` | Fetch StatCast datasets and projections |
| `daily_engine.py` | Hitter scoring: applies daily multipliers |
| `pitcher_daily_engine.py` | Pitcher scoring: applies matchup multipliers |
| `enricher.py` | Maps roster to projection systems; calculates base score |
| `pitcher_enricher.py` | Maps pitchers to projection systems |
| `optimizer.py` | SciPy linear programming solver (13 slots) |
| `harvester.py` | Ottoneu roster scraper (FanGraphs links, IsMinors) |
| `gameday_harvester.py` | MLB Stats API: lineups, BvP, ID resolution, statuses |
| `statcast_harvester.py` | Local lookup for cached StatCast metrics |
| `weather_harvester.py` | Real-time wind/rain from Rotowire |
| `park_factors.py` | Numerical venue multipliers for all 30 parks |
| `crosswalks.py` | Team abbreviation mappings (Ottoneu ↔ MLB API) |
| `config.py` | All scoring constants and multiplier bounds |
| `backtester.py` | Single-date hitter simulation: predicted lineup vs actual box scores |
| `pitcher_backtester.py` | Single-date pitcher simulation: projected vs actual results |
| `batch_backtester.py` | Season-wide accuracy audit across 50 random dates |
| `fa_backtester.py` | Free agent backtest: project FA pool vs actual results for a date |
| `scout.py` | Rank available free agents by Zebras efficiency score |
| `scout_harvester.py` | Fetch current free agent pool from FanGraphs API |
| `TODO.md` | Feature backlog |

---

*Built for the 162-game grind. Efficiency is the only metric that matters.*
