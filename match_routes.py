import math
import re
from pathlib import Path

from flask import Blueprint, jsonify, request

from database import get_db
from services.image_match_service import compare_images
from services.text_match_service import compare_item_text
from services.details_match_service import compare_item_details
from services.match_ranking_service import calculate_match_ranking


match_bp = Blueprint("matches", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = (BASE_DIR / "uploads").resolve()


def resolve_uploaded_image(image_path):
    """Resolve a safe image path inside the uploads directory."""
    if not isinstance(image_path, str) or not image_path.strip():
        return None

    relative_path = Path(image_path)

    if relative_path.is_absolute():
        return None

    if not relative_path.parts or relative_path.parts[0] != "uploads":
        return None

    full_path = (BASE_DIR / relative_path).resolve()

    if not full_path.is_relative_to(UPLOADS_DIR):
        return None

    if not full_path.is_file():
        return None

    return full_path


def validate_item_ids(data):
    """Validate the lost and found item IDs."""
    if not isinstance(data, dict):
        return None, None, (
            jsonify({"error": "JSON object required"}),
            400,
        )

    lost_id = data.get("lost_item_id")
    found_id = data.get("found_item_id")

    if (
        type(lost_id) is not int
        or type(found_id) is not int
        or lost_id <= 0
        or found_id <= 0
    ):
        return None, None, (
            jsonify({"error": "Valid positive item IDs are required"}),
            400,
        )

    if lost_id == found_id:
        return None, None, (
            jsonify({
                "error": "Lost and found items must be different"
            }),
            400,
        )

    return lost_id, found_id, None


def validate_scores(data):
    """Validate optional matching scores between 0 and 1."""
    probability = data.get("probability")

    if probability is not None:
        if (
            isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not math.isfinite(probability)
            or not 0 <= probability <= 1
        ):
            return None, (
                jsonify({
                    "error": "Probability must be between 0 and 1"
                }),
                400,
            )

    fields = [
        "text_similarity",
        "image_similarity",
        "location_score",
        "date_score",
        "category_match",
    ]

    scores = {}

    for field in fields:
        value = data.get(field)

        if value is None:
            scores[field] = None
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 1
        ):
            return None, (
                jsonify({
                    "error": f"{field} must be between 0 and 1"
                }),
                400,
            )
        else:
            scores[field] = value

    scores["probability"] = probability

    return scores, None


def get_valid_item_pair(connection, lost_id, found_id):
    """Fetch and validate a lost item and a found item."""
    lost_item = connection.execute(
        """
        SELECT id, type, title, description, image_path,
               location, date_lost_found, category
        FROM items
        WHERE id = ?
        """,
        (lost_id,),
    ).fetchone()

    found_item = connection.execute(
        """
        SELECT id, type, title, description, image_path,
               location, date_lost_found, category
        FROM items
        WHERE id = ?
        """,
        (found_id,),
    ).fetchone()

    if lost_item is None or found_item is None:
        return None, None, (
            jsonify({"error": "One or both items do not exist"}),
            404,
        )

    if (
        lost_item["type"] != "lost"
        or found_item["type"] != "found"
    ):
        return None, None, (
            jsonify({
                "error": (
                    "First item must be lost and second must be found"
                )
            }),
            400,
        )

    return lost_item, found_item, None


def is_candidate_match(lost_item, found_item):
    """
    Check if a found item is a plausible candidate for matching against a lost item.
    Prevents comparing and returning completely unrelated objects (e.g. water bottles for a watch).
    """
    # 1. Both items have images: eligible for visual comparison
    if lost_item.get("image_path") and found_item.get("image_path"):
        return True

    lost_title = (lost_item.get("title") or "").lower().strip()
    found_title = (found_item.get("title") or "").lower().strip()

    lost_cat = (lost_item.get("category") or "").lower().strip()
    found_cat = (found_item.get("category") or "").lower().strip()

    stopwords = {
        "the", "and", "with", "for", "lost", "found", "near", "from",
        "having", "has", "this", "that", "item", "some", "someone", "color", "grey", "black", "blue"
    }

    lost_title_words = set(re.findall(r"\b[a-z0-9]{3,}\b", lost_title)) - stopwords
    found_title_words = set(re.findall(r"\b[a-z0-9]{3,}\b", found_title)) - stopwords

    # 2. Direct title keyword overlap (e.g. "watch" in both, or "wallet" in both)
    if lost_title_words and found_title_words and (lost_title_words & found_title_words):
        return True

    # 3. Direct title substring match (e.g. "watch" in "samsung watch")
    if (len(lost_title) >= 3 and lost_title in found_title) or (len(found_title) >= 3 and found_title in lost_title):
        return True

    # 4. Check descriptive words
    lost_desc = (lost_item.get("description") or "").lower().strip()
    found_desc = (found_item.get("description") or "").lower().strip()

    lost_desc_words = set(re.findall(r"\b[a-z0-9]{3,}\b", lost_desc)) - stopwords
    found_desc_words = set(re.findall(r"\b[a-z0-9]{3,}\b", found_desc)) - stopwords

    all_lost_words = lost_title_words | lost_desc_words
    all_found_words = found_title_words | found_desc_words

    shared_words = all_lost_words & all_found_words

    # Multiple shared descriptive keywords
    if len(shared_words) >= 2:
        return True

    # 5. Matching specific category AND at least 1 meaningful shared keyword
    cat_match = bool(lost_cat and found_cat and lost_cat == found_cat and lost_cat != "other")
    if cat_match and len(shared_words) >= 1:
        return True

    return False


def calculate_pair_scores(lost_item, found_item):
    """
    Calculate available matching features.

    Images are optional. If either item has no valid uploaded image,
    image_similarity remains None and the other features are still used.
    """
    lost_details = dict(lost_item)
    found_details = dict(found_item)

    text_result = compare_item_text(lost_details, found_details)
    details_result = compare_item_details(
        lost_details,
        found_details,
    )

    lost_image = resolve_uploaded_image(lost_item["image_path"])
    found_image = resolve_uploaded_image(found_item["image_path"])

    image_similarity = None
    image_threshold = None
    image_predicted_match = None
    image_score_type = None

    if lost_image is not None and found_image is not None:
        try:
            image_result = compare_images(lost_image, found_image)
            image_similarity = float(image_result["similarity"])
            image_threshold = image_result.get("threshold")
            image_predicted_match = image_result.get(
                "predicted_match"
            )
            image_score_type = image_result.get("score_type")
        except Exception:
            match_bp.logger.exception(
                "Image comparison failed for lost item %s and found item %s",
                lost_item["id"],
                found_item["id"],
            )

    scores = {
        "image_similarity": image_similarity,
        "text_similarity": text_result["text_similarity"],
        "location_score": details_result["location_score"],
        "date_score": details_result["date_score"],
        "category_match": details_result["category_match"],
    }

    ranking_result = calculate_match_ranking(scores)

    return {
        **scores,
        **ranking_result,
        "title_similarity": text_result["title_similarity"],
        "description_similarity": text_result[
            "description_similarity"
        ],
        "image_threshold": image_threshold,
        "image_predicted_match": image_predicted_match,
        "image_score_type": image_score_type,
    }


@match_bp.route("/", methods=["GET"])
def get_matches():
    """Return saved matches, including their ranking scores."""
    connection = get_db()

    try:
        rows = connection.execute(
            """
            SELECT
                matches.*,
                lost.title AS lost_title,
                found.title AS found_title
            FROM matches
            JOIN items AS lost
                ON matches.lost_item_id = lost.id
            JOIN items AS found
                ON matches.found_item_id = found.id
            ORDER BY matches.created_at DESC
            """
        ).fetchall()

        return jsonify([dict(row) for row in rows]), 200

    finally:
        connection.close()


@match_bp.route("/", methods=["POST"])
def save_match():
    """Save externally supplied matching scores."""
    data = request.get_json(silent=True)

    lost_id, found_id, error = validate_item_ids(data)

    if error:
        return error

    scores, error = validate_scores(data)

    if error:
        return error

    ranking_result = calculate_match_ranking(scores)

    connection = get_db()

    try:
        _, _, error = get_valid_item_pair(
            connection, lost_id, found_id
        )

        if error:
            return error

        connection.execute(
            """
            INSERT INTO matches (
                lost_item_id, found_item_id, probability,
                text_similarity, image_similarity, location_score,
                date_score, category_match, ranking_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lost_item_id, found_item_id)
            DO UPDATE SET
                probability = excluded.probability,
                text_similarity = excluded.text_similarity,
                image_similarity = excluded.image_similarity,
                location_score = excluded.location_score,
                date_score = excluded.date_score,
                category_match = excluded.category_match,
                ranking_score = excluded.ranking_score
            """,
            (
                lost_id,
                found_id,
                scores["probability"],
                scores["text_similarity"],
                scores["image_similarity"],
                scores["location_score"],
                scores["date_score"],
                scores["category_match"],
                ranking_result["ranking_score"],
            ),
        )

        connection.commit()

        return jsonify({
            "message": "Match saved successfully",
            "lost_item_id": lost_id,
            "found_item_id": found_id,
            **ranking_result,
        }), 201

    finally:
        connection.close()


@match_bp.route("/compare", methods=["POST"])
def compare_items():
    """Calculate available features and save the pair's ranking."""
    data = request.get_json(silent=True)

    lost_id, found_id, error = validate_item_ids(data)

    if error:
        return error

    connection = get_db()

    try:
        lost_item, found_item, error = get_valid_item_pair(
            connection, lost_id, found_id
        )

        if error:
            return error

        lost_details = dict(lost_item)
        found_details = dict(found_item)

    finally:
        connection.close()

    try:
        result = calculate_pair_scores(lost_details, found_details)
    except Exception:
        match_bp.logger.exception("Matching calculation failed")
        return jsonify({
            "error": "Matching calculation failed. Check server logs."
        }), 500

    connection = get_db()

    try:
        connection.execute(
            """
            INSERT INTO matches (
                lost_item_id, found_item_id, probability,
                image_similarity, text_similarity, location_score,
                date_score, category_match, ranking_score
            )
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lost_item_id, found_item_id)
            DO UPDATE SET
                probability = NULL,
                image_similarity = excluded.image_similarity,
                text_similarity = excluded.text_similarity,
                location_score = excluded.location_score,
                date_score = excluded.date_score,
                category_match = excluded.category_match,
                ranking_score = excluded.ranking_score
            """,
            (
                lost_id,
                found_id,
                result["image_similarity"],
                result["text_similarity"],
                result["location_score"],
                result["date_score"],
                result["category_match"],
                result["ranking_score"],
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return jsonify({
        "message": "Matching features calculated and saved",
        "lost_item_id": lost_id,
        "found_item_id": found_id,
        **result,
        "probability": None,
        "saved_to_database": True,
    }), 200


@match_bp.route("/ranked/<int:lost_item_id>", methods=["GET"])
def get_ranked_matches(lost_item_id):
    """
    Compare an open lost item against candidate open found items.
    Filters out completely unrelated objects and low-scoring noise.
    """
    connection = get_db()

    try:
        lost_item = connection.execute(
            """
            SELECT id, type, title, description, image_path,
                   location, date_lost_found, category, status
            FROM items
            WHERE id = ?
            """,
            (lost_item_id,),
        ).fetchone()

        if lost_item is None:
            return jsonify({"error": "Lost item not found"}), 404

        if lost_item["type"] != "lost":
            return jsonify({
                "error": "The requested item must be a lost item"
            }), 400

        if lost_item["status"] != "open":
            return jsonify({
                "lost_item_id": lost_item_id,
                "lost_item_title": lost_item["title"],
                "total_matches": 0,
                "ranking_type": "weighted_match_ranking_not_probability",
                "matches": [],
                "message": "This lost item is not open for matching.",
            }), 200

        found_items = connection.execute(
            """
            SELECT id, type, title, description, image_path,
                   location, date_lost_found, category, status,
                   verification_question
            FROM items
            WHERE type = 'found'
              AND status = 'open'
              AND id != ?
            ORDER BY created_at DESC
            """,
            (lost_item_id,),
        ).fetchall()

        lost_details = dict(lost_item)

        # Pre-filter candidate found items to avoid checking unrelated objects
        candidate_found_items = [
            f for f in found_items
            if is_candidate_match(lost_details, dict(f))
        ]

        if not candidate_found_items:
            return jsonify({
                "lost_item_id": lost_item_id,
                "lost_item_title": lost_item["title"],
                "total_matches": 0,
                "ranking_type": "weighted_match_ranking_not_probability",
                "matches": [],
                "message": "No matching candidate items found.",
            }), 200

        # Calculate and save a fresh score only for candidate found items.
        candidate_ids = []
        for found_row in candidate_found_items:
            found_details = dict(found_row)
            candidate_ids.append(found_details["id"])

            try:
                result = calculate_pair_scores(
                    lost_details,
                    found_details,
                )
            except Exception:
                match_bp.logger.exception(
                    "Could not rank lost item %s against found item %s",
                    lost_item_id,
                    found_row["id"],
                )
                continue

            connection.execute(
                """
                INSERT INTO matches (
                    lost_item_id, found_item_id, probability,
                    image_similarity, text_similarity, location_score,
                    date_score, category_match, ranking_score
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lost_item_id, found_item_id)
                DO UPDATE SET
                    probability = NULL,
                    image_similarity = excluded.image_similarity,
                    text_similarity = excluded.text_similarity,
                    location_score = excluded.location_score,
                    date_score = excluded.date_score,
                    category_match = excluded.category_match,
                    ranking_score = excluded.ranking_score
                """,
                (
                    lost_item_id,
                    found_row["id"],
                    result["image_similarity"],
                    result["text_similarity"],
                    result["location_score"],
                    result["date_score"],
                    result["category_match"],
                    result["ranking_score"],
                ),
            )

        connection.commit()

        # Query only matches for candidate items with a minimum relevance score (>= 40.0)
        placeholders = ",".join("?" for _ in candidate_ids)
        rows = connection.execute(
            f"""
            SELECT
                matches.*,
                found.title AS found_title,
                found.description AS found_description,
                found.category AS found_category,
                found.location AS found_location,
                found.verification_question
            FROM matches
            JOIN items AS found
                ON matches.found_item_id = found.id
            WHERE matches.lost_item_id = ?
              AND found.type = 'found'
              AND found.status = 'open'
              AND found.id IN ({placeholders})
              AND matches.ranking_score >= 40.0
            ORDER BY
                matches.ranking_score DESC,
                matches.created_at DESC
            """,
            [lost_item_id] + candidate_ids,
        ).fetchall()

        return jsonify({
            "lost_item_id": lost_item_id,
            "lost_item_title": lost_item["title"],
            "total_matches": len(rows),
            "ranking_type": "weighted_match_ranking_not_probability",
            "matches": [dict(row) for row in rows],
        }), 200

    finally:
        connection.close()
