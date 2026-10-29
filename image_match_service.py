from pathlib import Path
from threading import Lock

from handoff.inference import ImageMatcher


BASE_DIR = Path(__file__).resolve().parent.parent

# Load the trained model only when it is first needed.
_matcher = None
_matcher_lock = Lock()


def get_image_matcher():
    """Return one reusable instance of the trained V4 image matcher."""
    global _matcher

    if _matcher is None:
        with _matcher_lock:
            if _matcher is None:
                _matcher = ImageMatcher()

    return _matcher


def compare_images(image_path_1, image_path_2):
    """
    Compare two images using the trained V4 model.

    Returns cosine similarity and the model's threshold-based decision.
    Similarity is NOT a probability.
    """
    path_1 = Path(image_path_1).resolve()
    path_2 = Path(image_path_2).resolve()

    # Only compare images stored inside this project's uploads folder.
    uploads_dir = (BASE_DIR / "uploads").resolve()

    for path in (path_1, path_2):
        if not path.is_relative_to(uploads_dir):
            raise ValueError("Images must be inside the uploads folder.")

        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path.name}")

    matcher = get_image_matcher()
    return matcher.score(path_1, path_2)
