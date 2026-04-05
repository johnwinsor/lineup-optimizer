import pandas as pd
from gameday_harvester import GameDayHarvester
from enricher import OttoneuEnricher
from defense_harvester import DefenseHarvester
from datetime import datetime
from park_factors import get_park_multiplier
from weather_harvester import WeatherHarvester
import os
import json
import re

class DailyEngine:
    def __init__(self, league_id=1077, team_id=7582, projection_system="steamer"):
        self.enricher = OttoneuEnricher(league_id, team_id, projection_system=projection_system)
        self.harvester = GameDayHarvester.get_instance()
        self.weather = WeatherHarvester()
        self.defense = DefenseHarvester()

    def _get_recency_weight(self, target_date: str):
        """
        Calculates the weight for current season data based on the date.
        """
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        month = dt.month
        if month <= 4: return 0.0
        if month == 5: return 0.3
        if month == 6: return 0.6
        return 1.0

    def get_free_agent_projections(self, target_date: str):
        """
        Loads the free_agents.json and calculates daily projections for them.
        """
        if not os.path.exists('free_agents.json'):
            return pd.DataFrame()
            
        with open('free_agents.json', 'r') as f:
            data = json.load(f).get('data', [])
        
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame()
        
        # Map fields to match Ottoneu Roster format
        df['Name'] = df['Name'].apply(lambda x: re.search(r'>(.*?)</a>', x).group(1) if '>' in str(x) else x)
        df['Team'] = df['Team'].apply(lambda x: re.search(r'>(.*?)</a>', x).group(1) if '>' in str(x) else x)
        df['POS'] = df['position']
        
        # Calculate Base Efficiency Score (Algorithm V2)
        df['Score'] = (
            (df['R'].astype(float) + df['HR'].astype(float) + df['RBI'].astype(float) + df['SB'].astype(float)) / 
            df['PA'].astype(float).replace(0, 1) * 100
        ) + (df['AVG'].astype(float) * 100)
        
        return self._process_daily_multipliers(df, target_date)

    def get_daily_projections(self, target_date: str):
        # 1. Base Roster and Season-long Projections
        hitters = self.enricher.enrich_roster()
        hitters = hitters.dropna(subset=['Score'])
        
        # 2. Map multipliers using the shared logic
        return self._process_daily_multipliers(hitters, target_date)

    def _process_daily_multipliers(self, hitters, target_date):
        matchups = self.harvester.get_daily_matchups(target_date)
        is_today = target_date == datetime.now().strftime("%Y-%m-%d")
        weather_report = self.weather.get_weather_report() if is_today else {}
        
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        year = dt.year
        weight_current = self._get_recency_weight(target_date) if year == 2026 else 0.0
        
        daily_scores = []
        is_starting = []
        breakdowns = []
        opponents = []
        sp_xeras = []
        warnings = []
        game_times = []
        is_opener_list = []
        
        teams_playing = matchups.get('_teams_playing', {})
        
        for _, row in hitters.iterrows():
            player_name = row['Name']
            team_abb = row.get('Team')
            
            # Use name-based lookup with team info to ensure correct ID (disambiguates Max Muncy, etc)
            mlb_id = self.harvester.get_mlb_id(player_name, target_year=year, team_abb=team_abb)
            
            daily_score = 0.0
            starting = False
            breakdown = []
            opponent = "N/A"
            sp_xera = "-"
            warning = ""
            game_time = None
            is_opener = False
            
            # Check for Injury status from Ottoneu
            if row.get('Injured') == True:
                daily_scores.append(0.0)
                is_starting.append(False)
                breakdowns.append("IL (Injured)")
                opponents.append("N/A")
                sp_xeras.append("-")
                warnings.append("🚨 INJURED (IL)")
                game_times.append(None)
                is_opener_list.append(False)
                continue

            # Check for Active Roster status (Minors check)
            if team_abb in teams_playing:
                team_data = teams_playing[team_abb]
                active_roster = team_data.get('active_roster', set())
                
                # If they have an MLB ID, check if they are in the active roster
                # We skip this if they are already confirmed in the boxscore (mlb_id in matchups)
                if mlb_id and mlb_id not in matchups and mlb_id not in active_roster:
                    daily_scores.append(0.0)
                    is_starting.append(False)
                    breakdowns.append(f"In Minors (Not on Active Roster for {team_abb})")
                    opponents.append("N/A")
                    sp_xeras.append("-")
                    warnings.append("🚨 MINORS")
                    game_times.append(None)
                    is_opener_list.append(False)
                    continue

            matchup = None
            if mlb_id and mlb_id in matchups:
                matchup = matchups[mlb_id]
            elif team_abb in teams_playing:
                # Team is playing, but player not in boxscore yet (Lineup Pending)
                team_data = teams_playing[team_abb]
                
                # Check for rainouts / postponements
                if team_data.get('is_postponed'):
                    daily_scores.append(0.0)
                    is_starting.append(False)
                    breakdowns.append("RAINOUT (Postponed)")
                    opponents.append(team_data.get('opposing_sp_name', 'N/A'))
                    sp_xeras.append("-")
                    warnings.append("🚨 RAINOUT / POSTPONED")
                    game_times.append(team_data.get('game_time'))
                    is_opener_list.append(False)
                    continue

                if not team_data['has_lineup']:
                    # Look up historical order if possible
                    last_order = self.harvester.get_last_starting_order(mlb_id, year=year)
                    matchup = {
                        'is_starting': True,
                        'batting_order': f"{last_order}00", 
                        'is_pending': True,
                        'opposing_sp_name': team_data['opposing_sp_name'],
                        'opposing_sp_id': team_data['opposing_sp_id'],
                        'opposing_c_id': team_data.get('opposing_c_id'),
                        'venue_name': team_data['venue_name'],
                        'home_team_abb': team_data['home_team_abb'],
                        'is_home': team_data['is_home'],
                        'game_status': team_data['game_status'],
                        'game_time': team_data.get('game_time')
                    }

            if matchup:
                game_time = matchup.get('game_time')
                
                # Double check for rainouts / postponements
                if matchup.get('is_postponed'):
                    daily_scores.append(0.0)
                    is_starting.append(False)
                    breakdowns.append("RAINOUT (Postponed)")
                    opponents.append(matchup.get('opposing_sp_name', 'N/A'))
                    sp_xeras.append("-")
                    warnings.append("🚨 RAINOUT / POSTPONED")
                    game_times.append(game_time)
                    is_opener_list.append(False)
                    continue

                # We now calculate score/opponent for anyone with a matchup (even bench)
                # but only mark 'starting' for those in the actual lineup
                if matchup.get('is_pending'):
                    starting = True
                    order_val = int(matchup.get('batting_order', '5')[0])
                    breakdown.append(f"Lineup Pending (Assumed #{order_val})")
                elif matchup.get('is_starting'):
                    starting = True
                else:
                    # Bench Assumption for comparison (Assume middle of order)
                    breakdown.append("Bench Assumption (Assumed #5)")

                base_score = row['Score']
                multiplier = 1.0
                
                breakdown.append(f"Base: {base_score:.2f}")
                
                if weight_current > 0:
                    breakdown.append(f"Recency: {int(weight_current*100)}%")
                
                # 1. Venue
                venue = matchup.get('venue_name', '')
                park_multiplier = get_park_multiplier(venue)
                if park_multiplier != 1.0:
                    multiplier *= park_multiplier
                    diff = int((park_multiplier - 1.0) * 100)
                    if diff != 0:
                        breakdown.append(f"Park: {diff:+}%")
                
                # 2. Opposing Pitcher
                sp_id = matchup.get('opposing_sp_id')
                if sp_id:
                    sp_data = self.harvester.get_pitcher_data(sp_id, year=year, weight_current=weight_current)
                    
                    # Use SIERA as the primary skill metric if available, then xERA, then ERA
                    pitcher_skill = sp_data.get('SIERA', sp_data.get('xera', sp_data.get('era', 4.0)))
                    sp_xera = f"{pitcher_skill:.2f}"
                    
                    opp_name = matchup.get('opposing_sp_name', 'Unknown')
                    opponent = f"{opp_name} ({sp_data['hand']})"
                    
                    era_factor = 1.0 + ((pitcher_skill - 4.0) / 4.0)
                    era_factor = max(0.7, min(1.3, era_factor))
                    multiplier *= era_factor
                    
                    diff = int((era_factor - 1.0) * 100)
                    if diff != 0:
                        breakdown.append(f"SP Skill: {diff:+}%")
                    
                    # Platoon
                    batter_hand_data = self.harvester.get_batter_data(mlb_id)
                    b_hand = batter_hand_data['hand']
                    p_hand = sp_data['hand']
                    
                    if b_hand == 'S':
                        multiplier *= 1.05
                        breakdown.append("Switch: +5%")
                    elif b_hand != p_hand:
                        multiplier *= 1.10
                        breakdown.append("Platoon: +10%")
                    else:
                        if b_hand == 'L':
                            multiplier *= 0.85
                            breakdown.append("Platoon (L/L): -15%")
                        else:
                            multiplier *= 0.95
                            breakdown.append("Platoon (R/R): -5%")

                    # 3. BvP
                    bvp = self.harvester.get_bvp_data(mlb_id, sp_id)
                    if bvp and bvp['pa'] >= 5:
                        ops = bvp['ops']
                        if ops > 1.000:
                            multiplier *= 1.15
                            breakdown.append(f"BvP Elite ({bvp['pa']} PA): +15%")
                        elif ops > 0.850:
                            multiplier *= 1.05
                            breakdown.append(f"BvP Good ({bvp['pa']} PA): +5%")
                        elif ops < 0.500:
                            multiplier *= 0.85
                            breakdown.append(f"BvP Poor ({bvp['pa']} PA): -15%")
                        elif ops < 0.650:
                            multiplier *= 0.95
                            breakdown.append(f"BvP Weak ({bvp['pa']} PA): -5%")

                    # 4. Basestealing Environment (Tiered)
                    sprint_speed = self.defense.get_sprint_speed(mlb_id)
                    
                    tier_mult = 0.0
                    if sprint_speed > 28.5:
                        tier_mult = 1.0 # Full impact for Elite
                    elif sprint_speed >= 27.5:
                        tier_mult = 0.5 # Half impact for Aggressive
                        
                    if tier_mult > 0:
                        sb_env_mult = 1.0
                        sb_breakdown = []
                        
                        # Catcher Pop Time (Deterrent Factor - Max 5%)
                        c_id = matchup.get('opposing_c_id')
                        if c_id:
                            pop_time = self.defense.get_pop_time(c_id)
                            if pop_time > 2.00:
                                boost = 1.0 + (0.05 * tier_mult)
                                sb_env_mult *= boost
                                sb_breakdown.append(f"Slow Catcher ({pop_time}s): +{((boost-1)*100):.1f}%")
                            elif pop_time < 1.90:
                                penalty = 1.0 - (0.05 * tier_mult)
                                sb_env_mult *= penalty
                                sb_breakdown.append(f"Elite Catcher ({pop_time}s): -{((1-penalty)*100):.1f}%")
                        
                        # Pitcher SB Rate (Primary Factor - Max 10%)
                        sb_rate = self.defense.get_pitcher_sb_rate(sp_id, year=year)
                        if sb_rate > 0.85:
                            boost = 1.0 + (0.10 * tier_mult)
                            sb_env_mult *= boost
                            sb_breakdown.append(f"Slow SP Delivery ({int(sb_rate*100)}% SB): +{int((boost-1)*100)}%")
                        elif sb_rate < 0.65:
                            penalty = 1.0 - (0.10 * tier_mult)
                            sb_env_mult *= penalty
                            sb_breakdown.append(f"Elite Hold-on SP ({int(sb_rate*100)}% SB): -{int((1-penalty)*100)}%")
                            
                        if sb_env_mult != 1.0:
                            multiplier *= sb_env_mult
                            breakdown.append(", ".join(sb_breakdown))

                # 5. Batting Order Context
                order_str = matchup.get('batting_order', '-')
                if order_str == '-' and not matchup.get('is_starting') and not matchup.get('is_pending'):
                    multiplier *= 1.05
                elif order_str and order_str != '-' and len(order_str) >= 1:
                    order_val = int(order_str[0])
                    order_multiplier = 1.0
                    if order_val == 1: order_multiplier = 1.15
                    elif order_val == 2: order_multiplier = 1.12
                    elif order_val == 3 or order_val == 4: order_multiplier = 1.10
                    elif order_val == 5: order_multiplier = 1.05
                    elif order_val == 6: order_multiplier = 1.00
                    elif order_val == 7: order_multiplier = 0.95
                    elif order_val == 8: order_multiplier = 0.90
                    elif order_val == 9: order_multiplier = 0.85
                    
                    multiplier *= order_multiplier
                    diff = int((order_multiplier - 1.0) * 100)
                    if diff != 0:
                        breakdown.append(f"Order #{order_val}: {diff:+}%")

                # StatCast (Blended)
                sc_hitter = self.harvester.statcast.get_blended_hitter_stats(mlb_id, weight_current=weight_current)
                is_superstar = False
                if sc_hitter is not None:
                    xwoba = float(sc_hitter.get('xwOBA', 0))
                    if xwoba > 0.400:
                        is_superstar = True 
                        multiplier *= 1.10
                        breakdown.append("xwOBA Elite: +10%")
                    elif xwoba > 0.370:
                        multiplier *= 1.05
                        breakdown.append("xwOBA Good: +5%")
                    
                    barrel_pct = float(sc_hitter.get('Barrel%', 0))
                    if barrel_pct > 15.0:
                        multiplier *= 1.05
                        breakdown.append("Barrel: +5%")

                daily_score = base_score * multiplier
                if is_superstar:
                    daily_score = max(daily_score, base_score * 0.85)

                # 5. Weather
                home_abb = matchup.get('home_team_abb')
                if home_abb in weather_report:
                    w = weather_report[home_abb]
                    if not w['is_dome']:
                        if w['wind_dir'] == "Out" and w['wind_speed'] >= 10:
                            boost = 1.05 if w['wind_speed'] < 20 else 1.10
                            multiplier *= boost
                            breakdown.append(f"Wind Out: +{int((boost-1)*100)}%")
                        elif w['wind_dir'] == "In" and w['wind_speed'] >= 10:
                            penalty = 0.95 if w['wind_speed'] < 20 else 0.90
                            multiplier *= penalty
                            breakdown.append(f"Wind In: -{int((1-penalty)*100)}%")
                        
                        if w['rain_risk'] >= 60:
                            warning = f"🚨 HIGH RAIN RISK ({w['rain_risk']}%)"
                        elif w['rain_risk'] >= 30:
                            warning = f"⚠️ Rain Risk ({w['rain_risk']}%)"

                if not starting:
                    daily_score = 0.0
                    breakdown.append("Not Starting: -100%")
                else:
                    daily_score = base_score * multiplier
                    if is_superstar:
                        daily_score = max(daily_score, base_score * 0.85)
            daily_scores.append(daily_score)
            is_starting.append(starting)
            breakdowns.append(", ".join(breakdown) if breakdown else "Base")
            opponents.append(opponent)
            sp_xeras.append(sp_xera)
            warnings.append(warning)
            game_times.append(game_time)
            is_opener_list.append(is_opener)
            
        hitters['DailyScore'] = daily_scores
        hitters['IsStarting'] = is_starting
        hitters['Breakdown'] = breakdowns
        hitters['Opponent'] = opponents
        hitters['SP_xERA'] = sp_xeras
        hitters['Warning'] = warnings
        hitters['GameTime'] = game_times
        hitters['IsOpener'] = is_opener_list
        
        return hitters.copy()

if __name__ == "__main__":
    engine = DailyEngine()
    test_date = "2024-06-15"
    projections = engine.get_daily_projections(test_date)
    print(projections[['Name', 'POS', 'DailyScore', 'Opponent']].sort_values(by='DailyScore', ascending=False).head(10))
