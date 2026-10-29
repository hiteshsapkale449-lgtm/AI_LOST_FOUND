import sqlite3
from pathlib import Path


# Find the project directory
BASE_DIR = Path(__file__).resolve().parent

# Database location
DB_DIR = BASE_DIR / "instance"
DB_PATH = DB_DIR / "lost_found.db"


def get_db():
    """Connect to the SQLite database."""
    DB_DIR.mkdir(exist_ok=True)

    connection = sqlite3.connect(DB_PATH)

    # Access rows using column names
    connection.row_factory = sqlite3.Row

    # Enable foreign key enforcement
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_db():
    """Initialize database tables and safely update the schema."""
    connection = get_db()

    try:
        schema_path = BASE_DIR / "schema.sql"

        # Read the database schema
        with open(schema_path, "r", encoding="utf-8") as file:
            schema = file.read()

        # Create existing tables if they do not exist
        connection.executescript(schema)

        # 1. Update matches table if ranking_score is missing
        columns = connection.execute(
            "PRAGMA table_info(matches)"
        ).fetchall()
        existing_match_columns = {column["name"] for column in columns}

        if "ranking_score" not in existing_match_columns:
            connection.execute(
                """
                ALTER TABLE matches
                ADD COLUMN ranking_score REAL
                """
            )

        # 2. Update items table with verification question & answer
        item_columns = connection.execute(
            "PRAGMA table_info(items)"
        ).fetchall()
        existing_item_columns = {column["name"] for column in item_columns}

        if "verification_question" not in existing_item_columns:
            connection.execute(
                """
                ALTER TABLE items
                ADD COLUMN verification_question TEXT
                """
            )

        if "verification_answer" not in existing_item_columns:
            connection.execute(
                """
                ALTER TABLE items
                ADD COLUMN verification_answer TEXT
                """
            )

        # 3. Create claims table if it does not already exist
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                claimant_name TEXT NOT NULL,
                claimant_email TEXT NOT NULL,
                claim_details TEXT NOT NULL,
                claimant_answer TEXT,
                answer_matched INTEGER DEFAULT 0,
                claimant_phone TEXT,
                claimant_meeting_preference TEXT,
                founder_phone TEXT,
                founder_meeting_info TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'approved', 'rejected')),
                review_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                FOREIGN KEY(item_id) REFERENCES items(id)
            )
            """
        )

        # Update claims table columns if missing
        claim_columns = connection.execute(
            "PRAGMA table_info(claims)"
        ).fetchall()
        existing_claim_columns = {column["name"] for column in claim_columns}

        columns_to_add = [
            ("claimant_answer", "TEXT"),
            ("answer_matched", "INTEGER DEFAULT 0"),
            ("claimant_phone", "TEXT"),
            ("claimant_meeting_preference", "TEXT"),
            ("founder_phone", "TEXT"),
            ("founder_meeting_info", "TEXT"),
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_claim_columns:
                connection.execute(
                    f"ALTER TABLE claims ADD COLUMN {col_name} {col_type}"
                )

        # Save database changes
        connection.commit()

        print("Database initialized successfully.")
        print("Claims table, verification columns, and contact handover columns are ready.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
