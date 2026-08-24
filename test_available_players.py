from data.repositories.players_repo import get_available_players

available = get_available_players()

print(f"Available Players: {len(available)}")
print()
print(available.head(20))