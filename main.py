import pandas as pd
from optimizer import OttoneuOptimizer
from datetime import datetime
import os
import re
import time
import pytz
import logging
from google import genai
from dotenv import load_dotenv
from display_utils import print_header, display_dataframe, print_narrative, print_section, print_info
from crosswalks import normalize_name
import config as C

# Boot logging before anything else
C.setup_logging()
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv(override=True)

def _breakdown_to_str(breakdown):
    """Convert a structured chip list to a human-readable string.
    Used for terminal display, AI narrative, and any legacy string context.
    """
    if not breakdown:
        return "-"
    if isinstance(breakdown, list):
        parts = []
        for c in breakdown:
            if isinstance(c, dict):
                parts.append(f"{c['label']}: {c['value']}" if c.get('value') else c['label'])
            else:
                parts.append(str(c))
        return ', '.join(parts)
    return str(breakdown)


def _get_pending_order(breakdown):
    """Return the assumed batting order digit from a Lineup Pending chip, or None."""
    if isinstance(breakdown, list):
        for c in breakdown:
            if isinstance(c, dict) and c.get('label', '').startswith('Lineup Pending'):
                m = re.search(r'Assumed #(\d)', c['label'])
                return m.group(1) if m else None
        return None
    m = re.search(r'Assumed #(\d)', str(breakdown))
    return m.group(1) if m else None


def generate_ai_narrative(lineup_df, sat_df, date_str, projection_system="steamer", team_name="Zurich Zebras", team_id=7582, skip_ai=False):
    if skip_ai:
        return "AI Narrative generation skipped."

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ GEMINI_API_KEY environment variable not set. Please set it to enable AI-generated narratives."

    try:
        print("\nGenerating AI Narrative...")
        client = genai.Client(api_key=api_key)

        proj_label = "Steamer" if projection_system == "steamer" else "ATC (Ariel Theoretical Composite)"

        starter_cols = [c for c in ['Slot', 'Player', 'Order', 'Opponent', 'SP_xERA', 'Score', 'Breakdown', 'Warning'] if c in lineup_df.columns]
        narrative_df = lineup_df[starter_cols].copy()
        narrative_df['Breakdown'] = narrative_df['Breakdown'].apply(_breakdown_to_str)
        lineup_text = narrative_df.to_string(index=False)

        # Build explicit name list for the formatting rule
        starter_names = lineup_df['Player'].tolist() if 'Player' in lineup_df.columns else []
        sat_names = sat_df['Player'].tolist() if sat_df is not None and 'Player' in sat_df.columns else []
        roster_names = ', '.join(f'**{n}**' for n in starter_names + sat_names)

        sat_text = "(none)"
        if sat_df is not None and not sat_df.empty:
            sat_cols = [c for c in ['Player', 'Slot', 'Opponent', 'SP_xERA', 'Score', 'Breakdown', 'Warning'] if c in sat_df.columns]
            top_sat = sat_df[sat_cols].sort_values('Score', ascending=False).head(4).copy()
            top_sat['Breakdown'] = top_sat['Breakdown'].apply(_breakdown_to_str)
            sat_text = top_sat.to_string(index=False)

        prompt = f"""
You are the lead fantasy baseball analyst for {team_name} (Ottoneu Team {team_id}), competing in a 5x5 Roto league.
The five scoring categories are: Runs (R), Home Runs (HR), RBI, Stolen Bases (SB), and Batting Average (AVG).
SB is the scarcest category — players with elite sprint speed are significantly overweighted in selection decisions.
Today is {date_str}. Projections sourced from {proj_label}.

SCORING SCALE (daily efficiency score):
- 90+  : Elite — weak pitcher, hitter's park, strong platoon/order advantage all aligned
- 60–89: Strong — recommended start
- 40–59: Marginal — starts only if no better option available
- <40  : Below floor — benched to preserve game caps

CONTEXT FOR DATA FIELDS:
- SP_xERA: opposing starter's expected ERA. Below 3.00 = elite arm (tough), above 5.00 = favorable matchup.
- Order: batting position in today's confirmed lineup. "Lineup Pending" means official lineup not yet posted; historical position assumed.
- Breakdown: factors that raised or lowered the score from the base projection (park, platoon, BvP, wind, batting order, etc.)
- Warning: weather or situational flags that introduce risk.

STARTING LINEUP:
{lineup_text}

TOP BENCHED PLAYERS (scored well but did not make the cut):
{sat_text}

FORMATTING RULE: Wrap the name in **double asterisks** every time you mention one of our rostered players — including the first mention and any repeat mentions. Do NOT bold opposing pitchers or other players not on our roster.
Our rostered players in this narrative: {roster_names}

Write a pre-game narrative for {team_name}. Be specific — reference actual player names, scores, and matchup details.
Cover the following, in whatever order feels natural:
1. The strongest plays of the day: who has the best combination of score, matchup context, and situational factors — and why.
2. Any notable platoon edges, favorable parks, wind, or BvP historical edges driving a score higher than the raw projection suggests.
3. The most interesting bench decision: which benched player came closest to making the lineup and what tipped the optimizer the other way.
4. Any warnings or risks worth flagging — weather, lineup pending, elite opposing pitcher — that could affect the day.

Analytical tone. No filler intro. 2–3 paragraphs.
"""
        def _is_transient(exc):
            s = str(exc)
            return any(code in s for code in ('503', '429', 'UNAVAILABLE', 'RESOURCE_EXHAUSTED'))

        # Primary model — 5 attempts with escalating backoff
        primary_exhausted = False
        for attempt in range(1, 6):
            try:
                response = client.models.generate_content(
                    model='gemini-3.1-flash-lite-preview',
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                if _is_transient(e) and attempt < 5:
                    delay = [5, 15, 30, 60][attempt - 1]
                    logger.warning(f"Gemini primary transient error (attempt {attempt}/5), retrying in {delay}s: {e}")
                    time.sleep(delay)
                elif _is_transient(e):
                    primary_exhausted = True
                    break  # capacity exhausted — try fallback
                else:
                    raise  # non-transient (auth, bad request) — fail fast on both models

        # Fallback model — 3 attempts with shorter backoff
        if primary_exhausted:
            logger.warning("Primary model exhausted — switching to fallback (gemini-2.5-flash-lite)")
            for attempt in range(1, 4):
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash-lite',
                        contents=prompt,
                    )
                    logger.info(f"Narrative generated via fallback model (attempt {attempt}/3)")
                    return response.text
                except Exception as e:
                    if _is_transient(e) and attempt < 3:
                        delay = 10 * attempt  # 10s, 20s
                        logger.warning(f"Gemini fallback transient error (attempt {attempt}/3), retrying in {delay}s: {e}")
                        time.sleep(delay)
                    else:
                        raise
    except Exception as e:
        return f"⚠️ Failed to generate AI narrative: {e}"

import argparse
import json
import numpy as np

def save_web_json(lineup_df, sat_df, target_date, ai_narrative, projection_system, filename="web_lineup.json"):
    """Saves the optimization results to a JSON file for the web dashboard."""
    # Sanitize DataFrames: Replace NaN/NaT with None so they become 'null' in JSON
    lineup_clean = lineup_df.replace({np.nan: None}).where(pd.notnull(lineup_df), None)
    sat_clean = sat_df.replace({np.nan: None}).where(pd.notnull(sat_df), None)

    data = {
        "target_date": target_date,
        "last_updated": datetime.now(pytz.UTC).isoformat(),
        "projection_system": projection_system.upper(),
        "total_efficiency_score": round(lineup_df['Score'].sum(), 2) if not lineup_df.empty else 0,
        "narrative": ai_narrative,
        "recommended_lineup": lineup_clean.to_dict(orient="records") if not lineup_clean.empty else [],
        "players_sat": sat_clean.to_dict(orient="records") if not sat_clean.empty else []
    }
    
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"\n[green]Web dashboard data exported to {filename}[/green]")

def run_optimizer_hitter(projection_system="steamer", target_date=None, team_id=7582, output_filename=None, skip_ai=False):
    # Determine target date and year using MLB (Eastern) Time
    mlb_tz = pytz.timezone('US/Eastern')
    now_mlb = datetime.now(mlb_tz)
    
    # Validate inputs early — fail fast with a clear message
    try:
        projection_system = C.validate_projection_system(projection_system)
    except ValueError as e:
        logger.error(str(e))
        return None

    if target_date:
        try:
            C.validate_date(target_date)
            year = int(target_date.split("-")[0])
        except ValueError as e:
            logger.error(str(e))
            return None
    else:
        target_date = now_mlb.strftime("%Y-%m-%d")
        year = now_mlb.year

    if not output_filename:
        output_filename = f"web_lineup_{team_id}.json"

    optimizer = OttoneuOptimizer(team_id=team_id, projection_system=projection_system)
    team_name = C.TEAM_NAMES.get(team_id, f"Team {team_id}")
    
    print_header(f"{team_name} ({team_id}) Lineup Optimizer [{projection_system.upper()}]", target_date)
    
    # 1. Gather Data for both tables
    print("Analyzing Roster and Matchups...")
    all_hitters = optimizer.daily_engine.get_daily_projections(target_date)
    all_hitters['norm_name_main'] = all_hitters['Name'].apply(normalize_name)
    full_roster = optimizer.enricher.enrich_roster()
    matchups = optimizer.daily_engine.harvester.get_daily_matchups(target_date)
    
    # 2. Run Daily Optimization
    lineup = optimizer.optimize_lineup(target_date=target_date)
    
    if lineup is not None and not lineup.empty:
        # Add Order column to lineup
        order_list = []
        for _, row in lineup.iterrows():
            name = row['Player']
            # We need the team abbreviation for this player to disambiguate
            p_roster_row = full_roster[full_roster['Name'] == name]
            p_team = p_roster_row['Team'].values[0] if not p_roster_row.empty else None
            
            mlb_id = optimizer.daily_engine.harvester.get_mlb_id(name, target_year=year, team_abb=p_team)
            matchup = matchups.get(mlb_id, {})
            
            order = "-"
            if not matchup and name in all_hitters['Name'].values:
                # Check if they were a 'Pending' starter
                proj_row = all_hitters[all_hitters['Name'] == name]
                if not proj_row.empty and _get_pending_order(proj_row['Breakdown'].values[0]) is not None:
                    order_num = _get_pending_order(proj_row['Breakdown'].values[0])
                    order = f"{order_num}*"
            else:
                raw_order = matchup.get('batting_order', '-')
                # Convert '100' to '1', etc.
                order = raw_order[0] if raw_order and raw_order != '-' and len(raw_order) >= 1 else '-'
            
            order_list.append(order)
        lineup['Order'] = order_list
        
        # Add Start column for terminal
        def format_terminal_time(iso_str):
            if not iso_str: return "-"
            try:
                dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
                return dt.astimezone(None).strftime('%I:%M %p') # Local time
            except:
                return "-"
        
        lineup['Start'] = lineup['GameTime'].apply(format_terminal_time)

        # === TABLE 1: RECOMMENDED LINEUP ===
        cols = ['Slot', 'Player', 'Order', 'Start', 'Opponent', 'SP_xERA', 'Score', 'Breakdown', 'Warning']
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
                
            team_abb = row.get('Team')
            mlb_id = harvester.get_mlb_id(name, target_year=year, team_abb=team_abb)
            matchup = matchups.get(mlb_id, {})
            order = matchup.get('batting_order', '-')
            clean_order = order[0] if order and order != '-' and len(order) >= 1 else '-'
            
            # Determine Why they Sat (Logic mirrored from backtester.py)
            norm_name = normalize_name(name)
            proj_row = all_hitters[all_hitters['norm_name_main'] == norm_name]
            
            proj_score = proj_row['DailyScore'].values[0] if not proj_row.empty else 0.0
            breakdown = proj_row['Breakdown'].values[0] if not proj_row.empty else "-"
            opponent = proj_row['Opponent'].values[0] if not proj_row.empty else "N/A"
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
                    note = "Lineup Pending (Not picked by Optimizer)."
                    if not proj_row.empty:
                        order_num = _get_pending_order(proj_row['Breakdown'].values[0])
                        clean_order = f"{order_num}*" if order_num else "TBA"
                    else:
                        clean_order = "TBA"
                elif not matchup.get('is_starting', False) and team_data.get('has_lineup'):
                    note = "Not in MLB Starting Lineup (Benched/IL/Rest)."
                else:
                    # Starting in MLB but not picked by our optimizer
                    if proj_score < min_floor:
                        note = f"Benched - Below Zebras Floor ({min_floor})."
                    else:
                        note = f"Benched - Lower projected efficiency than other options."

            sat_data.append({
                'Slot': 'BN',
                'Player': name,
                'POS': row['POS'],
                'Order': clean_order,
                'Start': format_terminal_time(proj_row['GameTime'].values[0] if not proj_row.empty else None),
                'Opponent': opponent,
                'SP_xERA': sp_xera,
                'Score': proj_score,
                'Breakdown': (breakdown + [{"label": note, "value": None, "type": "info"}]) if note else breakdown,
                'Warning': warning,
                'GameTime': proj_row['GameTime'].values[0] if not proj_row.empty else None
            })

        df_sat = pd.DataFrame(sat_data)
        if not df_sat.empty:
            cols = ['Slot', 'Player', 'Order', 'Start', 'Opponent', 'SP_xERA', 'Score', 'Breakdown', 'Warning']
            cols = [c for c in cols if c in df_sat.columns]
            display_dataframe(df_sat, title="PLAYERS SAT", columns=cols)

        # Narrative Generation - all teams, today only (tomorrow gated in update_web_data.py)
        team_name = C.TEAM_NAMES.get(team_id, f"Team {team_id}")
        ai_narrative = generate_ai_narrative(
            lineup, df_sat, target_date,
            projection_system=projection_system,
            team_name=team_name,
            team_id=team_id,
            skip_ai=skip_ai,
        )
        if not skip_ai:
            print_narrative(ai_narrative)
        
        print_info("\n[dim]Algorithm: Maximize projected 5x5 efficiency subject to positional caps.[/dim]")
        print_info("[dim]Factors: SIERA Difficulty, Dynamic Platoon Splits, Elite BvP, StatCast Peripherals, Weather.[/dim]")
        
        # Save JSON for the web
        # Ensure Slot is converted from Categorical to string for JSON serialization
        if 'Slot' in lineup.columns:
            lineup['Slot'] = lineup['Slot'].astype(str)
        save_web_json(lineup, df_sat, target_date, ai_narrative, projection_system, output_filename)
    else:
        logger.warning(f"No valid starters found for {target_date} — off-day or lineups not yet posted.")

def main():
    parser = argparse.ArgumentParser(description="Ottoneu Lineup Optimizer")
    parser.add_argument("--projection", type=str, default="steamer", help="Projection system (steamer, atc, thebat)")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--team", type=int, default=7582, help="Ottoneu Team ID")
    parser.add_argument("--output", type=str, help="Output JSON filename for web dashboard")
    parser.add_argument("--skip-ai", action="store_true", help="Skip AI narrative generation to save API quota")
    args = parser.parse_args()

    run_optimizer_hitter(
        projection_system=args.projection,
        target_date=args.date,
        team_id=args.team,
        output_filename=args.output,
        skip_ai=args.skip_ai
    )

if __name__ == "__main__":
    main()
