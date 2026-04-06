from harvester import OttoneuScraper
import pandas as pd

scraper = OttoneuScraper()
hitters, pitchers = scraper.get_roster()

print(f"Total hitters: {len(hitters)}")
if 'IsMinors' in hitters.columns:
    minors = hitters[hitters['IsMinors'] == True]
    print(f"Hitters marked as Minors ({len(minors)}):")
    if not minors.empty:
        print(minors[['Name', 'Team', 'IsMinors']])
else:
    print("No hitters marked as Minors.")

for name in ['Zac Veen', 'Luis Pena', 'Logan O\'Hoppe', 'Lars Nootbaar']:
    p = hitters[hitters['Name'].str.contains(name, na=False)]
    if not p.empty:
        row = p.iloc[0].to_dict()
        print(f"\n{name} data: Team={row['Team']}, IsMinors={row.get('IsMinors', False)}, Injured={row.get('Injured', False)}")
    else:
        print(f"\n{name} not found in hitters.")
