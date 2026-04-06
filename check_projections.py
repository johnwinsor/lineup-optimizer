import pandas as pd
import json
import unicodedata

def normalize(name):
    return unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')

for system in ['steamer', 'atc']:
    print(f"\n--- {system.upper()} ---")
    with open(f"projections-{system}.json", "r") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df['NormName'] = df['PlayerName'].apply(normalize)
    pena = df[df['NormName'].str.contains('Pena', na=False)]
    if not pena.empty:
        print(f"Players with 'Pena' (normalized) in {system} projections:")
        print(pena[['PlayerName', 'playerid', 'xMLBAMID']])
    else:
        print(f"No players with 'Pena' found in {system} projections.")
