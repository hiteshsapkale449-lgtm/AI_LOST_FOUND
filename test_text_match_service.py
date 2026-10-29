from services.text_match_service import (
    text_similarity,
    compare_item_text,
)


print("\nTEST 1: Identical text")

score = text_similarity(
    "Black leather wallet",
    "Black leather wallet"
)

print("Similarity:", score)
assert score == 1.0


print("\nTEST 2: Similar text")

score = text_similarity(
    "Black leather wallet with an ID card",
    "Black leather wallet found near the library"
)

print("Similarity:", score)
assert 0.0 < score < 1.0


print("\nTEST 3: Empty text")

score = text_similarity("", "")

print("Similarity:", score)
assert score == 0.0


print("\nTEST 4: Compare lost and found item details")

lost_item = {
    "title": "Black wallet",
    "description": "Black leather wallet with an ID card",
}

found_item = {
    "title": "Black leather wallet",
    "description": "Black wallet found near the college library",
}

result = compare_item_text(lost_item, found_item)

print("Title similarity:", result["title_similarity"])
print("Description similarity:", result["description_similarity"])
print("Combined similarity:", result["text_similarity"])
print("Score type:", result["score_type"])

assert 0.0 <= result["text_similarity"] <= 1.0

print("\nAll text-matching tests passed!")
