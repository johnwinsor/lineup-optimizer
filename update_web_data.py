import subprocess
import datetime
import pytz
import argparse

def main():
    parser = argparse.ArgumentParser(description="Update all 4 local lineup JSON files")
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

    # Define historical jobs (Last 3 days)
    history_jobs = []
    for i in range(1, 4):
        past_date = (datetime.datetime.now(tz) - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        for proj in ["atc", "steamer"]:
            history_jobs.append((proj, past_date, f"results_{proj}_{past_date}.json"))
            history_jobs.append((proj, past_date, f"pitcher_results_{proj}_{past_date}.json", "pitcher"))

    print(f"🚀 Updating local web data for {today}, {tomorrow}, and recent history...")

    # Run Hitters (Today/Tomorrow)
    for proj, date, filename in jobs:
        print(f"\n--- Generating Hitter Lineup: {filename} ({proj.upper()}) ---")
        cmd = [
            "uv", "run", "python", "main.py",
            "--projection", proj,
            "--date", date,
            "--output", filename
        ]
        if args.skip_ai:
            cmd.append("--skip-ai")
            
        subprocess.run(cmd)

    # Run Pitchers (Today/Tomorrow)
    for proj, date, filename in pitcher_jobs:
        print(f"\n--- Generating Pitcher Lineup: {filename} ({proj.upper()}) ---")
        cmd = [
            "uv", "run", "python", "pitcher_optimizer.py",
            "--proj", proj,
            "--date", date,
            "--output", filename
        ]
        subprocess.run(cmd)

    # Run History
    for job in history_jobs:
        proj, date, filename = job[0], job[1], job[2]
        is_pitcher = len(job) > 3
        
        if is_pitcher:
            print(f"\n--- Generating Historical Pitcher Results: {filename} ---")
            cmd = ["uv", "run", "python", "pitcher_backtester.py", date, "--proj", proj, "--output", filename]
        else:
            print(f"\n--- Generating Historical Hitter Results: {filename} ---")
            cmd = ["uv", "run", "python", "backtester.py", date, "--projection", proj, "--output", filename]
            
        subprocess.run(cmd)

    print("\n✅ All JSON files updated. Refresh your local browser to see changes.")

if __name__ == "__main__":
    main()
