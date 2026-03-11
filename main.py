from optimizer import OttoneuOptimizer
from datetime import datetime
from tabulate import tabulate

def main():
    print("Zurich Zebras (Ottoneu Team 7582) Lineup Optimizer")
    print("==================================================")
    
    today = datetime.now().strftime("%Y-%m-%d")
    optimizer = OttoneuOptimizer()
    
    # We run daily optimization for today
    lineup = optimizer.optimize_lineup(target_date=today)
    
    if lineup is not None and not lineup.empty:
        print(f"\nRecommended Daily Hitter Lineup ({today}):")
        # Ensure we show the breakdown, opponent, and warnings
        cols = ['Slot', 'Player', 'Opponent', 'Score', 'Breakdown', 'Warning']
        # Filter columns that exist
        cols = [c for c in cols if c in lineup.columns]
        print(tabulate(lineup[cols], headers='keys', tablefmt='grid', showindex=False))
        
        print(f"\nProjected Daily Efficiency Score: {lineup['Score'].sum():.2f}")
        
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
        print("To see long-term season projections, run the optimizer without a date parameter (requires code change).")

if __name__ == "__main__":
    main()
