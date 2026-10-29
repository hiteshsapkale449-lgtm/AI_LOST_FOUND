
import argparse
import csv
from pathlib import Path

from ultralytics import YOLO


# Project paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_DIR / "results"
OUTPUT_DIR = RESULTS_DIR / "yolo"
CSV_FILE = RESULTS_DIR / "yolo_detections.csv"

# Create output folders automatically
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Pretrained YOLO model.
# The model weights download automatically on the first run.
MODEL_NAME = "yolo11n.pt"

model = YOLO(MODEL_NAME)


def resolve_path(path_text):
    """Convert a relative path into a project-relative path."""
    path = Path(path_text)

    if not path.is_absolute():
        path = PROJECT_DIR / path

    return path.resolve()


def detect_objects(source_path):
    """Detect objects in one image or all images in a folder."""
    source = resolve_path(source_path)

    if not source.exists():
        print(f"ERROR: Path not found: {source}")
        return

    if source.is_file():
        allowed_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

        if source.suffix.lower() not in allowed_extensions:
            print("ERROR: Please provide a JPG, JPEG, PNG, BMP, or WEBP image.")
            return

    print(f"\nInput: {source}")
    print("Starting YOLO object detection...")

    try:
        predictions = model.predict(
            source=str(source),
            conf=0.25,
            save=True,
            save_txt=True,
            project=str(RESULTS_DIR),
            name="yolo",
            exist_ok=True,
            verbose=False
        )
    except Exception as error:
        print(f"Detection failed: {error}")
        return

    csv_rows = []
    total_objects = 0

    for result in predictions:
        image_name = Path(result.path).name
        boxes = result.boxes

        print(f"\nImage: {image_name}")

        if boxes is None or len(boxes) == 0:
            print("No objects detected.")
            continue

        for box in boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            label = result.names[class_id]

            coordinates = box.xyxy[0].tolist()
            x1, y1, x2, y2 = [round(value, 2) for value in coordinates]

            total_objects += 1

            print(
                f"Object: {label} | "
                f"Confidence: {confidence:.2%} | "
                f"Box: ({x1}, {y1}, {x2}, {y2})"
            )

            csv_rows.append([
                image_name,
                label,
                round(confidence, 4),
                x1,
                y1,
                x2,
                y2
            ])

    # Save all detected objects to a CSV file.
    write_header = not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0

    with CSV_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if write_header:
            writer.writerow([
                "image_name",
                "object_name",
                "confidence",
                "x1",
                "y1",
                "x2",
                "y2"
            ])

        writer.writerows(csv_rows)

    print("\nDetection finished.")
    print(f"Total detected objects: {total_objects}")
    print(f"Annotated images folder: {OUTPUT_DIR}")
    print(f"Detection CSV: {CSV_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="YOLO object detection for the Lost and Found project"
    )

    parser.add_argument(
        "--source",
        default="test_images/lost.jpg",
        help="Path to one image or a folder of images"
    )

    args = parser.parse_args()
    detect_objects(args.source)
