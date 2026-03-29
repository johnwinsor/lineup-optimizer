import statsapi
import pandas as pd
from pybaseball import statcast_catcher_poptime, statcast_sprint_speed
import os
import json
from datetime import datetime

class DefenseHarvester:
    def __init__(self, year=2025):
        self.year = year
        self.catcher_cache = {}
        self.pitcher_cache = {}
        self.sprint_speed_cache = {}
        
        # Mapping for primary catchers to use when lineup is pending
        self.team_primary_catcher = {
            140: 605270, # TEX (Jonah Heim)
            138: 575929, # STL (Willson Contreras)
            143: 592663, # PHI (J.T. Realmuto)
            118: 543760, # KC (Salvador Perez)
            121: 642547, # NYM (Francisco Alvarez)
            147: 669221, # NYY (Austin Wells)
            135: 669374, # SD (Luis Campusano)
            119: 643393, # LAD (Will Smith)
            111: 660688, # BOS (Connor Wong)
            141: 663656, # TOR (Alejandro Kirk)
            117: 641598, # HOU (Yainer Diaz)
            142: 663728, # MIN (Ryan Jeffers)
            108: 669127, # LAA (Logan O'Hoppe)
            137: 672275, # SF (Patrick Bailey)
            144: 670351, # ATL (Sean Murphy)
            112: 669257, # CHC (Miguel Amaya)
            114: 666969, # CLE (Bo Naylor)
            113: 518595, # CIN (Travis d'Arnaud)
            134: 668942, # PIT (Joey Bart)
            115: 673490, # COL (Drew Romo)
            109: 664034, # ARI (Gabriel Moreno)
            146: 663550, # MIA (Nick Fortes)
            158: 668800, # MIL (William Contreras)
            120: 624431, # WAS (Keibert Ruiz)
            110: 663531, # BAL (Adley Rutschman)
            145: 686676, # CHW (Korey Lee)
            116: 668670, # DET (Jake Rogers)
            133: 650333, # OAK (Shea Langeliers)
            136: 663083, # SEA (Cal Raleigh)
            139: 666181, # TB (Logan Driscoll)
        }
        self._load_data()

    def _load_data(self):
        # 1. Catcher Pop Times (2024 as baseline, 2025 if available)
        try:
            df_catchers = statcast_catcher_poptime(2024)
            for _, row in df_catchers.iterrows():
                self.catcher_cache[int(row['entity_id'])] = float(row['pop_2b_sba'])
        except Exception:
            pass
            
        # 2. Sprint Speeds (To identify our own speedsters)
        try:
            df_sprint = statcast_sprint_speed(2024)
            for _, row in df_sprint.iterrows():
                self.sprint_speed_cache[int(row['player_id'])] = float(row['sprint_speed'])
        except Exception:
            pass

    def get_primary_catcher(self, team_id):
        return self.team_primary_catcher.get(team_id)

    def get_pop_time(self, catcher_id):
        return self.catcher_cache.get(catcher_id, 1.97) # 1.97 is MLB Average

    def get_pitcher_sb_rate(self, pitcher_id, year=2025):
        if pitcher_id in self.pitcher_cache:
            return self.pitcher_cache[pitcher_id]
            
        try:
            # StatsAPI for Pitcher Stolen Base %
            stats = statsapi.get('people', {
                'personIds': pitcher_id, 
                'hydrate': f'stats(group=[pitching],type=[season],season={year})'
            })
            if 'people' in stats and stats['people']:
                p = stats['people'][0]
                if 'stats' in p and p['stats']:
                    splits = p['stats'][0].get('splits', [])
                    if splits:
                        s = splits[0]['stat']
                        sb = s.get('stolenBases', 0)
                        cs = s.get('caughtStealing', 0)
                        attempts = sb + cs
                        if attempts >= 5:
                            rate = sb / attempts
                            self.pitcher_cache[pitcher_id] = rate
                            return rate
        except Exception:
            pass
            
        if year == 2026:
            return self.get_pitcher_sb_rate(pitcher_id, year=2025)
            
        return 0.75 # MLB Average SB% is roughly 75-80% now

    def get_sprint_speed(self, player_id):
        return self.sprint_speed_cache.get(player_id, 27.0) # 27.0 is MLB Average

if __name__ == "__main__":
    harvester = DefenseHarvester()
    # J.T. Realmuto
    print(f"Realmuto Pop Time: {harvester.get_pop_time(592663)}")
    # Gerrit Cole
    print(f"Gerrit Cole SB Rate: {harvester.get_pitcher_sb_rate(543037, 2024)}")
    # Trea Turner
    print(f"Trea Turner Sprint: {harvester.get_sprint_speed(607208)}")
