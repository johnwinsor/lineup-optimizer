import requests

def check_player_spring_statcast(person_id):
    # Try fetching aggregate spring statcast for a specific player
    # gameType='S' is Spring Training
    url = f"https://statsapi.mlb.com/api/v1/people/{person_id}/stats?stats=statcastHitting&group=hitting&season=2026&gameType=S"
    
    print(f"Fetching Spring StatCast for ID {person_id}...")
    r = requests.get(url)
    if r.status_code != 200:
        print(f"Failed: {r.status_code}")
        return
    
    data = r.json()
    if 'stats' in data and data['stats']:
        splits = data['stats'][0].get('splits', [])
        if splits:
            stat = splits[0]['stat']
            print(f"Aggregate Spring Stats: {stat}")
        else:
            print("No spring StatCast splits found.")
    else:
        print("No spring StatCast data returned.")

if __name__ == "__main__":
    # Test with Mike Trout (545361)
    check_player_spring_statcast(545361)
