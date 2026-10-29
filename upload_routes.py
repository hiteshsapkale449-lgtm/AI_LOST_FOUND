import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, current_app
from PIL import Image, UnidentifiedImageError

upload_bp = Blueprint("upload", __name__)

ALLOWED_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp"
}


@upload_bp.route("/", methods=["POST"])
def upload_image():
    if "image" not in request.files:
        return jsonify({
            "error": "Image file is required"
        }), 400

    file = request.files["image"]

    if not file.filename:
        return jsonify({
            "error": "No file selected"
        }), 400

    try:
        image = Image.open(file.stream)
        image.verify()

        image_format = image.format

        if image_format not in ALLOWED_FORMATS:
            return jsonify({
                "error": "Only JPEG, PNG and WebP are supported"
            }), 400

        extension = ALLOWED_FORMATS[image_format]
        filename = f"{uuid.uuid4().hex}{extension}"

        file.stream.seek(0)

        upload_path = Path(
            current_app.config["UPLOAD_FOLDER"]
        ) / filename

        file.save(upload_path)

        return jsonify({
            "message": "Image uploaded",
            "image_path": f"uploads/{filename}"
        }), 201

    except (UnidentifiedImageError, OSError):
        return jsonify({
            "error": "Invalid image file"
        }), 400