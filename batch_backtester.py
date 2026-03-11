import random
from datetime import datetime, timedelta
from backtester import Backtester
import pandas as pd
from tabulate import tabulate
import sys

class BatchBacktester:
    def __init__(self):
        self.backtester = Backtester()

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

        print("\n\n=== BATCH BACKTEST SUMMARY (2025) ===")
        df = pd.DataFrame(results)
        
        summary = {
            'Metric': ['Runs', 'Home Runs', 'RBIs', 'Stolen Bases', 'Batting Avg'],
            'Started Total': [df['S_R'].sum(), df['S_HR'].sum(), df['S_RBI'].sum(), df['S_SB'].sum(), df['S_AVG'].mean()],
            'Benched Total': [df['B_R'].sum(), df['B_HR'].sum(), df['B_RBI'].sum(), df['B_SB'].sum(), df['B_AVG'].mean()],
            'Success Rate': [
                f"{(df['S_R'].sum() / (df['S_R'].sum() + df['B_R'].sum()) * 100):.1f}%",
                f"{(df['S_HR'].sum() / (df['S_HR'].sum() + df['B_HR'].sum()) * 100):.1f}%",
                f"{(df['S_RBI'].sum() / (df['S_RBI'].sum() + df['B_RBI'].sum()) * 100):.1f}%",
                f"{(df['S_SB'].sum() / (df['S_SB'].sum() + df['B_SB'].sum()) * 100):.1f}%",
                "N/A"
            ]
        }
        
        print(tabulate(summary, headers='keys', tablefmt='grid'))
        print(f"\nAverage Slots Filled: {df['Slots_Filled'].mean():.1f} / 13")
        print(f"Total Games Analyzed: {len(df)}")

if __name__ == "__main__":
    random.seed(42) # For reproducibility
    batch = BatchBacktester()
    batch.run_batch(50)
