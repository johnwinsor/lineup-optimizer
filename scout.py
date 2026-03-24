import json
import pandas as pd
import os
import re
from datetime import datetime
from statcast_harvester import StatCastHarvester
from daily_engine import DailyEngine
from display_utils import print_header, display_dataframe, print_section

class ZebrasScout:
    def __init__(self, projection_system="steamer"):
        self.statcast = StatCastHarvester()
        self.engine = DailyEngine(projection_system=projection_system) # To leverage the logic for projections
        self.projection_system = projection_system

    def _clean_name(self, html_name):
        if not html_name: return ""
        # Extract "Carlos Santana" from "<a href="...">Carlos Santana</a>"
        match = re.search(r'>(.*?)</a>', html_name)
        return match.group(1) if match else html_name

    def find_best_free_agents(self, top_n=20, min_pa=50):
        print_header(f"Zebras Free Agent Scout [{self.projection_system.upper()}]", f"Min PA: {min_pa}")
        
        if not os.path.exists('free_agents.json'):
            print("[red]Error: free_agents.json not found. Run scout_harvester.py first.[/red]")
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
            
        df['Score'] = final_scores
        df['Player'] = df['CleanName']
        df['POS'] = df['position']
        
        # 4. Filter and Rank
        # Sort by efficiency
        top_fa = df.sort_values(by='Score', ascending=False).head(top_n)
        
        display_dataframe(top_fa, title=f"TOP {top_n} FREE AGENT HITTERS (League 1077)", 
                          columns=['Player', 'POS', 'PA', 'Score'])

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scout the best available free agents in League 1077.")
    parser.add_argument("--pa", type=int, default=50, help="Minimum Plate Appearances (default: 50)")
    parser.add_argument("--top", type=int, default=20, help="Number of players to show (default: 20)")
    parser.add_argument("--projection", type=str, default="steamer", help="Projection system (steamer, atc, thebat)")
    
    args = parser.parse_args()
    
    scout = ZebrasScout(projection_system=args.projection)
    scout.find_best_free_agents(top_n=args.top, min_pa=args.pa)
