import pandas as pd
import numpy as np
import logging
from scipy.optimize import linprog
from enricher import OttoneuEnricher
from daily_engine import DailyEngine
import config as C

logger = logging.getLogger(__name__)


class OttoneuOptimizer:
    def __init__(self, league_id=1077, team_id=7582, min_score=None, projection_system="steamer"):
        self.enricher = OttoneuEnricher(league_id, team_id, projection_system=projection_system)
        self.daily_engine = DailyEngine(league_id, team_id, projection_system=projection_system)
        self.min_score = min_score if min_score is not None else C.MIN_SCORE_FLOOR
        # Pull "do not sit" list from config; defaults to empty for unlisted teams
        self.do_not_sit = C.DO_NOT_SIT.get(team_id, [])

    def optimize_lineup(self, target_date=None):
        if target_date:
            logger.info(f"Optimizing lineup for {target_date}...")
            hitters = self.daily_engine.get_daily_projections(target_date)
            hitters = hitters[hitters['IsStarting'] == True].copy()
            score_col = 'DailyScore'
            current_min = self.min_score
        else:
            hitters = self.enricher.enrich_roster()
            hitters = hitters.dropna(subset=['Score'])
            score_col = 'Score'
            current_min = 0

        if hitters.empty:
            logger.warning("No players available to optimize — roster is empty after filtering.")
            return None

        slots = ['C1', 'C2', '1B', '2B', 'SS', 'MI', '3B', 'OF1', 'OF2', 'OF3', 'OF4', 'OF5', 'UTIL']
        num_players = len(hitters)
        num_slots = len(slots)

        # Objective: maximise (score - floor), with large bonus to force DNS players in
        c = []
        for _, row in hitters.iterrows():
            is_core = row['Name'] in self.do_not_sit
            for _ in slots:
                profit = row[score_col] - current_min
                if is_core and target_date:
                    profit += 1000  # Force inclusion
                c.append(-profit)

        A_ub, b_ub = [], []
        A_eq, b_eq = [], []

        # Each slot filled at most once (≤1 when daily — allows empty slots on off-days)
        for s in range(num_slots):
            row_c = np.zeros(num_players * num_slots)
            for p in range(num_players):
                row_c[p * num_slots + s] = 1
            if target_date:
                A_ub.append(row_c); b_ub.append(1)
            else:
                A_eq.append(row_c); b_eq.append(1)

        # Each player used in at most one slot
        for p in range(num_players):
            row_c = np.zeros(num_players * num_slots)
            for s in range(num_slots):
                row_c[p * num_slots + s] = 1
            A_ub.append(row_c); b_ub.append(1)

        # Positional eligibility bounds
        bounds = []
        for _, player_row in hitters.iterrows():
            eligibility = self._get_eligibility(player_row['POS'])
            for s_name in slots:
                bounds.append((0, 1) if self._is_eligible(s_name, eligibility) else (0, 0))

        res = linprog(
            c,
            A_ub=A_ub, b_ub=b_ub,
            A_eq=A_eq if A_eq else None,
            b_eq=b_eq if b_eq else None,
            bounds=bounds,
            method='highs',
        )

        if not res.success:
            logger.error(f"LP optimization failed: {res.message}")
            return None

        chosen = []
        x = res.x.reshape((num_players, num_slots))
        for p in range(num_players):
            for s in range(num_slots):
                if x[p, s] > 0.5:
                    player = hitters.iloc[p]
                    entry = {
                        'Slot':   slots[s],
                        'Player': player['Name'],
                        'POS':    player['POS'],
                        'Score':  player[score_col],
                    }
                    for col in ('Breakdown', 'Opponent', 'SP_xERA', 'Warning', 'GameTime'):
                        if col in hitters.columns:
                            entry[col] = player[col]
                    chosen.append(entry)

        if not chosen:
            logger.warning("Optimizer produced no selections — all scores may be below floor.")
            return pd.DataFrame()

        df = pd.DataFrame(chosen)
        df['Slot'] = pd.Categorical(df['Slot'], categories=slots, ordered=True)
        return df.sort_values(by='Slot')

    def _get_eligibility(self, pos_str):
        return pos_str.replace('/', ' ').split()

    def _is_eligible(self, slot_name, eligibility):
        if slot_name.startswith('C'):  return 'C'  in eligibility
        if slot_name == '1B':          return '1B' in eligibility
        if slot_name == '2B':          return '2B' in eligibility
        if slot_name == 'SS':          return 'SS' in eligibility
        if slot_name == 'MI':          return '2B' in eligibility or 'SS' in eligibility
        if slot_name == '3B':          return '3B' in eligibility
        if slot_name.startswith('OF'): return 'OF' in eligibility
        if slot_name == 'UTIL':        return True
        return False


if __name__ == "__main__":
    import config as C
    C.setup_logging()
    optimizer = OttoneuOptimizer()
    lineup = optimizer.optimize_lineup(target_date="2025-06-15")
    if lineup is not None and not lineup.empty:
        print(lineup[['Slot', 'Player', 'Score']].to_string(index=False))
        print(f"\nTotal Score: {lineup['Score'].sum():.2f}")
    else:
        print("No valid lineup generated.")
