import requests
import pandas as pd

def check_spring_leaderboard():
    # Attempt to fetch spring training statcast leaderboard
    # Season 2026, Group: hitting, SeasonType: 'S' (Spring Training)
    url = "https://statsapi.mlb.com/api/v1/stats/leaderboard?sportId=1&season=2026&group=hitting&statType=statcast&seasonType=S&limit=1000"
    
    print("Fetching Spring Training StatCast Leaderboard...")
    r = requests.get(url)
    if r.status_code != 200:
        print(f"Failed to fetch: {r.status_code}")
        return
    
    data = r.json()
    leaders = data.get('leaderboard', [])
    print(f"Found {len(leaders)} players with StatCast data.\n")
    
    if leaders:
        # Check first entry to see available fields
        sample = leaders[0]
        print(f"Sample Player: {sample.get('person', {}).get('fullName')}")
        print(f"Stats Keys: {list(sample.get('stat', {}).keys())}")
        
        # Display top 5 by Avg EV
        top_5 = sorted(leaders, key=lambda x: x.get('stat', {}).get('exitVelocity', {}).get('avg', 0), reverse=True)[:5]
        for p in top_5:
            s = p['stat']
            print(f"{p['person']['fullName']}: Avg EV: {s.get('exitVelocity', {}).get('avg')} | Max EV: {s.get('exitVelocity', {}).get('max')} | Hard Hit%: {s.get('hardHitDegree')}")

if __name__ == "__main__":
    check_spring_leaderboard()
