import statsapi
from pybaseball import playerid_lookup
import pandas as pd
from datetime import datetime
import requests
from statcast_harvester import StatCastHarvester
from defense_harvester import DefenseHarvester
from crosswalks import TeamCrosswalk, PlayerCrosswalk, get_team_ottoneu

class GameDayHarvester:
    _instance = None
    _matchups_cache = {} 
    _bvp_cache = {} # Shared batter vs pitcher stats
    _player_data_cache = {} # Shared hand/stats/etc

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

    def get_mlb_id(self, player_name, target_year=2025):
        # Clean name for search
        search_name = player_name
        suffixes = [' Jr.', ' Sr.', ' II', ' III', ' IV']
        for s in suffixes:
            search_name = search_name.replace(s, '')
        
        try:
            # Use statsapi.lookup_player for the most reliable mapping to personId
            # We don't cache this at class level because names can be ambiguous
            cache_key = f"id_{player_name}_{target_year}"
            if cache_key in self.player_id_cache:
                return self.player_id_cache[cache_key]

            results = statsapi.lookup_player(search_name)
            if results:
                # If multiple found, pick the one active in the target year
                # Or just the first one if only one exists
                p_id = results[0]['id']
                self.player_id_cache[cache_key] = p_id
                return p_id
        except Exception:
            pass
            
        self.player_id_cache[cache_key] = None
        return None

    def get_daily_matchups(self, target_date: str):
        if target_date in self._matchups_cache:
            return self._matchups_cache[target_date]

        print(f"Fetching fresh matchups for {target_date} from MLB API...")
        matchups = {'_teams_playing': {}}
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
                    except Exception:
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
                box = statsapi.boxscore_data(game_id)
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
            except Exception:
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
                except Exception:
                    pass

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

    def get_last_starting_order(self, person_id, year=2025):
        if not person_id:
            return "5"
            
        cache_key = f"last_order_{person_id}_{year}"
        if cache_key in self.player_id_cache:
            return self.player_id_cache[cache_key]
            
        try:
            # Check past season and current season stats separately for reliability
            for y in [year, year + 1]:
                p = statsapi.get('person', {
                    'personId': person_id, 
                    'hydrate': f'stats(group=[hitting],type=[season],season={y})'
                })
                # ... rest of historical order logic ...
        except Exception:
            pass
        return "5"

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
        except Exception:
            pass
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
        except Exception:
            pass
            
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
            r = requests.get(url)
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
        except Exception:
            pass
            
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
                r = requests.get(url)
                # ... rest of pitcher fallback ...
        except Exception:
            pass
            
        self._player_data_cache[cache_key] = data
        return data

    def get_actual_boxscore_stats(self, target_date: str):
        actuals = {}
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        formatted_date = dt.strftime("%m/%d/%Y")
        games = statsapi.schedule(date=formatted_date)
        
        for game in games:
            try:
                box = statsapi.boxscore_data(game['game_id'])
            except Exception:
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
