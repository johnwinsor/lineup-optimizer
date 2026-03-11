import json
import pandas as pd
from statcast_harvester import StatCastHarvester
from daily_engine import DailyEngine
from tabulate import tabulate
from datetime import datetime
import re

class ZebrasScout:
    def __init__(self):
        self.statcast = StatCastHarvester()
        self.engine = DailyEngine() # To leverage the logic for projections
        
    def _clean_name(self, html_name):
        # Extract "Carlos Santana" from "<a href="...">Carlos Santana</a>"
        match = re.search(r'>(.*?)</a>', html_name)
        return match.group(1) if match else html_name

    def find_best_free_agents(self, top_n=20, min_pa=50):
        if not os.path.exists('free_agents.json'):
            print("Error: free_agents.json not found. Run scout_harvester.py first.")
            return
            
        with open('free_agents.json', 'r') as f:
            data = json.load(f).get('data', [])
            
        df = pd.DataFrame(data)
        if df.empty:
            print("No free agents found.")
            return

        # 1. Filter by Minimum PA
        df['PA'] = df['PA'].astype(float)
        df = df[df['PA'] >= min_pa].copy()
        
        if df.empty:
            print(f"No free agents found with at least {min_pa} PA.")
            return

        # 2. Basic Cleaning
        df['CleanName'] = df['Name'].apply(self._clean_name)
        
        # 2. Project Efficiency (Algorithm V2)
        # We'll use the same formula: (R+HR+RBI+SB)/PA * 100 + AVG * 100
        # These fields are directly in the FanGraphs JSON
        df['BaseScore'] = (
            (df['R'].astype(float) + df['HR'].astype(float) + df['RBI'].astype(float) + df['SB'].astype(float)) / 
            df['PA'].astype(float).replace(0, 1) * 100
        ) + (df['AVG'].astype(float) * 100)
        
        # 3. Apply Statcast Multipliers
        # Use current weight (March = 0% recency)
        today = datetime.now().strftime("%Y-%m-%d")
        weight_current = self.engine._get_recency_weight(today)
        
        final_scores = []
        for _, row in df.iterrows():
            mlb_id = row['xMLBAMID']
            multiplier = 1.0
            
            sc = self.statcast.get_blended_hitter_stats(mlb_id, weight_current=weight_current)
            if sc is not None:
                xwoba = float(sc.get('xwOBA', 0))
                if xwoba > 0.400: multiplier *= 1.10
                elif xwoba > 0.370: multiplier *= 1.05
                
                barrel = float(sc.get('Barrel%', 0))
                if barrel > 15.0: multiplier *= 1.05
            
            final_scores.append(row['BaseScore'] * multiplier)
            
        df['ZebrasScore'] = final_scores
        
        # 4. Filter and Rank
        # Sort by efficiency
        top_fa = df.sort_values(by='ZebrasScore', ascending=False).head(top_n)
        
        print(f"\n=== TOP {top_n} FREE AGENT HITTERS (League 1077) ===")
        print(tabulate(top_fa[['CleanName', 'position', 'PA', 'ZebrasScore']], 
                       headers=['Player', 'POS', 'PA', 'Efficiency'], 
                       tablefmt='grid', showindex=False, floatfmt=".2f"))

if __name__ == "__main__":
    import os
    import argparse
    
    parser = argparse.ArgumentParser(description="Scout the best available free agents in League 1077.")
    parser.add_argument("--pa", type=int, default=50, help="Minimum Plate Appearances (default: 50)")
    parser.add_argument("--top", type=int, default=20, help="Number of players to show (default: 20)")
    
    args = parser.parse_args()
    
    scout = ZebrasScout()
    scout.find_best_free_agents(top_n=args.top, min_pa=args.pa)
