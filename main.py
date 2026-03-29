import pandas as pd
from optimizer import OttoneuOptimizer
from datetime import datetime
import os
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv
from display_utils import print_header, display_dataframe, print_narrative, print_section, print_info

# Load environment variables from .env file, overriding any existing shell variables
load_dotenv(override=True)

def generate_ai_narrative(lineup_df, date_str, skip_ai=False):
    if skip_ai:
        return "AI Narrative generation skipped."
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ GEMINI_API_KEY environment variable not set. Please set it to enable AI-generated narratives."
    
    try:
        print("\nGenerating AI Narrative...")
        # Create client explicitly with the key from environment
        client = genai.Client(api_key=api_key)
        
        # Convert lineup data to a readable format for the LLM
        lineup_text = lineup_df[['Player', 'Opponent', 'Score', 'Breakdown', 'Warning']].to_string(index=False)
        
        prompt = f"""
You are the lead fantasy baseball analyst for the Zurich Zebras (Ottoneu Team 7582).
Today is {date_str}. Review the team's optimized starting lineup below.

LINEUP DATA:
{lineup_text}

Write a concise, 2-paragraph pre-game narrative for the team. 
- Paragraph 1: Highlight the top plays of the day (high scores, great matchups/platoon advantages).
- Paragraph 2: Mention any borderline plays, weather warnings, or interesting 'Historical Edge' (BvP) matchups.
Keep the tone professional, analytical, and focused on maximizing 5x5 Roto efficiency. Do not use filler introductions like 'Here is the narrative'.
"""
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"⚠️ Failed to generate AI narrative: {e}"

import argparse
import json

def save_web_json(lineup_df, sat_df, target_date, ai_narrative, projection_system, filename="web_lineup.json"):
    """Saves the optimization results to a JSON file for the web dashboard."""
    data = {
        "target_date": target_date,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "projection_system": projection_system.upper(),
        "total_efficiency_score": round(lineup_df['Score'].sum(), 2) if not lineup_df.empty else 0,
        "narrative": ai_narrative,
        "recommended_lineup": lineup_df.to_dict(orient="records") if not lineup_df.empty else [],
        "players_sat": sat_df.to_dict(orient="records") if not sat_df.empty else []
    }
    
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"\n[green]Web dashboard data exported to {filename}[/green]")

def main():
    parser = argparse.ArgumentParser(description="Zurich Zebras Lineup Optimizer")
    parser.add_argument("--projection", type=str, default="steamer", help="Projection system (steamer, atc, thebat)")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--output", type=str, default="web_lineup.json", help="Output JSON filename for web dashboard")
    parser.add_argument("--skip-ai", action="store_true", help="Skip AI narrative generation to save API quota")
    args = parser.parse_args()

    # Determine target date and year
    if args.date:
        target_date = args.date
        try:
            year = int(target_date.split("-")[0])
        except (ValueError, IndexError):
            print(f"Error: Invalid date format '{target_date}'. Use YYYY-MM-DD.")
            return
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")
        year = datetime.now().year

    optimizer = OttoneuOptimizer(projection_system=args.projection)
    
    print_header(f"Zurich Zebras (Ottoneu Team 7582) Lineup Optimizer [{args.projection.upper()}]", target_date)
    
    # 1. Gather Data for both tables
    print("Analyzing Roster and Matchups...")
    all_hitters = optimizer.daily_engine.get_daily_projections(target_date)
    full_roster = optimizer.enricher.enrich_roster()
    matchups = optimizer.daily_engine.harvester.get_daily_matchups(target_date)
    
    # 2. Run Daily Optimization
    lineup = optimizer.optimize_lineup(target_date=target_date)
    
    if lineup is not None and not lineup.empty:
        # Add Order column to lineup
        order_list = []
        for _, row in lineup.iterrows():
            name = row['Player']
            mlb_id = optimizer.daily_engine.harvester.get_mlb_id(name, target_year=year)
            matchup = matchups.get(mlb_id, {})
            
            order = "-"
            if not matchup and name in all_hitters['Name'].values:
                # Check if they were a 'Pending' starter
                proj_row = all_hitters[all_hitters['Name'] == name]
                if not proj_row.empty and 'Lineup Pending' in proj_row['Breakdown'].values[0]:
                    # Extract assumed order from breakdown e.g. "Lineup Pending (Assumed #1)"
                    breakdown = proj_row['Breakdown'].values[0]
                    match = re.search(r'Assumed #(\d)', breakdown)
                    if match:
                        order = f"{match.group(1)}*" 
                    else:
                        order = "TBA"
            else:
                raw_order = matchup.get('batting_order', '-')
                # Convert '100' to '1', etc.
                order = raw_order[0] if raw_order and raw_order != '-' and len(raw_order) >= 1 else '-'
            
            order_list.append(order)
        lineup['Order'] = order_list

        # === TABLE 1: RECOMMENDED LINEUP ===
        cols = ['Slot', 'Player', 'Order', 'Opponent', 'SP_xERA', 'Score', 'Breakdown', 'Warning']
        cols = [c for c in cols if c in lineup.columns]
        display_dataframe(lineup, title="RECOMMENDED DAILY LINEUP", columns=cols)
        
        print(f"\nProjected Daily Efficiency Score: {lineup['Score'].sum():.2f}")
        
        # === TABLE 2: PLAYERS SAT ===
        started_names = set(lineup['Player'].tolist())
        sat_data = []
        harvester = optimizer.daily_engine.harvester
        teams_playing = matchups.get('_teams_playing', {})
        
        for _, row in full_roster.iterrows():
            name = row['Name']
            if name in started_names:
                continue
                
            mlb_id = harvester.get_mlb_id(name, target_year=year)
            team_abb = row.get('Team')
            matchup = matchups.get(mlb_id, {})
            order = matchup.get('batting_order', '-')
            clean_order = order[0] if order and order != '-' and len(order) >= 1 else '-'
            
            # Determine Why they Sat (Logic mirrored from backtester.py)
            proj_row = all_hitters[all_hitters['Name'] == name]
            proj_score = proj_row['DailyScore'].values[0] if not proj_row.empty else 0.0
            breakdown = proj_row['Breakdown'].values[0] if not proj_row.empty else "-"
            opponent = proj_row['Opponent'].values[0] if not proj_row.empty else "-"
            sp_xera = proj_row['SP_xERA'].values[0] if not proj_row.empty else "-"
            warning = proj_row['Warning'].values[0] if not proj_row.empty else ""
            min_floor = optimizer.min_score
            
            if row.get('Injured') == True:
                note = "Injured (IL) - Not available."
                clean_order = "-"
            elif warning == "🚨 MINORS":
                note = "In the Minors (Not on Active Roster)."
                clean_order = "-"
            elif not mlb_id or (mlb_id not in matchups and team_abb not in teams_playing):
                note = "Team Off-day or No Game Scheduled."
            else:
                # Check if team is playing but lineup isn't out
                team_data = teams_playing.get(team_abb, {})
                if not matchup and team_data and not team_data.get('has_lineup'):
                    note = "Lineup Pending (Assumed Bench)."
                    # Check for assumed order from historical detection
                    if not proj_row.empty:
                        breakdown = proj_row['Breakdown'].values[0]
                        match = re.search(r'Assumed #(\d)', breakdown)
                        if match:
                            clean_order = f"{match.group(1)}*" 
                        else:
                            clean_order = "TBA"
                    else:
                        clean_order = "TBA"
                elif not matchup.get('is_starting', False):
                    note = "Not in MLB Starting Lineup (Benched/IL/Rest)."
                else:
                    # Starting in MLB but not picked by our optimizer
                    if proj_score < min_floor:
                        note = f"Benched - Below Zebras Floor ({min_floor})."
                    else:
                        note = f"Benched - Lower projected efficiency than other options."

            sat_data.append({
                'Player': name,
                'POS': row['POS'],
                'Order': clean_order,
                'Opponent': opponent,
                'SP_xERA': sp_xera,
                'Proj': proj_score,
                'Breakdown': breakdown,
                'Note': note
            })

        df_sat = pd.DataFrame(sat_data)
        if not df_sat.empty:
            display_dataframe(df_sat, title="PLAYERS SAT", columns=['Player', 'POS', 'Order', 'Opponent', 'SP_xERA', 'Proj', 'Breakdown', 'Note'])

        # Narrative Generation
        ai_narrative = generate_ai_narrative(lineup, target_date, skip_ai=args.skip_ai)
        print_narrative(ai_narrative)
        
        print_info("\n[dim]Algorithm: Maximize projected 5x5 efficiency subject to positional caps.[/dim]")
        print_info("[dim]Factors: SIERA Difficulty, Platoon Splits, Elite BvP, StatCast Peripherals, Weather.[/dim]")
        
        # Save JSON for the web
        # Ensure Slot is converted from Categorical to string for JSON serialization
        if 'Slot' in lineup.columns:
            lineup['Slot'] = lineup['Slot'].astype(str)
        save_web_json(lineup, df_sat, target_date, ai_narrative, args.projection, args.output)
    else:
        print(f"\nNo valid starters found for {target_date}. This may be an off-day or lineups are not yet posted.")

if __name__ == "__main__":
    main()
