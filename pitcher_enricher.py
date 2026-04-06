from enricher import BaseEnricher


class PitcherEnricher(BaseEnricher):

    @property
    def projection_filename(self):
        return f"projections-{self.projection_system}-pit.json"

    def enrich_roster(self):
        _, pitchers = self.scraper.get_roster()
        projections = self.fetch_projections()

        # Initialize projection columns
        for col in ['playerid', 'K/9_y', 'BB/9_y', 'ERA_y', 'WHIP_y', 'W_y', 'xMLBAMID']:
            pitchers[col] = None

        by_fgid, by_name = self._build_indexes(projections)

        for idx, row in pitchers.iterrows():
            m = self._match_player(row, by_fgid, by_name)
            if m is not None:
                pitchers.at[idx, 'playerid']  = m.get('playerid')
                pitchers.at[idx, 'K/9_y']    = m.get('K/9')
                pitchers.at[idx, 'BB/9_y']   = m.get('BB/9')
                pitchers.at[idx, 'ERA_y']     = m.get('ERA')
                pitchers.at[idx, 'WHIP_y']    = m.get('WHIP')
                pitchers.at[idx, 'W_y']       = m.get('W')
                pitchers.at[idx, 'xMLBAMID']  = m.get('xMLBAMID')

        # Zebras pitcher efficiency score V1:
        # (K/9 * 0.4) + (5.0 - ERA) + (1.5 - WHIP) * 2.0
        pitchers['Score'] = (
            (pitchers['K/9_y'].fillna(0).astype(float) * 0.4) +
            (5.0 - pitchers['ERA_y'].fillna(5.0).astype(float)) +
            (1.5 - pitchers['WHIP_y'].fillna(1.5).astype(float)) * 2.0
        )

        return pitchers.sort_values(by='Score', ascending=False)


if __name__ == "__main__":
    enricher = PitcherEnricher()
    pitchers = enricher.enrich_roster()
    print("Enriched Pitchers (Top 10 by Score):")
    print(pitchers[['Name', 'Team', 'ERA_y', 'WHIP_y', 'K/9_y', 'Score']].head(10))
