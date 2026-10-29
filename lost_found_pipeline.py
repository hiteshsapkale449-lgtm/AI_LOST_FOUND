
import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
YOLO_SCRIPT = PROJECT_DIR / "vision" / "yolo_detect.py"
MATCH_SCRIPT = PROJECT_DIR / "vision" / "main.py"


def run_pipeline(query, dataset, limit):
    query_path = Path(query)
    if not query_path.is_absolute():
        query_path = PROJECT_DIR / query_path

    dataset_path = Path(dataset)
    if not dataset_path.is_absolute():
        dataset_path = PROJECT_DIR / dataset_path

    if not query_path.is_file():
        print(f"ERROR: Lost-item image not found: {query_path}")
        return

    if not dataset_path.is_dir():
        print(f"ERROR: Dataset folder not found: {dataset_path}")
        return

    # Step 1: Run YOLO object detection.
    print("\nSTEP 1: YOLO object detection")

    yolo_command = [
        sys.executable,
        str(YOLO_SCRIPT),
        "--source",
        str(query_path)
    ]

    yolo_result = subprocess.run(
        yolo_command,
        cwd=str(PROJECT_DIR)
    )

    if yolo_result.returncode != 0:
        print("YOLO returned an error. Check the output above.")
        return

    # Step 2: Run OpenCV image matching.
    print("\nSTEP 2: OpenCV image matching")

    match_command = [
        sys.executable,
        str(MATCH_SCRIPT),
        "--query",
        str(query_path),
        "--dataset",
        str(dataset_path),
        "--limit",
        str(limit)
    ]

    match_result = subprocess.run(
        match_command,
        cwd=str(PROJECT_DIR)
    )

    if match_result.returncode != 0:
        print("Image matching returned an error.")
        return

    print("\nPipeline finished.")
    print("YOLO output folder: results/yolo")
    print("Matching CSV: results/matches.csv")
    print("YOLO CSV: results/yolo_detections.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run YOLO and OpenCV for Lost and Found"
    )

    parser.add_argument(
        "--query",
        default="uploads/lost.jpg"
    )

    parser.add_argument(
        "--dataset",
        default="dataset/extracted"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=3200
    )

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    run_pipeline(args.query, args.dataset, args.limit)
