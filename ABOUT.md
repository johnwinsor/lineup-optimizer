# Zurich Zebras Optimizer: The Science of Daily Roto Efficiency

Welcome to the Zurich Zebras Optimizer, a high-precision decision-engine designed specifically for the rigors of **Ottoneu Daily 5x5 (Roto) competition**. 

In a format defined by a strict 162-game cap, every plate appearance and every inning pitched is a finite resource. Our mission is to ensure that no "empty" stats ever enter your lineup. By combining elite industry projections with real-time environmental data and advanced Statcast peripherals, we provide a mathematically optimized roadmap to maximize your team's efficiency every single day.

---

### The Architecture of a Zebra Score
The "Zebra Score" is our proprietary metric for daily production. It is not a simple projection of raw totals; rather, it is an **Efficiency Rating** designed to identify who will produce the most value *per slot*.

#### Hitter Efficiency (V2 Algorithm)
A hitter's daily score begins with a baseline derived from their counting stat production (Runs, HR, RBI, SB) per plate appearance, added to their projected Batting Average. We then apply a series of dynamic, context-aware multipliers:
*   **Dynamic Platoon Splits**: Rather than using static weights, we ingest real-world career performance data (OPS vs LHP/RHP) directly from the MLB Stats API. A hitter's score is dynamically adjusted based on their historical delta against the specific handedness of today's opposing pitcher.
*   **Batting Order Density**: Players at the top of the lineup receive a boost to reflect the higher probability of additional plate appearances and run-scoring opportunities. Historical orders are automatically retrieved via boxscore analysis for players with "Pending" lineups.
*   **Venue & Environment**: We ingest Statcast park factors for all 30 MLB stadiums. A hitter in Coors Field receives a significantly different weight than one in Oracle Park.
*   **Weather Dynamics**: Real-time wind speed, wind direction, and air density (heat) are factored in. 15mph wind blowing "Out" in Wrigley is treated as a major performance catalyst.
*   **Real-Time Roster Tracking**: We interface directly with the MLB Stats API to track player promotions and levels. This ensures that newly promoted players (e.g. from AAA to MLB) are unlocked in the optimizer instantly, bypassing the lag of third-party platforms.

#### Pitcher Precision (V1 Algorithm)
Pitcher scores are designed to reward the "Ottoneu Trifecta": High Strikeouts, Low ERA, and elite WHIP. 
*   **The Baseline**: Calculated using a weighted formula of `(K/9 * 0.4) + (5.0 - ERA) + (1.5 - WHIP) * 2.0`.
*   **Opponent Power Index**: We calculate the aggregate efficiency of the *entire* opposing 9-man lineup. Starting against a "heavy" lineup results in a meaningful score reduction.
*   **Skill Delta**: We compare a pitcher's season-long ERA against their Statcast-derived **SIERA** and **xERA**. Pitchers showing "luck" (ERA much lower than xERA) are penalized, while those due for positive regression are boosted.

---

### The Stabilization Curve: Bridging the Seasons

In the early months of a new season, "current-year" statistics are notoriously noisy. A single hot week or one bad outing can wildly distort a player's metrics. To solve this, the Zurich Zebras Optimizer utilizes a **Weighted Stabilization Curve**. 

This proprietary algorithm ensures that we rely on last year's proven performance (2025) while gradually increasing our trust in the emerging reality of this year’s data (2026) as sample sizes stabilize.

| Month | Prior Season Weight (2025) | Current Season Weight (2026) |
| :--- | :--- | :--- |
| **April** | 100% | 0% |
| **May** | 70% | 30% |
| **June** | 40% | 60% |
| **July+** | 0% | 100% |

This ensures that in April, we aren't overreacting to small-sample "flukes." By July, the algorithm has fully transitioned to the current year, allowing it to capture mid-season breakouts and skill shifts with 100% accuracy.

---

### The "Superstar Shield"
We recognize that elite talent often defies the spreadsheet. Our algorithm includes a **Superstar Shield** for players with a Statcast xwOBA (Expected Weighted On-Base Average) above .400. These "Tier 1" players are protected from aggressive matchup-based benching; their scores are never allowed to drop below 85% of their baseline, ensuring your anchors stay in the lineup when they are healthy and active.

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
