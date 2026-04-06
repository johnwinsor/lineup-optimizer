import statsapi
from pybaseball import statcast_catcher_poptime, statcast_sprint_speed
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DefenseHarvester:
    def __init__(self, year=None):
        self.year = year or (datetime.now().year - 1)  # Default to prior season
        self.catcher_cache = {}
        self.pitcher_cache = {}
        self.sprint_speed_cache = {}

        # Primary catchers used when the lineup is not yet posted.
        # Update each season as rosters change.
        self.team_primary_catcher = {
            140: 605270,  # TEX — Jonah Heim
            138: 575929,  # STL — Willson Contreras
            143: 592663,  # PHI — J.T. Realmuto
            118: 543760,  # KC  — Salvador Perez
            121: 642547,  # NYM — Francisco Alvarez
            147: 669221,  # NYY — Austin Wells
            135: 669374,  # SD  — Luis Campusano
            119: 643393,  # LAD — Will Smith
            111: 660688,  # BOS — Connor Wong
            141: 663656,  # TOR — Alejandro Kirk
            117: 641598,  # HOU — Yainer Diaz
            142: 663728,  # MIN — Ryan Jeffers
            108: 669127,  # LAA — Logan O'Hoppe
            137: 672275,  # SF  — Patrick Bailey
            144: 670351,  # ATL — Sean Murphy
            112: 669257,  # CHC — Miguel Amaya
            114: 666969,  # CLE — Bo Naylor
            113: 518595,  # CIN — Travis d'Arnaud
            134: 668942,  # PIT — Joey Bart
            115: 673490,  # COL — Drew Romo
            109: 664034,  # ARI — Gabriel Moreno
            146: 663550,  # MIA — Nick Fortes
            158: 668800,  # MIL — William Contreras
            120: 624431,  # WAS — Keibert Ruiz
            110: 663531,  # BAL — Adley Rutschman
            145: 686676,  # CHW — Korey Lee
            116: 668670,  # DET — Jake Rogers
            133: 650333,  # OAK — Shea Langeliers
            136: 663083,  # SEA — Cal Raleigh
            139: 666181,  # TB  — Logan Driscoll
        }
        self._load_data()

    def _load_data(self):
        try:
            df_catchers = statcast_catcher_poptime(self.year)
            for _, row in df_catchers.iterrows():
                self.catcher_cache[int(row['entity_id'])] = float(row['pop_2b_sba'])
            logger.info(f"Loaded {len(self.catcher_cache)} catcher pop times for {self.year}.")
        except Exception as e:
            logger.warning(f"Failed to load catcher pop times for {self.year}: {e}")

        try:
            df_sprint = statcast_sprint_speed(self.year)
            for _, row in df_sprint.iterrows():
                self.sprint_speed_cache[int(row['player_id'])] = float(row['sprint_speed'])
            logger.info(f"Loaded {len(self.sprint_speed_cache)} sprint speeds for {self.year}.")
        except Exception as e:
            logger.warning(f"Failed to load sprint speeds for {self.year}: {e}")

    def get_primary_catcher(self, team_id):
        return self.team_primary_catcher.get(team_id)

    def get_pop_time(self, catcher_id):
        return self.catcher_cache.get(catcher_id, 1.97)  # 1.97s = MLB average

    def get_pitcher_sb_rate(self, pitcher_id, year=None):
        year = year or self.year
        cache_key = (pitcher_id, year)
        if cache_key in self.pitcher_cache:
            return self.pitcher_cache[cache_key]

        try:
            stats = statsapi.get('people', {
                'personIds': pitcher_id,
                'hydrate': f'stats(group=[pitching],type=[season],season={year})'
            })
            if 'people' in stats and stats['people']:
                splits = stats['people'][0].get('stats', [{}])[0].get('splits', [])
                if splits:
                    s = splits[0]['stat']
                    sb = s.get('stolenBases', 0)
                    cs = s.get('caughtStealing', 0)
                    attempts = sb + cs
                    if attempts >= 5:
                        rate = sb / attempts
                        self.pitcher_cache[cache_key] = rate
                        return rate
        except Exception as e:
            logger.warning(f"get_pitcher_sb_rate failed for pitcher {pitcher_id} ({year}): {e}")

        # If current season has no data yet, fall back to prior season
        current_year = datetime.now().year
        if year >= current_year and year > 2020:
            return self.get_pitcher_sb_rate(pitcher_id, year=year - 1)

        return 0.75  # MLB average SB% ≈ 75–80%

    def get_sprint_speed(self, player_id):
        return self.sprint_speed_cache.get(player_id, 27.0)  # 27.0 ft/s = MLB average


if __name__ == "__main__":
    import config as C
    C.setup_logging()
    harvester = DefenseHarvester()
    print(f"Realmuto Pop Time: {harvester.get_pop_time(592663)}")
    print(f"Gerrit Cole SB Rate: {harvester.get_pitcher_sb_rate(543037)}")
    print(f"Trea Turner Sprint: {harvester.get_sprint_speed(607208)}")
