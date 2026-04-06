import pandas as pd
from gameday_harvester import GameDayHarvester
from enricher import OttoneuEnricher
from defense_harvester import DefenseHarvester
from datetime import datetime
from park_factors import get_park_multiplier
from weather_harvester import WeatherHarvester
import config as C


class DailyEngine:
    def __init__(self, league_id=1077, team_id=7582, projection_system="steamer"):
        self.enricher = OttoneuEnricher(league_id, team_id, projection_system=projection_system)
        self.harvester = GameDayHarvester.get_instance()
        self.weather = WeatherHarvester()
        self.defense = DefenseHarvester()

    def get_daily_projections(self, target_date: str):
        hitters = self.enricher.enrich_roster()
        hitters = hitters.dropna(subset=['Score'])
        return self._process_daily_multipliers(hitters, target_date)

    def _process_daily_multipliers(self, hitters, target_date):
        matchups = self.harvester.get_daily_matchups(target_date)
        is_today = target_date == datetime.now().strftime("%Y-%m-%d")
        weather_report = self.weather.get_weather_report() if is_today else {}

        dt = datetime.strptime(target_date, "%Y-%m-%d")
        year = dt.year
        current_year = datetime.now().year
        weight_current = C.get_recency_weight(target_date) if year >= current_year else 0.0

        # ── ID resolution (roster-driven, projection-system-agnostic) ──────
        # Always resolve via FGID crosswalk → name search → MiLB fallback.
        # xMLBAMID from projections is intentionally ignored here: a player's
        # roster status is a fact about the player, not the projection system.
        player_id_to_mlb = {}
        for idx, row in hitters.iterrows():
            mlb_id = self.harvester.get_mlb_id(
                row['Name'], target_year=year,
                team_abb=row.get('Team'), fg_id=row.get('FGID')
            )
            if mlb_id:
                player_id_to_mlb[idx] = int(mlb_id)

        all_mlb_ids = list(set(int(i) for i in player_id_to_mlb.values()))
        mlb_statuses = self.harvester.get_player_statuses(all_mlb_ids)

        platoon_split_year = year - 1 if year >= current_year else year
        platoon_splits = self.harvester.get_platoon_splits(all_mlb_ids, year=platoon_split_year)

        # ── Per-player scoring loop ─────────────────────────────────────────
        daily_scores, is_starting, breakdowns = [], [], []
        opponents, sp_xeras, warnings, game_times, is_opener_list = [], [], [], [], []

        teams_playing = matchups.get('_teams_playing', {})

        for idx, row in hitters.iterrows():
            player_name = row['Name']
            team_abb = row.get('Team')
            mlb_id = player_id_to_mlb.get(idx)

            daily_score = 0.0
            starting = False
            breakdown = []
            opponent = "N/A"
            sp_xera = "-"
            warning = ""
            game_time = None
            is_opener = False

            # ── 1. Injured (Ottoneu flag) ───────────────────────────────────
            if row.get('Injured') is True:
                daily_scores.append(0.0); is_starting.append(False)
                breakdowns.append("IL (Injured)"); opponents.append("N/A")
                sp_xeras.append("-"); warnings.append("🚨 INJURED (IL)")
                game_times.append(None); is_opener_list.append(False)
                continue

            # ── 2. Minors check — MLB API (authoritative) ──────────────────
            mlb_confirmed_major = False
            if mlb_id:
                lookup_id = int(mlb_id)
                if lookup_id in mlb_statuses:
                    status = mlb_statuses[lookup_id]
                    if status['is_minors']:
                        daily_scores.append(0.0); is_starting.append(False)
                        breakdowns.append(f"In the Minors ({status['team_name']})")
                        opponents.append("N/A"); sp_xeras.append("-")
                        warnings.append("🚨 MINORS")
                        game_times.append(None); is_opener_list.append(False)
                        continue
                    else:
                        mlb_confirmed_major = True

            # ── 2b. Ottoneu IsMinors fallback — only when MLB ID could not be resolved ──
            if not mlb_id and row.get('IsMinors') is True:
                daily_scores.append(0.0); is_starting.append(False)
                breakdowns.append("In Minors (Ottoneu Roster — no MLB ID resolved)")
                opponents.append("N/A"); sp_xeras.append("-")
                warnings.append("🚨 MINORS")
                game_times.append(None); is_opener_list.append(False)
                continue

            # ── 3. Active roster secondary check ───────────────────────────
            if team_abb in teams_playing:
                team_data = teams_playing[team_abb]
                active_roster = team_data.get('active_roster', set())
                if mlb_id and mlb_id not in matchups and mlb_id not in active_roster:
                    if not mlb_confirmed_major:
                        daily_scores.append(0.0); is_starting.append(False)
                        breakdowns.append(f"In Minors (Not on Active Roster for {team_abb})")
                        opponents.append("N/A"); sp_xeras.append("-")
                        warnings.append("🚨 MINORS")
                        game_times.append(None); is_opener_list.append(False)
                        continue

            # ── 4. Resolve matchup ──────────────────────────────────────────
            matchup = None
            if mlb_id and mlb_id in matchups:
                matchup = matchups[mlb_id]
            elif team_abb in teams_playing:
                team_data = teams_playing[team_abb]

                if team_data.get('is_postponed'):
                    daily_scores.append(0.0); is_starting.append(False)
                    breakdowns.append("RAINOUT (Postponed)")
                    opponents.append(team_data.get('opposing_sp_name', 'N/A'))
                    sp_xeras.append("-"); warnings.append("🚨 RAINOUT / POSTPONED")
                    game_times.append(team_data.get('game_time')); is_opener_list.append(False)
                    continue

                if not team_data['has_lineup']:
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
                        'game_time': team_data.get('game_time'),
                        'is_postponed': False,
                    }

            # ── 5. Apply multipliers ────────────────────────────────────────
            if matchup:
                game_time = matchup.get('game_time')

                if matchup.get('is_postponed'):
                    daily_scores.append(0.0); is_starting.append(False)
                    breakdowns.append("RAINOUT (Postponed)")
                    opponents.append(matchup.get('opposing_sp_name', 'N/A'))
                    sp_xeras.append("-"); warnings.append("🚨 RAINOUT / POSTPONED")
                    game_times.append(game_time); is_opener_list.append(False)
                    continue

                if matchup.get('is_pending'):
                    starting = True
                    order_val = int(matchup.get('batting_order', '5')[0])
                    breakdown.append(f"Lineup Pending (Assumed #{order_val})")
                elif matchup.get('is_starting'):
                    starting = True
                else:
                    breakdown.append("Bench Assumption (Assumed #5)")

                base_score = row['Score']
                multiplier = 1.0
                breakdown.append(f"Base: {base_score:.2f}")

                if weight_current > 0:
                    breakdown.append(f"Recency: {int(weight_current * 100)}%")

                # Park factor
                venue = matchup.get('venue_name', '')
                park_mult = get_park_multiplier(venue)
                if park_mult != 1.0:
                    multiplier *= park_mult
                    diff = int((park_mult - 1.0) * 100)
                    if diff != 0:
                        breakdown.append(f"Park: {diff:+}%")

                # Opposing pitcher
                sp_id = matchup.get('opposing_sp_id')
                if sp_id:
                    sp_data = self.harvester.get_pitcher_data(sp_id, year=year, weight_current=weight_current)
                    pitcher_skill = sp_data.get('SIERA', sp_data.get('xera', sp_data.get('era', C.ERA_FACTOR_NEUTRAL)))
                    sp_xera = f"{pitcher_skill:.2f}"
                    opponent = f"{matchup.get('opposing_sp_name', 'Unknown')} ({sp_data['hand']})"

                    era_factor = 1.0 + ((pitcher_skill - C.ERA_FACTOR_NEUTRAL) / C.ERA_FACTOR_NEUTRAL)
                    era_factor = max(C.ERA_FACTOR_MIN, min(C.ERA_FACTOR_MAX, era_factor))
                    multiplier *= era_factor
                    diff = int((era_factor - 1.0) * 100)
                    if diff != 0:
                        breakdown.append(f"SP Skill: {diff:+}%")

                    # Platoon splits
                    b_hand = self.harvester.get_batter_data(mlb_id)['hand']
                    p_hand = sp_data['hand']
                    splits = platoon_splits.get(mlb_id, {})
                    ops_vs_l = splits.get('vs_l')
                    ops_vs_r = splits.get('vs_r')

                    applied_dynamic = False
                    if ops_vs_l and ops_vs_r:
                        relevant_ops = ops_vs_l if p_hand == 'L' else ops_vs_r
                        baseline_ops = (ops_vs_l + ops_vs_r) / 2.0
                        if baseline_ops > 0:
                            platoon_mult = relevant_ops / baseline_ops
                            platoon_mult = max(C.PLATOON_MULT_MIN, min(C.PLATOON_MULT_MAX, platoon_mult))
                            multiplier *= platoon_mult
                            applied_dynamic = True
                            diff = int((platoon_mult - 1.0) * 100)
                            if diff != 0:
                                breakdown.append(f"Dynamic Platoon ({p_hand}): {diff:+}%")
                            else:
                                breakdown.append(f"Neutral Platoon ({p_hand})")

                    if not applied_dynamic:
                        if b_hand == 'S':
                            multiplier *= C.SWITCH_HIT_BONUS
                            breakdown.append(f"Switch: +{int((C.SWITCH_HIT_BONUS - 1) * 100)}%")
                        elif b_hand != p_hand:
                            multiplier *= C.PLATOON_ADVANTAGE_BONUS
                            breakdown.append(f"Platoon: +{int((C.PLATOON_ADVANTAGE_BONUS - 1) * 100)}%")
                        elif b_hand == 'L':
                            multiplier *= C.PLATOON_LL_PENALTY
                            breakdown.append(f"Platoon (L/L): {int((C.PLATOON_LL_PENALTY - 1) * 100)}%")
                        else:
                            multiplier *= C.PLATOON_RR_PENALTY
                            breakdown.append(f"Platoon (R/R): {int((C.PLATOON_RR_PENALTY - 1) * 100)}%")

                    # BvP
                    bvp = self.harvester.get_bvp_data(mlb_id, sp_id)
                    if bvp and bvp['pa'] >= C.BVP_MIN_PA:
                        ops = bvp['ops']
                        if ops > C.BVP_ELITE_OPS:
                            multiplier *= C.BVP_ELITE_MULT
                            breakdown.append(f"BvP Elite ({bvp['pa']} PA): +{int((C.BVP_ELITE_MULT - 1) * 100)}%")
                        elif ops > C.BVP_GOOD_OPS:
                            multiplier *= C.BVP_GOOD_MULT
                            breakdown.append(f"BvP Good ({bvp['pa']} PA): +{int((C.BVP_GOOD_MULT - 1) * 100)}%")
                        elif ops < C.BVP_POOR_OPS:
                            multiplier *= C.BVP_POOR_MULT
                            breakdown.append(f"BvP Poor ({bvp['pa']} PA): {int((C.BVP_POOR_MULT - 1) * 100)}%")
                        elif ops < C.BVP_WEAK_OPS:
                            multiplier *= C.BVP_WEAK_MULT
                            breakdown.append(f"BvP Weak ({bvp['pa']} PA): {int((C.BVP_WEAK_MULT - 1) * 100)}%")

                    # Basestealing environment
                    sprint_speed = self.defense.get_sprint_speed(mlb_id)
                    if sprint_speed > C.SPRINT_SPEED_ELITE:
                        tier_mult = 1.0
                    elif sprint_speed >= C.SPRINT_SPEED_GOOD:
                        tier_mult = 0.5
                    else:
                        tier_mult = 0.0

                    if tier_mult > 0:
                        sb_env_mult = 1.0
                        sb_breakdown = []
                        c_id = matchup.get('opposing_c_id')
                        if c_id:
                            pop_time = self.defense.get_pop_time(c_id)
                            if pop_time > C.CATCHER_POP_SLOW:
                                boost = 1.0 + (C.SB_CATCHER_MULT * tier_mult)
                                sb_env_mult *= boost
                                sb_breakdown.append(f"Slow Catcher ({pop_time}s): +{((boost - 1) * 100):.1f}%")
                            elif pop_time < C.CATCHER_POP_ELITE:
                                penalty = 1.0 - (C.SB_CATCHER_MULT * tier_mult)
                                sb_env_mult *= penalty
                                sb_breakdown.append(f"Elite Catcher ({pop_time}s): -{((1 - penalty) * 100):.1f}%")

                        sb_rate = self.defense.get_pitcher_sb_rate(sp_id, year=year)
                        if sb_rate > C.SB_RATE_SLOW_SP:
                            boost = 1.0 + (C.SB_PITCHER_MULT * tier_mult)
                            sb_env_mult *= boost
                            sb_breakdown.append(f"Slow SP Delivery ({int(sb_rate * 100)}% SB): +{int((boost - 1) * 100)}%")
                        elif sb_rate < C.SB_RATE_HOLD_SP:
                            penalty = 1.0 - (C.SB_PITCHER_MULT * tier_mult)
                            sb_env_mult *= penalty
                            sb_breakdown.append(f"Elite Hold SP ({int(sb_rate * 100)}% SB): -{int((1 - penalty) * 100)}%")

                        if sb_env_mult != 1.0:
                            multiplier *= sb_env_mult
                            breakdown.append(", ".join(sb_breakdown))

                # Batting order
                order_str = matchup.get('batting_order', '-')
                if order_str and order_str != '-' and len(order_str) >= 1:
                    try:
                        order_val = int(order_str[0])
                        order_mult = C.ORDER_MULTIPLIERS.get(order_val, 1.0)
                        multiplier *= order_mult
                        diff = int((order_mult - 1.0) * 100)
                        if diff != 0:
                            breakdown.append(f"Order #{order_val}: {diff:+}%")
                    except (ValueError, IndexError):
                        pass

                # StatCast — informational only; no multiplier applied.
                # xwOBA and Barrel% quality is already embedded in the projection
                # system (Steamer/ATC). Applying a second multiplier double-counts it.
                sc_hitter = self.harvester.statcast.get_blended_hitter_stats(mlb_id, weight_current=weight_current)
                if sc_hitter is not None:
                    xwoba = float(sc_hitter.get('xwOBA', 0))
                    if xwoba > C.XWOBA_ELITE:
                        breakdown.append(f"xwOBA Elite ({xwoba:.3f})")
                    elif xwoba > C.XWOBA_GOOD:
                        breakdown.append(f"xwOBA Good ({xwoba:.3f})")

                # Weather (applied after score so it doesn't compound the superstar floor)
                home_abb = matchup.get('home_team_abb')
                if home_abb in weather_report:
                    w = weather_report[home_abb]
                    if not w['is_dome']:
                        if w['wind_dir'] == "Out" and w['wind_speed'] >= C.WIND_SPEED_MODERATE:
                            boost = C.WIND_OUT_STRONG_MULT if w['wind_speed'] >= C.WIND_SPEED_STRONG else C.WIND_OUT_MODERATE_MULT
                            multiplier *= boost
                            breakdown.append(f"Wind Out: +{int((boost - 1) * 100)}%")
                        elif w['wind_dir'] == "In" and w['wind_speed'] >= C.WIND_SPEED_MODERATE:
                            penalty = C.WIND_IN_STRONG_MULT if w['wind_speed'] >= C.WIND_SPEED_STRONG else C.WIND_IN_MODERATE_MULT
                            multiplier *= penalty
                            breakdown.append(f"Wind In: -{int((1 - penalty) * 100)}%")

                        if w['rain_risk'] >= C.RAIN_HIGH_RISK_PCT:
                            warning = f"🚨 HIGH RAIN RISK ({w['rain_risk']}%)"
                        elif w['rain_risk'] >= C.RAIN_MODERATE_RISK_PCT:
                            warning = f"⚠️ Rain Risk ({w['rain_risk']}%)"

                if not starting:
                    daily_score = 0.0
                    breakdown.append("Not Starting: -100%")
                else:
                    # Cap total multiplier — prevents extreme compounding when
                    # several favorable/unfavorable factors stack simultaneously
                    multiplier = max(C.DAILY_MULT_MIN, min(C.DAILY_MULT_MAX, multiplier))
                    daily_score = base_score * multiplier

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
    test_date = datetime.now().strftime("%Y-%m-%d")
    projections = engine.get_daily_projections(test_date)
    print(projections[['Name', 'POS', 'DailyScore', 'Opponent']].sort_values(by='DailyScore', ascending=False).head(10))
