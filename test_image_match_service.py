from pathlib import Path

from services.image_match_service import compare_images


BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"

image1 = UPLOADS_DIR / "bc98a671762346b1816949560537956c.jpg"
image2 = UPLOADS_DIR / "59ca8807beb4414c9e430da16adef160.jpg"

try:
    result = compare_images(image1, image2)

    print("\nAI image comparison successful!")
    print("Image 1:", image1.name)
    print("Image 2:", image2.name)
    print("Similarity:", result["similarity"])
    print("Threshold:", result["threshold"])
    print("Predicted match:", result["predicted_match"])
    print("Score type:", result["score_type"])
    print("Device:", result["device"])

except Exception as error:
    print("\nAI image comparison failed.")
    print(type(error).__name__ + ":", error)
