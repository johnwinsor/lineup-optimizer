from daily_engine import DailyEngine
from gameday_harvester import GameDayHarvester
import pandas as pd
from tabulate import tabulate
from datetime import datetime
import argparse

class FreeAgentBacktester:
    def __init__(self, league_id=1077):
        self.engine = DailyEngine(league_id)
        self.harvester = self.engine.harvester

    def run_fa_backtest(self, target_date: str, top_n=20):
        print(f"--- Running Free Agent Audit for {target_date} ---")
        
        # 1. Get and Project Free Agents
        print("Fetching and projecting available Free Agents...")
        fa_hitters = self.engine.get_free_agent_projections(target_date)
        if fa_hitters.empty:
            print("No free agents found or no data available.")
            return

        # 2. Filter for only starters
        starters = fa_hitters[fa_hitters['IsStarting'] == True].copy()
        if starters.empty:
            print("No free agents were in MLB starting lineups today.")
            return

        # 3. Fetch Actual Results
        actuals = self.harvester.get_actual_boxscore_stats(target_date)
        ev_stats = self.harvester.get_statcast_ev_stats(target_date)
        
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        year = dt.year

        # 4. Build Results Table
        fa_results = []
        for _, row in starters.iterrows():
            mlb_id = row['xMLBAMID']
            p_stats = {'R': 0, 'HR': 0, 'RBI': 0, 'SB': 0, 'AB': 0, 'H': 0, 'SO': 0, 'CS': 0}
            if mlb_id and mlb_id in actuals:
                p_stats = actuals[mlb_id]
            
            ev = ev_stats.get(mlb_id, {'avg_ev': 0, 'max_ev': 0})
            
            fa_results.append({
                'Player': row['Name'],
                'POS': row['POS'],
                'Team': row['Team'],
                'Opponent': row['Opponent'],
                'Proj': f"{row['DailyScore']:.2f}",
                'Actual': f"{p_stats['H']}/{p_stats['AB']}, {p_stats['HR']} HR, {p_stats['SB']} SB",
                'SO': p_stats['SO'],
                'SB/CS': f"{p_stats['SB']}/{p_stats['CS']}",
                'EV (Avg/Max)': f"{ev['avg_ev']:.1f}/{ev['max_ev']:.1f}",
                'Breakdown': row['Breakdown']
            })

        df = pd.DataFrame(fa_results)
        # Rank by Actual Production (HR, SB, H) then Proj
        df['Prod_Score'] = df['Actual'].apply(lambda x: sum([int(s.split()[0]) for s in x.split(',') if 'HR' in s or 'SB' in s]))
        df['H'] = df['Actual'].apply(lambda x: int(x.split('/')[0]))
        
        df_ranked = df.sort_values(by=['Prod_Score', 'H', 'Proj'], ascending=False).head(top_n)

        print(f"\n=== TOP {top_n} FREE AGENT PERFORMANCES ===")
        print(tabulate(df_ranked[['Player', 'POS', 'Opponent', 'Proj', 'Actual', 'SO', 'SB/CS', 'EV (Avg/Max)']], 
                       headers='keys', tablefmt='grid', showindex=False))

        # Narrative
        print("\n=== MARKET GEM NARRATIVE ===")
        if not df_ranked.empty:
            gem = df_ranked.iloc[0]
            if gem['Prod_Score'] > 0 or gem['H'] > 0:
                print(f"Market Gem found: **{gem['Player']}** produced {gem['Actual']} against {gem['Opponent']}. "
                      f"He was projected at {gem['Proj']} based on: {gem['Breakdown']}.")
            else:
                print("The waiver wire was quiet today. No significant free agent breakouts detected.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest Free Agent performance for a specific date.")
    parser.add_argument("date", nargs="?", default="2024-06-15", help="The date to backtest in YYYY-MM-DD format.")
    parser.add_argument("--top", type=int, default=20, help="Number of players to show.")
    
    args = parser.parse_args()
    
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'.")
        exit(1)

    tester = FreeAgentBacktester()
    tester.run_fa_backtest(args.date, top_n=args.top)
