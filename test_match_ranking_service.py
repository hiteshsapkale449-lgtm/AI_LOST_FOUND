from services.match_ranking_service import calculate_match_ranking


print("\nTEST 1: Calculate a score using all five features")

scores = {
    "image_similarity": 0.9999999403953552,
    "text_similarity": 0.5914,
    "location_score": 0.2857,
    "date_score": 1.0,
    "category_match": 0.0,
}

result = calculate_match_ranking(scores)

print("Ranking score:", result["ranking_score"], "/ 100")
print("Score type:", result["score_type"])
print("Included features:", result["included_features"])

assert result["ranking_score"] is not None
assert 0 <= result["ranking_score"] <= 100
assert len(result["included_features"]) == 5


print("\nTEST 2: Handle a missing feature")

scores_with_missing_data = {
    "image_similarity": 0.8,
    "text_similarity": 0.6,
    "location_score": None,
    "date_score": 1.0,
    "category_match": 1.0,
}

result = calculate_match_ranking(scores_with_missing_data)

print("Ranking score:", result["ranking_score"], "/ 100")
print("Excluded features:", result["excluded_features"])

assert result["ranking_score"] is not None
assert "location_score" in result["excluded_features"]


print("\nTEST 3: Handle all missing features")

result = calculate_match_ranking({
    "image_similarity": None,
    "text_similarity": None,
    "location_score": None,
    "date_score": None,
    "category_match": None,
})

print("Ranking score:", result["ranking_score"])

assert result["ranking_score"] is None


print("\nAll match-ranking tests passed!")
