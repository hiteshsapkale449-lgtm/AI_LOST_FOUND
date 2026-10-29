"""
Example adapter for backend integration with the V4 image matcher.

Keep this file beside inference.py. The matcher is initialized lazily once
per Python process and reused for subsequent image comparisons.
"""

from inference import ImageMatcher

_matcher = None


def get_matcher():
    """Return the process-level matcher, initializing it only when needed."""
    global _matcher
    if _matcher is None:
        _matcher = ImageMatcher()
    return _matcher


def compare_images(lost_image_path, found_image_path):
    """
    Compare two image paths and return the V4 inference result.

    similarity is cosine similarity, NOT a probability.
    predicted_match is a candidate-screening decision, not confirmation.
    """
    return get_matcher().score(lost_image_path, found_image_path)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Test the V4 backend adapter on two image files."
    )
    parser.add_argument("image1", help="First image path")
    parser.add_argument("image2", help="Second image path")
    args = parser.parse_args()

    result = compare_images(args.image1, args.image2)
    print(json.dumps(result, indent=2))
