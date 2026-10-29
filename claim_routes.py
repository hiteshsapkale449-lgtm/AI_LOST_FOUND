import re
from difflib import SequenceMatcher
from flask import Blueprint, jsonify, request, session

from database import get_db


claim_bp = Blueprint("claims", __name__)

ALLOWED_STATUSES = {"pending", "approved", "rejected"}


def get_logged_in_user(connection):
    """Return the authenticated user, or None."""
    user_id = session.get("user_id")

    if user_id is None:
        return None

    return connection.execute(
        "SELECT id, name, email FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def check_answer_match(expected, claimant):
    """
    Check if the claimant's answer matches the finder's expected answer.
    Returns 1 if matched, 0 otherwise.
    """
    if not expected or not claimant:
        return 0

    norm_exp = re.sub(r"[^a-z0-9]", "", expected.lower())
    norm_cla = re.sub(r"[^a-z0-9]", "", claimant.lower())

    if not norm_exp or not norm_cla:
        return 0

    # 1. Exact normalized match
    if norm_exp == norm_cla:
        return 1

    # 2. Substring match (if reasonably long)
    if (len(norm_exp) >= 3 and norm_exp in norm_cla) or (len(norm_cla) >= 3 and norm_cla in norm_exp):
        return 1

    # 3. Fuzzy similarity ratio >= 0.8
    ratio = SequenceMatcher(None, norm_exp, norm_cla).ratio()
    if ratio >= 0.8:
        return 1

    return 0


@claim_bp.route("/", methods=["POST"])
def create_claim():
    """Submit a claim for an open found item."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    item_id = data.get("item_id")
    claim_details = data.get("claim_details")
    claimant_phone = (data.get("claimant_phone") or "").strip() or None
    claimant_meeting_pref = (data.get("claimant_meeting_preference") or "").strip() or None

    claimant_answer = data.get("claimant_answer", "")
    if isinstance(claimant_answer, str):
        claimant_answer = claimant_answer.strip()
    else:
        claimant_answer = ""

    if type(item_id) is not int or item_id <= 0:
        return jsonify({"error": "A valid item_id is required"}), 400

    if not isinstance(claim_details, str) or not claim_details.strip():
        return jsonify({"error": "Claim details are required"}), 400

    claim_details = claim_details.strip()

    if len(claim_details) < 8 or len(claim_details) > 1000:
        return jsonify({
            "error": "Claim details must be between 8 and 1000 characters"
        }), 400

    connection = get_db()

    try:
        user = get_logged_in_user(connection)

        if user is None:
            return jsonify({"error": "Login required to submit a claim"}), 401

        item = connection.execute(
            """
            SELECT id, type, status, user_id, verification_question, verification_answer
            FROM items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()

        if item is None:
            return jsonify({"error": "Item not found"}), 404

        if item["type"] != "found":
            return jsonify({
                "error": "Claims can only be submitted for found items"
            }), 400

        if item["status"] != "open":
            return jsonify({
                "error": "This item is no longer open for claims"
            }), 409

        if item["user_id"] == user["id"]:
            return jsonify({
                "error": "You cannot submit a claim for your own found item"
            }), 403

        # Check whether the verification question answers match
        expected_answer = item["verification_answer"]
        answer_matched = check_answer_match(expected_answer, claimant_answer)

        cursor = connection.execute(
            """
            INSERT INTO claims (
                item_id,
                claimant_name,
                claimant_email,
                claim_details,
                claimant_answer,
                answer_matched,
                claimant_phone,
                claimant_meeting_preference
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                user["name"],
                user["email"],
                claim_details,
                claimant_answer or None,
                answer_matched,
                claimant_phone,
                claimant_meeting_pref,
            ),
        )

        connection.commit()

        return jsonify({
            "message": "Claim submitted successfully",
            "claim_id": cursor.lastrowid,
            "item_id": item_id,
            "status": "pending",
            "answer_matched": bool(answer_matched),
        }), 201

    except Exception:
        connection.rollback()
        claim_bp.logger.exception("Could not submit claim")
        return jsonify({"error": "Could not submit claim"}), 500

    finally:
        connection.close()


@claim_bp.route("/", methods=["GET"])
def get_claims():
    """List claims only for found items owned by the logged-in user."""
    status = request.args.get("status")

    if status and status not in ALLOWED_STATUSES:
        return jsonify({"error": "Invalid claim status"}), 400

    connection = get_db()

    try:
        user = get_logged_in_user(connection)

        if user is None:
            return jsonify({"error": "Login required to view claims"}), 401

        query = """
            SELECT
                claims.id,
                claims.item_id,
                claims.claimant_name,
                claims.claimant_email,
                claims.claimant_phone,
                claims.claimant_meeting_preference,
                claims.claim_details,
                claims.claimant_answer,
                claims.answer_matched,
                claims.founder_phone,
                claims.founder_meeting_info,
                claims.status,
                claims.review_note,
                claims.created_at,
                claims.reviewed_at,
                items.title AS item_title,
                items.location AS item_location,
                items.verification_question,
                items.verification_answer
            FROM claims
            JOIN items ON items.id = claims.item_id
            WHERE items.user_id = ?
              AND items.type = 'found'
        """
        parameters = [user["id"]]

        if status:
            query += " AND claims.status = ?"
            parameters.append(status)

        query += " ORDER BY claims.created_at DESC"

        rows = connection.execute(query, parameters).fetchall()

        return jsonify([dict(row) for row in rows]), 200

    finally:
        connection.close()


@claim_bp.route("/my", methods=["GET"])
def get_my_claims():
    """Return all claims submitted by the logged-in user with founder contact info."""
    connection = get_db()

    try:
        user = get_logged_in_user(connection)

        if user is None:
            return jsonify({"error": "Login required to view your claims"}), 401

        rows = connection.execute(
            """
            SELECT
                claims.id,
                claims.item_id,
                claims.claimant_name,
                claims.claimant_email,
                claims.claimant_phone,
                claims.claimant_meeting_preference,
                claims.claim_details,
                claims.claimant_answer,
                claims.answer_matched,
                claims.status,
                claims.review_note,
                claims.founder_phone,
                claims.founder_meeting_info,
                claims.created_at,
                claims.reviewed_at,
                items.title AS item_title,
                items.location AS item_location,
                items.image_path AS item_image_path,
                founder.name AS founder_name,
                founder.email AS founder_email
            FROM claims
            JOIN items ON items.id = claims.item_id
            LEFT JOIN users AS founder ON founder.id = items.user_id
            WHERE claims.claimant_email = ?
            ORDER BY claims.created_at DESC
            """,
            (user["email"],),
        ).fetchall()

        return jsonify([dict(row) for row in rows]), 200

    finally:
        connection.close()


@claim_bp.route("/<int:claim_id>/review", methods=["PATCH"])
def review_claim(claim_id):
    """Allow only the found-item owner to approve or reject a claim and share handover contact info."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    status = data.get("status")
    review_note = data.get("review_note", "")
    founder_phone = (data.get("founder_phone") or "").strip() or None
    founder_meeting_info = (data.get("founder_meeting_info") or "").strip() or None

    if status not in ("approved", "rejected"):
        return jsonify({
            "error": "Status must be approved or rejected"
        }), 400

    if not isinstance(review_note, str):
        return jsonify({"error": "Review note must be text"}), 400

    review_note = review_note.strip()

    if len(review_note) > 1000:
        return jsonify({
            "error": "Review note must be 1000 characters or fewer"
        }), 400

    connection = get_db()

    try:
        user = get_logged_in_user(connection)

        if user is None:
            return jsonify({"error": "Login required to review claims"}), 401

        claim = connection.execute(
            """
            SELECT
                claims.id,
                claims.item_id,
                claims.status,
                items.user_id AS item_owner_id,
                items.status AS item_status,
                items.type AS item_type
            FROM claims
            JOIN items ON items.id = claims.item_id
            WHERE claims.id = ?
            """,
            (claim_id,),
        ).fetchone()

        if claim is None:
            return jsonify({"error": "Claim not found"}), 404

        if (
            claim["item_type"] != "found"
            or claim["item_owner_id"] != user["id"]
        ):
            return jsonify({
                "error": "Only the owner of this found item can review its claims"
            }), 403

        if claim["status"] != "pending":
            return jsonify({
                "error": "Only pending claims can be reviewed"
            }), 409

        if status == "approved":
            if claim["item_status"] != "open":
                return jsonify({
                    "error": "This item is no longer open for claims"
                }), 409

            connection.execute(
                """
                UPDATE items
                SET status = 'resolved'
                WHERE id = ?
                  AND user_id = ?
                  AND type = 'found'
                  AND status = 'open'
                """,
                (claim["item_id"], user["id"]),
            )

            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                connection.rollback()
                return jsonify({
                    "error": "The item could not be resolved"
                }), 409

            # Once one claim is approved, reject other pending claims
            # for the same item.
            connection.execute(
                """
                UPDATE claims
                SET status = 'rejected',
                    review_note = 'Another claim was approved',
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE item_id = ?
                  AND id != ?
                  AND status = 'pending'
                """,
                (claim["item_id"], claim_id),
            )

        connection.execute(
            """
            UPDATE claims
            SET status = ?,
                review_note = ?,
                founder_phone = ?,
                founder_meeting_info = ?,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'pending'
            """,
            (status, review_note, founder_phone, founder_meeting_info, claim_id),
        )

        connection.commit()

        return jsonify({
            "message": "Claim reviewed successfully",
            "claim_id": claim_id,
            "status": status,
            "founder_phone": founder_phone,
            "founder_meeting_info": founder_meeting_info,
        }), 200

    except Exception:
        connection.rollback()
        claim_bp.logger.exception("Could not review claim")
        return jsonify({"error": "Could not review claim"}), 500

    finally:
        connection.close()
