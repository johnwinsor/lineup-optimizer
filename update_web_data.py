import datetime
import pytz
import argparse
import json
from main import run_optimizer_hitter
from pitcher_optimizer import run_pitcher_optimizer

def main():
    parser = argparse.ArgumentParser(description="Update all team lineup JSON files (Optimized)")
    parser.add_argument("--skip-ai", action="store_true", help="Skip AI narrative generation to save quota")
    args = parser.parse_args()

    # Determine Today and Tomorrow in MLB Time
    tz = pytz.timezone('US/Eastern')
    today = datetime.datetime.now(tz).strftime('%Y-%m-%d')
    tomorrow = (datetime.datetime.now(tz) + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    # Define the 4 combinations for hitters
    jobs = [
        ("atc", today, "lineup_atc_today.json"),
        ("steamer", today, "lineup_steamer_today.json"),
        ("atc", tomorrow, "lineup_atc_tomorrow.json"),
        ("steamer", tomorrow, "lineup_steamer_tomorrow.json"),
    ]
    
    # Define the 4 combinations for pitchers
    pitcher_jobs = [
        ("atc", today, "pitchers_atc_today.json"),
        ("steamer", today, "pitchers_steamer_today.json"),
        ("atc", tomorrow, "pitchers_atc_tomorrow.json"),
        ("steamer", tomorrow, "pitchers_steamer_tomorrow.json"),
    ]

    # Define the Teams
    teams = [7582, 7587]
    
    print(f"🚀 Updating local web data for {len(teams)} teams for {today} and {tomorrow}...")
    print("✨ Optimization: Reusing projection data in-memory across all runs.")

    # Run Hitters (Today/Tomorrow)
    for team in teams:
        for proj, date, base_filename in jobs:
            # Filename format: lineup_7582_atc_today.json
            filename = base_filename.replace("lineup_", f"lineup_{team}_")
            print(f"\n--- Generating Hitter Lineup: {filename} (Team {team}, {proj.upper()}) ---")
            
            # Call directly instead of subprocess
            run_optimizer_hitter(
                projection_system=proj,
                target_date=date,
                team_id=team,
                output_filename=filename,
                skip_ai=args.skip_ai
            )

    # Run Pitchers (Today/Tomorrow) - Still Zebras only for now
    for proj, date, filename in pitcher_jobs:
        print(f"\n--- Generating Pitcher Lineup: {filename} ({proj.upper()}) ---")
        
        # Call directly instead of subprocess
        data = run_pitcher_optimizer(target_date=date, projection_system=proj)
        
        # Save JSON manually since run_pitcher_optimizer returns dict
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Web dashboard data exported to {filename}")

    print("\n✅ All JSON files updated. Refresh your local browser to see changes.")

if __name__ == "__main__":
    main()
