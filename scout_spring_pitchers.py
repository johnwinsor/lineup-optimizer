import json
import pandas as pd
import os
import re
import argparse
from crosswalks import normalize_name
from harvester import OttoneuScraper

def clean_html(text):
    if not text: return ""
    return re.sub(r'<.*?>', '', text)

def load_json_data(file_path, data_key=None):
    if not os.path.exists(file_path):
        return None
    with open(file_path, 'r') as f:
        data = json.load(f)
    if data_key and isinstance(data, dict):
        return data.get(data_key, [])
    return data

def analyze_fa_pitchers_spring(min_ip=5, top_n=15):
    # 1. Load Spring Training Pitcher Data
    spring_data = load_json_data('spring_training_pitchers.json')
    if spring_data is None:
        print("Error: spring_training_pitchers.json not found. Run spring_harvester.py first.")
        return
    
    spring_df = pd.DataFrame(spring_data)
    spring_df['IP'] = pd.to_numeric(spring_df['IP'], errors='coerce')
    spring_df['K-BB%'] = pd.to_numeric(spring_df['K-BB%'], errors='coerce')
    spring_df['K/9'] = pd.to_numeric(spring_df['K/9'], errors='coerce')
    spring_df['BB/9'] = pd.to_numeric(spring_df['BB/9'], errors='coerce')
    spring_df['ERA'] = pd.to_numeric(spring_df['ERA'], errors='coerce')
    spring_df['WHIP'] = pd.to_numeric(spring_df['WHIP'], errors='coerce')
    spring_df['SwStr%'] = pd.to_numeric(spring_df['SwStr%'], errors='coerce')
    spring_df['PlayerName_Norm'] = spring_df['PlayerName'].apply(normalize_name)

    # 2. Get Zurich Zebras Roster (to exclude)
    scraper = OttoneuScraper()
    try:
        _, zebras_pitchers = scraper.get_roster()
        zebras_names = set(zebras_pitchers['Name'].apply(normalize_name).tolist())
    except Exception as e:
        print(f"Warning: Could not fetch live roster ({e}). Using empty set.")
        zebras_names = set()

    # 3. Load Free Agents and Map Ottoneu IDs
    fa_data = load_json_data('free_agents.json', data_key='data')
    fa_map = {} # norm_name -> {ottid, position}
    if fa_data:
        for p in fa_data:
            name = normalize_name(clean_html(p.get('Name', '')))
            fa_map[name] = {
                'ottid': p.get('ottid'),
                'Pos': p.get('positionDB', p.get('position', ''))
            }
    else:
        print("Error: free_agents.json not found. Run scout_harvester.py first.")
        return

    # 4. Load ATC Pitcher Projections for Comparison
    atc_data = load_json_data('projections-atc-pit.json')
    atc_map = {} # norm_name -> atc_stats
    if atc_data:
        for p in atc_data:
            name = normalize_name(p.get('PlayerName', ''))
            atc_map[name] = {
                'K/9': p.get('K/9', 8.0),
                'BB/9': p.get('BB/9', 3.0),
                'ERA': p.get('ERA', 4.50)
            }

    # 5. Filter for Free Agents
    fa_spring = spring_df[
        (spring_df['PlayerName_Norm'].isin(fa_map.keys())) & 
        (~spring_df['PlayerName_Norm'].isin(zebras_names)) &
        (spring_df['IP'] >= min_ip)
    ].copy()

    # Add FA info and ATC info
    fa_spring['OttoneuID'] = fa_spring['PlayerName_Norm'].map(lambda x: fa_map[x]['ottid'])
    fa_spring['ATC_K/9'] = fa_spring['PlayerName_Norm'].map(lambda x: atc_map.get(x, {}).get('K/9', 8.0))
    fa_spring['ATC_ERA'] = fa_spring['PlayerName_Norm'].map(lambda x: atc_map.get(x, {}).get('ERA', 4.50))
    fa_spring['K_Diff'] = fa_spring['K/9'] - fa_spring['ATC_K/9']

    # 6. Sort and Display (Primary Sort by K-BB%)
    fa_spring = fa_spring.sort_values(by='K-BB%', ascending=False).head(top_n)

    print(f"\nTOP {top_n} FREE AGENT PITCHERS BY SPRING PERFORMANCE (Min {min_ip} IP)")
    print("-" * 140)
    
    results = []
    for _, row in fa_spring.iterrows():
        ott_link = f"https://ottoneu.fangraphs.com/1077/playercard?id={row['OttoneuID']}"
        results.append({
            'Player': row['PlayerName'],
            'IP': round(row['IP'], 1),
            'K-BB%': f"{round(row['K-BB%']*100, 1)}%",
            'K/9 (ST)': round(row['K/9'], 1),
            'ATC K/9': round(row['ATC_K/9'], 1),
            'K Diff': round(row['K_Diff'], 1),
            'SwStr%': f"{round(row['SwStr%']*100, 1)}%",
            'ERA': round(row['ERA'], 2),
            'WHIP': round(row['WHIP'], 2),
            'Ottoneu Link': ott_link
        })
    
    if not results:
        print("No players found matching criteria.")
        return

    df_results = pd.DataFrame(results)
    print(df_results.to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scout Free Agent Pitchers based on Spring Training performance.")
    parser.add_argument("--ip", type=float, default=5.0, help="Minimum Innings Pitched (default: 5.0)")
    parser.add_argument("--top", type=int, default=15, help="Number of top players to show (default: 15)")
    
    args = parser.parse_args()
    analyze_fa_pitchers_spring(min_ip=args.ip, top_n=args.top)
