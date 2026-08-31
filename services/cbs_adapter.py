# cbs_adapter.py
# Add the parent directory to sys.path so Python can find 'scripts'
#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

#from scripts.cbs_adapter import CBSTeam



class CBSPlayer:

    def __init__(self, row):

        self.id = row["provider_player_id"]

        self.name = row["player_name"]

        self.position = row["position"]

        self.projected_points = (
            row["projected_points"] or 0
        )

        self.avg_points = (
            row["average_points"] or 0
        )

        self.lineupSlot = (
            row["roster_position"] or "BE"
        )

        self.injuryStatus = ""



class CBSTeam:

    def __init__(self, roster_df):

        self.roster = []

        for _, row in roster_df.iterrows():
            self.roster.append(
                CBSPlayer(row)
            )