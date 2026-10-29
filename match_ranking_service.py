
import math


# Initial weights for the five matching features.
# These are configurable starting values, not trained weights.
MATCH_WEIGHTS = {
    "image_similarity": 0.35,
    "text_similarity": 0.30,
    "location_score": 0.15,
    "date_score": 0.10,
    "category_match": 0.10,
}


def calculate_match_ranking(scores):
    """
    Calculate an overall match-ranking score from 0 to 100.

    Missing scores are excluded, and the remaining weights
    are normalized so they add up to 1.

    This is a ranking score, NOT a probability.
    """
    if not isinstance(scores, dict):
        raise TypeError("Scores must be provided as a dictionary.")

    weighted_total = 0.0
    available_weight = 0.0
    included_features = []
    excluded_features = []

    for feature, weight in MATCH_WEIGHTS.items():
        value = scores.get(feature)

        # Ignore missing scores.
        if value is None:
            excluded_features.append(feature)
            continue

        # Reject invalid scores.
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            raise ValueError(
                f"{feature} must be a number between 0 and 1, "
                "or None."
            )

        weighted_total += value * weight
        available_weight += weight
        included_features.append(feature)

    if available_weight == 0:
        return {
            "ranking_score": None,
            "ranking_score_out_of": 100,
            "score_type": "weighted_match_ranking_not_probability",
            "included_features": [],
            "excluded_features": excluded_features,
        }

    ranking_score = (
        weighted_total / available_weight
    ) * 100

    return {
        "ranking_score": round(ranking_score, 2),
        "ranking_score_out_of": 100,
        "score_type": "weighted_match_ranking_not_probability",
        "included_features": included_features,
        "excluded_features": excluded_features,
    }
