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

    # Define the 4 combinations
    jobs = [
        ("atc", today, "lineup_atc_today.json"),
        ("steamer", today, "lineup_steamer_today.json"),
        ("atc", tomorrow, "lineup_atc_tomorrow.json"),
        ("steamer", tomorrow, "lineup_steamer_tomorrow.json"),
    ]

    print(f"🚀 Updating local web data for {today} and {tomorrow}...")

    for proj, date, filename in jobs:
        print(f"\n--- Generating {filename} ({proj.upper()}) ---")
        cmd = [
            "uv", "run", "python", "main.py",
            "--projection", proj,
            "--date", date,
            "--output", filename
        ]
        if args.skip_ai:
            cmd.append("--skip-ai")
            
        subprocess.run(cmd)

    print("\n✅ All 4 files updated. Refresh your local browser to see changes.")

if __name__ == "__main__":
    main()
