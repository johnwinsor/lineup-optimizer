import pandas as pd
import numpy as np
from scipy.optimize import linprog
from enricher import OttoneuEnricher
from daily_engine import DailyEngine

class OttoneuOptimizer:
    def __init__(self, league_id=1077, team_id=7582, min_score=40.0, projection_system="steamer"):
        self.enricher = OttoneuEnricher(league_id, team_id, projection_system=projection_system)
        self.daily_engine = DailyEngine(league_id, team_id, projection_system=projection_system)
        self.min_score = min_score
        # Players who should never be benched if they are starting in MLB (Team 7582 specific)
        self.do_not_sit = [
            "Trea Turner", "Yordan Alvarez", "Kyle Schwarber", 
            "Christian Yelich", "Junior Caminero", "Kazuma Okamoto"
        ] if team_id == 7582 else []

    def optimize_lineup(self, target_date=None):
        if target_date:
            print(f"Optimizing for specific date: {target_date}")
            hitters = self.daily_engine.get_daily_projections(target_date)
            # Filter for players who are actually starting in MLB
            hitters = hitters[hitters['IsStarting'] == True].copy()
            score_col = 'DailyScore'
            current_min = self.min_score
        else:
            hitters = self.enricher.enrich_roster()
            hitters = hitters.dropna(subset=['Score'])
            score_col = 'Score'
            current_min = 0
            
        if hitters.empty:
            print("No players available to optimize.")
            return None
            
        slots = ['C1', 'C2', '1B', '2B', 'SS', 'MI', '3B', 'OF1', 'OF2', 'OF3', 'OF4', 'OF5', 'UTIL']
        num_players = len(hitters)
        num_slots = len(slots)
        
        # objective function: maximize (Score - min_score)
        c = []
        for _, row in hitters.iterrows():
            is_core = row['Name'] in self.do_not_sit
            for s in range(num_slots):
                profit = (row[score_col] - current_min)
                if is_core and target_date:
                    profit += 1000 # Force inclusion of DO NOT SIT players
                c.append(-profit)
        
        A_eq = []
        b_eq = []
        A_ub = []
        b_ub = []
        
        for s in range(num_slots):
            row_constraint = np.zeros(num_players * num_slots)
            for p in range(num_players):
                row_constraint[p * num_slots + s] = 1
            if target_date:
                A_ub.append(row_constraint)
                b_ub.append(1)
            else:
                A_eq.append(row_constraint)
                b_eq.append(1)
            
        for p in range(num_players):
            row_constraint = np.zeros(num_players * num_slots)
            for s in range(num_slots):
                row_constraint[p * num_slots + s] = 1
            A_ub.append(row_constraint)
            b_ub.append(1)
            
        bounds = []
        for p_idx, player_row in hitters.iterrows():
            eligibility = self._get_eligibility(player_row['POS'])
            for s_name in slots:
                if self._is_eligible(s_name, eligibility):
                    bounds.append((0, 1))
                else:
                    bounds.append((0, 0))
                    
        if not A_eq:
            A_eq, b_eq = None, None
            
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
        
        if not res.success:
            print("Optimization failed:", res.message)
            return None
            
        chosen_players = []
        x = res.x.reshape((num_players, num_slots))
        for p in range(num_players):
            for s in range(num_slots):
                if x[p, s] > 0.5:
                    res_dict = {
                        'Slot': slots[s],
                        'Player': hitters.iloc[p]['Name'],
                        'POS': hitters.iloc[p]['POS'],
                        'Score': hitters.iloc[p][score_col]
                    }
                    if 'Breakdown' in hitters.columns:
                        res_dict['Breakdown'] = hitters.iloc[p]['Breakdown']
                    if 'Opponent' in hitters.columns:
                        res_dict['Opponent'] = hitters.iloc[p]['Opponent']
                    if 'SP_xERA' in hitters.columns:
                        res_dict['SP_xERA'] = hitters.iloc[p]['SP_xERA']
                    if 'Warning' in hitters.columns:
                        res_dict['Warning'] = hitters.iloc[p]['Warning']
                    if 'GameTime' in hitters.columns:
                        res_dict['GameTime'] = hitters.iloc[p]['GameTime']
                    chosen_players.append(res_dict)
        
        if not chosen_players:
            return pd.DataFrame()
            
        df = pd.DataFrame(chosen_players)
        df['Slot'] = pd.Categorical(df['Slot'], categories=slots, ordered=True)
        return df.sort_values(by='Slot')

    def _get_eligibility(self, pos_str):
        return pos_str.replace('/', ' ').split()

    def _is_eligible(self, slot_name, eligibility):
        if slot_name.startswith('C'):
            return 'C' in eligibility
        if slot_name == '1B':
            return '1B' in eligibility
        if slot_name == '2B':
            return '2B' in eligibility
        if slot_name == 'SS':
            return 'SS' in eligibility
        if slot_name == 'MI':
            return '2B' in eligibility or 'SS' in eligibility
        if slot_name == '3B':
            return '3B' in eligibility
        if slot_name.startswith('OF'):
            return 'OF' in eligibility
        if slot_name == 'UTIL':
            return True # any hitter
        return False

if __name__ == "__main__":
    optimizer = OttoneuOptimizer()
    lineup = optimizer.optimize_lineup(target_date="2024-06-15")
    if lineup is not None and not lineup.empty:
        print("Optimized Lineup:")
        print(lineup)
        print(f"\nTotal Team Score: {lineup['Score'].sum():.2f}")
    else:
        print("No valid lineup generated.")
