# MLB Park Factors for the 2025 Season
# Based on Statcast/FanGraphs projections where 100 is neutral.
# Factors > 100 favor hitters, < 100 favor pitchers.

PARK_FACTORS = {
    "Coors Field": 115,
    "Oriole Park at Camden Yards": 117,
    "Camden Yards": 117,
    "Sutter Health Park": 110,
    "Dodger Stadium": 108,
    "Fenway Park": 107,
    "George M. Steinbrenner Field": 106,
    "Comerica Park": 105,
    "Wrigley Field": 104,
    "Nationals Park": 104,
    "Yankee Stadium": 104,
    "Citizens Bank Park": 104,
    "Rogers Centre": 103,
    "Great American Ball Park": 103,
    "Chase Field": 103,
    "Target Field": 102,
    "Angel Stadium": 101,
    "Truist Park": 101,
    "Kauffman Stadium": 101,
    "Progressive Field": 100,
    "Globe Life Field": 100,
    "American Family Field": 99,
    "Rate Field": 99,
    "Guaranteed Rate Field": 99,
    "Daikin Park": 98,
    "Minute Maid Park": 98,
    "Petco Park": 98,
    "PNC Park": 98,
    "Oracle Park": 97,
    "loanDepot park": 97,
    "Citi Field": 96,
    "Busch Stadium": 96,
    "T-Mobile Park": 95,
    "Oakland Coliseum": 93, # 2024 baseline if used
    "Tropicana Field": 93,  # 2024 baseline if used
}

def get_park_factor(venue_name):
    """
    Returns the overall run-scoring park factor for a given venue.
    Defaults to 100 if the venue is not found.
    """
    return PARK_FACTORS.get(venue_name, 100)

def get_park_multiplier(venue_name):
    """
    Returns a multiplier (e.g. 1.05 for a 105 factor).
    """
    factor = get_park_factor(venue_name)
    return factor / 100.0
