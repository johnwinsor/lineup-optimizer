import statsapi
from pybaseball import playerid_lookup
import pandas as pd
from datetime import datetime
import requests
import json
import logging
import os
from statcast_harvester import StatCastHarvester
from defense_harvester import DefenseHarvester
from crosswalks import TeamCrosswalk, PlayerCrosswalk, get_team_ottoneu, normalize_name

logging.basicConfig(level=logging.WARNING, format='%(levelname)s [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

PLAYER_ID_CROSSWALK_FILE = "player_id_crosswalk.json"

class GameDayHarvester:
    _instance = None
    _matchups_cache = {}
    _bvp_cache = {}         # Shared batter vs pitcher stats
    _player_data_cache = {} # Shared hand/stats/etc
    _id_crosswalk = None    # Persistent FGID -> MLB BAMID crosswalk
    _boxscore_cache = {}    # game_pk -> boxscore_data result

    @classmethod
    def _load_id_crosswalk(cls):
        if cls._id_crosswalk is None:
            try:
                with open(PLAYER_ID_CROSSWALK_FILE, 'r') as f:
                    cls._id_crosswalk = json.load(f)
                logger.info(f"Loaded {len(cls._id_crosswalk)} entries from player ID crosswalk.")
            except (FileNotFoundError, json.JSONDecodeError):
                cls._id_crosswalk = {}
        return cls._id_crosswalk

    @classmethod
    def _save_id_crosswalk(cls):
        if cls._id_crosswalk is not None:
            try:
                with open(PLAYER_ID_CROSSWALK_FILE, 'w') as f:
                    json.dump(cls._id_crosswalk, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to save player ID crosswalk: {e}")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = GameDayHarvester()
        return cls._instance

    def __init__(self):
        # Cache for player IDs to avoid repeated lookups
        self.player_id_cache = {}
        # Cache for team abbreviations
        self.team_abb_cache = {}
        # Cache for active rosters: { team_id: set(mlb_ids) }
        self.active_rosters = {}
        self.statcast = StatCastHarvester()
        self.defense = DefenseHarvester()

    def get_mlb_id(self, player_name, target_year=None, team_abb=None, fg_id=None):
        if target_year is None:
            target_year = datetime.now().year

        # 1. Check persistent FGID crosswalk first (most reliable)
        if fg_id:
            fg_key = str(fg_id)
            crosswalk = self._load_id_crosswalk()
            if fg_key in crosswalk:
                return crosswalk[fg_key]['mlb_id']

        # Clean name for search
        search_name = player_name
        suffixes = [' Jr.', ' Sr.', ' II', ' III', ' IV']
        for s in suffixes:
            search_name = search_name.replace(s, '')
        search_name = normalize_name(search_name)

        cache_key = f"id_{player_name}_{target_year}_{team_abb}"
        if cache_key in self.player_id_cache:
            return self.player_id_cache[cache_key]

        p_id = None
        target_mlb_abb = TeamCrosswalk.to_mlb(team_abb) if team_abb else None

        def _team_matches(person_id):
            """Returns True if this person belongs to the target MLB org (handles minor leaguers via parentOrgId)."""
            if not target_mlb_abb:
                return True
            try:
                p_info = statsapi.get('person', {'personId': person_id, 'hydrate': 'currentTeam'})
                if p_info and 'people' in p_info:
                    current_team = p_info['people'][0].get('currentTeam', {})
                    for check_id in filter(None, [current_team.get('id'), current_team.get('parentOrgId')]):
                        team_data = statsapi.get('team', {'teamId': check_id})
                        if team_data and 'teams' in team_data:
                            if team_data['teams'][0].get('abbreviation') == target_mlb_abb:
                                return True
            except Exception as e:
                logger.warning(f"_team_matches failed for person {person_id}: {e}")
            return False

        try:
            # 2. statsapi MLB-level name lookup
            # Always run _team_matches() when team_abb is provided — this prevents nickname false
            # positives (e.g. "luis pena" returning Severino) regardless of result count.
            # When no team_abb is given, trust a single result directly.
            results = statsapi.lookup_player(search_name)
            if results and team_abb:
                for r in results:
                    if _team_matches(r['id']):
                        p_id = r['id']
                        break
            elif len(results) == 1:
                p_id = results[0]['id']
        except Exception as e:
            logger.warning(f"statsapi.lookup_player failed for '{player_name}': {e}")

        # 3. MiLB search fallback — searches High-A through Triple-A when MLB lookup misses
        if p_id is None and team_abb:
            for sport_id in [11, 12, 13, 14, 15, 16]:
                try:
                    results = statsapi.lookup_player(search_name, sportId=sport_id)
                    for r in results:
                        if _team_matches(r['id']):
                            p_id = r['id']
                            logger.info(f"Found '{player_name}' via MiLB search (sportId={sport_id}): {p_id}")
                            break
                    if p_id:
                        break
                except Exception as e:
                    logger.warning(f"MiLB lookup (sportId={sport_id}) failed for '{player_name}': {e}")

        # 4. Pybaseball fallback
        if p_id is None:
            try:
                name_parts = search_name.split()
                if len(name_parts) >= 2:
                    lookup = playerid_lookup(name_parts[-1], name_parts[0])
                    if not lookup.empty:
                        lookup = lookup.sort_values(by='mlb_played_last', ascending=False)
                        p_id = int(lookup.iloc[0]['key_mlbam'])
            except Exception as e:
                logger.warning(f"pybaseball fallback failed for '{player_name}': {e}")

        if p_id is None:
            logger.warning(f"Could not resolve MLB ID for '{player_name}' (team={team_abb}, fgid={fg_id})")

        # Cache in memory
        self.player_id_cache[cache_key] = p_id

        # Persist to crosswalk if we have an FGID anchor
        if p_id and fg_id:
            crosswalk = self._load_id_crosswalk()
            crosswalk[str(fg_id)] = {'mlb_id': p_id, 'name': player_name}
            self._save_id_crosswalk()

        return p_id

    def get_daily_matchups(self, target_date: str):
        if target_date in self._matchups_cache:
            return self._matchups_cache[target_date]

        logger.info(f"Fetching fresh matchups for {target_date} from MLB API...")
        matchups = {'_teams_playing': {}, '_starting_pitchers': {}}
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        formatted_date = dt.strftime("%m/%d/%Y")
        
        games = statsapi.schedule(date=formatted_date)
        
        for game in games:
            # Check for rainouts / postponements
            status = game.get('status', 'Unknown')
            is_postponed = (status == 'Postponed')
            
            game_id = game['game_id']
            game_time = game.get('game_datetime')
            away_id = game.get('away_id')
            home_id = game.get('home_id')
            venue = game.get('venue_name', 'Unknown')
            
            # Cache active rosters for these teams
            for t_id in [away_id, home_id]:
                if t_id and t_id not in self.active_rosters:
                    try:
                        roster = statsapi.get('team_roster', {'teamId': t_id, 'rosterType': 'active'})
                        self.active_rosters[t_id] = {p['person']['id'] for p in roster.get('roster', [])}
                    except Exception as e:
                        logger.warning(f"Failed to fetch active roster for team {t_id}: {e}")
                        self.active_rosters[t_id] = set()

            # Resolve team abbreviations from schedule IDs (more reliable for future games)
            away_abb = get_team_ottoneu(self.get_team_abb(away_id))
            home_abb = get_team_ottoneu(self.get_team_abb(home_id))
            
            away_sp = None
            home_sp = None
            away_c = None
            home_c = None
            
            try:
                # Try to get detailed boxscore (best for confirmed lineups)
                if game_id not in self._boxscore_cache:
                    self._boxscore_cache[game_id] = statsapi.boxscore_data(game_id)
                box = self._boxscore_cache[game_id]
                if box:
                    for p in box.get('awayPitchers', []):
                        if p.get('personId') and p.get('name') != 'Pitchers':
                            away_sp = {'name': p['name'], 'personId': p['personId']}
                            break
                    for p in box.get('homePitchers', []):
                        if p.get('personId') and p.get('name') != 'Pitchers':
                            home_sp = {'name': p['name'], 'personId': p['personId']}
                            break
                    # Find Catchers
                    for b in box.get('awayBatters', []):
                        if b.get('position') == 'C':
                            away_c = {'name': b['name'], 'personId': b['personId']}
                            break
                    for b in box.get('homeBatters', []):
                        if b.get('position') == 'C':
                            home_c = {'name': b['name'], 'personId': b['personId']}
                            break
            except Exception as e:
                logger.warning(f"Boxscore fetch failed for game {game_id}: {e}")
                box = None

            # Fallback for pitchers if boxscore is empty (crucial for future games)
            if not away_sp or not home_sp:
                try:
                    game_data = statsapi.get('game', {'gamePk': game_id}).get('gameData', {})
                    probables = game_data.get('probablePitchers', {})
                    if not away_sp and probables.get('away'):
                        away_sp = {'name': probables['away']['fullName'], 'personId': probables['away']['id']}
                    if not home_sp and probables.get('home'):
                        home_sp = {'name': probables['home']['fullName'], 'personId': probables['home']['id']}
                except Exception as e:
                    logger.warning(f"Probable pitcher fallback failed for game {game_id}: {e}")

            # Fallback for catchers (crucial for Lineup Pending scenarios)
            if not away_c:
                c_id = self.defense.get_primary_catcher(game.get('away_id'))
                if c_id:
                    away_c = {'personId': c_id}
            if not home_c:
                c_id = self.defense.get_primary_catcher(game.get('home_id'))
                if c_id:
                    home_c = {'personId': c_id}

            # Initial team entry
            if away_abb:
                matchups['_teams_playing'][away_abb] = {
                    'has_lineup': False,
                    'opposing_sp_name': home_sp['name'] if home_sp else None,
                    'opposing_sp_id': home_sp['personId'] if home_sp else None,
                    'opposing_c_id': home_c['personId'] if home_c else None,
                    'venue_name': venue,
                    'home_team_abb': home_abb,
                    'is_home': False,
                    'game_status': status,
                    'is_postponed': is_postponed,
                    'game_time': game_time,
                    'active_roster': self.active_rosters.get(away_id, set())
                }
            if home_abb:
                matchups['_teams_playing'][home_abb] = {
                    'has_lineup': False,
                    'opposing_sp_name': away_sp['name'] if away_sp else None,
                    'opposing_sp_id': away_sp['personId'] if away_sp else None,
                    'opposing_c_id': away_c['personId'] if away_c else None,
                    'venue_name': venue,
                    'home_team_abb': home_abb,
                    'is_home': True,
                    'game_status': status,
                    'is_postponed': is_postponed,
                    'game_time': game_time,
                    'active_roster': self.active_rosters.get(home_id, set())
                }
            
            # Add pitchers to global map (handles doubleheaders)
            if away_sp and 'personId' in away_sp:
                matchups['_starting_pitchers'][away_sp['personId']] = {
                    'name': away_sp['name'],
                    'opposing_team': home_abb,
                    'venue_name': venue,
                    'home_team_abb': home_abb,
                    'is_home': False,
                    'game_status': status,
                    'is_postponed': is_postponed,
                    'game_time': game_time,
                    'has_lineup': box is not None
                }
            if home_sp and 'personId' in home_sp:
                matchups['_starting_pitchers'][home_sp['personId']] = {
                    'name': home_sp['name'],
                    'opposing_team': away_abb,
                    'venue_name': venue,
                    'home_team_abb': home_abb,
                    'is_home': True,
                    'game_status': status,
                    'is_postponed': is_postponed,
                    'game_time': game_time,
                    'has_lineup': box is not None
                }
            
            # Process batters if boxscore is available
            if box:
                if box.get('awayBatters'):
                    for batter in box['awayBatters']:
                        if isinstance(batter, dict) and 'personId' in batter:
                            raw_order = batter.get('battingOrder', '')
                            is_start = raw_order.endswith('00') and len(raw_order) == 3
                            clean_order = raw_order[0] if is_start else '-'
                            
                            if is_start: matchups['_teams_playing'][away_abb]['has_lineup'] = True
                            matchups[batter['personId']] = {
                                'is_starting': is_start,
                                'batting_order': clean_order,
                                'opposing_sp_name': home_sp['name'] if home_sp else None,
                                'opposing_sp_id': home_sp['personId'] if home_sp else None,
                                'opposing_c_id': home_c['personId'] if home_c else None,
                                'venue_name': venue,
                                'home_team_abb': home_abb,
                                'is_home': False,
                                'game_status': status,
                                'is_postponed': is_postponed,
                                'game_time': game_time
                            }
                            
                if box.get('homeBatters'):
                    for batter in box['homeBatters']:
                        if isinstance(batter, dict) and 'personId' in batter:
                            raw_order = batter.get('battingOrder', '')
                            is_start = raw_order.endswith('00') and len(raw_order) == 3
                            clean_order = raw_order[0] if is_start else '-'
                            
                            if is_start: matchups['_teams_playing'][home_abb]['has_lineup'] = True
                            matchups[batter['personId']] = {
                                'is_starting': is_start,
                                'batting_order': clean_order,
                                'opposing_sp_name': away_sp['name'] if away_sp else None,
                                'opposing_sp_id': away_sp['personId'] if away_sp else None,
                                'opposing_c_id': away_c['personId'] if away_c else None,
                                'venue_name': venue,
                                'home_team_abb': home_abb,
                                'is_home': True,
                                'game_status': status,
                                'is_postponed': is_postponed,
                                'game_time': game_time
                            }
                        
        self._matchups_cache[target_date] = matchups
        return matchups

    def get_last_starting_order(self, person_id, year=2026):
        if not person_id:
            return "5"

        # Use a simple cache key that doesn't depend on the year
        cache_key = f"last_order_{person_id}"
        if cache_key in self.player_id_cache:
            return self.player_id_cache[cache_key]

        try:
            # Check current year then previous year
            for check_year in [year, year - 1]:
                params = {
                    'personId': person_id,
                    'hydrate': f'stats(group=[hitting],type=[gameLog],season={check_year})'
                }
                p = statsapi.get('person', params)

                if p and 'people' in p and p['people'][0].get('stats'):
                    stats_list = p['people'][0]['stats']
                    for s in stats_list:
                        if s.get('type', {}).get('displayName') == 'gameLog':
                            splits = s.get('splits', [])
                            if splits:
                                # Look for the most recent 5 games where they might have started
                                # We limit to 5 to avoid too many API calls for boxscores
                                for split in reversed(splits[-5:]):
                                    game_pk = split.get('game', {}).get('gamePk')
                                    if not game_pk: continue

                                    try:
                                        # Fetch boxscore with caching to avoid repeated API hits
                                        if game_pk not in self._boxscore_cache:
                                            self._boxscore_cache[game_pk] = statsapi.boxscore_data(game_pk)
                                        box = self._boxscore_cache[game_pk]
                                        # Search in both away and home batters
                                        for team in ['awayBatters', 'homeBatters']:
                                            for batter in box.get(team, []):
                                                if batter.get('personId') == person_id:
                                                    order = batter.get('battingOrder', '')
                                                    # Starts end in '00'
                                                    if order and order.endswith('00'):
                                                        res = order[0]
                                                        self.player_id_cache[cache_key] = res
                                                        return res
                                    except Exception as e:
                                        logger.warning(f"Boxscore lookup failed for game {game_pk}: {e}")
                                        continue
        except Exception as e:
            logger.warning(f"get_last_starting_order failed for player {person_id}: {e}")

        # Fallback to middle of the order
        self.player_id_cache[cache_key] = "5"
        return "5"
    def get_player_statuses(self, mlb_ids):
        """Fetches current team status for multiple MLB IDs in bulk."""
        if not mlb_ids: return {}
        
        # Convert to strings and filter out None
        ids = [str(i) for i in mlb_ids if i]
        if not ids: return {}
        
        results = {}
        # Batch by 50 to avoid URL length issues
        for i in range(0, len(ids), 50):
            batch = ids[i:i+50]
            try:
                params = {'personIds': ','.join(batch), 'hydrate': 'currentTeam'}
                p = statsapi.get('people', params)
                for person in p.get('people', []):
                    p_id = person.get('id')
                    current_team = person.get('currentTeam', {})
                    # If parentOrgId is present, they are in the minors (assigned to an affiliate)
                    is_minors = 'parentOrgId' in current_team
                    team_name = current_team.get('name', 'Unknown')
                    results[p_id] = {'is_minors': is_minors, 'team_name': team_name}
            except Exception as e:
                logger.warning(f"get_player_statuses batch failed: {e}")
                continue
        return results

    def get_platoon_splits(self, mlb_ids, year=2025):
        """Fetches vs LHP and vs RHP OPS splits for multiple MLB IDs in bulk."""
        if not mlb_ids: return {}
        
        ids = [str(i) for i in mlb_ids if i]
        results = {}
        
        # Batch by 50
        for i in range(0, len(ids), 50):
            batch = ids[i:i+50]
            try:
                # vl = vs Left, vr = vs Right
                params = {
                    'personIds': ','.join(batch), 
                    'hydrate': f'stats(group=[hitting],type=[statSplits],season={year},sitCodes=[vl,vr])'
                }
                p = statsapi.get('people', params)
                for person in p.get('people', []):
                    p_id = person.get('id')
                    splits_data = {'vs_l': None, 'vs_r': None, 'pa_vs_l': 0, 'pa_vs_r': 0}

                    stats = person.get('stats', [])
                    if stats:
                        for split in stats[0].get('splits', []):
                            desc = split.get('split', {}).get('description')
                            stat = split.get('stat', {})
                            ops_str = stat.get('ops')
                            pa = int(stat.get('plateAppearances', 0) or 0)
                            if ops_str:
                                try:
                                    ops_val = float(ops_str)
                                    if desc == 'vs Left':
                                        splits_data['vs_l'] = ops_val
                                        splits_data['pa_vs_l'] = pa
                                    elif desc == 'vs Right':
                                        splits_data['vs_r'] = ops_val
                                        splits_data['pa_vs_r'] = pa
                                except ValueError:
                                    continue
                    results[p_id] = splits_data
            except Exception as e:
                logger.warning(f"get_platoon_splits batch failed (year={year}): {e}")
                continue
        return results

    def get_team_abb(self, team_id):
        if not team_id: return ""
        if team_id in self.team_abb_cache:
            return self.team_abb_cache[team_id]
            
        try:
            team = statsapi.get('team', {'teamId': team_id})
            if team and 'teams' in team:
                abb = team['teams'][0].get('abbreviation', '')
                self.team_abb_cache[team_id] = abb
                return abb
        except Exception as e:
            logger.warning(f"get_team_abb failed for team {team_id}: {e}")
        return ""

    def get_batter_data(self, person_id):
        if not person_id:
            return {'hand': 'R'}
            
        cache_key = f"batter_{person_id}"
        if cache_key in self._player_data_cache:
            return self._player_data_cache[cache_key]

        data = {'hand': 'R'}
        try:
            player = statsapi.get('person', {'personId': person_id})
            if player and 'people' in player:
                p = player['people'][0]
                data['hand'] = p.get('batSide', {}).get('code', 'R')
        except Exception as e:
            logger.warning(f"get_batter_data failed for player {person_id}: {e}")
            
        self._player_data_cache[cache_key] = data
        return data

    def get_hitter_statcast_data(self, person_id, weight_current=0.0):
        return self.statcast.get_blended_hitter_stats(person_id, weight_current=weight_current)

    def get_bvp_data(self, batter_id, pitcher_id):
        if not batter_id or not pitcher_id:
            return None
            
        cache_key = f"{batter_id}_{pitcher_id}"
        if cache_key in self._bvp_cache:
            return self._bvp_cache[cache_key]

        data = None
        try:
            url = f'https://statsapi.mlb.com/api/v1/people/{batter_id}/stats?stats=vsPlayerTotal&group=hitting&opposingPlayerId={pitcher_id}'
            r = requests.get(url, timeout=10)
            stats_json = r.json()
            if 'stats' in stats_json and stats_json['stats']:
                splits = stats_json['stats'][0].get('splits', [])
                if splits:
                    s = splits[0]['stat']
                    data = {
                        'pa': int(s.get('plateAppearances', 0)),
                        'ops': float(s.get('ops', 0.0)),
                        'avg': float(s.get('avg', 0.0))
                    }
        except Exception as e:
            logger.warning(f"get_bvp_data failed for batter {batter_id} vs pitcher {pitcher_id}: {e}")
            
        self._bvp_cache[cache_key] = data
        return data

    def get_pitcher_data(self, person_id, year=2025, weight_current=0.0):
        if not person_id:
            return {'hand': 'R', 'era': 4.0, 'xera': 4.0}
            
        cache_key = f"pitcher_{person_id}_{year}_{weight_current}"
        if cache_key in self._player_data_cache:
            return self._player_data_cache[cache_key]

        data = {'hand': 'R', 'era': 4.0, 'xera': 4.0}
        
        try:
            # 1. Get Handedness
            player = statsapi.get('person', {'personId': person_id})
            if player and 'people' in player:
                p = player['people'][0]
                data['hand'] = p.get('pitchHand', {}).get('code', 'R')
            
            # 2. Check Blended StatCast
            sc_stats = self.statcast.get_blended_pitcher_stats(person_id, weight_current=weight_current)
            if sc_stats is not None:
                data['xera'] = float(sc_stats.get('xERA', sc_stats.get('SIERA', sc_stats.get('kwERA', 4.0))))
                data['SIERA'] = float(sc_stats.get('SIERA', data['xera']))
                data['era'] = float(sc_stats.get('ERA', 4.0))
            else:
                # Fallback to statsapi Season Stats
                url = f'https://statsapi.mlb.com/api/v1/people/{person_id}/stats?stats=season&group=pitching&season={year}'
                r = requests.get(url, timeout=10)
                stats_json = r.json()
                if 'stats' in stats_json and stats_json['stats']:
                    s = stats_json['stats'][0].get('splits', [{}])[0].get('stat', {})
                    data['era'] = float(s.get('era', 4.0))
                    data['xera'] = float(s.get('era', 4.0))
        except Exception as e:
            logger.warning(f"get_pitcher_data failed for player {person_id}: {e}")
            
        self._player_data_cache[cache_key] = data
        return data

    def get_actual_boxscore_stats(self, target_date: str):
        actuals = {}
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        formatted_date = dt.strftime("%m/%d/%Y")
        games = statsapi.schedule(date=formatted_date)
        
        for game in games:
            try:
                gid = game['game_id']
                if gid not in self._boxscore_cache:
                    self._boxscore_cache[gid] = statsapi.boxscore_data(gid)
                box = self._boxscore_cache[gid]
            except Exception as e:
                logger.warning(f"Boxscore fetch failed for game {game['game_id']}: {e}")
                continue
                
            for team_batters in ['awayBatters', 'homeBatters']:
                if box.get(team_batters):
                    for batter in box[team_batters]:
                        if isinstance(batter, dict) and 'personId' in batter and batter.get('ab'):
                            try:
                                actuals[batter['personId']] = {
                                    'R': int(batter.get('r', 0)),
                                    'HR': int(batter.get('hr', 0)),
                                    'RBI': int(batter.get('rbi', 0)),
                                    'SB': int(batter.get('sb', 0)),
                                    'AB': int(batter.get('ab', 0)),
                                    'H': int(batter.get('h', 0)),
                                    'SO': int(batter.get('k', 0)),
                                }
                            except:
                                continue
        return actuals
