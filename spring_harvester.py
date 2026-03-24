import subprocess
import json
import os

def fetch_data(url, filename, label):
    print(f"Fetching {label} data...")
    try:
        # Using curl to fetch the data
        result = subprocess.run(['curl', '-s', url], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        with open(filename, 'w') as f:
            json.dump(data, f)
        print(f"Successfully saved {len(data)} {label} records to {filename}")
        return data
    except Exception as e:
        print(f"Error fetching {label}: {e}")
        return None

def fetch_spring_training_stats():
    # Hitters
    h_url = "https://www.fangraphs.com/api/leaders/minor-league/data?pos=all&level=0&lg=33&stats=bat&qual=10&type=0&team=&season=2026&seasonend=2026&org=&ind=0"
    fetch_data(h_url, "spring_training_hitters.json", "Spring Training Hitters")
    
    # Pitchers
    p_url = "https://www.fangraphs.com/api/leaders/minor-league/data?pos=all&level=0&lg=33&stats=pit&qual=5&type=0&team=&season=2026&seasonend=2026&org=&ind=0"
    fetch_data(p_url, "spring_training_pitchers.json", "Spring Training Pitchers")

if __name__ == "__main__":
    fetch_spring_training_stats()
