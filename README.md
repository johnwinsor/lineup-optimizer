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
Ensure you have the latest StatCast datasets for the current season.
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

## 🛠 Project Structure

- `main.py`: Entry point for today's optimization.
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
