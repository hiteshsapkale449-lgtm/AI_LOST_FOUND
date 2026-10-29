
import csv
from pathlib import Path

from vision.image_preprocess import SUPPORTED_EXTENSIONS
from vision.image_model import extract_features, compare_features


def find_dataset_images(dataset_dir):
    """Find supported images inside the dataset and subfolders."""
    root = Path(dataset_dir)

    if not root.is_dir():
        raise FileNotFoundError(
            f"Dataset folder not found: {root.resolve()}"
        )

    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def search_dataset(query_image, dataset_dir, max_images=1000):
    """Compare one query photo with images in the dataset."""
    query_path = Path(query_image)

    if not query_path.is_file():
        raise FileNotFoundError(
            f"Query image not found: {query_path.resolve()}"
        )

    query_features = extract_features(query_path)
    results = []
    checked = 0

    for candidate_path in find_dataset_images(dataset_dir):

        # Do not compare the query image with itself.
        if candidate_path.resolve() == query_path.resolve():
            continue

        # Stop after the requested number of comparisons.
        if max_images > 0 and checked >= max_images:
            break

        try:
            candidate_features = extract_features(candidate_path)

            scores = compare_features(
                query_features,
                candidate_features
            )

            results.append({
                "image_path": str(candidate_path),
                "category_folder": candidate_path.parent.name,
                "score": scores["score"],
                "image_score": scores["image_score"],
                "color_score": scores["color_score"]
            })

            checked += 1

            if checked % 10 == 0:
                print(f"Images compared: {checked}")

        except (OSError, ValueError, RuntimeError) as error:
            print(f"Skipped {candidate_path}: {error}")

    # Highest similarity score first.
    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results, checked


def save_results(results, output_path):
    """Save matching results in a CSV spreadsheet."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "image_path",
        "category_folder",
        "score",
        "image_score",
        "color_score"
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"Results saved to: {output_path.resolve()}")
