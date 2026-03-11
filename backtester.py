from optimizer import OttoneuOptimizer
from gameday_harvester import GameDayHarvester
import pandas as pd
from tabulate import tabulate
from datetime import datetime

class Backtester:
    def __init__(self, league_id=1077, team_id=7582):
        self.optimizer = OttoneuOptimizer(league_id, team_id)
        self.harvester = self.optimizer.daily_engine.harvester

    def run_backtest(self, target_date: str):
        print(f"--- Running Backtest for {target_date} ---")
        
        # 1. Get All Players and their Daily Status
        print("1. Analyzing Roster and Matchups...")
        # Get all hitters with daily data
        all_hitters = self.optimizer.daily_engine.get_daily_projections(target_date)
        # We also need the ones that were NOT starting to explain why they sat
        full_roster = self.optimizer.enricher.enrich_roster()
        matchups = self.harvester.get_daily_matchups(target_date)
        
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        year = dt.year

        # 2. Get Predicted Optimal Lineup
        lineup = self.optimizer.optimize_lineup(target_date=target_date)
        
        # 3. Fetch Actual Results
        actuals = self.harvester.get_actual_boxscore_stats(target_date)
        ev_stats = self.harvester.get_statcast_ev_stats(target_date)

        # Build Started Table
        started_data = []
        total_r = total_hr = total_rbi = total_sb = total_h = total_ab = 0
        
        if lineup is not None and not lineup.empty:
            for _, row in lineup.iterrows():
                player_name = row['Player']
                mlb_id = self.harvester.get_mlb_id(player_name, target_year=year)
                matchup = matchups.get(mlb_id, {})
                sp_id = matchup.get('opposing_sp_id')
                sp_data = self.harvester.get_pitcher_data(sp_id, year=year) if sp_id else {'hand': '?', 'era': 0, 'xera': 0}
                
                p_stats = {'R': 0, 'HR': 0, 'RBI': 0, 'SB': 0, 'AB': 0, 'H': 0, 'SO': 0, 'CS': 0}
                if mlb_id and mlb_id in actuals:
                    p_stats = actuals[mlb_id]
                
                ev = ev_stats.get(mlb_id, {'avg_ev': 0, 'max_ev': 0})
                
                started_data.append({
                    'Slot': row['Slot'],
                    'Player': player_name,
                    'Opponent': f"{matchup.get('opposing_sp_name')} ({sp_data['hand']}, {sp_data.get('xera', sp_data['era']):.2f})",
                    'Proj': f"{row['Score']:.2f}",
                    'Actual': f"{p_stats['H']}/{p_stats['AB']}, {p_stats['HR']} HR, {p_stats['SB']} SB",
                    'SO': f"{p_stats['SO']}",
                    'SB/CS': f"{p_stats['SB']}/{p_stats['CS']}",
                    'EV (Avg/Max)': f"{ev['avg_ev']:.1f}/{ev['max_ev']:.1f}",
                    'Breakdown': row.get('Breakdown', 'Base')
                })
                
                total_r += p_stats['R']
                total_hr += p_stats['HR']
                total_rbi += p_stats['RBI']
                total_sb += p_stats['SB']
                total_ab += p_stats['AB']
                total_h += p_stats['H']

        # Build Sat Table
        sat_data = []
        started_names = set(lineup['Player'].tolist()) if lineup is not None else set()
        total_sat_r = total_sat_hr = total_sat_rbi = total_sat_sb = total_sat_h = total_sat_ab = 0
        
        for _, row in full_roster.iterrows():
            name = row['Name']
            if name in started_names:
                continue
                
            mlb_id = self.harvester.get_mlb_id(name, target_year=year)
            
            p_stats = {'R': 0, 'HR': 0, 'RBI': 0, 'SB': 0, 'AB': 0, 'H': 0, 'SO': 0, 'CS': 0}
            if mlb_id and mlb_id in actuals:
                p_stats = actuals[mlb_id]
            
            ev = ev_stats.get(mlb_id, {'avg_ev': 0, 'max_ev': 0})
                
            # Determine Why they Sat
            proj_score = 0.0
            min_floor = self.optimizer.min_score
            if not mlb_id or mlb_id not in matchups:
                note = "Team Off-day or No Game Scheduled."
            else:
                matchup = matchups[mlb_id]
                if not matchup['is_starting']:
                    note = "Not in MLB Starting Lineup (Benched/IL/Rest)."
                else:
                    # They were starting in MLB but not picked by our optimizer
                    proj_row = all_hitters[all_hitters['Name'] == name]
                    proj_score = proj_row['DailyScore'].values[0] if not proj_row.empty else 0
                    
                    if proj_score < min_floor:
                        note = f"Benched - Below Zebras Floor ({min_floor})."
                    else:
                        note = f"Benched - Lower projected efficiency than other options."

            sat_data.append({
                'Player': name,
                'POS': row['POS'],
                'Proj': f"{proj_score:.2f}",
                'Actual': f"{p_stats['H']}/{p_stats['AB']}, {p_stats['HR']} HR, {p_stats['SB']} SB",
                'SO': f"{p_stats['SO']}",
                'SB/CS': f"{p_stats['SB']}/{p_stats['CS']}",
                'EV (Avg/Max)': f"{ev['avg_ev']:.1f}/{ev['max_ev']:.1f}",
                'Note': note
            })
            
            total_sat_r += p_stats['R']
            total_sat_hr += p_stats['HR']
            total_sat_rbi += p_stats['RBI']
            total_sat_sb += p_stats['SB']
            total_sat_ab += p_stats['AB']
            total_sat_h += p_stats['H']

        # Print Tables
        print("\n=== LINEUP STARTED ===")
        df_started = pd.DataFrame(started_data)
        if not df_started.empty:
            print(tabulate(df_started[['Slot', 'Player', 'Opponent', 'Proj', 'Actual', 'SO', 'SB/CS', 'EV (Avg/Max)', 'Breakdown']], 
                           headers='keys', tablefmt='grid', showindex=False))
        else:
            print("No players started.")

        print("\n=== PLAYERS SAT ===")
        df_sat = pd.DataFrame(sat_data)
        if not df_sat.empty:
            print(tabulate(df_sat[['Player', 'POS', 'Proj', 'Actual', 'SO', 'SB/CS', 'EV (Avg/Max)', 'Note']], 
                           headers='keys', tablefmt='grid', showindex=False))

        # Totals
        avg = (total_h / total_ab) if total_ab > 0 else 0.0
        print("\n--- Daily Lineup Total Production ---")
        print(f"Runs: {total_r} | HR: {total_hr} | RBI: {total_rbi} | SB: {total_sb} | AVG: {avg:.3f} ({total_h}/{total_ab})")
        
        sat_avg = (total_sat_h / total_sat_ab) if total_sat_ab > 0 else 0.0
        print(f"\n--- Total Production from Benched Players (Opportunity Cost) ---")
        print(f"Runs: {total_sat_r} | HR: {total_sat_hr} | RBI: {total_sat_rbi} | SB: {total_sat_sb} | AVG: {sat_avg:.3f} ({total_sat_h}/{total_sat_ab})")

        # Post-Game Narrative
        print("\n=== POST-GAME ANALYSIS NARRATIVE ===")
        
        # 1. Prediction Win
        # Find player with best HR + SB production in started lineup
        lineup_df = pd.DataFrame(started_data)
        lineup_df['Prod'] = lineup_df['Actual'].apply(lambda x: sum([int(s.split()[0]) for s in x.split(',') if 'HR' in s or 'SB' in s]))
        lineup_df['H'] = lineup_df['Actual'].apply(lambda x: int(x.split('/')[0]))
        
        narrative = ""
        if not lineup_df.empty:
            best_prod = lineup_df.sort_values(by=['Prod', 'H'], ascending=False).iloc[0]
            if best_prod['Prod'] > 0 or best_prod['H'] > 0:
                narrative += f"The Prediction Win: **{best_prod['Player']}** lived up to his {best_prod['Proj']} projection, providing {best_prod['Actual']} against {best_prod['Opponent']}."
            
            # 2. The Flop
            worst_prod = lineup_df.sort_values(by=['Proj'], ascending=False)
            flop = worst_prod[worst_prod['Actual'].str.startswith('0/')].iloc[0] if not worst_prod[worst_prod['Actual'].str.startswith('0/')].empty else None
            if flop is not None:
                narrative += f"\n\nThe Flop: Despite a strong {flop['Proj']} projection, **{flop['Player']}** struggled today, going {flop['Actual'].split(',')[0]}."

        # 3. Bench Hero
        sat_df = pd.DataFrame(sat_data)
        sat_df['H'] = sat_df['Actual'].apply(lambda x: int(x.split('/')[0]) if '/' in x else 0)
        sat_df['HR'] = sat_df['Actual'].apply(lambda x: 1 if '1 HR' in x else (2 if '2 HR' in x else 0))
        
        bench_hero = sat_df.sort_values(by=['HR', 'H'], ascending=False).iloc[0] if not sat_df.empty else None
        if bench_hero is not None and (bench_hero['H'] > 0 or bench_hero['HR'] > 0):
            narrative += f"\n\nThe Bench Hero: We left **{bench_hero['Player']}** on the bench ({bench_hero['Actual']}), which hurt. Note: {bench_hero['Note']}"
        else:
            narrative += "\n\nEfficiency Note: The bench remained quiet today, confirming our start/sit decisions were sound."

        print(narrative if narrative else "No significant statistical anomalies detected for this date.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backtest the Ottoneu Lineup Optimizer for a specific date.")
    parser.add_argument("date", nargs="?", default="2024-06-15", help="The date to backtest in YYYY-MM-DD format (default: 2024-06-15)")
    
    args = parser.parse_args()
    
    # Simple validation
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Please use YYYY-MM-DD.")
        exit(1)

    backtester = Backtester()
    backtester.run_backtest(args.date)
