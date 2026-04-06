"""
ZebrasConfig — Single source of truth for all scoring constants and app settings.

Change a value here to tune the algorithm. Every multiplier, threshold,
and scoring weight lives in this file so you never have to grep through
engine code to find magic numbers.
"""

from datetime import datetime
import logging
import sys
import os

# ---------------------------------------------------------------------------
# Recency blending — prior season vs. current season StatCast weight
# ---------------------------------------------------------------------------
# Key = calendar month, value = fraction of current-year data to use.
# Months not listed default to RECENCY_DEFAULT.
RECENCY_WEIGHTS = {
    4: 0.0,   # April — full prior-year weight; current season too small
    5: 0.3,   # May   — lean prior
    6: 0.6,   # June  — balanced
}
RECENCY_DEFAULT = 1.0  # July+ uses current season entirely


def get_recency_weight(target_date: str) -> float:
    """Returns the fraction [0.0–1.0] of current-season StatCast data to blend in."""
    month = datetime.strptime(target_date, "%Y-%m-%d").month
    return RECENCY_WEIGHTS.get(month, RECENCY_DEFAULT)


# ---------------------------------------------------------------------------
# Opposing pitcher difficulty
# ---------------------------------------------------------------------------
ERA_FACTOR_MIN = 0.70       # Maximum penalty (facing an ace)
ERA_FACTOR_MAX = 1.30       # Maximum boost (facing a bad pitcher)
ERA_FACTOR_NEUTRAL = 4.00   # League-average ERA — used as the baseline divisor

# ---------------------------------------------------------------------------
# Platoon splits
# ---------------------------------------------------------------------------
PLATOON_MULT_MIN = 0.80
PLATOON_MULT_MAX = 1.20
SWITCH_HIT_BONUS = 1.05          # Switch hitters are never fully penalized
PLATOON_ADVANTAGE_BONUS = 1.10   # Opposite-hand matchup (e.g. LHB vs RHP)
PLATOON_LL_PENALTY = 0.85        # Same-hand disadvantage: L batter vs L pitcher
PLATOON_RR_PENALTY = 0.95        # Same-hand disadvantage: R batter vs R pitcher

# ---------------------------------------------------------------------------
# Batter vs Pitcher (BvP)
# ---------------------------------------------------------------------------
BVP_MIN_PA = 5             # Minimum plate appearances before BvP is applied

BVP_ELITE_OPS = 1.000      # Career OPS vs this pitcher — elite
BVP_GOOD_OPS  = 0.850      # Good
BVP_WEAK_OPS  = 0.650      # Weak
BVP_POOR_OPS  = 0.500      # Poor

BVP_ELITE_MULT = 1.15
BVP_GOOD_MULT  = 1.05
BVP_WEAK_MULT  = 0.95
BVP_POOR_MULT  = 0.85

# ---------------------------------------------------------------------------
# Basestealing environment
# ---------------------------------------------------------------------------
SPRINT_SPEED_ELITE = 28.5   # ft/s — elite speed; full SB tier multiplier
SPRINT_SPEED_GOOD  = 27.5   # ft/s — good speed; half SB tier multiplier

CATCHER_POP_SLOW  = 2.00    # Pop time (sec) — slow catcher, SB boost
CATCHER_POP_ELITE = 1.90    # Pop time (sec) — elite catcher, SB penalty
SB_CATCHER_MULT   = 0.05    # Per-tier boost/penalty for catcher pop time

SB_RATE_SLOW_SP = 0.85      # SP SB-allowed rate — easy to run on
SB_RATE_HOLD_SP = 0.65      # SP SB-allowed rate — hard to run on
SB_PITCHER_MULT = 0.10      # Per-tier boost/penalty for SP hold ability

# ---------------------------------------------------------------------------
# Batting order
# ---------------------------------------------------------------------------
ORDER_MULTIPLIERS = {
    1: 1.15, 2: 1.12, 3: 1.10, 4: 1.10,
    5: 1.05, 6: 1.00, 7: 0.95, 8: 0.90, 9: 0.85,
}

# ---------------------------------------------------------------------------
# StatCast / xwOBA
# ---------------------------------------------------------------------------
XWOBA_ELITE = 0.400
XWOBA_GOOD  = 0.370
XWOBA_ELITE_MULT = 1.10
XWOBA_GOOD_MULT  = 1.05

BARREL_PCT_ELITE      = 15.0
BARREL_PCT_ELITE_MULT = 1.05

# Superstar shield: elite xwOBA players can't fall below this fraction of base score
SUPERSTAR_FLOOR = 0.85

# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------
WIND_SPEED_MODERATE = 10   # MPH — minimum to apply wind multiplier
WIND_SPEED_STRONG   = 20   # MPH — threshold for stronger multiplier

WIND_OUT_MODERATE_MULT = 1.05
WIND_OUT_STRONG_MULT   = 1.10
WIND_IN_MODERATE_MULT  = 0.95
WIND_IN_STRONG_MULT    = 0.90

HEAT_THRESHOLD = 85    # °F — above this, apply heat penalty
HEAT_PENALTY   = 0.95

RAIN_HIGH_RISK_PCT     = 60   # % chance — high risk warning
RAIN_MODERATE_RISK_PCT = 30   # % chance — moderate risk warning

# ---------------------------------------------------------------------------
# Pitcher scoring
# ---------------------------------------------------------------------------
PITCHER_STAT_MULT_MIN    = 0.80
PITCHER_STAT_MULT_MAX    = 1.20
PITCHER_ERA_SKILL_WEIGHT = 0.10   # Multiplier per ERA unit of xERA improvement

OPP_POWER_NEUTRAL  = 52.0   # League-average hitter efficiency baseline score
OPP_POWER_MULT_MIN = 0.85
OPP_POWER_MULT_MAX = 1.15

AGG_BVP_MIN_PA   = 3
AGG_BVP_GOOD_OPS = 0.650   # Below this is favorable for the pitcher
AGG_BVP_BAD_OPS  = 0.850   # Above this is unfavorable for the pitcher
AGG_BVP_GOOD_MULT = 1.12
AGG_BVP_BAD_MULT  = 0.88

# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------
MIN_SCORE_FLOOR = 40.0   # Players projected below this are not started

# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------
TEAM_IDS = [7582, 7587, 7581, 7641]

TEAM_NAMES = {
    7582: "Zurich Zebras",
    7587: "Ghost Ride the WHIP",
    7581: "Austin Waves",
    7641: "LawDog",
}

# Players who should never be benched when starting in MLB — update as roster changes.
# Keyed by Ottoneu team_id; teams not listed get an empty list.
DO_NOT_SIT = {
    7582: [
        "Trea Turner", "Yordan Alvarez", "Kyle Schwarber",
        "Christian Yelich", "Junior Caminero", "Kazuma Okamoto",
    ],
}

# ---------------------------------------------------------------------------
# Projection systems
# ---------------------------------------------------------------------------
VALID_PROJECTION_SYSTEMS = {"steamer", "atc"}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = "optimizer.log"

def setup_logging(console_level=logging.WARNING, file_level=logging.INFO):
    """
    Configure the root logger.

    console_level — minimum level printed to the terminal (default: WARNING,
                    so the CLI stays clean and only problems break through).
    file_level    — minimum level written to optimizer.log (default: INFO,
                    capturing all status messages for post-run inspection).
    """
    root = logging.getLogger()
    if root.handlers:
        return  # Already configured — idempotent

    root.setLevel(logging.DEBUG)  # Let handlers filter individually

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — INFO and above → optimizer.log
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(file_level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler — WARNING and above → stdout (keeps Rich output clean)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(console_level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
def validate_date(date_str: str) -> str:
    """Raises ValueError with a clear message if date_str is not YYYY-MM-DD."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        raise ValueError(f"Invalid date '{date_str}'. Expected format: YYYY-MM-DD.")

def validate_projection_system(system: str) -> str:
    """Raises ValueError if system is not a known projection system."""
    s = system.lower()
    if s not in VALID_PROJECTION_SYSTEMS:
        raise ValueError(
            f"Unknown projection system '{system}'. "
            f"Valid options: {', '.join(sorted(VALID_PROJECTION_SYSTEMS))}"
        )
    return s
