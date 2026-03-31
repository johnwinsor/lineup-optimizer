# Zurich Zebras (Ottoneu Team 7582) Optimizer - Project Status

## 1. System Architecture
The optimizer is a multi-stage pipeline designed for **Daily 5x5 Roto Efficiency** maximization.

- **Harvester (`harvester.py`)**: Scrapes the official Ottoneu team page to get the live 40-man roster, team affiliations, and positional eligibility.
- **Enricher (`enricher.py`)**: Fetches season-long Steamer projections and calculates a baseline "Efficiency Score" (Counting Stats per PA + AVG).
- **StatCast Harvester (`statcast_harvester.py`)**: Downloads and parses full MLB datasets for advanced metrics (xwOBA, Barrel%, xERA, SIERA).
- **Spring Harvester (`spring_harvester.py`)**: Fetches live 2026 Spring Training hitter and pitcher stats from FanGraphs for early-season scouting.
- **Spring Hitter Scout (`scout_spring_fa.py`)**: Analyzes free agent hitters surging in spring training compared to their ATC baseline.
- **Spring Pitcher Scout (`scout_spring_pitchers.py`)**: Identifies free agent pitchers with elite spring metrics (K-BB%, SwStr%) relative to projections.
- **Park Factor Engine (`park_factors.py`)**: Provides a numerical lookup for all 30 MLB stadiums based on Statcast run-scoring environments.
- **Weather Harvester (`weather_harvester.py`)**: Scrapes real-time weather, wind, and rain risk from Rotowire.
- **GameDay Harvester (`gameday_harvester.py`)**: Interfaces with MLB Stats API to fetch real-time starting lineups, batting orders, opposing SP data, and historical BvP stats. Now includes **Pending Lineup Detection** to identify teams playing before official cards are posted.
- **Daily Engine (`daily_engine.py`)**: The "Brain" of the operation. It applies dynamic multipliers (Platoon, Order, SP Skill, etc.) to the baseline score. Handles **Lineup Pending** scenarios by optimistically projecting starters with a default middle-of-the-order multiplier.
- **Optimizer (`optimizer.py`)**: A Linear Programming model (SciPy) that solves for the 13 most productive positional slots.
- **Backtester (`backtester.py`)**: A "Live Dashboard" tool to verify the algorithm against any date (defaults to Today). Now includes real-time game status (e.g., "Warmup", "Pre-Game", "Live"), full 5x5 actual stats, and support for pending lineups.
- **Batch Backtester (`batch_backtester.py`)**: Runs randomized simulations across the season to generate aggregate success rate reports.
- **Free Agent Scout (`scout.py`)**: Analyzes all available free agent hitters in League 1077 and ranks them by their Zebras Efficiency Score. Fixed bug in name cleaning logic.

- **Pitcher Optimizer (`pitcher_optimizer.py`)**: Orchestrates the daily pitcher evaluation and generates JSON reports for the dashboard.
- **Pitcher Daily Engine (`pitcher_daily_engine.py`)**: Applies dynamic multipliers (Venue, Weather, Statcast, BvP, Opponent Strength) to rostered starters.
- **Pitcher Enricher (`pitcher_enricher.py`)**: Maps rostered pitchers to ATC/Steamer projections and calculates a base efficiency score.

## 2. The "Zebras Algorithm" (Projection Logic)
### Hitter Algorithm (V2):
...
### Pitcher Algorithm (V1):
The final `PitcherProjScore` for a starter is:
`BaseScore * [Park Factor (Inv)] * [Weather Factor] * [Statcast Boost] * [Agg BvP Factor] * [Opponent Power]`

| Factor | Condition | Impact |
| :--- | :--- | :--- |
| **Base Score** | `(K/9 * 0.4) + (5.0 - ERA) + (1.5 - WHIP) * 2.0` | **Baseline** |
| **Park Factor** | Inverse of hitter multiplier (e.g. Coors = 0.85x) | **0.8x to 1.2x** |
| **Weather** | Wind In (+), Wind Out (-), Heat (>85F) (-) | **±5% to 10%** |
| **Statcast** | `(Projected ERA - Blended xERA) * 0.1` | **Dynamic** |
| **Agg BvP** | Average OPS allowed to current lineup (min 3 PA) | **0.85x to 1.15x** |
| **Opp Power** | Aggregate Efficiency Score of opposing lineup | **0.85x to 1.15x** |

### Lineup Pending Logic (Historical Assumption):
When a team is scheduled to play but the official lineup has not yet been announced:
1.  **Status**: The player is marked as **"Pending"** in the optimizer.
2.  **Order**: Displayed as **"X*"** (e.g., **"1*"**), where X is the batting order from the last completed game they started in. Falls back to **"5*"** if no history is found.
3.  **Multiplier**: The algorithm applies the appropriate order multiplier (e.g., 1.15x for #1) based on this historical assumption to ensure core players are prioritized correctly.
4.  **Note**: The Breakdown column clarifies: **"Lineup Pending (Assumed #X)"**.

### Multipliers & Weights:
| Factor | Condition | Impact |
| :--- | :--- | :--- |
| **Order Factor** | Batting Order Position (1 to 9) | **0.85x to 1.15x** |
| **Lineup Pending** | Game scheduled, card not posted | **Historical Order Multiplier** |
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
- **Run Hitter Backtest**: `uv run python backtester.py YYYY-MM-DD`
- **Run Pitcher Backtest**: `uv run python pitcher_backtester.py YYYY-MM-DD`
- **Find Free Agent Upgrades**: `uv run python scout.py --pa 50`
- **Harvest Spring Stats**: `uv run python spring_harvester.py`
- **Scout Spring Hitters**: `uv run python scout_spring_fa.py --pa 15`
- **Scout Spring Pitchers**: `uv run python scout_spring_pitchers.py --ip 5`
- **Analyze Spring Performances**: `uv run python spring_analyzer.py --pa 15`
- **Refresh All Data**: `uv run python fetch_statcast.py`

## 6. Web Dashboard & Automation
The optimizer includes a zero-cost static web dashboard hosted on GitHub Pages.

- **Automation**: GitHub Actions runs `main.py` hourly to generate four views (ATC Today/Tomorrow, Steamer Today/Tomorrow).
- **Data Hosting**: JSON data is pushed to the `gh-pages` branch, keeping the `main` branch clean.
- **Frontend**: `index.html` (Tailwind + Alpine.js) fetches the JSON and renders the dashboard.

## 7. Local Web Development
To iterate on the web dashboard without waiting for GitHub Actions:

1.  **Generate Local Data**:
    Run the helper script to update all 4 lineup combinations (ATC/Steamer for Today/Tomorrow):
    ```bash
    python update_web_data.py
    ```
    *Use `--skip-ai` to save your Gemini API quota during development.*

2.  **Start Local Server**:
    Run Python's built-in HTTP server in the project root:
    ```bash
    python -m http.server 8000
    ```

3.  **View Dashboard**:
    Open your browser to `http://localhost:8000`. Changes to `index.html` will be visible upon refresh.

## 8. Implementation Notes & Disambiguation
- **Efficiency Focus**: The core goal is to maximize stats *per slot*, adhering to the Ottoneu 162-game season cap.
- **Zebras Floor**: A minimum efficiency threshold (default: 40.0) that must be met to start a non-core player.
- **Narrative Logic**: Post-game summaries use a `TotalProd` (5x5 weighted) score to evaluate "Wins" and "Flops."
- **Live Status**: The backtester displays real-time game progress (e.g., "Top 7th", "Final") and live 5x5 stats.
