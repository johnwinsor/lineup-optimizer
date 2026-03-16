import json
import pandas as pd
import os
import re
import statsapi
from harvester import OttoneuScraper
from crosswalks import normalize_name
from display_utils import print_header, display_dataframe
from gameday_harvester import GameDayHarvester
from datetime import datetime, timedelta

def clean_name(html_name):
    # Extract "Carlos Santana" from "<a href="...">Carlos Santana</a>"
    match = re.search(r'>(.*?)</a>', html_name)
    return match.group(1) if match else html_name

def analyze_spring_training(min_pa=10, top_n=20, lookback_days=7, mode='top'):
    today = datetime.now().strftime("%Y-%m-%d")
    title = "Spring Training Analysis" if mode == 'top' else "Under-the-Radar Scout"
    print_header(title, f"Min PA: {min_pa} | rolling {lookback_days}-day StatCast")
    
    # 1. Load Spring Training Data
    if not os.path.exists('spring_training_hitters.json'):
        print("Error: spring_training_hitters.json not found.")
        return
        
    with open('spring_training_hitters.json', 'r') as f:
        spring_data = json.load(f)
    spring_df = pd.DataFrame(spring_data)

    # 2. Get Zurich Zebras Roster
    scraper = OttoneuScraper()
    zebras_hitters, _ = scraper.get_roster()
    zebras_names = set(zebras_hitters['Name'].apply(normalize_name).tolist())

    # 3. Load Free Agents
    fa_names = set()
    if os.path.exists('free_agents.json'):
        with open('free_agents.json', 'r') as f:
            fa_data = json.load(f).get('data', [])
        for p in fa_data:
            fa_names.add(normalize_name(clean_name(p.get('Name', ''))))

    # 4. Fetch Rolling StatCast & Swing Data
    print(f"Crawling {lookback_days}-day play-by-play for EV and Whiff metrics (this may take a moment)...")
    rolling_data = {} # { mlb_id: {'evs': [], 'swings': 0, 'misses': 0} }
    today_dt = datetime.now()
    
    for i in range(lookback_days):
        formatted_date = (today_dt - timedelta(days=i)).strftime("%m/%d/%Y")
        games = statsapi.schedule(date=formatted_date)
        
        for game in games:
            if game.get('status') in ['Cancelled', 'Postponed']: continue
            try:
                pbp = statsapi.get('game_playByPlay', {'gamePk': game['game_id']})
                for play in pbp.get('allPlays', []):
                    b_id = play.get('matchup', {}).get('batter', {}).get('id')
                    if not b_id: continue
                    if b_id not in rolling_data:
                        rolling_data[b_id] = {'evs': [], 'swings': 0, 'misses': 0}
                    
                    for event in play.get('playEvents', []):
                        if event.get('hitData') and 'launchSpeed' in event['hitData']:
                            rolling_data[b_id]['evs'].append(float(event['hitData']['launchSpeed']))
                        
                        desc = event.get('details', {}).get('description', '').lower()
                        is_swing = False
                        is_miss = False
                        
                        if 'swinging strike' in desc:
                            is_swing = True
                            is_miss = True
                        elif 'foul' in desc or 'in play' in desc:
                            is_swing = True
                        
                        if is_swing:
                            rolling_data[b_id]['swings'] += 1
                            if is_miss:
                                rolling_data[b_id]['misses'] += 1
            except: continue

    # Calculate rolling summaries
    player_stats = {}
    for b_id, d in rolling_data.items():
        evs = d['evs']
        whiff_pct = (d['misses'] / d['swings'] * 100) if d['swings'] > 0 else 0
        player_stats[b_id] = {
            'avg_ev': sum(evs) / len(evs) if evs else 0,
            'max_ev': max(evs) if evs else 0,
            'ev_count': len(evs),
            'whiff_pct': whiff_pct,
            'swings': d['swings']
        }

    # 5. Process Spring Data
    spring_df['PA'] = pd.to_numeric(spring_df['PA'], errors='coerce')
    spring_df['wRC+'] = pd.to_numeric(spring_df['wRC+'], errors='coerce')
    
    if mode == 'top':
        final_df = spring_df[spring_df['PA'] >= min_pa].sort_values(by='wRC+', ascending=False).head(top_n).copy()
    else:
        # UNDER THE RADAR MODE
        under_radar = spring_df[spring_df['PA'] >= min_pa].copy()
        under_radar = under_radar[under_radar['wRC+'] < 110]
        
        valid_hits = []
        for idx, row in under_radar.iterrows():
            mlb_id = row.get('xMLBAMID')
            stats = player_stats.get(mlb_id, {'avg_ev': 0, 'whiff_pct': 100, 'swings': 0})
            if (stats['avg_ev'] >= 90) or (stats['whiff_pct'] <= 15 and stats['swings'] >= 10):
                valid_hits.append(idx)
        
        final_df = under_radar.loc[valid_hits].copy()
        final_df['tmp_ev'] = final_df['xMLBAMID'].apply(lambda x: player_stats.get(x, {}).get('avg_ev', 0))
        final_df = final_df.sort_values(by='tmp_ev', ascending=False).head(top_n)

    # 6. Map Ownership and Stats
    results = []
    for _, row in final_df.iterrows():
        name = row['PlayerName']
        norm_name = normalize_name(name)
        mlb_id = row.get('xMLBAMID')
        
        ownership = "Other Team"
        if norm_name in zebras_names: ownership = "Zurich Zebras"
        elif norm_name in fa_names: ownership = "FREE AGENT"
        
        stats = player_stats.get(mlb_id, {'avg_ev': 0, 'max_ev': 0, 'ev_count': 0, 'whiff_pct': 0, 'swings': 0})
        ev_str = f"{stats['avg_ev']:.1f}/{stats['max_ev']:.1f} ({stats['ev_count']})" if stats['avg_ev'] > 0 else "-"
        whiff_str = f"{stats['whiff_pct']:.1f}%" if stats['swings'] >= 5 else "-"
        
        results.append({
            'Player': name,
            'wRC+': round(row['wRC+'], 1),
            'PA': int(row['PA']),
            'BB': int(row['BB']),
            'SO': int(row['SO']),
            'EV Avg/Max': ev_str,
            'Whiff%': whiff_str,
            'Ownership': ownership
        })

    # 7. Output Table
    df_results = pd.DataFrame(results)
    cols = ['Player', 'wRC+', 'PA', 'BB', 'SO', 'EV Avg/Max', 'Whiff%', 'Ownership']
    display_dataframe(df_results, title=f"{title} (League 1077)", columns=cols)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyze Spring Training performances.")
    parser.add_argument("--pa", type=int, default=10, help="Minimum PA (default: 10)")
    parser.add_argument("--top", type=int, default=20, help="Number of players (default: 20)")
    parser.add_argument("--days", type=int, default=7, help="StatCast lookback days (default: 7)")
    parser.add_argument("--radar", action="store_true", help="Under-the-radar mode (Low wRC+ but high StatCast)")
    args = parser.parse_args()
    
    mode = 'radar' if args.radar else 'top'
    analyze_spring_training(min_pa=args.pa, top_n=args.top, lookback_days=args.days, mode=mode)
