# Zurich Zebras (Ottoneu Team 7582) Optimizer - Project Status

## 1. System Architecture
The optimizer is a multi-stage pipeline designed for **Daily 5x5 Roto Efficiency** maximization.

- **Harvester (`harvester.py`)**: Scrapes the official Ottoneu team page to get the live 40-man roster, team affiliations, and positional eligibility.
- **Enricher (`enricher.py`)**: Fetches season-long Steamer projections and calculates a baseline "Efficiency Score" (Counting Stats per PA + AVG).
- **StatCast Harvester (`statcast_harvester.py`)**: Downloads and parses full MLB datasets for advanced metrics (xwOBA, Barrel%, xERA, SIERA).
- **Spring Harvester (`spring_harvester.py`)**: Fetches live 2026 Spring Training hitter stats from FanGraphs for early-season scouting.
- **Park Factor Engine (`park_factors.py`)**: Provides a numerical lookup for all 30 MLB stadiums based on Statcast run-scoring environments.
- **Weather Harvester (`weather_harvester.py`)**: Scrapes real-time weather, wind, and rain risk from Rotowire.
- **GameDay Harvester (`gameday_harvester.py`)**: Interfaces with MLB Stats API to fetch real-time starting lineups, batting orders, opposing SP data, and historical BvP stats.
- **Daily Engine (`daily_engine.py`)**: The "Brain" of the operation. It applies dynamic multipliers (Platoon, Order, SP Skill, etc.) to the baseline score.
- **Optimizer (`optimizer.py`)**: A Linear Programming model (SciPy) that solves for the 13 most productive positional slots.
- **Backtester (`backtester.py`)**: A "Live Dashboard" tool to verify the algorithm against any date (defaults to Today). Now includes real-time game status and full 5x5 actual stats.
- **Batch Backtester (`batch_backtester.py`)**: Runs randomized simulations across the season to generate aggregate success rate reports.
- **Free Agent Scout (`scout.py`)**: Analyzes all available free agent hitters in League 1077 and ranks them by their Zebras Efficiency Score.

## 2. The "Zebras Algorithm" (Projection Logic)
The final `ProjScore` for a player on a given day is: 
`Baseline Score * [Park Factor] * [Pitcher Skill] * [Platoon Factor] * [Order Factor] * [BvP Factor] * [StatCast Boosts] * [Weather Factor]`

### Multipliers & Weights:
| Factor | Condition | Impact |
| :--- | :--- | :--- |
| **Order Factor** | Batting Order Position (1 to 9) | **0.85x to 1.15x** |
| **Park Factor** | Numerical lookup per stadium | **0.9x to 1.2x** |
| **Wind (Out)** | Speed >= 10 MPH blowing Out | **+5% to +10%** |
| **Wind (In)** | Speed >= 10 MPH blowing In | **-5% to -10%** |
| **Platoon** | Opposite Hand Matchup (L vs R) | **+10%** |
| **Platoon (L/L)** | Left-handed Batter vs Left-handed Pitcher | **-15%** |
| **Switch Hitter** | Always has platoon advantage | **+5%** |
| **SP Skill** | Linear scale: `1.0 + (xERA - 4.0)/4.0` | **0.7x to 1.3x** |
| **BvP Elite** | Career OPS > 1.000 vs SP (min 5 PA) | **+15%** |
| **xwOBA Elite** | Season xwOBA > .400 | **+10%** |
| **xwOBA Good** | Season xwOBA > .370 | **+5%** |
| **Barrel%** | Season Barrel% > 15% | **+5%** |

### Superstar Shield:
Elite players (xwOBA > .400) are protected from aggressive matchup-based penalties. Their `DailyScore` is prevented from dropping below **85% of their baseline score**, regardless of the opposing pitcher or park factor.

## 3. Recency Bias & Stabilization
The algorithm transitions from prior-season (2025) to current-season (2026) performance as sample sizes stabilize:
- **April**: **0% Current Year** (100% 2025 Baseline)
- **May**: **30% Current Year**
- **June**: **60% Current Year**
- **July+**: **100% Current Year**

## 4. Data Sources & Source of Truth
- **Roster**: `https://ottoneu.fangraphs.com/1077/team?team=7582`
- **Projections**: FanGraphs API (Steamer)
- **Advanced Metrics**: Baseball Savant / FanGraphs Leaderboards (JSON)
- **Weather**: Rotowire Weather Report
- **Live/Historical Games**: MLB Stats API (`statsapi.mlb.com`)

## 5. Operational Commands
- **Run Optimizer (Today)**: `uv run python main.py`
- **Run Live Dashboard (Today)**: `uv run python backtester.py`
- **Run Historical Backtest**: `uv run python backtester.py YYYY-MM-DD`
- **Find Free Agent Upgrades**: `uv run python scout.py --pa 50`
- **Harvest Spring Stats**: `uv run python spring_harvester.py`
- **Refresh StatCast Data**: `uv run python fetch_statcast.py`

## 6. Implementation Notes & Disambiguation
- **Efficiency Focus**: The core goal is to maximize stats *per slot*, adhering to the Ottoneu 162-game season cap.
- **Zebras Floor**: A minimum efficiency threshold (default: 40.0) that must be met to start a non-core player.
- **Narrative Logic**: Post-game summaries use a `TotalProd` (5x5 weighted) score to evaluate "Wins" and "Flops."
- **Live Status**: The backtester displays real-time game progress (e.g., "Top 7th", "Final") and live 5x5 stats.
