import pandas as pd
import json
import requests
from harvester import OttoneuScraper

class OttoneuEnricher:
    def __init__(self, league_id=1077, team_id=7582):
        self.scraper = OttoneuScraper(league_id, team_id)

    def fetch_steamer_projections(self):
        print("Fetching Steamer batting projections...")
        url = "https://www.fangraphs.com/api/projections?stats=bat&type=steamer"
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Failed to fetch Steamer projections")
        return pd.DataFrame(response.json())

    def enrich_roster(self):
        hitters, pitchers = self.scraper.get_roster()
        projections = self.fetch_steamer_projections()
        
        # Match by name
        # Note: Projections have 'PlayerName', Roster has 'Name'
        enriched_hitters = pd.merge(
            hitters, 
            projections[['PlayerName', 'PA', 'R', 'HR', 'RBI', 'SB', 'AVG', 'playerid']], 
            left_on='Name', 
            right_on='PlayerName', 
            how='left'
        )
        
        # Calculate a simple efficiency score (sum of counting stats per PA)
        # 5x5 categories: R, HR, RBI, SB, AVG
        # We'll weight them equally for now, except AVG which is already a rate.
        # Score = (R + HR + RBI + SB) / PA * 100  + AVG * 100
        enriched_hitters['Score'] = (
            (enriched_hitters['R_y'].astype(float) + 
             enriched_hitters['HR_y'].astype(float) + 
             enriched_hitters['RBI_y'].astype(float) + 
             enriched_hitters['SB_y'].astype(float)) / 
            enriched_hitters['PA_y'].astype(float) * 100
        ) + (enriched_hitters['AVG_y'].astype(float) * 100)
        
        return enriched_hitters.sort_values(by='Score', ascending=False)

if __name__ == "__main__":
    enricher = OttoneuEnricher()
    hitters = enricher.enrich_roster()
    print("Enriched Hitters (Top 10 by Score):")
    print(hitters[['Name', 'POS', 'PA_y', 'Score']].head(10))
