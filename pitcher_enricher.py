import pandas as pd
import json
import os
from harvester import OttoneuScraper
from crosswalks import normalize_name

class PitcherEnricher:
    def __init__(self, league_id=1077, team_id=7582, projection_system="steamer"):
        self.scraper = OttoneuScraper(league_id, team_id)
        self.projection_system = projection_system.lower()

    def fetch_projections(self):
        filename = f"projections-{self.projection_system}-pit.json"
        
        try:
            with open(filename, "r") as f:
                data = json.load(f)
            return pd.DataFrame(data)
        except FileNotFoundError:
            raise Exception(f"Failed to load {self.projection_system.upper()} pitcher projections. Run fetch_statcast.py first.")

    def enrich_roster(self):
        _, pitchers = self.scraper.get_roster()
        projections = self.fetch_projections()
        
        # Initialize result columns
        cols_to_add = ['playerid', 'K/9_y', 'BB/9_y', 'ERA_y', 'WHIP_y', 'W_y', 'xMLBAMID']
        for col in cols_to_add:
            pitchers[col] = None

        # Create normalization mapping
        projections['norm_name'] = projections['PlayerName'].apply(normalize_name)
        
        for idx, row in pitchers.iterrows():
            name = row['Name']
            fgid = str(row.get('FGID', ''))
            norm = normalize_name(name)
            
            match = pd.DataFrame()
            if fgid and fgid != 'nan' and fgid != '':
                match = projections[projections['playerid'].astype(str) == fgid]
            if match.empty:
                match = projections[projections['norm_name'] == norm]
            
            if not match.empty:
                m = match.iloc[0]
                pitchers.at[idx, 'playerid'] = m.get('playerid')
                pitchers.at[idx, 'K/9_y'] = m.get('K/9')
                pitchers.at[idx, 'BB/9_y'] = m.get('BB/9')
                pitchers.at[idx, 'ERA_y'] = m.get('ERA')
                pitchers.at[idx, 'WHIP_y'] = m.get('WHIP')
                pitchers.at[idx, 'W_y'] = m.get('W')
                pitchers.at[idx, 'xMLBAMID'] = m.get('xMLBAMID')

        # Calculate Base Efficiency Score (Pitcher V1)
        # Formula: (K/9 * 0.4) + (5.0 - ERA) + (1.5 - WHIP) * 2.0
        # This rewards high K, low ERA, and very low WHIP.
        pitchers['Score'] = (
            (pitchers['K/9_y'].fillna(0).astype(float) * 0.4) + 
            (5.0 - pitchers['ERA_y'].fillna(5.0).astype(float)) + 
            (1.5 - pitchers['WHIP_y'].fillna(1.5).astype(float)) * 2.0
        )
        
        return pitchers.sort_values(by='Score', ascending=False)

if __name__ == "__main__":
    enricher = PitcherEnricher()
    pitchers = enricher.enrich_roster()
    print("Enriched Pitchers (Top 10 by Score):")
    print(pitchers[['Name', 'Team', 'ERA_y', 'WHIP_y', 'K/9_y', 'Score']].head(10))
