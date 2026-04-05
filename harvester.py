import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

class OttoneuScraper:
    _roster_cache = {} # { team_id: (hitters_df, pitchers_df) }

    def __init__(self, league_id=1077, team_id=7582):
        self.league_id = league_id
        self.team_id = team_id
        self.url = f"https://ottoneu.fangraphs.com/{league_id}/team?team={team_id}"

    _level_cache = {} # { fg_id: level_string }

    def get_player_level(self, fg_id):
        if not fg_id: return "MLB"
        if fg_id in self._level_cache:
            return self._level_cache[fg_id]
        
        try:
            url = f"https://www.fangraphs.com/players/player/{fg_id}/stats"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                # Look for (AAA), (AA), etc. in the team/position area
                # It's often in a <span> or aria-label
                text = soup.get_text()
                # Search for level patterns
                levels = ["(AAA)", "(AA)", "(A+)", "(A)", "(A-)", "(RK)"]
                for level in levels:
                    if level in text:
                        res = level.strip("()")
                        self._level_cache[fg_id] = res
                        return res
                
                # Check for "mlevel":"..." in the scripts
                scripts = soup.find_all("script")
                for script in scripts:
                    if script.string and '"mlevel":' in script.string:
                        match = re.search(r'"mlevel":"([^"]+)"', script.string)
                        if match:
                            mlevel = match.group(1)
                            if mlevel != "MLB":
                                self._level_cache[fg_id] = mlevel
                                return mlevel
            
            self._level_cache[fg_id] = "MLB"
            return "MLB"
        except Exception:
            return "MLB"

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
            # Fallback for different page structures
            tables = soup.find_all("table", class_="rumble-table")
            
        if len(tables) < 2:
            raise Exception("Could not find both hitters and pitchers tables on page")
            
        hitters = self._parse_table(tables[0], is_pitcher=False)
        pitchers = self._parse_table(tables[1], is_pitcher=True)
        
        OttoneuScraper._roster_cache[self.team_id] = (hitters, pitchers)
        return hitters.copy(), pitchers.copy()

    def _parse_table(self, table, is_pitcher=False):
        headers_row = table.find("thead").find_all("th")
        headers = [th.text.strip() for th in headers_row]
        rows = table.find("tbody").find_all("tr")
        
        data = []
        for row in rows:
            cols = row.find_all("td")
            if not cols: continue
            
            # Check if this is a section header (like "Minors" or "Injured")
            if len(cols) == 1 and 'section-leader' in cols[0].get('class', []):
                continue

            row_data = {}
            # Check for Minors/IL status based on row class or position in table
            is_minors = 'minors' in str(row.get('class', [])).lower()
            
            for i, col in enumerate(cols):
                if i >= len(headers): break
                header = headers[i]
                
                if header == 'Player' or header == 'Name':
                    link = col.find("a")
                    full_text = col.text.strip()
                    
                    # Robust team extraction from the full cell text
                    teams = ['ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET', 
                             'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'OAK', 
                             'PHI', 'PIT', 'SDP', 'SEA', 'SFG', 'STL', 'TBR', 'TEX', 'TOR', 'WSH', 'WSN', 'ATH']
                    
                    team_candidate = ""
                    for t in teams:
                        # Look for team code surrounded by whitespace or at the end
                        if re.search(rf'\b{t}\b', full_text):
                            team_candidate = t
                            break
                    
                    if link:
                        row_data['OttoneuID'] = link['href'].split('=')[-1]
                        row_data['Name'] = link.text.strip()
                        row_data['Team'] = team_candidate
                        
                        # Injury detection
                        il_count = full_text.count('IL')
                        if "MIL" in full_text:
                            row_data['Injured'] = il_count > 1
                        else:
                            row_data['Injured'] = il_count > 0
                            
                        # FGID extraction
                        fg_link = col.find("a", href=lambda x: x and "fangraphs.com" in x)
                        if fg_link:
                            row_data['FGID'] = fg_link['href'].split('playerid=')[-1].split('&')[0]
                    else:
                        row_data['Name'] = full_text
                        row_data['Team'] = team_candidate
                else:
                    val = col.text.strip()
                    if header == 'POS':
                        row_data[header] = val
                        row_data['PosList'] = val.replace('/', ' ').split()
                    elif header == 'Team' and val:
                        row_data['Team'] = val
                    else:
                        row_data[header] = val
            
            # Additional check for minors players who often have no team listed in the table
            if is_minors:
                row_data['IsMinors'] = True
                
            data.append(row_data)
        
        return pd.DataFrame(data)

if __name__ == "__main__":
    scraper = OttoneuScraper()
    hitters, pitchers = scraper.get_roster()
    print(hitters[['Name', 'Team', 'Injured']].head())
