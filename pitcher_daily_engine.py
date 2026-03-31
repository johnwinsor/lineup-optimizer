import pandas as pd
from gameday_harvester import GameDayHarvester
from pitcher_enricher import PitcherEnricher
from enricher import OttoneuEnricher
from datetime import datetime
from park_factors import get_park_multiplier
from weather_harvester import WeatherHarvester
import os
import json
import re

class PitcherDailyEngine:
    def __init__(self, league_id=1077, team_id=7582, projection_system="steamer"):
        self.enricher = PitcherEnricher(league_id, team_id, projection_system=projection_system)
        self.hitter_enricher = OttoneuEnricher(league_id, team_id, projection_system=projection_system)
        self.harvester = GameDayHarvester()
        self.weather = WeatherHarvester()
        self.league_id = league_id
        self.team_id = team_id

    def _get_recency_weight(self, target_date: str):
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        month = dt.month
        if month <= 4: return 0.0
        if month == 5: return 0.3
        if month == 6: return 0.6
        return 1.0

    def _get_projected_lineup(self, team_abb, hitter_projections):
        """
        Returns the top 9 projected hitters for a team based on their baseline score.
        Useful when official lineup is not yet posted.
        """
        # FanGraphs projection 'Team' field is usually uppercase (e.g. 'NYY')
        # Ensure hitter_projections has 'Score'
        if 'Score' not in hitter_projections.columns:
            hitter_projections['Score'] = (
                (hitter_projections['R'].astype(float) + hitter_projections['HR'].astype(float) + 
                 hitter_projections['RBI'].astype(float) + hitter_projections['SB'].astype(float)) / 
                hitter_projections['PA'].astype(float).replace(0, 1) * 100
            ) + (hitter_projections['AVG'].astype(float) * 100)
            
        team_pool = hitter_projections[hitter_projections['Team'] == team_abb].copy()
        if team_pool.empty:
            return []
            
        # Take top 9 by score, but also filter for those with significant PA to avoid call-up noise
        # Sort by PA first to find established players, then take top 9 by score among the top 15 by PA
        probable_starters = team_pool.sort_values(by='PA', ascending=False).head(15)
        probable_starters = probable_starters.sort_values(by='Score', ascending=False).head(9)
        
        return probable_starters['xMLBAMID'].tolist()

    def get_daily_projections(self, target_date: str):
        # 1. Base Roster and Season-long Projections
        pitchers = self.enricher.enrich_roster()
        hitter_projections = self.hitter_enricher.fetch_projections()
        
        # 2. Get Daily Matchups
        matchups = self.harvester.get_daily_matchups(target_date)
        teams_playing = matchups.get('_teams_playing', {})
        
        # 3. Identify Starters
        starting_map = {}
        for team_abb, data in teams_playing.items():
            sp_id = data.get('opposing_sp_id')
            sp_name = data.get('opposing_sp_name')
            if sp_id:
                starting_map[sp_id] = {
                    'name': sp_name,
                    'opposing_team': team_abb,
                    'venue_name': data['venue_name'],
                    'home_team_abb': data['home_team_abb'],
                    'is_home': not data['is_home'],
                    'game_time': data.get('game_time'),
                    'game_status': data.get('game_status'),
                    'has_lineup': data.get('has_lineup', False)
                }

        is_today = target_date == datetime.now().strftime("%Y-%m-%d")
        weather_report = self.weather.get_weather_report() if is_today else {}
        weight_current = self._get_recency_weight(target_date)
        
        daily_scores = []
        is_starting = []
        breakdowns = []
        opponents = []
        warnings = []
        game_times = []
        
        for _, row in pitchers.iterrows():
            player_name = row['Name']
            mlb_id = row.get('xMLBAMID')
            if pd.isna(mlb_id) or not mlb_id:
                mlb_id = self.harvester.get_mlb_id(player_name)
            else:
                mlb_id = int(mlb_id)
            
            daily_score = 0.0
            starting = False
            breakdown = []
            opponent = "N/A"
            warning = ""
            game_time = None
            
            if mlb_id and mlb_id in starting_map:
                starting = True
                m = starting_map[mlb_id]
                opponent = m['opposing_team']
                game_time = m['game_time']
                
                base_score = row['Score']
                multiplier = 1.0
                breakdown.append(f"Base: {base_score:.2f}")

                # 1. Venue (Inverse of Hitter)
                park_mult = get_park_multiplier(m['venue_name'])
                pitcher_park_mult = 2.0 - park_mult
                if pitcher_park_mult != 1.0:
                    multiplier *= pitcher_park_mult
                    diff = int((pitcher_park_mult - 1.0) * 100)
                    breakdown.append(f"Park: {diff:+}%")

                # 2. Weather
                home_abb = m['home_team_abb']
                if home_abb in weather_report:
                    w = weather_report[home_abb]
                    if not w['is_dome']:
                        if w['wind_dir'] == "In" and w['wind_speed'] >= 10:
                            boost = 1.05 if w['wind_speed'] < 20 else 1.10
                            multiplier *= boost
                            breakdown.append(f"Wind In: +{int((boost-1)*100)}%")
                        elif w['wind_dir'] == "Out" and w['wind_speed'] >= 10:
                            penalty = 0.95 if w['wind_speed'] < 20 else 0.90
                            multiplier *= penalty
                            breakdown.append(f"Wind Out: -{int((1-penalty)*100)}%")
                        
                        temp = w.get('temp', 70)
                        if temp > 85:
                            multiplier *= 0.98
                            breakdown.append("Heat (>85F): -2%")

                # 3. Statcast Blended SIERA/xERA
                sc_stats = self.harvester.statcast.get_blended_pitcher_stats(mlb_id, weight_current=weight_current)
                if sc_stats is not None:
                    proj_era = row['ERA_y'] if not pd.isna(row['ERA_y']) else 4.0
                    blended_xera = float(sc_stats.get('xERA', sc_stats.get('SIERA', proj_era)))
                    era_delta = (proj_era - blended_xera) * 0.1
                    if abs(era_delta) > 0.01:
                        multiplier *= (1.0 + era_delta)
                        breakdown.append(f"Statcast (xERA {blended_xera:.2f}): {era_delta*100:+.1f}%")

                # 4. Rigorous Opponent Research: BvP & Lineup Strength
                opp_lineup_ids = []
                if m['has_lineup']:
                    opp_lineup_ids = [pid for pid, val in matchups.items() if isinstance(val, dict) and val.get('opposing_sp_id') == mlb_id]
                else:
                    # Fallback: Get Projected Starting 9 for the opposing team
                    opp_lineup_ids = self._get_projected_lineup(m['opposing_team'], hitter_projections)
                    if opp_lineup_ids:
                        breakdown.append(f"Projected Opp Lineup (Pending Card)")
                
                if opp_lineup_ids:
                    # Aggregate BvP
                    bvp_ops_list = []
                    for b_id in opp_lineup_ids:
                        bvp = self.harvester.get_bvp_data(b_id, mlb_id)
                        if bvp and bvp['pa'] >= 3:
                            bvp_ops_list.append(bvp['ops'])
                    
                    if bvp_ops_list:
                        avg_ops = sum(bvp_ops_list) / len(bvp_ops_list)
                        ops_factor = 1.0 + (0.750 - avg_ops) * 0.5 
                        ops_factor = max(0.85, min(1.15, ops_factor))
                        if abs(ops_factor - 1.0) > 0.01:
                            multiplier *= ops_factor
                            breakdown.append(f"Agg BvP (OPS {avg_ops:.3f}): {int((ops_factor-1)*100):+}%")

                    # Opponent Lineup Power (Using Hitter Efficiency Scores)
                    opp_scores = []
                    for b_id in opp_lineup_ids:
                        h_match = hitter_projections[hitter_projections['xMLBAMID'] == b_id]
                        if not h_match.empty:
                            h = h_match.iloc[0]
                            h_score = ((h['R']+h['HR']+h['RBI']+h['SB'])/h['PA']*100) + (h['AVG']*100)
                            opp_scores.append(h_score)
                        else:
                            opp_scores.append(40.0) # Neutral Floor
                    
                    if opp_scores:
                        avg_opp_score = sum(opp_scores) / len(opp_scores)
                        # Neutral is ~50.0 efficiency. Penalty for high, boost for low.
                        opp_mult = 1.0 + (50.0 - avg_opp_score) / 200.0
                        opp_mult = max(0.85, min(1.15, opp_mult))
                        if abs(opp_mult - 1.0) > 0.01:
                            multiplier *= opp_mult
                            breakdown.append(f"Opp Power ({avg_opp_score:.1f}): {int((opp_mult-1)*100):+}%")

                daily_score = base_score * multiplier
            
            daily_scores.append(daily_score)
            is_starting.append(starting)
            breakdowns.append(", ".join(breakdown) if breakdown else "Base")
            opponents.append(opponent)
            warnings.append(warning)
            game_times.append(game_time)
            
        pitchers['DailyScore'] = daily_scores
        pitchers['IsStarting'] = is_starting
        pitchers['Breakdown'] = breakdowns
        pitchers['Opponent'] = opponents
        pitchers['Warning'] = warnings
        pitchers['GameTime'] = game_times
        
        return pitchers.copy()

if __name__ == "__main__":
    engine = PitcherDailyEngine()
    test_date = "2026-04-01"
    print(f"Running Rigorous Pitcher Analysis for {test_date}...")
    projections = engine.get_daily_projections(test_date)
    starters = projections[projections['IsStarting'] == True]
    print(starters[['Name', 'Team', 'DailyScore', 'Opponent', 'Breakdown']].sort_values(by='DailyScore', ascending=False))
