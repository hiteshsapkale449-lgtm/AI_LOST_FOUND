
from datetime import date
from difflib import SequenceMatcher
import re


def normalize_location(location):
    """Normalize a location string for comparison."""
    if not isinstance(location, str):
        return ""

    location = location.lower().strip()
    location = re.sub(r"[^a-z0-9\s]", " ", location)
    location = re.sub(r"\s+", " ", location)

    return location


def calculate_location_score(location1, location2):
    """
    Compare two location descriptions.
    Returns a score between 0.0 and 1.0.
    """
    loc1 = normalize_location(location1)
    loc2 = normalize_location(location2)

    if not loc1 or not loc2:
        return None

    if loc1 == loc2:
        return 1.0

    return round(
        SequenceMatcher(None, loc1, loc2).ratio(),
        4
    )


def calculate_date_score(date1, date2):
    """
    Compare lost and found dates.

    Same day: 1.0
    Each additional day apart reduces the score.
    Dates more than 30 days apart: 0.0

    Returns None if either date is missing or invalid.
    """
    if not date1 or not date2:
        return None

    try:
        parsed_date1 = date.fromisoformat(str(date1)[:10])
        parsed_date2 = date.fromisoformat(str(date2)[:10])
    except (ValueError, TypeError):
        return None

    days_apart = abs((parsed_date1 - parsed_date2).days)

    if days_apart > 30:
        return 0.0

    return round(1 - (days_apart / 30), 4)


def normalize_category(category):
    """Normalize a category value for comparison."""
    if not isinstance(category, str):
        return ""

    category = category.lower().strip()
    category = re.sub(r"[^a-z0-9\s]", " ", category)
    category = re.sub(r"\s+", " ", category)

    return category


def calculate_category_match(category1, category2):
    """
    Compare item categories.

    Returns:
        1.0 for matching categories
        0.0 for different categories
        None if either category is missing
    """
    cat1 = normalize_category(category1)
    cat2 = normalize_category(category2)

    if not cat1 or not cat2:
        return None

    return 1.0 if cat1 == cat2 else 0.0


def compare_item_details(lost_item, found_item):
    """
    Calculate location, date, and category scores
    for a lost item and a found item.
    """
    location_score = calculate_location_score(
        lost_item.get("location"),
        found_item.get("location"),
    )

    date_score = calculate_date_score(
        lost_item.get("date_lost_found"),
        found_item.get("date_lost_found"),
    )

    category_match = calculate_category_match(
        lost_item.get("category"),
        found_item.get("category"),
    )

    return {
        "location_score": location_score,
        "date_score": date_score,
        "category_match": category_match,
    }