from pathlib import Path

from flask import Blueprint, jsonify, request, session

from database import get_db

item_bp = Blueprint("items", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = (BASE_DIR / "uploads").resolve()


def logged_in_user_id():
    """Return the logged-in user's ID, or None."""
    user_id = session.get("user_id")

    if isinstance(user_id, int) and user_id > 0:
        return user_id

    return None


def valid_image_path(image_path):
    """Allow only existing image files directly inside uploads."""
    if not isinstance(image_path, str) or not image_path.startswith("uploads/"):
        return False

    filename = image_path[len("uploads/"):]

    if not filename or Path(filename).name != filename:
        return False

    if Path(filename).suffix.lower() not in {
        ".jpg", ".jpeg", ".png", ".webp"
    }:
        return False

    try:
        resolved_path = (UPLOADS_DIR / filename).resolve()
        return (
            resolved_path.parent == UPLOADS_DIR
            and resolved_path.is_file()
        )
    except (OSError, ValueError):
        return False


# Create a lost or found report (login required)
@item_bp.route("/", methods=["POST"])
def create_item():
    user_id = logged_in_user_id()

    if user_id is None:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    item_type = data.get("type")
    title = data.get("title")
    image_path = data.get("image_path")

    if item_type not in ("lost", "found"):
        return jsonify({"error": "Type must be lost or found"}), 400

    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "Title is required"}), 400

    if image_path is not None and not valid_image_path(image_path):
        return jsonify({"error": "Invalid image_path or image file not found"}), 400

    optional_fields = (
        "description", "category", "location", "date_lost_found",
        "verification_question", "verification_answer"
    )

    for field in optional_fields:
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            return jsonify({"error": f"{field} must be a string"}), 400

    v_question = (data.get("verification_question") or "").strip() or None
    v_answer = (data.get("verification_answer") or "").strip() or None

    connection = get_db()

    try:
        cursor = connection.execute(
            """
            INSERT INTO items (
                user_id, type, title, description, category,
                location, date_lost_found, image_path,
                verification_question, verification_answer
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                item_type,
                title.strip(),
                data.get("description"),
                data.get("category"),
                data.get("location"),
                data.get("date_lost_found"),
                image_path,
                v_question,
                v_answer,
            ),
        )

        connection.commit()

        return jsonify({
            "message": "Item created",
            "item_id": cursor.lastrowid,
        }), 201

    except Exception:
        connection.rollback()
        return jsonify({"error": "Could not create item"}), 500

    finally:
        connection.close()


# Get all reports (public - hides secret verification_answer)
@item_bp.route("/", methods=["GET"])
def get_items():
    current_uid = logged_in_user_id()
    connection = get_db()

    try:
        rows = connection.execute(
            "SELECT * FROM items ORDER BY created_at DESC"
        ).fetchall()

        items = []
        for row in rows:
            d = dict(row)
            # Only item owner can see the expected verification_answer
            if current_uid is None or d.get("user_id") != current_uid:
                d.pop("verification_answer", None)
            items.append(d)

        return jsonify(items), 200

    finally:
        connection.close()


# Get one report by ID (public - hides secret verification_answer)
@item_bp.route("/<int:item_id>", methods=["GET"])
def get_item(item_id):
    current_uid = logged_in_user_id()
    connection = get_db()

    try:
        row = connection.execute(
            "SELECT * FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()

        if row is None:
            return jsonify({"error": "Item not found"}), 404

        d = dict(row)
        if current_uid is None or d.get("user_id") != current_uid:
            d.pop("verification_answer", None)

        return jsonify(d), 200

    finally:
        connection.close()


# Update a report's status (owner login required)
@item_bp.route("/<int:item_id>/status", methods=["PATCH"])
def update_status(item_id):
    user_id = logged_in_user_id()

    if user_id is None:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    status = data.get("status")

    if status not in ("open", "resolved"):
        return jsonify({"error": "Invalid status"}), 400

    connection = get_db()

    try:
        item = connection.execute(
            "SELECT id, user_id FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()

        if item is None:
            return jsonify({"error": "Item not found"}), 404

        if item["user_id"] != user_id:
            return jsonify({
                "error": "You are not authorized to update this item"
            }), 403

        connection.execute(
            "UPDATE items SET status = ? WHERE id = ? AND user_id = ?",
            (status, item_id, user_id),
        )

        connection.commit()

        return jsonify({
            "message": "Status updated",
            "item_id": item_id,
            "status": status,
        }), 200

    except Exception:
        connection.rollback()
        return jsonify({"error": "Could not update item status"}), 500

    finally:
        connection.close()
