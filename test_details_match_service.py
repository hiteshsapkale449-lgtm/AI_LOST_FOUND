
from services.details_match_service import compare_item_details


lost_item = {
    "location": "College Library",
    "date_lost_found": "2026-10-21",
    "category": "Accessories",
}

found_item = {
    "location": "College Library",
    "date_lost_found": "2026-10-21",
    "category": "Accessories",
}

result = compare_item_details(lost_item, found_item)

print("Location score:", result["location_score"])
print("Date score:", result["date_score"])
print("Category match:", result["category_match"])

assert result["location_score"] == 1.0
assert result["date_score"] == 1.0
assert result["category_match"] == 1.0

print("\nAll location, date, and category tests passed!")

