"""
build_crosswalk.py — Pre-build the FGID → MLB ID crosswalk for all Ottoneu roster players.

Run once daily (via daily_refresh.yml) before the optimizer or any StatCast fetch.
This gives every downstream process a reliable, projection-system-agnostic MLB ID
for each player — including minor leaguers, recent call-ups, and players absent from
one projection system but present in another.

Usage:
    uv run python build_crosswalk.py            # resolves new/unknown players only
    uv run python build_crosswalk.py --force     # re-resolves every player
    uv run python build_crosswalk.py --report    # print crosswalk summary without changes
"""

import argparse
import logging
import pandas as pd
import config as C
from harvester import OttoneuScraper
from gameday_harvester import GameDayHarvester

C.setup_logging(console_level=logging.INFO)
logger = logging.getLogger(__name__)


def collect_roster(team_id: int) -> pd.DataFrame:
    """Return the combined hitter + pitcher roster for one Ottoneu team."""
    scraper = OttoneuScraper(league_id=1077, team_id=team_id)
    hitters, pitchers = scraper.get_roster()
    return pd.concat([hitters, pitchers], ignore_index=True)


def build_crosswalk(force_refresh: bool = False) -> None:
    harvester = GameDayHarvester()
    crosswalk = harvester._load_id_crosswalk()

    # ── Collect all unique players across all tracked teams ──────────────────
    seen_keys: set[tuple] = set()
    players: list[dict] = []

    for team_id in C.TEAM_IDS:
        team_name = C.TEAM_NAMES.get(team_id, f"Team {team_id}")
        try:
            roster = collect_roster(team_id)
        except Exception as e:
            logger.error(f"[{team_name}] Failed to scrape roster: {e}")
            continue

        for _, row in roster.iterrows():
            name = str(row.get('Name') or '').strip()
            team = str(row.get('Team') or '').strip()
            fgid = str(row.get('FGID') or '').strip()
            if not name:
                continue
            dedup_key = (name.lower(), team)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            players.append({'name': name, 'team': team or None, 'fgid': fgid or None})

    print(f"Found {len(players)} unique players across {len(C.TEAM_IDS)} teams.")

    # ── Resolve MLB IDs ──────────────────────────────────────────────────────
    resolved, already_cached, failed = 0, 0, []

    for p in players:
        fgid = p['fgid']

        if not force_refresh and fgid and fgid in crosswalk:
            already_cached += 1
            continue

        mlb_id = harvester.get_mlb_id(p['name'], team_abb=p['team'], fg_id=fgid)
        if mlb_id:
            resolved += 1
            # get_mlb_id() already persists to the crosswalk when it resolves
            # via fallback. If the player has no FGID the result is cached
            # in-memory only for this run — acceptable, as FGID-less players
            # are rare on Ottoneu.
        else:
            failed.append(f"{p['name']} ({p['team'] or 'no team'})")

    # ── Summary ──────────────────────────────────────────────────────────────
    total = len(crosswalk)
    print(f"\nCrosswalk build complete:")
    print(f"  Newly resolved : {resolved}")
    print(f"  Already cached : {already_cached}")
    print(f"  Failed         : {len(failed)}")
    print(f"  Total in file  : {total}")

    if failed:
        print(f"\nCould not resolve MLB ID for:")
        for f in failed:
            print(f"  - {f}")


def print_report() -> None:
    """Print a summary of the current crosswalk without making any changes."""
    harvester = GameDayHarvester()
    crosswalk = harvester._load_id_crosswalk()
    print(f"Crosswalk contains {len(crosswalk)} entries:")
    for fgid, entry in sorted(crosswalk.items(), key=lambda x: x[1].get('name', '')):
        print(f"  {fgid:15s}  mlb_id={entry['mlb_id']:8}  {entry.get('name', '?')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the Ottoneu → MLB ID crosswalk")
    parser.add_argument("--force",  action="store_true", help="Re-resolve all players, even if already cached")
    parser.add_argument("--report", action="store_true", help="Print current crosswalk contents without changes")
    args = parser.parse_args()

    if args.report:
        print_report()
    else:
        build_crosswalk(force_refresh=args.force)
