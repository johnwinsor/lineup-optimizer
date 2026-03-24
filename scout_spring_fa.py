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

def analyze_fa_spring(min_pa=10, top_n=15, pos_filter=None):
    # 1. Load Spring Training Data
    spring_data = load_json_data('spring_training_hitters.json')
    if spring_data is None:
        print("Error: spring_training_hitters.json not found. Run spring_harvester.py first.")
        return
    
    spring_df = pd.DataFrame(spring_data)
    spring_df['PA'] = pd.to_numeric(spring_df['PA'], errors='coerce')
    spring_df['wRC+'] = pd.to_numeric(spring_df['wRC+'], errors='coerce')
    spring_df['PlayerName_Norm'] = spring_df['PlayerName'].apply(normalize_name)

    # 2. Get Zurich Zebras Roster (to exclude)
    scraper = OttoneuScraper()
    try:
        zebras_hitters, _ = scraper.get_roster()
        zebras_names = set(zebras_hitters['Name'].apply(normalize_name).tolist())
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

    # 4. Load ATC Projections for Comparison
    atc_data = load_json_data('projections-atc.json')
    atc_map = {} # norm_name -> atc_wrc
    if atc_data:
        for p in atc_data:
            name = normalize_name(p.get('PlayerName', ''))
            atc_map[name] = p.get('wRC+', 100)

    # 5. Filter for Free Agents
    fa_spring = spring_df[
        (spring_df['PlayerName_Norm'].isin(fa_map.keys())) & 
        (~spring_df['PlayerName_Norm'].isin(zebras_names)) &
        (spring_df['PA'] >= min_pa)
    ].copy()

    # Add FA info and ATC info
    fa_spring['OttoneuID'] = fa_spring['PlayerName_Norm'].map(lambda x: fa_map[x]['ottid'])
    fa_spring['Pos'] = fa_spring['PlayerName_Norm'].map(lambda x: fa_map[x]['Pos'])
    fa_spring['ATC_wRC+'] = fa_spring['PlayerName_Norm'].map(lambda x: atc_map.get(x, 100))
    fa_spring['Surge'] = fa_spring['wRC+'] - fa_spring['ATC_wRC+']

    # Positional Filter
    if pos_filter:
        fa_spring = fa_spring[fa_spring['Pos'].str.contains(pos_filter, case=False, na=False)]

    # 6. Sort and Display
    fa_spring = fa_spring.sort_values(by='wRC+', ascending=False).head(top_n)

    print(f"\nTOP {top_n} FREE AGENT HITTERS BY SPRING PERFORMANCE (Min {min_pa} PA)")
    if pos_filter:
        print(f"Filtering for Position: {pos_filter}")
    print("-" * 125)
    
    results = []
    for _, row in fa_spring.iterrows():
        ott_link = f"https://ottoneu.fangraphs.com/1077/playercard?id={row['OttoneuID']}"
        results.append({
            'Player': row['PlayerName'],
            'Pos': row['Pos'],
            'PA': int(row['PA']),
            'wRC+ (ST)': round(row['wRC+'], 1),
            'ATC wRC+': round(row['ATC_wRC+'], 1),
            'Surge': round(row['Surge'], 1),
            'AVG': round(row['AVG'], 3),
            'HR': int(row['HR']),
            'Ottoneu Link': ott_link
        })
    
    if not results:
        print("No players found matching criteria.")
        return

    df_results = pd.DataFrame(results)
    print(df_results.to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scout Free Agents based on Spring Training performance.")
    parser.add_argument("--pa", type=int, default=10, help="Minimum Plate Appearances (default: 10)")
    parser.add_argument("--top", type=int, default=15, help="Number of top players to show (default: 15)")
    parser.add_argument("--pos", type=str, default=None, help="Filter by position (e.g., SS, OF, C)")
    
    args = parser.parse_args()
    analyze_fa_spring(min_pa=args.pa, top_n=args.top, pos_filter=args.pos)
