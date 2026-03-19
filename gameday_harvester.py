import statsapi
from pybaseball import playerid_lookup
import pandas as pd
from datetime import datetime
import requests
from statcast_harvester import StatCastHarvester
from crosswalks import TeamCrosswalk, PlayerCrosswalk

class GameDayHarvester:
    def __init__(self):
        # Cache for player IDs to avoid repeated lookups
        self.player_id_cache = {}
        self.statcast = StatCastHarvester()

    def get_mlb_id(self, player_name, target_year=2025):
        cache_key = f"{player_name}_{target_year}"
        if cache_key in self.player_id_cache:
            return self.player_id_cache[cache_key]

        # Use manual mapping if available
        search_name = PlayerCrosswalk.get_name_map(player_name)

        # Clean the name: Remove common suffixes
        suffixes = [' Jr.', ' Sr.', ' II', ' III', ' IV']
        for s in suffixes:
            search_name = search_name.replace(s, '')
        
        try:
            # Use statsapi.lookup_player for the most reliable mapping to personId
            lookup = statsapi.lookup_player(search_name)
            if lookup:
                # If there are multiple, prefer players with a debut date or current team
                if len(lookup) > 1:
                    lookup = sorted(lookup, key=lambda x: x.get('mlbDebutDate', '0000'), reverse=True)
                
                mlb_id = lookup[0]['id']
                self.player_id_cache[cache_key] = int(mlb_id)
                return int(mlb_id)
        except Exception:
            pass
            
        self.player_id_cache[cache_key] = None
        return None

    def get_daily_matchups(self, target_date: str):
        matchups = {'_teams_playing': {}}
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        formatted_date = dt.strftime("%m/%d/%Y")
        
        games = statsapi.schedule(date=formatted_date)
        
        for game in games:
            game_id = game['game_id']
            venue = game.get('venue_name', 'Unknown')
            status = game.get('status', 'Unknown')
            
            try:
                box = statsapi.boxscore_data(game_id)
            except Exception:
                continue
            
            away_abb = box.get('teamInfo', {}).get('away', {}).get('abbreviation')
            home_abb = box.get('teamInfo', {}).get('home', {}).get('abbreviation')
            
            # Map abbreviations to Ottoneu format for consistent lookup
            away_abb = TeamCrosswalk.to_ottoneu(away_abb)
            home_abb = TeamCrosswalk.to_ottoneu(home_abb)
            
            away_sp = None
            home_sp = None
            for p in box.get('awayPitchers', []):
                if p.get('personId') and p.get('name') != 'Pitchers':
                    away_sp = p
                    break
            for p in box.get('homePitchers', []):
                if p.get('personId') and p.get('name') != 'Pitchers':
                    home_sp = p
                    break

            # Initial team entry
            if away_abb:
                matchups['_teams_playing'][away_abb] = {
                    'has_lineup': False,
                    'opposing_sp_name': home_sp['name'] if home_sp else None,
                    'opposing_sp_id': home_sp['personId'] if home_sp else None,
                    'venue_name': venue,
                    'home_team_abb': home_abb,
                    'is_home': False,
                    'game_status': status
                }
            if home_abb:
                matchups['_teams_playing'][home_abb] = {
                    'has_lineup': False,
                    'opposing_sp_name': away_sp['name'] if away_sp else None,
                    'opposing_sp_id': away_sp['personId'] if away_sp else None,
                    'venue_name': venue,
                    'home_team_abb': home_abb,
                    'is_home': True,
                    'game_status': status
                }
            
            if box.get('awayBatters'):
                for batter in box['awayBatters']:
                    if isinstance(batter, dict) and 'personId' in batter:
                        is_start = batter.get('battingOrder', '0').endswith('00') and len(batter.get('battingOrder', '0')) == 3
                        if is_start: matchups['_teams_playing'][away_abb]['has_lineup'] = True
                        matchups[batter['personId']] = {
                            'is_starting': is_start,
                            'batting_order': batter.get('battingOrder'),
                            'opposing_sp_name': home_sp['name'] if home_sp else None,
                            'opposing_sp_id': home_sp['personId'] if home_sp else None,
                            'venue_name': venue,
                            'home_team_abb': home_abb,
                            'is_home': False,
                            'game_status': status
                        }
                        
            if box.get('homeBatters'):
                for batter in box['homeBatters']:
                    if isinstance(batter, dict) and 'personId' in batter:
                        is_start = batter.get('battingOrder', '0').endswith('00') and len(batter.get('battingOrder', '0')) == 3
                        if is_start: matchups['_teams_playing'][home_abb]['has_lineup'] = True
                        matchups[batter['personId']] = {
                            'is_starting': is_start,
                            'batting_order': batter.get('battingOrder'),
                            'opposing_sp_name': away_sp['name'] if away_sp else None,
                            'opposing_sp_id': away_sp['personId'] if away_sp else None,
                            'venue_name': venue,
                            'home_team_abb': home_abb,
                            'is_home': True,
                            'game_status': status
                        }
                        
        return matchups

    def get_batter_data(self, person_id):
        if not person_id:
            return {'hand': 'R'}
            
        cache_key = f"batter_{person_id}"
        if cache_key in self.player_id_cache:
            return self.player_id_cache[cache_key]

        data = {'hand': 'R'}
        try:
            player = statsapi.get('person', {'personId': person_id})
            if player and 'people' in player:
                p = player['people'][0]
                data['hand'] = p.get('batSide', {}).get('code', 'R')
        except Exception:
            pass
            
        self.player_id_cache[cache_key] = data
        return data

    def get_hitter_statcast_data(self, person_id, weight_current=0.0):
        return self.statcast.get_blended_hitter_stats(person_id, weight_current=weight_current)

    def get_bvp_data(self, batter_id, pitcher_id):
        if not batter_id or not pitcher_id:
            return None
            
        cache_key = f"bvp_{batter_id}_{pitcher_id}"
        if cache_key in self.player_id_cache:
            return self.player_id_cache[cache_key]

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
            
        self.player_id_cache[cache_key] = data
        return data

    def get_pitcher_data(self, person_id, year=2025, weight_current=0.0):
        if not person_id:
            return {'hand': 'R', 'era': 4.0, 'xera': 4.0}
            
        cache_key = f"pitcher_{person_id}_{year}_{weight_current}"
        if cache_key in self.player_id_cache:
            return self.player_id_cache[cache_key]

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
                stats_json = r.json()
                if 'stats' in stats_json and stats_json['stats']:
                    splits = stats_json['stats'][0].get('splits', [])
                    if splits:
                        data['era'] = float(splits[0]['stat'].get('era', 4.0))
                        data['xera'] = data['era']
                elif year == 2026:
                    return self.get_pitcher_data(person_id, year=2025, weight_current=0.0)

        except Exception:
            pass
            
        self.player_id_cache[cache_key] = data
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
                                    'CS': int(batter.get('caughtStealing', 0))
                                }
                            except ValueError:
                                pass
                                
        return actuals

    def get_statcast_ev_stats(self, target_date: str):
        """
        Returns { personId: {'avg_ev': float, 'max_ev': float} }
        """
        ev_stats = {}
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        formatted_date = dt.strftime("%m/%d/%Y")
        games = statsapi.schedule(date=formatted_date)
        
        for game in games:
            game_id = game['game_id']
            try:
                pbp = statsapi.get('game_playByPlay', {'gamePk': game_id})
                for play in pbp.get('allPlays', []):
                    batter_id = play.get('matchup', {}).get('batter', {}).get('id')
                    if not batter_id: continue
                    
                    # Exit velocity is usually in the last playEvent's hitData
                    hit_data = None
                    for event in play.get('playEvents', []):
                        if event.get('hitData'):
                            hit_data = event['hitData']
                            break
                    
                    if hit_data and 'launchSpeed' in hit_data:
                        ev = float(hit_data['launchSpeed'])
                        if batter_id not in ev_stats:
                            ev_stats[batter_id] = []
                        ev_stats[batter_id].append(ev)
            except Exception:
                continue
        
        # Calculate summaries
        summary = {}
        for b_id, evs in ev_stats.items():
            summary[b_id] = {
                'avg_ev': sum(evs) / len(evs),
                'max_ev': max(evs)
            }
        return summary

if __name__ == "__main__":
    harvester = GameDayHarvester()
    test_date = "2024-06-15"
    print(f"Testing GameDayHarvester for {test_date}...")
    matchups = harvester.get_daily_matchups(test_date)
    print(f"Found {len(matchups)} players in matchups.")
    
    test_name = "Victor Scott II"
    mlb_id = harvester.get_mlb_id(test_name)
    print(f"MLB ID for {test_name}: {mlb_id}")
    if mlb_id and mlb_id in matchups:
        print(f"Matchup data: {matchups[mlb_id]}")
