import json
import pandas as pd
import os

class StatCastHarvester:
    def __init__(self, prior_year=2025, current_year=2026):
        self.prior_year = prior_year
        self.current_year = current_year
        
        # Load Prior Year
        self.prior_hitters = self._load_data(f'statcast-hitters-{prior_year}.json')
        self.prior_pitchers = self._load_data(f'statcast-pitchers-{prior_year}.json')
        
        # Load Current Year
        self.current_hitters = self._load_data(f'statcast-hitters-{current_year}.json')
        self.current_pitchers = self._load_data(f'statcast-pitchers-{current_year}.json')

    def _load_data(self, filename):
        if not os.path.exists(filename):
            return pd.DataFrame()
        try:
            with open(filename, 'r') as f:
                raw = json.load(f)
                df = pd.DataFrame(raw.get('data', []))
                if not df.empty:
                    return df.set_index('xMLBAMID')
                return df
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return pd.DataFrame()

    def get_blended_hitter_stats(self, mlb_id, weight_current=0.0):
        prior = self.prior_hitters.loc[mlb_id] if not self.prior_hitters.empty and mlb_id in self.prior_hitters.index else None
        current = self.current_hitters.loc[mlb_id] if not self.current_hitters.empty and mlb_id in self.current_hitters.index else None
        
        if prior is None and current is None:
            return None
        
        if prior is None: return current
        if current is None or weight_current == 0: return prior
        
        # Blend specific metrics
        weight_prior = 1.0 - weight_current
        blended = prior.copy()
        
        for col in ['xwOBA', 'xAVG', 'Barrel%', 'HardHit%']:
            if col in prior and col in current:
                try:
                    p_val = float(prior[col])
                    c_val = float(current[col])
                    blended[col] = (p_val * weight_prior) + (c_val * weight_current)
                except (ValueError, TypeError):
                    pass
        return blended

    def get_blended_pitcher_stats(self, mlb_id, weight_current=0.0):
        prior = self.prior_pitchers.loc[mlb_id] if not self.prior_pitchers.empty and mlb_id in self.prior_pitchers.index else None
        current = self.current_pitchers.loc[mlb_id] if not self.current_pitchers.empty and mlb_id in self.current_pitchers.index else None
        
        if prior is None and current is None:
            return None
        
        if prior is None: return current
        if current is None or weight_current == 0: return prior
        
        weight_prior = 1.0 - weight_current
        blended = prior.copy()
        
        # xERA, SIERA, kwERA
        for col in ['xERA', 'SIERA', 'kwERA', 'ERA']:
            if col in prior and col in current:
                try:
                    p_val = float(prior[col])
                    c_val = float(current[col])
                    blended[col] = (p_val * weight_prior) + (c_val * weight_current)
                except (ValueError, TypeError):
                    pass
        return blended

if __name__ == "__main__":
    harvester = StatCastHarvester()
    # Test blended calculation
    skenes_id = 694973
    stats = harvester.get_blended_pitcher_stats(skenes_id, weight_current=0.3)
    if stats is not None:
        print(f"Blended stats for ID {skenes_id}: xERA={stats.get('xERA')}")
