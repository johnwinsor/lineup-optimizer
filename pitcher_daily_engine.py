import pandas as pd
from gameday_harvester import GameDayHarvester
from pitcher_enricher import PitcherEnricher
from enricher import OttoneuEnricher
from datetime import datetime
from park_factors import get_park_multiplier
from weather_harvester import WeatherHarvester
import config as C


class PitcherDailyEngine:
    def __init__(self, league_id=1077, team_id=7582, projection_system="steamer"):
        self.enricher = PitcherEnricher(league_id, team_id, projection_system=projection_system)
        self.hitter_enricher = OttoneuEnricher(league_id, team_id, projection_system=projection_system)
        self.harvester = GameDayHarvester.get_instance()
        self.weather = WeatherHarvester()
        self.league_id = league_id
        self.team_id = team_id

    def get_opposing_lineup_power(self, team_abb, hitter_projections):
        """Returns the top-9 projected hitters for a team by baseline score."""
        if 'Score' not in hitter_projections.columns:
            hitter_projections['Score'] = (
                (hitter_projections['R'].astype(float) +
                 hitter_projections['HR'].astype(float) +
                 hitter_projections['RBI'].astype(float) +
                 hitter_projections['SB'].astype(float)) /
                hitter_projections['PA'].astype(float).replace(0, 1) * 100
            ) + (hitter_projections['AVG'].astype(float) * 100)

        team_pool = hitter_projections[hitter_projections['Team'] == team_abb].copy()
        if team_pool.empty:
            return []

        probable = team_pool.sort_values(by='PA', ascending=False).head(15)
        probable = probable.sort_values(by='Score', ascending=False).head(9)
        return probable['xMLBAMID'].tolist()

    def get_daily_projections(self, target_date: str):
        pitchers = self.enricher.enrich_roster()
        hitter_projections = self.hitter_enricher.fetch_projections()
        matchups = self.harvester.get_daily_matchups(target_date)
        starting_map = matchups.get('_starting_pitchers', {})

        dt = datetime.strptime(target_date, "%Y-%m-%d")
        year = dt.year
        current_year = datetime.now().year

        is_today = target_date == datetime.now().strftime("%Y-%m-%d")
        weather_report = self.weather.get_weather_report() if is_today else {}
        weight_current = C.get_recency_weight(target_date) if year >= current_year else 0.0

        daily_scores, is_starting, breakdowns = [], [], []
        opponents, warnings, game_times, is_opener_list = [], [], [], []

        for _, row in pitchers.iterrows():
            player_name = row['Name']
            mlb_id = row.get('xMLBAMID')
            fg_id = row.get('FGID')
            if pd.isna(mlb_id) or not mlb_id:
                mlb_id = self.harvester.get_mlb_id(player_name, target_year=year, fg_id=fg_id)
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

                if m.get('is_postponed'):
                    daily_scores.append(0.0); is_starting.append(False)
                    breakdowns.append("RAINOUT (Postponed)"); opponents.append(opponent)
                    warnings.append("🚨 RAINOUT / POSTPONED")
                    game_times.append(game_time); is_opener_list.append(False)
                    continue

                base_score = row['Score']
                multiplier = 1.0
                breakdown.append(f"Base: {base_score:.2f}")

                # Park factor (inverse for pitchers — pitcher-friendly parks boost score)
                park_mult = get_park_multiplier(m['venue_name'])
                pitcher_park_mult = 2.0 - park_mult
                if pitcher_park_mult != 1.0:
                    multiplier *= pitcher_park_mult
                    diff = int((pitcher_park_mult - 1.0) * 100)
                    breakdown.append(f"Park: {diff:+}%")

                # Weather
                home_abb = m['home_team_abb']
                if home_abb in weather_report:
                    w = weather_report[home_abb]
                    if not w['is_dome']:
                        if w['wind_dir'] == "In" and w['wind_speed'] >= C.WIND_SPEED_MODERATE:
                            boost = C.WIND_OUT_STRONG_MULT if w['wind_speed'] >= C.WIND_SPEED_STRONG else C.WIND_OUT_MODERATE_MULT
                            multiplier *= boost
                            breakdown.append(f"Wind In: +{int((boost - 1) * 100)}%")
                        elif w['wind_dir'] == "Out" and w['wind_speed'] >= C.WIND_SPEED_MODERATE:
                            penalty = C.WIND_IN_STRONG_MULT if w['wind_speed'] >= C.WIND_SPEED_STRONG else C.WIND_IN_MODERATE_MULT
                            multiplier *= penalty
                            breakdown.append(f"Wind Out: -{int((1 - penalty) * 100)}%")

                        if w.get('temp', 0) > C.HEAT_THRESHOLD:
                            multiplier *= C.HEAT_PENALTY
                            breakdown.append(f"Heat (>{C.HEAT_THRESHOLD}F): {int((C.HEAT_PENALTY - 1) * 100)}%")

                        if w['rain_risk'] >= C.RAIN_HIGH_RISK_PCT:
                            warning = f"🚨 HIGH RAIN RISK ({w['rain_risk']}%)"
                        elif w['rain_risk'] >= C.RAIN_MODERATE_RISK_PCT:
                            warning = f"⚠️ Rain Risk ({w['rain_risk']}%)"

                # StatCast skill delta — projected ERA vs blended xERA
                sp_data = self.harvester.get_pitcher_data(mlb_id, year=year, weight_current=weight_current)
                xera = sp_data.get('xera')
                proj_era = row.get('ERA_y')
                if xera and proj_era:
                    delta = float(proj_era) - float(xera)
                    sc_mult = 1.0 + (delta * C.PITCHER_ERA_SKILL_WEIGHT)
                    sc_mult = max(C.PITCHER_STAT_MULT_MIN, min(C.PITCHER_STAT_MULT_MAX, sc_mult))
                    multiplier *= sc_mult
                    diff_pct = int((sc_mult - 1.0) * 100)
                    if diff_pct != 0:
                        breakdown.append(f"Statcast (xERA {float(xera):.2f}): {diff_pct:+}%")

                # Aggregate BvP — opposing projected top-9
                opp_team = m['opposing_team']
                opp_ids = self.get_opposing_lineup_power(opp_team, hitter_projections)
                if opp_ids:
                    bvp_list = []
                    for b_id in opp_ids:
                        bvp = self.harvester.get_bvp_data(b_id, mlb_id)
                        if bvp and bvp['pa'] >= C.AGG_BVP_MIN_PA:
                            bvp_list.append(bvp['ops'])
                    if bvp_list:
                        avg_ops = sum(bvp_list) / len(bvp_list)
                        if avg_ops < C.AGG_BVP_GOOD_OPS:
                            multiplier *= C.AGG_BVP_GOOD_MULT
                            breakdown.append(f"Agg BvP (OPS {avg_ops:.3f}): +{int((C.AGG_BVP_GOOD_MULT - 1) * 100)}%")
                        elif avg_ops > C.AGG_BVP_BAD_OPS:
                            multiplier *= C.AGG_BVP_BAD_MULT
                            breakdown.append(f"Agg BvP (OPS {avg_ops:.3f}): {int((C.AGG_BVP_BAD_MULT - 1) * 100)}%")

                # Opponent power — aggregate efficiency of opposing top-9
                opp_pool = hitter_projections[hitter_projections['Team'] == opp_team]
                if not opp_pool.empty:
                    opp_top9 = opp_pool.sort_values(by='Score', ascending=False).head(9)
                    avg_opp = opp_top9['Score'].mean()
                    power_factor = 1.0 - ((avg_opp - C.OPP_POWER_NEUTRAL) / 100.0)
                    power_factor = max(C.OPP_POWER_MULT_MIN, min(C.OPP_POWER_MULT_MAX, power_factor))
                    multiplier *= power_factor
                    diff_pct = int((power_factor - 1.0) * 100)
                    if diff_pct != 0:
                        breakdown.append(f"Opp Power ({avg_opp:.1f}): {diff_pct:+}%")

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
