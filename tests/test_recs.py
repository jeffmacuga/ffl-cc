# test_recommendations.py

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from services.recommendation_service import get_recommendations

data = get_recommendations()

print("\nRoster Needs")
print(data["roster_needs"])

print("\nRecommendations")
print(
    data["recommendations"].head(25)
)