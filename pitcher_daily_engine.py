import pandas as pd
from gameday_harvester import GameDayHarvester
from pitcher_enricher import PitcherEnricher
from enricher import OttoneuEnricher
from datetime import datetime
from park_factors import get_park_multiplier
from weather_harvester import WeatherHarvester
import os
import json

class PitcherDailyEngine:
    def __init__(self, league_id=1077, team_id=7582, projection_system="steamer"):
        self.enricher = PitcherEnricher(league_id, team_id, projection_system=projection_system)
        self.hitter_enricher = OttoneuEnricher(league_id, team_id, projection_system=projection_system)
        self.harvester = GameDayHarvester.get_instance()
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

    def get_opposing_lineup_power(self, team_abb, target_date, hitter_projections):
        """
        Returns the top 9 projected hitters for a team based on their baseline score.
        Useful when official lineup is not yet posted.
        """
        if 'Score' not in hitter_projections.columns:
            hitter_projections['Score'] = (
                (hitter_projections['R'].astype(float) + hitter_projections['HR'].astype(float) + 
                 hitter_projections['RBI'].astype(float) + hitter_projections['SB'].astype(float)) / 
                hitter_projections['PA'].astype(float).replace(0, 1) * 100
            ) + (hitter_projections['AVG'].astype(float) * 100)
            
        team_pool = hitter_projections[hitter_projections['Team'] == team_abb].copy()
        if team_pool.empty:
            return []
            
        probable_starters = team_pool.sort_values(by='PA', ascending=False).head(15)
        probable_starters = probable_starters.sort_values(by='Score', ascending=False).head(9)
        
        return probable_starters['xMLBAMID'].tolist()

    def get_daily_projections(self, target_date: str):
        # 1. Base Roster and Season-long Projections
        pitchers = self.enricher.enrich_roster()
        hitter_projections = self.hitter_enricher.fetch_projections()
        
        # 2. Get Daily Matchups
        matchups = self.harvester.get_daily_matchups(target_date)
        
        # 3. Identify Starters
        starting_map = matchups.get('_starting_pitchers', {})
        
        is_today = target_date == datetime.now().strftime("%Y-%m-%d")
        weather_report = self.weather.get_weather_report() if is_today else {}
        weight_current = self._get_recency_weight(target_date)
        
        daily_scores = []
        is_starting = []
        breakdowns = []
        opponents = []
        warnings = []
        game_times = []
        is_opener_list = []
        
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
            is_opener = False
            
            if mlb_id and mlb_id in starting_map:
                starting = True
                m = starting_map[mlb_id]
                opponent = m['opposing_team']
                game_time = m['game_time']
                
                # Check for rainouts / postponements
                if m.get('is_postponed'):
                    daily_scores.append(0.0)
                    is_starting.append(False)
                    breakdowns.append("RAINOUT (Postponed)")
                    opponents.append(opponent)
                    warnings.append("🚨 RAINOUT / POSTPONED")
                    game_times.append(game_time)
                    is_opener_list.append(False)
                    continue
                
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
                        
                        if w.get('temp', 0) > 85:
                            multiplier *= 0.95
                            breakdown.append("Heat (>85F): -5%")
                        
                        if w['rain_risk'] >= 60:
                            warning = f"🚨 HIGH RAIN RISK ({w['rain_risk']}%)"
                        elif w['rain_risk'] >= 30:
                            warning = f"⚠️ Rain Risk ({w['rain_risk']}%)"

                # 3. Statcast (Projected vs Blended)
                # Formula: (Projected ERA - Blended xERA) * 0.1 multiplier boost
                sp_data = self.harvester.get_pitcher_data(mlb_id, year=2026, weight_current=weight_current)
                xera = sp_data.get('xera')
                proj_era = row.get('ERA_y')
                
                if xera and proj_era:
                    diff = proj_era - xera
                    sc_mult = 1.0 + (diff * 0.1)
                    sc_mult = max(0.8, min(1.2, sc_mult))
                    multiplier *= sc_mult
                    diff_pct = int((sc_mult - 1.0) * 100)
                    if diff_pct != 0:
                        breakdown.append(f"Statcast (xERA {xera:.2f}): {diff_pct:+}%")

                # 4. Agg BvP
                # Average OPS allowed to current/projected lineup
                opp_team = m['opposing_team']
                if m.get('has_lineup'):
                    # Use actual lineup from matchups
                    opp_ids = [p_id for p_id, d in matchups.items() if isinstance(d, dict) and d.get('home_team_abb') == opp_team or d.get('opposing_team') == opp_team]
                    # Actually, matchups is indexed by MLB ID. 
                    # Let's find players whose team is opp_team.
                    opp_ids = []
                    for p_id, d in matchups.items():
                        if isinstance(d, dict) and d.get('is_starting'):
                            # Find if this player is on the opposing team
                            # Need to check team_abb
                            pass # TODO: improve this
                
                # For now, use projected top 9 for power/bvp
                opp_ids = self.get_opposing_lineup_power(opp_team, target_date, hitter_projections)
                
                if opp_ids:
                    bvp_list = []
                    for b_id in opp_ids:
                        bvp = self.harvester.get_bvp_data(b_id, mlb_id)
                        if bvp and bvp['pa'] >= 3:
                            bvp_list.append(bvp['ops'])
                    
                    if bvp_list:
                        avg_ops = sum(bvp_list) / len(bvp_list)
                        # OPS > 0.850 is bad for pitcher, OPS < 0.650 is good
                        if avg_ops < 0.650:
                            multiplier *= 1.12
                            breakdown.append(f"Agg BvP (OPS {avg_ops:.3f}): +12%")
                        elif avg_ops > 0.850:
                            multiplier *= 0.88
                            breakdown.append(f"Agg BvP (OPS {avg_ops:.3f}): -12%")

                # 5. Opponent Power
                # Calculate aggregate projected efficiency of opposing top 9
                opp_scores = []
                opp_pool = hitter_projections[hitter_projections['Team'] == opp_team]
                if not opp_pool.empty:
                    opp_top9 = opp_pool.sort_values(by='Score', ascending=False).head(9)
                    avg_opp_score = opp_top9['Score'].mean()
                    
                    # 52.0 is a "neutral" league average efficiency
                    power_factor = 1.0 - ((avg_opp_score - 52.0) / 100.0)
                    power_factor = max(0.85, min(1.15, power_factor))
                    multiplier *= power_factor
                    diff_pct = int((power_factor - 1.0) * 100)
                    if diff_pct != 0:
                        breakdown.append(f"Opp Power ({avg_opp_score:.1f}): {diff_pct:+}%")

                daily_score = base_score * multiplier

            daily_scores.append(daily_score)
            is_starting.append(starting)
            breakdowns.append(", ".join(breakdown) if breakdown else "Base")
            opponents.append(opponent)
            warnings.append(warning)
            game_times.append(game_time)
            is_opener_list.append(is_opener)
            
        pitchers['DailyScore'] = daily_scores
        pitchers['IsStarting'] = is_starting
        pitchers['Breakdown'] = breakdowns
        pitchers['Opponent'] = opponents
        pitchers['Warning'] = warnings
        pitchers['GameTime'] = game_times
        pitchers['IsOpener'] = is_opener_list
        
        return pitchers.copy()

if __name__ == "__main__":
    engine = PitcherDailyEngine()
    test_date = datetime.now().strftime("%Y-%m-%d")
    projections = engine.get_daily_projections(test_date)
    starters = projections[projections['IsStarting'] == True]
    print(starters[['Name', 'Team', 'DailyScore', 'Opponent', 'Breakdown']].sort_values(by='DailyScore', ascending=False))
