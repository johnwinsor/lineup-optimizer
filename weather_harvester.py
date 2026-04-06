import requests
from bs4 import BeautifulSoup
import re
import time
import logging

logger = logging.getLogger(__name__)

WEATHER_TTL_SECONDS = 3600  # Re-fetch at most once per hour

class WeatherHarvester:
    _cache = None
    _cache_time = 0.0

    def __init__(self):
        self.url = "https://www.rotowire.com/baseball/weather.php"
        self.team_map = {
            'Diamondbacks': 'ARI', 'Braves': 'ATL', 'Orioles': 'BAL', 'Red Sox': 'BOS',
            'Cubs': 'CHC', 'White Sox': 'CHW', 'Reds': 'CIN', 'Guardians': 'CLE',
            'Rockies': 'COL', 'Tigers': 'DET', 'Astros': 'HOU', 'Royals': 'KCR',
            'Angels': 'LAA', 'Dodgers': 'LAD', 'Marlins': 'MIA', 'Brewers': 'MIL',
            'Twins': 'MIN', 'Mets': 'NYM', 'Yankees': 'NYY', 'Athletics': 'ATH',
            'Phillies': 'PHI', 'Pirates': 'PIT', 'Padres': 'SDP', 'Giants': 'SFG',
            'Mariners': 'SEA', 'Cardinals': 'STL', 'Rays': 'TBR', 'Rangers': 'TEX',
            'Blue Jays': 'TOR', 'Nationals': 'WAS'
        }

    def get_weather_report(self):
        now = time.time()
        if WeatherHarvester._cache is not None and (now - WeatherHarvester._cache_time) < WEATHER_TTL_SECONDS:
            return WeatherHarvester._cache

        try:
            response = requests.get(self.url, timeout=10)
            if response.status_code != 200:
                return {}
            
            soup = BeautifulSoup(response.content, "html.parser")
            weather_boxes = soup.find_all('div', class_='weather-box')
            
            report = {}
            for box in weather_boxes:
                teams_div = box.find('div', class_='weather-box__teams')
                if not teams_div: continue
                
                visit_team_name = teams_div.find('a', class_='is-visit').find('div').text.strip()
                home_team_name = teams_div.find('a', class_='is-home').find('div').text.strip()
                
                home_abb = self.team_map.get(home_team_name)
                if not home_abb: continue
                
                weather_div = box.find('div', class_='weather-box__weather')
                condition = weather_div.find('div', class_='heading').text.strip()
                details = weather_div.find('div', class_='text-80').text.strip()
                
                # Parse details for rain risk and wind
                rain_risk = 0
                rain_match = re.search(r'(\d+)% chance of precipitation', details)
                if rain_match:
                    rain_risk = int(rain_match.group(1))
                
                wind_speed = 0
                wind_dir = "None"
                wind_match = re.search(r'(\d+) MPH wind blowing ([\w\s-]+)', details)
                if wind_match:
                    wind_speed = int(wind_match.group(1))
                    raw_dir = wind_match.group(2).lower()
                    
                    if "out" in raw_dir:
                        wind_dir = "Out"
                    elif "in" in raw_dir:
                        wind_dir = "In"
                    elif "right to left" in raw_dir or "r-l" in raw_dir:
                        wind_dir = "R-L"
                    elif "left to right" in raw_dir or "l-r" in raw_dir:
                        wind_dir = "L-R"
                    else:
                        wind_dir = "Cross"
                
                # Check for "In" or "Out" or "Left to Right" etc.
                # Rotowire often says "blowing out", "blowing in", "blowing right to left"
                
                report[home_abb] = {
                    'home_team': home_team_name,
                    'visit_team': visit_team_name,
                    'condition': condition,
                    'rain_risk': rain_risk,
                    'wind_speed': wind_speed,
                    'wind_dir': wind_dir,
                    'is_dome': "dome" in details.lower() or "roof closed" in details.lower()
                }
                
            WeatherHarvester._cache = report
            WeatherHarvester._cache_time = now
            return report
        except Exception as e:
            logger.warning(f"Weather harvest failed: {e}")
            return WeatherHarvester._cache if WeatherHarvester._cache is not None else {}

if __name__ == "__main__":
    harvester = WeatherHarvester()
    report = harvester.get_weather_report()
    for team, data in report.items():
        print(f"{data['visit_team']} @ {data['home_team']} ({team}): {data['condition']}, Rain: {data['rain_risk']}%, Wind: {data['wind_speed']} MPH {data['wind_dir']}")
