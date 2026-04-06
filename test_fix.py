from daily_engine import DailyEngine
from datetime import datetime
import pandas as pd
import numpy as np

for system in ['steamer', 'atc']:
    print(f"\n--- Testing system: {system.upper()} ---")
    engine = DailyEngine(projection_system=system)
    target_date = datetime.now().strftime("%Y-%m-%d")
    
    hitters = engine.enricher.enrich_roster()
    pena_idx = hitters[hitters['Name'].str.contains('Luis Pena', na=False)].index[0]
    pena_row = hitters.loc[pena_idx]
    
    print(f"Luis Pena in enriched roster: xMLBAMID={pena_row.get('xMLBAMID')}")
    
    # Simulate the daily engine ID lookup
    mlb_id = pena_row.get('xMLBAMID')
    if not mlb_id or pd.isna(mlb_id):
        print("xMLBAMID missing, calling get_mlb_id...")
        mlb_id = engine.harvester.get_mlb_id(pena_row['Name'], team_abb=pena_row.get('Team'))
    
    print(f"Resulting MLB ID: {mlb_id}")
    
    if mlb_id:
        statuses = engine.harvester.get_player_statuses([mlb_id])
        print(f"Status from MLB API: {statuses.get(int(mlb_id))}")
    
    projections = engine._process_daily_multipliers(hitters, target_date)
    pena_final = projections[projections['Name'].str.contains('Luis Pena', na=False)].iloc[0]
    print(f"Final Breakdown: {pena_final['Breakdown']}")
