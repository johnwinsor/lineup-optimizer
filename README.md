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
Run the main optimizer to see the recommended starting hitters for today's MLB games.
```bash
uv run python main.py
```

## 🧪 Backtesting Workflow

The backtesting framework allows you to "time travel" to any date in the 2025 season to evaluate the algorithm's predictive accuracy against actual MLB box scores.

### Run a Backtest
Pass a specific date in `YYYY-MM-DD` format:
```bash
uv run python backtester.py 2025-07-04
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

### Advanced Modes

#### 1. Top Performers (Default)
Ranks players by `wRC+` and cross-references ownership in League 1077.
```bash
uv run python spring_analyzer.py --top 20 --days 7
```

#### 2. Under-the-Radar Scout (`--radar`)
Uncovers "hidden gems" by filtering for players with poor surface results (wRC+ < 110) but elite StatCast peripherals. It identifies players meeting either of these triggers:
- **High Impact**: Average Exit Velocity >= 90 MPH.
- **Elite Discipline**: Whiff Rate <= 15%.
```bash
uv run python spring_analyzer.py --radar --days 10
```

### Key Metrics Tracked
- **wRC+**: Overall offensive contribution relative to league average.
- **EV Avg/Max**: Rolling average and peak exit velocity from the last X days of games.
- **Whiff%**: Real-time swinging strike rate (Misses / Swings) crawled from MLB play-by-play data.
- **Ownership**: Real-time status in League 1077 (**Zurich Zebras**, **FREE AGENT**, or **Other Team**).

### What happens in a Backtest?
1. **Roster Scrape**: Identifies the Zurich Zebras 40-man roster.
2. **Matchup Analysis**: Fetch confirmed MLB starting lineups and opposing pitchers for that date.
3. **Projection**: Applies the **Zebras Algorithm** (Platoon, SP Skill, BvP, StatCast) to generate daily `ProjScore`s.
4. **Optimization**: Solves a linear programming model to fill 13 positional slots.
5. **Validation**: Fetches actual post-game box scores and compares the predicted production against your bench's opportunity cost.

## 🧠 The Zebras Algorithm

The system moves beyond season averages to target high-upside daily matchups:

- **Numerical Park Factors**: Applies stadium-specific multipliers for all 30 MLB parks (e.g., Coors Field, Camden Yards).
- **Weather & Wind**: Scrapes real-time weather from Rotowire to apply boosts for wind blowing out (+10%) and penalties for wind blowing in. Generates rain risk warnings (🚨).
- **Pitcher Difficulty**: Prioritizes **xERA** and **SIERA** over surface ERA to identify vulnerable pitchers.
- **Bi-directional Platoon**: Rewards opposite-hand advantages (+10%) and penalizes same-side disadvantages (up to -15% for L/L).
- **Elite BvP**: Applies bonuses for hitters with a proven historical track record against a specific SP (min 5 PA).
- **StatCast Peripherals**: Real-time boosts for elite **xwOBA** and **Barrel%** trends.
- **Recency Bias**: Time-weighted stabilization logic that progressively shifts focus from prior-season baselines to current-season performance.

## 📈 The Zebras Efficiency Score (Proj)

The core metric used by the optimizer is the **Zebras Efficiency Score** (labeled as **"Proj"** in tables). This value represents the **projected 5x5 production value per 100 Plate Appearances**. 

In an Ottoneu 162-game cap environment, this score tells us: *"How much total Roto value will this player generate for every trip to the plate today?"*

### 1. The Baseline Formula
The foundation of the score uses season-long Steamer projections:
> **Baseline Score** = `[(R + HR + RBI + SB) / PA * 100] + [AVG * 100]`

### 2. The Daily Multipliers
The **Daily Engine** then applies dynamic multipliers to the baseline based on the day's specific context:
- **Order Factor:** Rewards high-volume slots (**+15% for Leadoff**) and penalizes the bottom of the order (**-15% for 9th**).
- **Lineup Pending (New!):** Optimistically projects starters for teams playing but with no posted lineup. Assumes the **batting order from the player's last completed start** (e.g., **"1*"**) to ensure core players are prioritized correctly based on their typical role.
- **Park Factor:** 0.90x to 1.20x (e.g., Coors Field vs. Petco Park).
- **Pitcher Skill:** 0.70x to 1.30x (Based on the opposing SP's xERA/SIERA).
- **Platoon Advantage:** +10% for opposite hand, -15% for L/L matchups.
- **BvP (Batter vs. Pitcher):** +15% for "Elite" history, -15% for "Poor."
- **StatCast Boosts:** +10% for elite **xwOBA (> .400)** and **+5% for Barrel% (> 15.0%)**.
- **Superstar Shield:** Elite hitters (xwOBA > .400) have a **protected floor of 85% of their baseline score**, preventing them from being benched due to extreme matchups.
- **Weather:** +5-10% for wind blowing out, warnings for rain.

### 3. Understanding the Tiers
| Score Range | Tier | Rationale |
| :--- | :--- | :--- |
| **90.0+** | **Elite / Superstar** | A top-tier hitter facing a weak pitcher in a hitter's park. |
| **60.0 - 85.0** | **Strong Play** | An everyday starter with a clear advantage (Platoon or high Order). |
| **45.0 - 55.0** | **Average / Baseline** | League-average performance; a safe starting option. |
| **40.0** | **Zebras Floor** | **Hard Cutoff**. Below this, we bench the player to save game caps. |
| **< 35.0** | **Avoid** | Significant disadvantage (e.g., backup player batting 9th against an ace). |

## 🌐 Automated Web Dashboard

The Zurich Zebras Optimizer features a **zero-cost static web dashboard** hosted on GitHub Pages. It provides a mobile-friendly view of daily and tomorrow's optimized lineups across multiple projection systems.

### Features
- **Multi-Projection Support**: Toggle between **ATC** and **Steamer** baselines.
- **Advance Planning**: View optimized lineups for both **Today** and **Tomorrow**.
- **AI Analyst**: Real-time pre-game narrative generated by Google Gemini.
- **Live Status**: Displays game status (e.g., "Top 3rd", "Warmup", "Final") and live stats when games are active.
- **Historical Order Detection**: Clearly marks assumed batting orders (e.g., `1*`) when official lineups are pending.

### Architecture
1.  **Automation (GitHub Actions)**:
    - **Daily Refresh**: Runs `fetch_statcast.py` at 4 AM UTC to update seasonal baselines and projections.
    - **Hourly Updates**: Runs `main.py` every hour during the MLB season to refresh lineups, weather, and game statuses.
2.  **Data Layer**: Python scripts export state to structured JSON files (e.g., `lineup_atc_today.json`). These are hosted directly on the `gh-pages` branch.
3.  **Frontend**: A lightweight `index.html` built with **Tailwind CSS** and **Alpine.js**. It fetches the latest JSON data on page load, ensuring zero server overhead.

### Local Web Development
To iterate on the dashboard locally:
1.  **Generate Data**: Run `python update_web_data.py --skip-ai` to populate all 4 projection/date JSON combinations.
2.  **Launch Server**: Run `python -m http.server 8000`.
3.  **View**: Open `http://localhost:8000` in your browser.

## 🛠 Project Structure

- `main.py`: Entry point for daily optimization and terminal display.
- `index.html`: Web dashboard frontend (Alpine.js + Tailwind).
- `update_web_data.py`: Helper script to generate all web JSON views.
- `.github/workflows/`: Automation for daily data refreshes and hourly lineup updates.
- `backtester.py`: Simulation engine for historical analysis.
- `batch_backtester.py`: Aggregate performance auditor.
- `fa_backtester.py`: Historical performance auditor for free agents.
- `scout.py`: Current free agent identifying tool.
- `daily_engine.py`: Logic for applying daily matchup multipliers.
- `harvester.py`: Ottoneu roster and FanGraphs scraper.
- `gameday_harvester.py`: MLB Stats API interface for lineups and BvP.
- `statcast_harvester.py`: Local lookup for advanced StatCast metrics.
- `optimizer.py`: SciPy-based linear programming optimizer.

---
*Built for the 162-game grind. Efficiency is the only metric that matters.*
