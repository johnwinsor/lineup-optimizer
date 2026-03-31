import pandas as pd
from pitcher_daily_engine import PitcherDailyEngine
from gameday_harvester import GameDayHarvester
from datetime import datetime
from display_utils import print_header, display_dataframe, print_narrative, print_totals
import argparse

class PitcherBacktester:
    def __init__(self, league_id=1077, team_id=7582, projection_system="atc"):
        self.engine = PitcherDailyEngine(league_id, team_id, projection_system=projection_system)
        self.harvester = self.engine.harvester
        self.projection_system = projection_system

    def save_web_json(self, results_data, target_date, filename):
        """Saves pitcher backtest results to a JSON file for the web dashboard."""
        import json
        data = {
            "target_date": target_date,
            "last_updated": datetime.now().isoformat(),
            "projection_system": self.projection_system.upper(),
            "pitcher_starts": results_data
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Historical pitcher results saved to {filename}")

    def run_backtest(self, target_date: str, output_json=None):
        print_header(f"Zurich Zebras Pitcher Backtester [{self.projection_system.upper()}]", target_date)
        
        # 1. Get Daily Projections
        print("1. Analyzing Roster and Matchups...")
        projections = self.engine.get_daily_projections(target_date)
        starters = projections[projections['IsStarting'] == True].copy()
        
        # 2. Fetch Actual Results
        print("2. Fetching Actual Pitching Results...")
        actuals = self.harvester.get_actual_pitching_stats(target_date)
        
        results_data = []
        for _, row in starters.iterrows():
            player_name = row['Name']
            mlb_id = row.get('xMLBAMID')
            if not mlb_id or pd.isna(mlb_id):
                mlb_id = self.harvester.get_mlb_id(player_name)
            
            p_stats = actuals.get(mlb_id, {'IP': '0.0', 'H': 0, 'ER': 0, 'BB': 0, 'SO': 0, 'W': 0, 'L': 0})
            
            # IP cleaning
            ip_str = str(p_stats['IP'])
            
            results_data.append({
                'Player': player_name,
                'Team': row['Team'],
                'Opponent': row['Opponent'],
                'Proj Score': round(row['DailyScore'], 1),
                'Actual': f"{ip_str} IP, {p_stats['ER']} ER, {p_stats['SO']} K, {'W' if p_stats['W'] else ('L' if p_stats['L'] else '-')}",
                'IP': ip_str,
                'ER': p_stats['ER'],
                'K': p_stats['SO'],
                'W': p_stats['W'],
                'Breakdown': row['Breakdown']
            })

        if not results_data:
            print(f"\nNo rostered pitchers scheduled to start on {target_date}.")
            # Even if no starters, save an empty results file if requested
            if output_json:
                self.save_web_json([], target_date, output_json)
            return

        df_results = pd.DataFrame(results_data)
        display_dataframe(df_results, title="PITCHER PERFORMANCE", 
                          columns=['Player', 'Team', 'Opponent', 'Proj Score', 'Actual', 'Breakdown'])

        # Simple Narrative
        narrative_parts = []
        for p in results_data:
            if p['IP'] == '0.0':
                narrative_parts.append(f"No appearance recorded for **{p['Player']}**. Was he scratched or pushed back?")
                continue
                
            ip_val = float(p['IP'])
            if ip_val >= 5.0 and p['ER'] <= 2:
                narrative_parts.append(f"The Prediction Win: **{p['Player']}** delivered on his {p['Proj Score']} projection with a strong outing: {p['Actual']}.")
            elif p['ER'] >= 4:
                narrative_parts.append(f"The Tough Start: Despite the {p['Proj Score']} projection, **{p['Player']}** struggled today, allowing {p['ER']} ER in {p['IP']} IP.")
            else:
                narrative_parts.append(f"Standard Outing: **{p['Player']}** provided baseline value ({p['Actual']}) against {p['Opponent']}.")

        if narrative_parts:
            print_narrative("\n\n".join(narrative_parts))
            
        if output_json:
            self.save_web_json(results_data, target_date, output_json)

if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Backtest Zurich Zebras Pitcher Optimizer")
    parser.add_argument("date", nargs="?", default=today, help="Date to backtest (YYYY-MM-DD)")
    parser.add_argument("--proj", type=str, default="atc", choices=["atc", "steamer"], help="Projection system")
    parser.add_argument("--output", type=str, help="Output JSON filename for web dashboard")
    
    args = parser.parse_args()
    
    backtester = PitcherBacktester(projection_system=args.proj)
    backtester.run_backtest(args.date, output_json=args.output)
