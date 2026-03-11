import subprocess
import json
import os
import sys
from datetime import datetime

# We will fetch data for both the prior season (2025) and the current season (2026)
PRIOR_SEASON = 2025
CURRENT_SEASON = 2026

def get_url(stats_type, season):
    # type=24 is hitters, type=502 is pitchers
    base = "https://www.fangraphs.com/api/leaders/major-league/data?age=&pos=all&lg=all&qual=0"
    url = f"{base}&stats={stats_type}&season={season}&season1={season}&startdate={season}-03-01&enddate={season}-11-01&month=0&hand=&team=0&pageitems=2000000000&pagenum=1&ind=0&rost=0&players="
    if stats_type == 'bat':
        url += "&type=24"
    else:
        url += "&type=502"
    return url

def fetch_and_save(url, filename, description):
    print(f"Fetching {description}...")
    try:
        # Using curl to bypass potential 403s
        result = subprocess.run(['curl', '-s', url], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        with open(filename, 'w') as f:
            json.dump(data, f)
        print(f"Successfully saved {len(data.get('data', []))} records to {filename}")
        return data
    except Exception as e:
        print(f"Error fetching {filename}: {e}", file=sys.stderr)
        return None

def main():
    # 1. Prior Year Data (Baseline)
    fetch_and_save(get_url('bat', PRIOR_SEASON), f"statcast-hitters-{PRIOR_SEASON}.json", f"{PRIOR_SEASON} MLB Hitters")
    fetch_and_save(get_url('pit', PRIOR_SEASON), f"statcast-pitchers-{PRIOR_SEASON}.json", f"{PRIOR_SEASON} MLB Pitchers")

    # 2. Current Year Data (Recency)
    fetch_and_save(get_url('bat', CURRENT_SEASON), f"statcast-hitters-{CURRENT_SEASON}.json", f"{CURRENT_SEASON} MLB Hitters")
    fetch_and_save(get_url('pit', CURRENT_SEASON), f"statcast-pitchers-{CURRENT_SEASON}.json", f"{CURRENT_SEASON} MLB Pitchers")

if __name__ == "__main__":
    main()
