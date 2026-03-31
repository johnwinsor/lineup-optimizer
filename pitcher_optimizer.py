import argparse
from datetime import datetime, timedelta
import json
from pitcher_daily_engine import PitcherDailyEngine

def run_pitcher_optimizer(target_date=None, projection_system="atc"):
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
        
    engine = PitcherDailyEngine(projection_system=projection_system)
    projections = engine.get_daily_projections(target_date)
    
    # Filter for starters
    starters = projections[projections['IsStarting'] == True].copy()
    
    # Sort by DailyScore
    starters = starters.sort_values(by='DailyScore', ascending=False)
    
    results = []
    for _, row in starters.iterrows():
        results.append({
            'Player': row['Name'],
            'Team': row['Team'],
            'Opponent': row['Opponent'],
            'Score': round(row['DailyScore'], 1),
            'Breakdown': row['Breakdown'],
            'Warning': row['Warning'],
            'GameTime': row['GameTime']
        })
        
    return {
        'target_date': target_date,
        'projection_system': projection_system,
        'pitcher_starts': results,
        'last_updated': datetime.now().isoformat()
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zurich Zebras Pitcher Optimizer")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--proj", type=str, default="atc", choices=["atc", "steamer"], help="Projection system")
    parser.add_argument("--output", type=str, help="Output JSON file")
    
    args = parser.parse_args()
    
    data = run_pitcher_optimizer(target_date=args.date, projection_system=args.proj)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Results saved to {args.output}")
    else:
        print(f"\nPITCHER OPTIMIZER RESULTS ({data['target_date']} - {data['projection_system'].upper()})")
        print("-" * 100)
        if not data['pitcher_starts']:
            print("No rostered pitchers scheduled to start.")
        for p in data['pitcher_starts']:
            print(f"{p['Player']} ({p['Team']}) vs {p['Opponent']} | SCORE: {p['Score']}")
            print(f"  Breakdown: {p['Breakdown']}")
            if p['Warning']: print(f"  WARNING: {p['Warning']}")
            print("-" * 100)
