from espn_api.football import League

league = League(
    league_id=465649962,
    year=2026,
    swid="{E8418BEB-2939-480F-818B-EB2939E80F06}",
    espn_s2="AEAtk3BaOcADlcYivYJmH7p2BvHMp4vpKCmVn%2B6aucUeZN3pYFIeecyM%2Fst66dXM0tvd9%2FMudnDZva8KkNLrB57N1sMa0MaVtOybvbSe8OdIf3SWLuB9Hzk5UQI7LeHOUVj2lQVEwSa6Q%2F85csfri%2FlU8RIc5gTNfkkrZzLbI2L8owzcUKxYwxPSuHI%2FKlBwx9ji%2BXJahc3FfVKI0UCZ2jNmKjJc37FzQ7z1qqxL5RQrwFHHks4gS1qrrrpvKwOZGDBNNPCR9Q3lzdV7lI4uQkTfmo%2Bw7%2FaoyQ74%2FPxj%2FmHtl2V6PZ1%2FsltH6TcZ65k7SS%2FuKk1nQsW0vislxG61jELHQ%2FbcAAYwxMGWVz35AOvRe0hYAXGz8Ie707pcgXCic1M%3D"

)

for pick in league.draft[:5]:
    print(pick.__dict__)