# Zurich Zebras Optimizer: The Science of Daily Roto Efficiency

Welcome to the Zurich Zebras Optimizer, a high-precision decision-engine designed specifically for the rigors of **Ottoneu Daily 5x5 (Roto) competition**.

In a format defined by a strict 162-game cap, every plate appearance and every inning pitched is a finite resource. Our mission is to ensure that no "empty" stats ever enter your lineup. By combining elite industry projections with real-time environmental data and advanced Statcast peripherals, we provide a mathematically optimized roadmap to maximize your team's efficiency every single day.

---

### The Architecture of a Zebra Score
The "Zebra Score" is our proprietary metric for daily production. It is not a simple projection of raw totals; rather, it is an **Efficiency Rating** designed to identify who will produce the most value *per slot*.

#### Hitter Efficiency (V3 Algorithm)
A hitter's daily score begins with a baseline derived from their full-season projections (ATC or Steamer), then scaled to a per-game rate:

```
Base Score = ((R + HR + RBI + SB × 1.5) / PA × 100) + (AVG × 89)
```

Key design choices:
- **SB weighted 1.5×** to reflect category scarcity — stolen bases are meaningfully harder to replace than Runs, HR, or RBI at league scale.
- **AVG coefficient of 89** maintains a consistent H/PA denominator (AVG × 0.89 AB/PA ≈ H/PA), replacing the old H/AB mix.

We then apply a series of dynamic, context-aware multipliers. The **total multiplier is capped at +35% above and −30% below the base score**, preventing extreme compounding when multiple factors stack:

*   **Dynamic Platoon Splits**: Real-world career OPS vs LHP/RHP from the MLB Stats API. Static fallbacks apply when live splits are unavailable: opposite-hand advantage +7%, L batter vs L pitcher −10%, R batter vs R pitcher −3%. Switch hitters receive a +3% bonus to avoid unfair penalization.
*   **Batting Order Density**: Players at the top of the lineup receive a boost to reflect higher PA probability. Range spans +10% (leadoff) to −9% (ninth), tightened from the prior ±15% to a research-supported ±10%.
*   **Opposing Pitcher Difficulty**: ERA-based adjustment capped at ±20% relative to a league-average baseline of 4.00. Facing an ace reduces the score; facing a replacement-level arm boosts it.
*   **Batter vs. Pitcher (BvP)**: Historical head-to-head data applied only when ≥25 PA exist (below this threshold, results are predominantly noise). Effect sizes are modest by design — ±3% to ±8% — reflecting BvP's real but limited predictive value at typical sample sizes.
*   **Venue & Park Factors**: Statcast park factors for all 30 MLB stadiums.
*   **Basestealing Environment**: For players with elite (≥28.5 ft/s) or above-average (≥27.5 ft/s) sprint speed, modest adjustments are applied for catcher pop time and pitcher hold ability. A below-average catcher (>2.05s pop time) or permissive SP delivery adds a small boost; an elite catcher (<1.90s) or exceptional hold pitcher applies a small penalty. These modifiers are intentionally small (±2–4% on the full score) because stolen base value is only a portion of most players' total production.
*   **Weather Dynamics**: Real-time wind speed and direction factored in. A 20+ MPH wind blowing out adds up to +10%; a strong wind in carries up to −10%.
*   **Real-Time Roster Tracking**: Direct MLB Stats API integration for immediate detection of minor league promotions — bypassing the lag of third-party platforms.
*   **xwOBA & Barrel Rate (Informational)**: Elite Statcast quality indicators (xwOBA ≥ .400, elite barrel rate) are surfaced in the score breakdown for context, but no separate multiplier is applied — projection systems already incorporate contact quality, and a second boost would create systematic double-counting.

#### Pitcher Precision (V1 Algorithm)
Pitcher scores are designed to reward the "Ottoneu Trifecta": High Strikeouts, Low ERA, and elite WHIP.
*   **The Baseline**: Calculated using a weighted formula of `(K/9 * 0.4) + (5.0 - ERA) + (1.5 - WHIP) * 2.0`.
*   **Opponent Power Index**: We calculate the aggregate efficiency of the *entire* opposing 9-man lineup. Starting against a "heavy" lineup results in a meaningful score reduction.
*   **Skill Delta**: We compare a pitcher's season-long ERA against their Statcast-derived **SIERA** and **xERA**. Pitchers showing "luck" (ERA much lower than xERA) are penalized, while those due for positive regression are boosted.

---

### The Stabilization Curve: Bridging the Seasons

In the early months of a new season, "current-year" statistics are notoriously noisy. A single hot week or one bad outing can wildly distort a player's metrics. To solve this, the Zurich Zebras Optimizer utilizes a **Weighted Stabilization Curve**.

This proprietary algorithm ensures that we rely on last year's proven performance while gradually increasing our trust in the emerging reality of this year's data as sample sizes stabilize.

| Month | Prior Season Weight | Current Season Weight |
| :--- | :--- | :--- |
| **April** | 100% | 0% |
| **May** | 70% | 30% |
| **June** | 40% | 60% |
| **July+** | 0% | 100% |

This ensures that in April, we aren't overreacting to small-sample "flukes." By July, the algorithm has fully transitioned to the current year, allowing it to capture mid-season breakouts and skill shifts with 100% accuracy.

---

### Data Sources & Refresh Frequency
To maintain mathematical rigor, we pull from the most trusted repositories in professional baseball.

| Data Category | Source | Refresh Frequency |
| :--- | :--- | :--- |
| **League Roster & Eligibility** | Ottoneu (League 1077) | Hourly |
| **Baseline Projections** | ATC (Ariel Cohen) & Steamer | Daily |
| **Live MLB Lineups** | MLB Stats API | Hourly |
| **Platoon Splits & Roster Status** | MLB Stats API (Real-time) | Hourly |
| **Advanced Metrics (xwOBA, SIERA)** | Baseball Savant / FanGraphs | Daily |
| **Batter vs. Pitcher (BvP)** | MLB Historical Data | Real-time per run |
| **Weather & Wind Risk** | Rotowire Weather Report | Hourly |
| **Park Factors** | Statcast Venue Intelligence | Seasonally |

---

### Our Design Philosophy: Rigor Over Intuition
This optimizer was built on the principle that "gut feeling" is the enemy of Roto efficiency. By automating the analysis of thousands of data points—from wind direction in Chicago to the "Pop Time" of an opposing catcher—we provide a level of scrutiny that manual management cannot match.

Every recommendation you see on this dashboard is the result of a **Linear Programming model** that solves for the single most productive combination of 13 hitters and a rotation of starters, ensuring your team is always positioned to climb the standings.
