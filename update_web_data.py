import datetime
import pytz
import argparse
import json
import logging
import config as C
from main import run_optimizer_hitter
from pitcher_optimizer import run_pitcher_optimizer

C.setup_logging()
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Update all team lineup JSON files")
    parser.add_argument("--skip-ai", action="store_true", help="Skip AI narrative generation")
    args = parser.parse_args()

    tz = pytz.timezone('US/Eastern')
    today    = datetime.datetime.now(tz).strftime('%Y-%m-%d')
    tomorrow = (datetime.datetime.now(tz) + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    hitter_jobs = [
        ("steamer", today,    "lineup_steamer_today.json"),
        ("atc",     today,    "lineup_atc_today.json"),
        ("steamer", tomorrow, "lineup_steamer_tomorrow.json"),
        ("atc",     tomorrow, "lineup_atc_tomorrow.json"),
    ]
    pitcher_jobs = [
        ("steamer", today,    "pitchers_steamer_today.json"),
        ("atc",     today,    "pitchers_atc_today.json"),
        ("steamer", tomorrow, "pitchers_steamer_tomorrow.json"),
        ("atc",     tomorrow, "pitchers_atc_tomorrow.json"),
    ]

    print(f"Updating web data for {len(C.TEAM_IDS)} teams — {today} and {tomorrow}...")

    for team in C.TEAM_IDS:
        team_name = C.TEAM_NAMES.get(team, f"Team {team}")

        for proj, date, base_file in hitter_jobs:
            filename = base_file.replace("lineup_", f"lineup_{team}_")
            print(f"  [{team_name}] {proj.upper()} hitters {date} → {filename}")
            try:
                run_optimizer_hitter(
                    projection_system=proj,
                    target_date=date,
                    team_id=team,
                    output_filename=filename,
                    skip_ai=args.skip_ai or (date == tomorrow),
                )
            except Exception as e:
                logger.error(f"Hitter job failed ({team}, {proj}, {date}): {e}")

        for proj, date, base_file in pitcher_jobs:
            filename = base_file.replace("pitchers_", f"pitchers_{team}_")
            print(f"  [{team_name}] {proj.upper()} pitchers {date} → {filename}")
            try:
                data = run_pitcher_optimizer(target_date=date, projection_system=proj, team_id=team)
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                logger.error(f"Pitcher job failed ({team}, {proj}, {date}): {e}")

    print("Done. All JSON files updated.")


if __name__ == "__main__":
    main()
