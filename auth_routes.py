from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

auth_bp = Blueprint("auth", __name__)


# Register a user
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not all(isinstance(x, str) and x.strip()
               for x in [name, email, password]):
        return jsonify({
            "error": "Name, email and password are required"
        }), 400

    if len(password) < 8:
        return jsonify({
            "error": "Password must be at least 8 characters"
        }), 400

    password_hash = generate_password_hash(password)

    connection = get_db()

    try:
        connection.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (name.strip(), email.strip().lower(), password_hash)
        )

        connection.commit()

        return jsonify({
            "message": "Registration successful"
        }), 201

    except Exception:
        connection.rollback()

        return jsonify({
            "error": "Registration failed. Email may already exist."
        }), 400

    finally:
        connection.close()


# Log in
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": "Email and password required"}), 400

    connection = get_db()

    try:
        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),)
        ).fetchone()

        if user is None or not check_password_hash(
            user["password_hash"], password
        ):
            return jsonify({
                "error": "Invalid email or password"
            }), 401

        session["user_id"] = user["id"]

        return jsonify({
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        }), 200

    finally:
        connection.close()


# Check current session
@auth_bp.route("/me", methods=["GET"])
def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "logged_in": False,
            "user": None
        }), 200

    connection = get_db()

    try:
        user = connection.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if user is None:
            session.clear()
            return jsonify({
                "logged_in": False,
                "user": None
            }), 200

        return jsonify({
            "logged_in": True,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        }), 200

    finally:
        connection.close()


# Log out
@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()

    return jsonify({
        "message": "Logged out successfully"
    }), 200
