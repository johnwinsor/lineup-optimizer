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
            
        record_count = len(data) if isinstance(data, list) else len(data.get('data', []))
        print(f"Successfully saved {record_count} records to {filename}")
        return data
    except Exception as e:
        print(f"Error fetching {filename}: {e}", file=sys.stderr)
        return None

def compare_steamer_projections(old_data, new_data):
    if not old_data or not new_data:
        return
        
    old_list = old_data if isinstance(old_data, list) else old_data.get('data', [])
    new_list = new_data if isinstance(new_data, list) else new_data.get('data', [])
    
    old_map = {str(p.get('playerid')): p for p in old_list if 'playerid' in p}
    
    print("\n--- Steamer Projections Changes Summary ---")
    significant_changes = []
    
    for p in new_list:
        pid = str(p.get('playerid'))
        if pid not in old_map:
            continue
            
        old_p = old_map[pid]
        name = p.get('PlayerName', 'Unknown')
        
        # Check for significant changes
        pa_diff = p.get('PA', 0) - old_p.get('PA', 0)
        hr_diff = p.get('HR', 0) - old_p.get('HR', 0)
        woba_diff = p.get('wOBA', 0) - old_p.get('wOBA', 0)
        
        if abs(pa_diff) > 15 or abs(hr_diff) >= 2 or abs(woba_diff) >= 0.010:
            significant_changes.append(
                f"{name}: PA {old_p.get('PA', 0):.0f}->{p.get('PA', 0):.0f} ({pa_diff:+.0f}), "
                f"HR {old_p.get('HR', 0):.1f}->{p.get('HR', 0):.1f} ({hr_diff:+.1f}), "
                f"wOBA {old_p.get('wOBA', 0):.3f}->{p.get('wOBA', 0):.3f} ({woba_diff:+.3f})"
            )
            
    if significant_changes:
        print(f"Found {len(significant_changes)} significant projection updates:")
        for change in significant_changes[:20]: # show up to 20
            print(f"  - {change}")
        if len(significant_changes) > 20:
            print(f"  ... and {len(significant_changes) - 20} more.")
    else:
        print("No significant changes in player projections today.")
    print("-------------------------------------------\n")

def main():
    # 1. Prior Year Data (Baseline)
    fetch_and_save(get_url('bat', PRIOR_SEASON), f"statcast-hitters-{PRIOR_SEASON}.json", f"{PRIOR_SEASON} MLB Hitters")
    fetch_and_save(get_url('pit', PRIOR_SEASON), f"statcast-pitchers-{PRIOR_SEASON}.json", f"{PRIOR_SEASON} MLB Pitchers")

    # 2. Current Year Data (Recency)
    fetch_and_save(get_url('bat', CURRENT_SEASON), f"statcast-hitters-{CURRENT_SEASON}.json", f"{CURRENT_SEASON} MLB Hitters")
    fetch_and_save(get_url('pit', CURRENT_SEASON), f"statcast-pitchers-{CURRENT_SEASON}.json", f"{CURRENT_SEASON} MLB Pitchers")

    # 3. Projections
    for stats_type in ["bat", "pit"]:
        type_label = "Hitters" if stats_type == "bat" else "Pitchers"
        for system in ["steamer", "atc"]:
            # Standard filenames that enricher.py expects
            if stats_type == "bat":
                effective_file = f"projections-{system}.json"
            else:
                effective_file = f"projections-{system}-pit.json"

            old_proj_data = None
            if os.path.exists(effective_file):
                try:
                    with open(effective_file, 'r') as f:
                        old_proj_data = json.load(f)
                except Exception:
                    pass

            proj_url = f"https://www.fangraphs.com/api/projections?stats={stats_type}&type={system}"
            new_proj_data = fetch_and_save(proj_url, effective_file, f"{system.upper()} {type_label} Projections")

            if old_proj_data and new_proj_data and stats_type == "bat":
                print(f"\n--- {system.upper()} {type_label} Changes ---")
                compare_steamer_projections(old_proj_data, new_proj_data)
            
            # Backward compatibility for the original steamer-hitters.json
            if system == "steamer" and stats_type == "bat":
                import shutil
                shutil.copy2(effective_file, "steamer-hitters.json")

if __name__ == "__main__":
    main()
