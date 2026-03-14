import subprocess
import json
import os

def fetch_spring_training_hitters(filename):
    url = "https://www.fangraphs.com/api/leaders/minor-league/data?pos=all&level=0&lg=33&stats=bat&qual=10&type=0&team=&season=2026&seasonend=2026&org=&ind=0"
    
    print(f"Fetching Spring Training hitters data...")
    try:
        # Using curl to fetch the data as seen in scout_harvester.py
        result = subprocess.run(['curl', '-s', url], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        with open(filename, 'w') as f:
            json.dump(data, f)
        print(f"Successfully saved {len(data)} Spring Training hitter records to {filename}")
        return data
    except Exception as e:
        print(f"Error fetching Spring Training hitters: {e}")
        return None

if __name__ == "__main__":
    fetch_spring_training_hitters("spring_training_hitters.json")
