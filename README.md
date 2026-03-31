# Zurich Zebras Ottoneu Optimizer

A daily lineup optimization and backtesting framework for the Zurich Zebras (Ottoneu Team 7582). This tool maximizes 5x5 Roto efficiency by dynamically projecting daily player performance based on real-time matchups, advanced StatCast peripherals, and historical BvP data.

## 🚀 Quick Start

### 1. Installation
This project uses `uv` for lightning-fast dependency management.
```bash
# Clone the repository and sync dependencies
uv sync
```

### 2. Prepare Data
Ensure you have the latest StatCast datasets and Steamer projections cached locally.
**Note:** You must run this script once a day before running the main optimizer or free agent tools, as they now rely on this cached data to run much faster! It will also output a summary of any significant shifts in player projections.
```bash
uv run python fetch_statcast.py
```

### 3. Generate Today's Optimal Lineup
Run the main hitter optimizer:
```bash
uv run python main.py
```

### 4. Evaluate Starting Pitchers
Run the pitcher optimizer to see efficiency rankings for rostered starters:
```bash
uv run python pitcher_optimizer.py
```

## 🧪 Backtesting Workflow

The backtesting framework allows you to "time travel" to any date to evaluate the algorithm's predictive accuracy against actual MLB box scores.

### Run a Hitter Backtest
```bash
uv run python backtester.py 2025-07-04
```

### Run a Pitcher Backtest
```bash
uv run python pitcher_backtester.py 2025-07-04
```

### Run a Season Audit
Run 50 random simulations across the 2025 season to see the aggregate success rate of the algorithm:
```bash
uv run python batch_backtester.py
```

## 🚀 Projection System Selection

The optimizer supports multiple projection baselines. You can toggle between them using the `--projection` flag:

- **Steamer (`--projection steamer`)**: The default system. Aggressive on breakout candidates.
- **ATC (`--projection atc`)**: Ariel Theoretical Composite. A weighted average of multiple systems. Highly recommended for "Efficiency Maximization" as it reduces outlier variance.

#### Usage Examples:
- **Run Optimizer with ATC**: `uv run python main.py --projection atc`
- **Backtest with ATC**: `uv run python backtester.py --projection atc`
- **Batch Test with ATC**: `uv run python batch_backtester.py --projection atc`
- **Scout Free Agents**: `uv run python scout.py --projection atc`

## 📊 Compact Terminal Display

The Zurich Zebras optimizer is designed for mobile and laptop developers. To prevent table overlap on smaller screens, we use a compact display strategy:

- **Non-Expanding Tables**: Tables in `display_utils.py` do not force full-terminal width.
- **Shorthand Stats**: The backtester uses compact 5x5 notation: `H/AB R R HR HR RBI I SB S`.
- **Simplified Box Lines**: We use `SIMPLE_HEAD` borders to maximize content area.
- **Shortened Opponent Data**: Pitcher skill (xERA/SIERA) is rounded to 1 decimal place.

### Find Free Agent Upgrades
Scout the most efficient available hitters in your league (League 1077):
```bash
# Refresh free agent list
uv run python scout_harvester.py

# Find top performers with at least 50 Plate Appearances
uv run python scout.py --pa 50
```

### Audit Free Agent History
Analyze the actual historical performance of free agents for a specific date:
```bash
uv run python fa_backtester.py 2025-07-04
```

## 🌸 Spring Training Analyzer

The Spring Training Analyzer is a specialized scouting tool designed for the early season. it bridges the gap between traditional box score stats (`wRC+`) and underlying StatCast metrics to find breakouts and hidden gems.

### Basic Usage
Refresh your local spring training data first, then run the analyzer:
```bash
# Refresh data from FanGraphs
uv run python spring_harvester.py

# Run top performer analysis (Min 15 PA)
uv run python spring_analyzer.py --pa 15
```

## 🧠 The Zebras Algorithm

The system moves beyond season averages to target high-upside daily matchups:

- **Numerical Park Factors**: Applies stadium-specific multipliers for all 30 MLB parks (e.g., Coors Field, Camden Yards).
- **Weather & Wind**: Scrapes real-time weather from Rotowire to apply boosts for wind blowing out (+10%) and penalties for wind blowing in. Generates rain risk warnings (🚨).
- **Pitcher Difficulty**: Prioritizes **xERA** and **SIERA** over surface ERA to identify vulnerable pitchers.
- **Bi-directional Platoon**: Rewards opposite-hand advantages (+10%) and penalizes same-side disadvantages (up to -15% for L/L).
- **Elite BvP**: Applies bonuses for hitters with a proven historical track record against a specific SP (min 5 PA).
- **StatCast Peripherals**: Real-time boosts for elite **xwOBA** and **Barrel%** trends.
- **Recency Bias**: Time-weighted stabilization logic that progressively shifts focus from prior-season baselines to current-season performance.

## 📈 Efficiency Algorithms

### Hitter Efficiency (Proj)
> **Baseline Score** = `[(R + HR + RBI + SB) / PA * 100] + [AVG * 100]`
- **Superstar Shield:** Elite hitters (xwOBA > .400) have a **protected floor of 85% of their baseline score**, preventing them from being benched due to extreme matchups.

### Pitcher Efficiency (Proj)
> **PitcherProjScore** = `BaseScore * [Park Factor (Inv)] * [Weather Factor] * [Statcast Boost] * [Agg BvP Factor] * [Opponent Power]`
- **Base Score:** `(K/9 * 0.4) + (5.0 - ERA) + (1.5 - WHIP) * 2.0`. Rewards high strikeout rates and elite ratios.
- **Rigorous Opponent Research:** Analyzes the specific 9 hitters in the opposing lineup (or projected top 9 if official card is pending) to calculate **Aggregate BvP OPS** and **Opponent Lineup Power**.

## 📊 Understanding the Tiers
#### Hitter Tiers
| Score Range | Tier | Rationale |
| :--- | :--- | :--- |
| **90.0+** | **Elite / Superstar** | A top-tier hitter facing a weak pitcher in a hitter's park. |
| **60.0 - 85.0** | **Strong Play** | An everyday starter with a clear advantage (Platoon or high Order). |
| **40.0** | **Zebras Floor** | **Hard Cutoff**. Below this, we bench the player to save game caps. |

#### Pitcher Tiers
| Score Range | Tier | Rationale |
| :--- | :--- | :--- |
| **7.0+** | **Elite Start** | An ace-level projection in a favorable park/matchup. |
| **5.0 - 6.5** | **Strong Start** | Solid SP with a clear tactical advantage. |
| **3.0 - 4.5** | **Streamer / Baseline** | Standard outing; typical for mid-rotation arms. |
| **< 2.5** | **Dangerous** | Avoid starting due to poor ratios or elite opposing offense. |

## 🌐 Automated Web Dashboard

The Zurich Zebras Optimizer features a **zero-cost static web dashboard** hosted on GitHub Pages. 

### Features
- **Multi-Projection Support**: Toggle between **ATC** and **Steamer** baselines.
- **Advance Planning**: View optimized lineups for both **Today** and **Tomorrow**.
- **Pitcher Evaluation**: Daily efficiency cards for rostered starting pitchers.
- **Recent Performance**: Visual 3-day history showing actual Roto production and pitcher results.
- **AI Analyst**: Real-time pre-game narrative generated by Google Gemini.
- **Live Status**: Displays game status (e.g., "Top 3rd", "Warmup", "Final") and live stats when games are active.

### Architecture
1.  **Automation (GitHub Actions)**:
    - **Daily Refresh**: Runs `fetch_statcast.py` at 4 AM UTC to update seasonal baselines and projections.
    - **Hourly Updates**: Runs `update_web_data.py` every hour to refresh lineups, pitchers, weather, and recent history.
2.  **Data Layer**: Python scripts export state to structured JSON files (Lineups, Pitcher Starts, and 3-day History). These are hosted directly on the `gh-pages` branch.
3.  **Frontend**: A lightweight `index.html` built with **Tailwind CSS** and **Alpine.js**.

### Local Web Development
1.  **Generate Data**: Run `python update_web_data.py --skip-ai`.
2.  **Launch Server**: Run `python -m http.server 8000`.
3.  **View**: Open `http://localhost:8000` in your browser.

## 🛠 Project Structure

- `main.py`: Entry point for daily hitter optimization.
- `pitcher_optimizer.py`: Entry point for daily pitcher optimization.
- `index.html`: Web dashboard frontend (Alpine.js + Tailwind).
- `update_web_data.py`: Helper script to generate all web JSON views.
- `backtester.py`: Simulation engine for historical hitter analysis.
- `pitcher_backtester.py`: Simulation engine for historical pitcher analysis.
- `pitcher_daily_engine.py`: Logic for applying pitcher matchup multipliers.
- `pitcher_enricher.py`: Maps pitchers to projection systems.
- `daily_engine.py`: Logic for applying daily hitter matchup multipliers.
- `harvester.py`: Ottoneu roster and FanGraphs scraper.
- `gameday_harvester.py`: MLB Stats API interface for lineups, BvP, and actual results.
- `statcast_harvester.py`: Local lookup for advanced StatCast metrics.
- `optimizer.py`: SciPy-based linear programming optimizer.

---
*Built for the 162-game grind. Efficiency is the only metric that matters.*
