import pandas as pd
from optimizer import OttoneuOptimizer
from datetime import datetime
from tabulate import tabulate

def main():
    print("Zurich Zebras (Ottoneu Team 7582) Lineup Optimizer")
    print("==================================================")
    
    today = datetime.now().strftime("%Y-%m-%d")
    year = datetime.now().year
    optimizer = OttoneuOptimizer()
    
    # 1. Gather Data for both tables
    print("Analyzing Roster and Matchups...")
    all_hitters = optimizer.daily_engine.get_daily_projections(today)
    full_roster = optimizer.enricher.enrich_roster()
    matchups = optimizer.daily_engine.harvester.get_daily_matchups(today)
    
    # 2. Run Daily Optimization
    lineup = optimizer.optimize_lineup(target_date=today)
    
    if lineup is not None and not lineup.empty:
        # Add Order column to lineup
        order_list = []
        for _, row in lineup.iterrows():
            name = row['Player']
            mlb_id = optimizer.daily_engine.harvester.get_mlb_id(name, target_year=year)
            order = matchups.get(mlb_id, {}).get('batting_order', '-')
            # Convert '100' to '1', etc.
            clean_order = order[0] if order and order != '-' and len(order) >= 1 else '-'
            order_list.append(clean_order)
        lineup['Order'] = order_list

        # === TABLE 1: RECOMMENDED LINEUP ===
        print(f"\n=== RECOMMENDED DAILY LINEUP ({today}) ===")
        cols = ['Slot', 'Player', 'Order', 'Opponent', 'Score', 'Breakdown', 'Warning']
        cols = [c for c in cols if c in lineup.columns]
        print(tabulate(lineup[cols], headers='keys', tablefmt='grid', showindex=False, floatfmt=".2f"))
        
        print(f"\nProjected Daily Efficiency Score: {lineup['Score'].sum():.2f}")
        
        # === TABLE 2: PLAYERS SAT ===
        print("\n=== PLAYERS SAT ===")
        started_names = set(lineup['Player'].tolist())
        sat_data = []
        harvester = optimizer.daily_engine.harvester
        
        for _, row in full_roster.iterrows():
            name = row['Name']
            if name in started_names:
                continue
                
            mlb_id = harvester.get_mlb_id(name, target_year=year)
            matchup = matchups.get(mlb_id, {})
            order = matchup.get('batting_order', '-')
            clean_order = order[0] if order and order != '-' and len(order) >= 1 else '-'
            
            # Determine Why they Sat (Logic mirrored from backtester.py)
            proj_score = 0.0
            min_floor = optimizer.min_score
            
            if not mlb_id or mlb_id not in matchups:
                note = "Team Off-day or No Game Scheduled."
            else:
                if not matchup['is_starting']:
                    note = "Not in MLB Starting Lineup (Benched/IL/Rest)."
                else:
                    # Starting in MLB but not picked by our optimizer
                    proj_row = all_hitters[all_hitters['Name'] == name]
                    proj_score = proj_row['DailyScore'].values[0] if not proj_row.empty else 0
                    
                    if proj_score < min_floor:
                        note = f"Benched - Below Zebras Floor ({min_floor})."
                    else:
                        note = f"Benched - Lower projected efficiency than other options."

            sat_data.append({
                'Player': name,
                'POS': row['POS'],
                'Order': clean_order,
                'Proj': proj_score,
                'Note': note
            })

        df_sat = pd.DataFrame(sat_data)
        if not df_sat.empty:
            print(tabulate(df_sat[['Player', 'POS', 'Order', 'Proj', 'Note']], 
                           headers=['Player', 'POS', 'Order', 'Proj', 'Note'], 
                           tablefmt='grid', showindex=False, floatfmt=".2f"))

        # Narrative Generation
        print("\n=== ZEBRAS ANALYST NARRATIVE ===")
        top_player = lineup.sort_values(by='Score', ascending=False).iloc[0]
        sp_target = lineup[lineup['Breakdown'].str.contains(r'SP Skill: \+', na=False)]
        
        narrative = f"Today's lineup is anchored by **{top_player['Player']}** facing {top_player['Opponent']}."
        if "Platoon" in top_player['Breakdown']:
            narrative += " He has a major platoon advantage that we expect him to exploit."
            
        if not sp_target.empty:
            best_matchup = sp_target.sort_values(by='Score', ascending=False).iloc[0]
            narrative += f"\n\nHigh-Upside Matchup: **{best_matchup['Player']}** is facing a particularly vulnerable arm today ({best_matchup['Opponent']}). This is a 'sure bet' for counting stat production."
        
        warnings = lineup[lineup['Warning'] != ""]
        if not warnings.empty:
            narrative += f"\n\nBorderline Plays: We are starting **{', '.join(warnings['Player'].tolist())}** despite weather concerns. Keep a close eye on the radar before lock; if the game is postponed, these are your first pivots."
        
        if "BvP" in str(lineup['Breakdown'].tolist()):
            bvp_player = lineup[lineup['Breakdown'].str.contains('BvP', na=False)].iloc[0]
            narrative += f"\n\nHistorical Edge: **{bvp_player['Player']}** has shown he sees {bvp_player['Opponent'].split('(')[0].strip()} extremely well in the past. We're leaning on that historical comfort today."

        print(narrative)
        
        print("\nAlgorithm: Maximize projected 5x5 efficiency (Counting Stats/PA + AVG) subject to positional caps.")
        print("Factors: xERA Difficulty, Platoon Splits, Elite BvP, StatCast Peripherals, Weather.")
    else:
        print(f"\nNo valid starters found for {today}. This may be an off-day or lineups are not yet posted.")

if __name__ == "__main__":
    main()
