import requests
from bs4 import BeautifulSoup
import pandas as pd

class OttoneuScraper:
    def __init__(self, league_id=1077, team_id=7582):
        self.league_id = league_id
        self.team_id = team_id
        self.url = f"https://ottoneu.fangraphs.com/{league_id}/team?team={team_id}"

    def get_roster(self):
        response = requests.get(self.url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch {self.url}: {response.status_code}")
        
        soup = BeautifulSoup(response.content, "html.parser")
        tables = soup.find_all('table')
        
        if not tables:
            raise Exception("No tables found on the page.")
        
        # Table 0: Hitters
        hitters_df = self._parse_table(tables[0], is_hitter=True)
        # Table 1: Pitchers
        pitchers_df = self._parse_table(tables[1], is_hitter=False)
        
        return hitters_df, pitchers_df

    def _parse_table(self, table, is_hitter=True):
        rows = table.find_all('tr')
        headers = [th.text.strip() for th in rows[0].find_all('th')]
        
        data = []
        for row in rows[1:]:
            cols = row.find_all('td')
            if not cols:
                continue
            
            row_data = {'FGID': None, 'OttoneuID': None}
            for i, col in enumerate(cols):
                header = headers[i]
                if header == 'Player':
                    player_link = col.find('a')
                    if player_link:
                        row_data['Name'] = player_link.text.strip()
                        href = player_link.get('href', '')
                        # Ottoneu player link is usually /playercard?player_id=XXXX or /XXXX/players/ID
                        if 'player_id=' in href:
                            row_data['OttoneuID'] = href.split('player_id=')[-1]
                        elif '/players/' in href:
                            row_data['OttoneuID'] = href.split('/')[-1]
                        
                        # Look for FanGraphs ID in any link in the cell
                        all_links = col.find_all('a')
                        for link in all_links:
                            l_href = link.get('href', '')
                            if 'fangraphs.com' in l_href:
                                if 'playerid=' in l_href:
                                    row_data['FGID'] = l_href.split('playerid=')[-1].split('&')[0]
                                elif '/players/' in l_href:
                                    parts = l_href.split('/')
                                    for part in parts:
                                        if part.isdigit():
                                            row_data['FGID'] = part
                                            break
                            # Some Ottoneu pages have a stats link that contains the FGID
                            elif 'statss.aspx?playerid=' in l_href:
                                row_data['FGID'] = l_href.split('playerid=')[-1].split('&')[0]

                        # Extract team from text (e.g. "Trea Turner PHI")
                        full_text = col.get_text(strip=True)
                        row_data['Team'] = full_text.replace(row_data['Name'], "").strip()
                        # Team info might contain other icons/text, clean it up
                        # PHI SS -> PHI
                        if row_data['Team']:
                            # Handle cases like "STL OUT" or "DET DH"
                            parts = row_data['Team'].split(' ')
                            team_candidate = parts[0]
                            # If it's something like "STLOUT", we need to be careful. 
                            # Most MLB abbreviations are 2-3 characters.
                            # Let's take the first 3 if it's not a known exception.
                            if len(team_candidate) > 3:
                                team_candidate = team_candidate[:3]
                            row_data['Team'] = team_candidate
                    else:
                        row_data['Name'] = col.text.strip()
                        row_data['Team'] = ""
                else:
                    val = col.text.strip()
                    if header == 'POS':
                        # Convert "1B/2B/3B" to ["1B", "2B", "3B"]
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
    print(hitters[['Name', 'Team', 'FGID', 'OttoneuID']].head())
    print("\nPitchers Columns:", pitchers.columns.tolist())
    print(pitchers[['Name', 'Team', 'FGID', 'OttoneuID']].head())
