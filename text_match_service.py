import re
from difflib import SequenceMatcher


def normalize_text(text):
    """Clean and normalize text before comparison."""
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def text_similarity(text1, text2):
    """
    Compare two pieces of text.

    Returns a score from 0.0 to 1.0.
    This is a text similarity score, not a probability.
    """
    normalized1 = normalize_text(text1)
    normalized2 = normalize_text(text2)

    if not normalized1 or not normalized2:
        return 0.0

    if normalized1 == normalized2:
        return 1.0

    return SequenceMatcher(
        None,
        normalized1,
        normalized2
    ).ratio()


def compare_item_text(lost_item, found_item):
    """
    Compare the titles and descriptions of a lost item
    and a found item.
    """
    lost_title = normalize_text(lost_item.get("title", ""))
    found_title = normalize_text(found_item.get("title", ""))

    lost_description = normalize_text(
        lost_item.get("description", "")
    )
    found_description = normalize_text(
        found_item.get("description", "")
    )

    title_score = text_similarity(lost_title, found_title)

    description_score = text_similarity(
        lost_description,
        found_description
    )

    # Give the title 40% weight and the description 60% weight.
    combined_score = (
        0.4 * title_score
        + 0.6 * description_score
    )

    return {
        "text_similarity": round(combined_score, 4),
        "title_similarity": round(title_score, 4),
        "description_similarity": round(description_score, 4),
        "score_type": "text_similarity_not_probability",
    }
