import requests
from bs4 import BeautifulSoup
import pandas as pd

class OttoneuScraper:
    _roster_cache = {} # { team_id: (hitters_df, pitchers_df) }

    def __init__(self, league_id=1077, team_id=7582):
        self.league_id = league_id
        self.team_id = team_id
        self.url = f"https://ottoneu.fangraphs.com/{league_id}/team?team={team_id}"

    def get_roster(self):
        if self.team_id in OttoneuScraper._roster_cache:
            h, p = OttoneuScraper._roster_cache[self.team_id]
            return h.copy(), p.copy()

        print(f"Scraping Ottoneu roster for team {self.team_id}...")
        response = requests.get(self.url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch {self.url}: {response.status_code}")
        
        soup = BeautifulSoup(response.content, "html.parser")
        tables = soup.find_all("table")
        if len(tables) < 2:
            raise Exception("Could not find both hitters and pitchers tables on page")
            
        hitters = self._parse_table(tables[0])
        pitchers = self._parse_table(tables[1])
        
        OttoneuScraper._roster_cache[self.team_id] = (hitters, pitchers)
        return hitters.copy(), pitchers.copy()

    def _parse_table(self, table):
        headers_row = table.find("thead").find_all("th")
        headers = [th.text.strip() for th in headers_row]
        rows = table.find("tbody").find_all("tr")
        
        data = []
        for row in rows:
            cols = row.find_all("td")
            if not cols: continue
            
            row_data = {}
            for i, col in enumerate(cols):
                if i >= len(headers): break
                header = headers[i]
                
                # Ottoneu calls the name column "Player" now, but we expect "Name"
                if header == 'Player' or header == 'Name':
                    # Parse name and Ottoneu ID
                    link = col.find("a")
                    if link:
                        row_data['OttoneuID'] = link['href'].split('=')[-1]
                        full_text = col.text.strip()
                        
                        # Fix: Improve injury detection by counting "IL" and specifically handling "MIL"
                        il_count = full_text.count('IL')
                        if "MIL" in full_text:
                            row_data['Injured'] = il_count > 1
                        else:
                            row_data['Injured'] = il_count > 0
                        
                        # Robust team extraction
                        teams = ['ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET', 
                                 'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'OAK', 
                                 'PHI', 'PIT', 'SDP', 'SEA', 'SFG', 'STL', 'TBR', 'TEX', 'TOR', 'WSH']
                        
                        team_candidate = ""
                        # Try to find a known team in the text
                        for t in teams:
                            if t in full_text:
                                team_candidate = t
                                break
                        
                        # Extract name (everything before the first paren or team code)
                        name_part = full_text
                        for t in teams:
                            if t in name_part:
                                name_part = name_part.split(t)[0].strip()
                        if '(' in name_part:
                            name_part = name_part.split('(')[0].strip()
                        
                        row_data['Name'] = name_part
                        row_data['Team'] = team_candidate
                        
                        # Extract FGID
                        fg_link = col.find("a", href=lambda x: x and "fangraphs.com" in x)
                        if fg_link:
                            row_data['FGID'] = fg_link['href'].split('playerid=')[-1].split('&')[0]
                    else:
                        row_data['Name'] = col.text.strip()
                        row_data['Team'] = ""
                else:
                    val = col.text.strip()
                    if header == 'POS':
                        row_data[header] = val
                        row_data['PosList'] = val.replace('/', ' ').split()
                    else:
                        row_data[header] = val
            data.append(row_data)
        
        return pd.DataFrame(data)

if __name__ == "__main__":
    scraper = OttoneuScraper()
    hitters, pitchers = scraper.get_roster()
    print("Hitters Columns:", hitters.columns.tolist())
    print(hitters[['Name', 'Team', 'Injured', 'FGID', 'OttoneuID']].head())
    print("\nPitchers Columns:", pitchers.columns.tolist())
    print(pitchers[['Name', 'Team', 'Injured', 'FGID', 'OttoneuID']].head())
