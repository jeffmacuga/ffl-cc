import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.draft_service import draft_player

draft_player(
    player_name="TEST_PLAYER",
    position="WR",
    my_pick=True
)

print("Draft completed")