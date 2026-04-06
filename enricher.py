import pandas as pd
import json
import os
import logging
from harvester import OttoneuScraper
from crosswalks import normalize_name

logger = logging.getLogger(__name__)


class BaseEnricher:
    """
    Shared projection-loading and player-matching logic for both hitter
    and pitcher enrichers. Subclasses implement `projection_filename` and
    `enrich_roster()`.
    """
    _projection_cache = {}  # Keyed by filename — shared across all subclasses

    def __init__(self, league_id=1077, team_id=7582, projection_system="steamer"):
        self.scraper = OttoneuScraper(league_id, team_id)
        self.projection_system = projection_system.lower()

    @property
    def projection_filename(self):
        raise NotImplementedError

    def fetch_projections(self):
        cache_key = self.projection_filename
        if cache_key in BaseEnricher._projection_cache:
            return BaseEnricher._projection_cache[cache_key].copy()

        logger.info(f"Loading {self.projection_system.upper()} projections from {self.projection_filename}...")
        try:
            with open(self.projection_filename, "r") as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            BaseEnricher._projection_cache[cache_key] = df
            return df.copy()
        except FileNotFoundError:
            raise Exception(
                f"Projection file '{self.projection_filename}' not found. "
                "Run 'uv run python fetch_statcast.py' first."
            )

    def _build_indexes(self, projections):
        """
        Builds two O(1) lookup dicts from the projections DataFrame.
        Returns (by_fgid, by_name) where:
          by_fgid  = {str(playerid): Series}
          by_name  = {normalized_name: Series}  (first occurrence wins)
        """
        projections = projections.copy()
        projections['norm_name'] = projections['PlayerName'].apply(normalize_name)
        by_fgid = {str(r['playerid']): r for _, r in projections.iterrows()}
        by_name = {}
        for _, r in projections.iterrows():
            nn = r['norm_name']
            if nn not in by_name:
                by_name[nn] = r
        return by_fgid, by_name

    def _match_player(self, row, by_fgid, by_name):
        """
        Returns the matched projection row (Series) or None.
        Prefers FGID match; falls back to normalized name.
        """
        fgid = str(row.get('FGID', ''))
        if fgid and fgid not in ('nan', ''):
            m = by_fgid.get(fgid)
            if m is not None:
                return m
        return by_name.get(normalize_name(str(row.get('Name', ''))))


class OttoneuEnricher(BaseEnricher):

    @property
    def projection_filename(self):
        return f"projections-{self.projection_system}.json"

    def enrich_roster(self):
        hitters, _ = self.scraper.get_roster()
        projections = self.fetch_projections()

        # Initialize projection columns
        for col in ['playerid', 'PA_y', 'R_y', 'HR_y', 'RBI_y', 'SB_y', 'AVG_y', 'xMLBAMID']:
            hitters[col] = None

        by_fgid, by_name = self._build_indexes(projections)

        for idx, row in hitters.iterrows():
            m = self._match_player(row, by_fgid, by_name)
            if m is not None:
                hitters.at[idx, 'playerid']  = m['playerid']
                hitters.at[idx, 'PA_y']      = m['PA']
                hitters.at[idx, 'R_y']       = m['R']
                hitters.at[idx, 'HR_y']      = m['HR']
                hitters.at[idx, 'RBI_y']     = m['RBI']
                hitters.at[idx, 'SB_y']      = m['SB']
                hitters.at[idx, 'AVG_y']     = m['AVG']
                hitters.at[idx, 'xMLBAMID']  = m['xMLBAMID']

        # Zebras hitter efficiency score — three improvements vs. original formula:
        #   1. Consistent denominator: AVG coefficient changed from 100 to 89
        #      (reflects H/PA = AVG × AB/PA ≈ AVG × 0.89 rather than mixing H/AB with counting/PA)
        #   2. SB weighted 1.5× to reflect category scarcity in 5×5 Roto
        #      (stolen bases are meaningfully harder to replace than R/HR/RBI at league scale)
        #   3. PA normalization retained — for two starters with the same PA/game,
        #      per-PA rate correctly ranks daily expected quality
        pa  = hitters['PA_y'].fillna(1).astype(float).replace(0, 1)
        r   = hitters['R_y'].fillna(0).astype(float)
        hr  = hitters['HR_y'].fillna(0).astype(float)
        rbi = hitters['RBI_y'].fillna(0).astype(float)
        sb  = hitters['SB_y'].fillna(0).astype(float)
        avg = hitters['AVG_y'].fillna(0).astype(float)
        hitters['Score'] = ((r + hr + rbi + sb * 1.5) / pa * 100) + (avg * 89)

        return hitters.sort_values(by='Score', ascending=False)


if __name__ == "__main__":
    enricher = OttoneuEnricher()
    hitters = enricher.enrich_roster()
    print("Enriched Hitters (Top 10 by Score):")
    print(hitters[['Name', 'POS', 'PA_y', 'Score']].head(10))
