
import cv2
import numpy as np
import argparse
import csv
from pathlib import Path

# Project folders
PROJECT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def get_image_histogram(image_path):
    """Create a color histogram for an image."""
    image = cv2.imread(str(image_path))

    if image is None:
        return None

    image = cv2.resize(image, (256, 256))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    histogram = cv2.calcHist(
        [hsv], [0, 1, 2], None,
        [8, 8, 8], [0, 180, 0, 256, 0, 256]
    )

    cv2.normalize(histogram, histogram)
    return histogram


def compare_images(query_histogram, candidate_path):
    """Return a similarity score between 0 and 100."""
    candidate_histogram = get_image_histogram(candidate_path)

    if candidate_histogram is None:
        return None

    distance = cv2.compareHist(
        query_histogram,
        candidate_histogram,
        cv2.HISTCMP_BHATTACHARYYA
    )

    similarity = max(0.0, 1.0 - distance) * 100
    return round(similarity, 2)


def find_matches(query_path, dataset_path, limit=50):
    query_path = Path(query_path)
    dataset_path = Path(dataset_path)

    if not query_path.is_absolute():
        query_path = PROJECT_DIR / query_path

    if not dataset_path.is_absolute():
        dataset_path = PROJECT_DIR / dataset_path

    if not query_path.is_file():
        print(f"ERROR: Query image not found: {query_path}")
        print("Put a test image at test_images/lost.jpg.")
        return

    if not dataset_path.is_dir():
        print(f"ERROR: Dataset folder not found: {dataset_path}")
        return

    query_histogram = get_image_histogram(query_path)

    if query_histogram is None:
        print("ERROR: OpenCV could not read the query image.")
        return

    print("Lost and Found image matching started.")
    print(f"Query image: {query_path}")
    print(f"Dataset folder: {dataset_path}")
    print("Scanning dataset images...")

    results = []
    scanned = 0

    # Process one image at a time to support large datasets.
    for image_path in dataset_path.rglob("*"):
        if not image_path.is_file():
            continue

        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        if image_path.resolve() == query_path.resolve():
            continue

        scanned += 1

        score = compare_images(query_histogram, image_path)

        if score is not None:
            results.append((score, image_path))

        if scanned % 500 == 0:
            print(f"Scanned {scanned} images...")

    if not results:
        print("No readable dataset images found.")
        print("Check whether the ZIP file has been extracted.")
        return

    results.sort(key=lambda item: item[0], reverse=True)
    top_results = results[:limit]

    output_file = RESULTS_DIR / "matches.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Rank", "Image Path", "Similarity Score (%)"])

        for rank, (score, image_path) in enumerate(top_results, start=1):
            writer.writerow([rank, str(image_path), score])

    print(f"\nImages scanned: {scanned}")
    print(f"Matches found: {len(results)}")
    print(f"\nTop {len(top_results)} matching images:")

    for rank, (score, image_path) in enumerate(top_results, start=1):
        print(f"{rank}. {image_path} | Similarity: {score}%")

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OpenCV Lost and Found image matcher"
    )

    parser.add_argument(
        "--query",
        default="test_images/lost.jpg",
        help="Path to the lost item's image"
    )

    parser.add_argument(
        "--dataset",
        default="dataset",
        help="Path to the extracted dataset folder"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of matching results to display"
    )

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    find_matches(args.query, args.dataset, args.limit)
