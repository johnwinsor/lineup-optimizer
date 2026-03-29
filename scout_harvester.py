import subprocess
import json
import os

LEAGUE_ID = 1077
TEAM_ID = 7582

def fetch_fangraphs_api(team_id, filename):
    # ft=-1 for free agents, ft=TEAM_ID for roster
    url = f"https://www.fangraphs.com/api/leaders/major-league/data?age=&pos=all&stats=bat&lg=all&qual=0&season=2025&season1=2025&startdate=2025-03-01&enddate=2025-11-01&month=0&hand=&team=0&pageitems=2000000000&pagenum=1&ind=0&rost=0&players=&type=502&postseason=&sortdir=default&sortstat=FSalary&fl={LEAGUE_ID}&ft={team_id}"
    
    print(f"Fetching data for ft={team_id}...")
    try:
        result = subprocess.run(['curl', '-s', url], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        with open(filename, 'w') as f:
            json.dump(data, f)
        print(f"Successfully saved {len(data.get('data', []))} records to {filename}")
        return data
    except Exception as e:
        print(f"Error fetching {filename}: {e}")
        return None

def main():
    # 1. Fetch Free Agents
    fetch_fangraphs_api(-1, "free_agents.json")
    # 2. Fetch Our Roster (API version)
    fetch_fangraphs_api(TEAM_ID, "zebras_roster_api.json")

if __name__ == "__main__":
    main()
