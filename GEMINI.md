# Zurich Zebras (Ottoneu Team 7582) Optimizer - Project Status

## 1. System Architecture
The optimizer is a multi-stage pipeline designed for **Daily 5x5 Roto Efficiency** maximization.

- **Harvester (`harvester.py`)**: Scrapes the official Ottoneu team page to get the live 40-man roster, team affiliations, and positional eligibility.
- **Enricher (`enricher.py`)**: Fetches season-long Steamer projections and calculates a baseline "Efficiency Score" (Counting Stats per PA + AVG).
- **StatCast Harvester (`statcast_harvester.py`)**: Downloads and parses full MLB datasets for advanced metrics (xwOBA, Barrel%, xERA, SIERA).
- **Park Factor Engine (`park_factors.py`)**: Provides a numerical lookup for all 30 MLB stadiums based on Statcast run-scoring environments.
- **Weather Harvester (`weather_harvester.py`)**: Scrapes real-time weather, wind, and rain risk from Rotowire.
- **GameDay Harvester (`gameday_harvester.py`)**: Interfaces with MLB Stats API to fetch real-time starting lineups, opposing SP data, and historical BvP stats.
- **Daily Engine (`daily_engine.py`)**: The "Brain" of the operation. It applies dynamic multipliers to the baseline score based on daily matchup context.
- **Optimizer (`optimizer.py`)**: A Linear Programming model (SciPy) that solves for the 13 most productive positional slots.
- **Backtester (`backtester.py`)**: A simulation tool to verify the algorithm against any historical 2025 date using actual box score results.
- **Batch Backtester (`batch_backtester.py`)**: Runs randomized simulations across the full 2025 season to generate aggregate success rate reports.
- **Free Agent Scout (`scout.py`)**: Analyzes all available free agent hitters in League 1077 and ranks them by their Zebras Efficiency Score.
- **Free Agent Backtester (`fa_backtester.py`)**: Audits the actual historical performance of available free agents for a specific date.

## 2. The "Zebras Algorithm" (Projection Logic)
The final `ProjScore` for a player on a given day is: 
`Baseline Score * [Park Factor] * [Pitcher Skill] * [Platoon Factor] * [BvP Factor] * [StatCast Boosts] * [Weather Factor]`

### Multipliers & Weights:
| Factor | Condition | Impact |
| :--- | :--- | :--- |
| **Park Factor** | Numerical lookup per stadium | **0.9x to 1.2x** |
| **Wind (Out)** | Speed >= 10 MPH blowing Out | **+5% to +10%** |
| **Wind (In)** | Speed >= 10 MPH blowing In | **-5% to -10%** |
| **Rain Risk** | Precipitation chance >= 30% | **Warning Icon** |
| **Platoon** | Opposite Hand Matchup (L vs R) | **+10%** |
| **Platoon (L/L)** | Left-handed Batter vs Left-handed Pitcher | **-15%** |
| **Platoon (R/R)** | Right-handed Batter vs Right-handed Pitcher | **-5%** |
| **Switch Hitter** | Always has platoon advantage | **+5%** |
| **SP Skill** | Linear scale: `1.0 + (xERA - 4.0)/4.0` | **0.7x to 1.3x** |
| **BvP Elite** | Career OPS > 1.000 vs SP (min 5 PA) | **+15%** |
| **BvP Good** | Career OPS > .850 vs SP (min 5 PA) | **+5%** |
| **BvP Poor** | Career OPS < .500 vs SP (min 5 PA) | **-15%** |
| **xwOBA Elite** | Season xwOBA > .420 | **+10%** |
| **xwOBA Good** | Season xwOBA > .380 | **+5%** |
| **Barrel%** | Season Barrel% > 15% | **+5%** |

### 3. Recency Bias & Stabilization
The algorithm automatically transitions from prior-season baselines to current-season performance as sample sizes stabilize:
- **April**: **0% Current Year** (100% 2025 Baseline)
- **May**: **30% Current Year** (Early trend recognition)
- **June**: **60% Current Year** (Current year becomes primary driver)
- **July+**: **100% Current Year** (Baseline fully established by 2026 data)

## 4. Data Sources & Source of Truth
- **Roster**: `https://ottoneu.fangraphs.com/1077/team?team=7582`
- **Projections**: FanGraphs API (Steamer)
- **Advanced Metrics**: Baseball Savant / FanGraphs Leaderboards (JSON)
- **Weather**: Rotowire Weather Report
- **Live/Historical Games**: MLB Stats API (`statsapi.mlb.com`)

## 5. Operational Commands
- **Run Optimizer (Daily)**: `uv run python main.py`
- **Run Backtest (Date)**: `uv run python backtester.py YYYY-MM-DD`
- **Run Season Audit**: `uv run python batch_backtester.py`
- **Find Free Agent Upgrades**: `uv run python scout.py --pa 50`
- **Audit Free Agent History**: `uv run python fa_backtester.py YYYY-MM-DD`
- **Refresh StatCast Data**: `uv run python fetch_statcast.py`

## 6. Implementation Notes & Disambiguation
- **Name Mapping**: The `GameDayHarvester` uses a "year-aware" mapping to handle common name collisions (e.g., Josh Smith, Victor Scott II).
- **Efficiency Focus**: The core goal is to maximize stats *per slot*, adhering to the Ottoneu 162-game season cap.
- **Positional Slots**: 2 C, 1B, 2B, SS, MI, 3B, 5 OF, 1 UTIL.
- **Zebras Floor**: A minimum efficiency threshold (default: 40.0) that must be met to start a non-core player.
- **Superstar Shield**: Elite players (xwOBA > .400) are protected from aggressive matchup-based penalties.
