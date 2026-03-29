from daily_engine import DailyEngine
from gameday_harvester import GameDayHarvester
import pandas as pd
from datetime import datetime
import argparse
from display_utils import print_header, display_dataframe, print_narrative

class FreeAgentBacktester:
    def __init__(self, league_id=1077):
        self.engine = DailyEngine(league_id)
        self.harvester = self.engine.harvester

    def run_fa_backtest(self, target_date: str, top_n=20):
        print_header("Zebras Free Agent Audit", target_date)

        # 1. Get and Project Free Agents
        print("Fetching and projecting available Free Agents...")
        fa_hitters = self.engine.get_free_agent_projections(target_date)
        if fa_hitters.empty:
            print("No free agents found or no data available.")
            return

        # 2. Get Actual Boxscore Stats for FA
        actuals = self.harvester.get_actual_boxscore_stats(target_date)
        if not actuals:
            print("No free agents were in MLB starting lineups today.")
            return
            
        ev_stats = self.harvester.get_statcast_ev_stats(target_date)
        
        # 3. Match and Build Results
        fa_results = []
        year = datetime.strptime(target_date, "%Y-%m-%d").year
        
        for _, row in fa_hitters.iterrows():
            mlb_id = self.harvester.get_mlb_id(row['Name'], target_year=year)
            if not mlb_id or mlb_id not in actuals:
                continue
                
            p_stats = actuals[mlb_id]
            ev = ev_stats.get(mlb_id, {'avg_ev': 0, 'max_ev': 0})
            
            fa_results.append({
                'Player': row['Name'],
                'POS': row['POS'],
                'Opponent': row['Opponent'],
                'Proj': float(row['DailyScore']),
                'Actual': f"{p_stats['H']}/{p_stats['AB']}, {p_stats['R']} R, {p_stats['HR']} HR, {p_stats['RBI']} RBI, {p_stats['SB']} SB",
                'stats': p_stats,
                'SO': p_stats['SO'],
                'SB/CS': f"{p_stats['SB']}/{p_stats['CS']}",
                'EV (Avg/Max)': f"{ev['avg_ev']:.1f}/{ev['max_ev']:.1f}",
                'Breakdown': row['Breakdown']
            })

        df = pd.DataFrame(fa_results)
        if df.empty:
            print("No free agent starters found in today's box scores.")
            return

        # Rank by Actual Production (HR, SB, H) then Proj
        # Score each player based on 5x5 contributions
        df['Prod_Score'] = df['stats'].apply(lambda s: s['R'] + s['HR']*2 + s['RBI'] + s['SB'] + (1 if s['H'] > 0 else 0))
        df['H'] = df['stats'].apply(lambda s: s['H'])

        df_ranked = df.sort_values(by=['Prod_Score', 'H', 'Proj'], ascending=False).head(top_n)

        display_dataframe(df_ranked, title=f"TOP {top_n} FREE AGENT PERFORMANCES", 
                          columns=['Player', 'POS', 'Opponent', 'Proj', 'Actual', 'SO', 'SB/CS', 'EV (Avg/Max)'])

        # Narrative
        narrative_parts = []
        if not df_ranked.empty:
            gem = df_ranked.iloc[0]
            if gem['Prod_Score'] > 0 or gem['H'] > 0:
                narrative_parts.append(f"Market Gem found: **{gem['Player']}** produced {gem['Actual']} against {gem['Opponent']}. "
                                     f"He was projected at {gem['Proj']:.2f} based on: {gem['Breakdown']}.")
            else:
                narrative_parts.append("The waiver wire was quiet today. No significant free agent breakouts detected.")

        if narrative_parts:
            print_narrative("\n\n".join(narrative_parts))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest Free Agent performance for a specific date.")
    parser.add_argument("date", nargs="?", default="2025-06-15", help="The date to backtest in YYYY-MM-DD format.")
    
    args = parser.parse_args()
    
    fa_backtester = FreeAgentBacktester()
    fa_backtester.run_fa_backtest(args.date)
