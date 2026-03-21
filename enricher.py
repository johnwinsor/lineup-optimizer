import pandas as pd
import json
import requests
import os
from harvester import OttoneuScraper
from crosswalks import normalize_name

class OttoneuEnricher:
    def __init__(self, league_id=1077, team_id=7582, projection_system="steamer"):
        self.scraper = OttoneuScraper(league_id, team_id)
        self.projection_system = projection_system.lower()

    def fetch_projections(self):
        print(f"Loading {self.projection_system.upper()} batting projections from local cache...")
        filename = f"projections-{self.projection_system}.json"
        
        # Backward compatibility for old filename
        if not os.path.exists(filename) and self.projection_system == "steamer":
            filename = "steamer-hitters.json"

        try:
            with open(filename, "r") as f:
                data = json.load(f)
            return pd.DataFrame(data)
        except FileNotFoundError:
            raise Exception(f"Failed to load {self.projection_system.upper()} projections. Please run 'uv run python fetch_statcast.py' first.")

    def enrich_roster(self):
        hitters, pitchers = self.scraper.get_roster()
        projections = self.fetch_projections()
        
        # Initialize result columns in hitters
        for col in ['playerid', 'PA_y', 'R_y', 'HR_y', 'RBI_y', 'SB_y', 'AVG_y', 'xMLBAMID']:
            hitters[col] = None

        # Create normalization mapping for projections
        projections['norm_name'] = projections['PlayerName'].apply(normalize_name)
        
        # 1. Match Loop
        for idx, row in hitters.iterrows():
            name = row['Name']
            fgid = str(row.get('FGID', ''))
            norm = normalize_name(name)
            
            match = pd.DataFrame()
            
            # Try FGID match if available
            if fgid and fgid != 'nan' and fgid != '':
                match = projections[projections['playerid'].astype(str) == fgid]
            
            # Try Normalized Name match if no FGID match
            if match.empty:
                match = projections[projections['norm_name'] == norm]
            
            if not match.empty:
                m = match.iloc[0]
                hitters.at[idx, 'playerid'] = m['playerid']
                hitters.at[idx, 'PA_y'] = m['PA']
                hitters.at[idx, 'R_y'] = m['R']
                hitters.at[idx, 'HR_y'] = m['HR']
                hitters.at[idx, 'RBI_y'] = m['RBI']
                hitters.at[idx, 'SB_y'] = m['SB']
                hitters.at[idx, 'AVG_y'] = m['AVG']
                hitters.at[idx, 'xMLBAMID'] = m['xMLBAMID']

        # Calculate a simple efficiency score
        # Note: We use .astype(float) and handle division by zero
        hitters['Score'] = (
            (hitters['R_y'].fillna(0).astype(float) + 
             hitters['HR_y'].fillna(0).astype(float) + 
             hitters['RBI_y'].fillna(0).astype(float) + 
             hitters['SB_y'].fillna(0).astype(float)) / 
            hitters['PA_y'].fillna(1).astype(float).replace(0, 1) * 100
        ) + (hitters['AVG_y'].fillna(0).astype(float) * 100)
        
        return hitters.sort_values(by='Score', ascending=False)

if __name__ == "__main__":
    enricher = OttoneuEnricher()
    hitters = enricher.enrich_roster()
    print("Enriched Hitters (Top 10 by Score):")
    print(hitters[['Name', 'POS', 'PA_y', 'Score']].head(10))
