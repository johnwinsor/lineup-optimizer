import random
from datetime import datetime, timedelta
from backtester import Backtester
import pandas as pd
import sys
from display_utils import print_header, display_dataframe, print_section

class BatchBacktester:
    def __init__(self, projection_system="steamer"):
        self.backtester = Backtester(projection_system=projection_system)
        self.projection_system = projection_system

    def get_random_dates(self, count=50):
        # 2025 Regular Season: March 27 to Sept 28
        start_date = datetime(2025, 3, 27)
        end_date = datetime(2025, 9, 28)
        
        delta = end_date - start_date
        all_dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
        return [d.strftime("%Y-%m-%d") for d in random.sample(all_dates, count)]

    def run_batch(self, count=50):
        dates = self.get_random_dates(count)
        results = []
        
        print_header(f"Zebras Batch Backtester [{self.projection_system.upper()}]", "2025 Simulation")
        print(f"🚀 Starting Batch Backtest of {count} random dates from 2025...")
        
        for i, date in enumerate(dates):
            # Print progress without cluttering
            sys.stdout.write(f"\rProcessing {i+1}/{count}: {date}...")
            sys.stdout.flush()
            
            try:
                # We need to capture the results without printing the full tables
                # I'll modify the backtester logic slightly for batch use
                lineup = self.backtester.optimizer.optimize_lineup(target_date=date)
                actuals = self.backtester.harvester.get_actual_boxscore_stats(date)
                
                if lineup is None or lineup.empty:
                    continue

                # Score Started
                s_r = s_hr = s_rbi = s_sb = s_h = s_ab = 0
                for _, row in lineup.iterrows():
                    mlb_id = self.backtester.harvester.get_mlb_id(row['Player'], target_year=2025)
                    if mlb_id and mlb_id in actuals:
                        p = actuals[mlb_id]
                        s_r += p['R']; s_hr += p['HR']; s_rbi += p['RBI']; s_sb += p['SB']; s_h += p['H']; s_ab += p['AB']

                # Score Bench (Active only)
                b_r = b_hr = b_rbi = b_sb = b_h = b_ab = 0
                full_roster = self.backtester.optimizer.enricher.enrich_roster()
                started_names = set(lineup['Player'].tolist())
                matchups = self.backtester.harvester.get_daily_matchups(date)
                
                for _, row in full_roster.iterrows():
                    if row['Name'] in started_names: continue
                    mlb_id = self.backtester.harvester.get_mlb_id(row['Name'], target_year=2025)
                    if mlb_id and mlb_id in matchups and matchups[mlb_id]['is_starting']:
                        if mlb_id in actuals:
                            p = actuals[mlb_id]
                            b_r += p['R']; b_hr += p['HR']; b_rbi += p['RBI']; b_sb += p['SB']; b_h += p['H']; b_ab += p['AB']

                results.append({
                    'Date': date,
                    'S_R': s_r, 'S_HR': s_hr, 'S_RBI': s_rbi, 'S_SB': s_sb, 'S_AVG': (s_h/s_ab) if s_ab > 0 else 0,
                    'B_R': b_r, 'B_HR': b_hr, 'B_RBI': b_rbi, 'B_SB': b_sb, 'B_AVG': (b_h/b_ab) if b_ab > 0 else 0,
                    'Slots_Filled': len(lineup)
                })
            except Exception:
                continue

        print("\n")
        df = pd.DataFrame(results)
        
        summary_data = [
            {'Metric': 'Runs', 'Started': df['S_R'].sum(), 'Benched': df['B_R'].sum(), 'Success Rate': f"{(df['S_R'].sum() / (df['S_R'].sum() + df['B_R'].sum()) * 100):.1f}%"},
            {'Metric': 'Home Runs', 'Started': df['S_HR'].sum(), 'Benched': df['B_HR'].sum(), 'Success Rate': f"{(df['S_HR'].sum() / (df['S_HR'].sum() + df['B_HR'].sum()) * 100):.1f}%"},
            {'Metric': 'RBIs', 'Started': df['S_RBI'].sum(), 'Benched': df['B_RBI'].sum(), 'Success Rate': f"{(df['S_RBI'].sum() / (df['S_RBI'].sum() + df['B_RBI'].sum()) * 100):.1f}%"},
            {'Metric': 'Stolen Bases', 'Started': df['S_SB'].sum(), 'Benched': df['B_SB'].sum(), 'Success Rate': f"{(df['S_SB'].sum() / (df['S_SB'].sum() + df['B_SB'].sum()) * 100):.1f}%"},
            {'Metric': 'Batting Avg', 'Started': f"{df['S_AVG'].mean():.3f}", 'Benched': f"{df['B_AVG'].mean():.3f}", 'Success Rate': 'N/A'}
        ]
        
        display_dataframe(pd.DataFrame(summary_data), title="BATCH BACKTEST SUMMARY (2025)")
        print(f"\n[bold white]Average Slots Filled:[/bold white] [bold cyan]{df['Slots_Filled'].mean():.1f} / 13[/bold cyan]")
        print(f"[bold white]Total Games Analyzed:[/bold white] [bold cyan]{len(df)}[/bold cyan]")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch backtest the Ottoneu Lineup Optimizer.")
    parser.add_argument("--count", type=int, default=50, help="Number of random dates to test (default: 50)")
    parser.add_argument("--projection", type=str, default="steamer", help="Projection system (steamer, atc, thebat)")
    
    args = parser.parse_args()
    
    random.seed(42) # For reproducibility
    batch = BatchBacktester(projection_system=args.projection)
    batch.run_batch(args.count)
