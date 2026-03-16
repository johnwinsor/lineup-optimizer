import re
import unicodedata

class TeamCrosswalk:
    # MLB StatsAPI -> Ottoneu/FanGraphs
    MLB_TO_OTTONEU = {
        'CWS': 'CHW',
        'KC': 'KCR',
        'WSH': 'WAS',
        'SD': 'SDP',
        'SF': 'SFG',
        'AZ': 'ARI',
        'TB': 'TBR',
        'ANA': 'LAA', # Historical/Alternate
        'FLA': 'MIA'  # Historical
    }

    # Ottoneu/FanGraphs -> MLB StatsAPI
    OTTONEU_TO_MLB = {v: k for k, v in MLB_TO_OTTONEU.items()}

    @classmethod
    def to_ottoneu(cls, mlb_abb):
        if not mlb_abb: return ""
        return cls.MLB_TO_OTTONEU.get(mlb_abb, mlb_abb)

    @classmethod
    def to_mlb(cls, ott_abb):
        if not ott_abb: return ""
        return cls.OTTONEU_TO_MLB.get(ott_abb, ott_abb)

class PlayerCrosswalk:
    # Manual Name Mappings: Ottoneu/FanGraphs Name -> MLB/Steamer Name
    # Only needed if normalization doesn't solve it.
    NAME_MAP = {
        'Pete Alonso': 'Peter Alonso',
        'Cedric Mullins II': 'Cedric Mullins',
        'Michael Chavis': 'Mike Chavis',
        'Kike Hernandez': 'Enrique Hernandez',
        'Ha-Seong Kim': 'Ha-seong Kim',
        'Jung Hoo Lee': 'Jung-hoo Lee',
        'Hyeseong Kim': 'Hye-seong Kim',
        'Yordan Alvarez': 'Yordan \u00c1lvarez'
    }

    @classmethod
    def get_name_map(cls, name):
        return cls.NAME_MAP.get(name, name)

def normalize_name(name):
    """
    Strips accents, removes suffixes (Jr, Sr, III), and converts to lowercase.
    """
    if not name or not isinstance(name, str):
        return ""
    
    # Remove accents
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    
    # Remove suffixes (Jr, Sr, II, III, etc)
    name = re.sub(r'(\s+(Jr\.|Sr\.|II|III|IV|V))$', '', name, flags=re.IGNORECASE)
    
    # Clean whitespace and lowercase
    return name.strip().lower()

def get_team_ottoneu(mlb_abb):
    return TeamCrosswalk.to_ottoneu(mlb_abb)

def get_team_mlb(ott_abb):
    return TeamCrosswalk.to_mlb(ott_abb)
