import json
import pandas as pd
from harvester import OttoneuScraper
from crosswalks import normalize_name

def analyze_spring_training():
    # 1. Load Spring Training Data
    with open('spring_training_hitters.json', 'r') as f:
        spring_data = json.load(f)
    
    spring_df = pd.DataFrame(spring_data)
    
    # 2. Get Zurich Zebras Roster
    scraper = OttoneuScraper()
    zebras_hitters, _ = scraper.get_roster()
    zebras_names = set(zebras_hitters['Name'].apply(normalize_name).tolist())

    # 3. Process Spring Data
    # Filter for reasonable PA sample (e.g. min 10 PA) to avoid 1-for-1 outliers
    top_spring = spring_df[spring_df['PA'] >= 10].copy()
    top_spring['wRC+'] = pd.to_numeric(top_spring['wRC+'], errors='coerce')
    top_spring = top_spring.sort_values(by='wRC+', ascending=False).head(20)

    # 4. Map Ownership
    results = []
    for _, row in top_spring.iterrows():
        name = row['PlayerName']
        norm_name = normalize_name(name)
        
        fantasy_team = "Zurich Zebras" if norm_name in zebras_names else "OTHER / FA"
        
        results.append({
            'Player': name,
            'Age': row['Age'],
            'wRC+': f"{row['wRC+']:.1f}",
            'PA': int(row['PA']),
            'Fantasy Team': fantasy_team
        })

    # 5. Output Table
    print("\nTOP 20 SPRING TRAINING HITTERS BY wRC+ (Min 10 PA)")
    print("-" * 80)
    df_results = pd.DataFrame(results)
    print(df_results.to_string(index=False))

if __name__ == "__main__":
    analyze_spring_training()
