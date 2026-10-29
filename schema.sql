CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT NOT NULL
        CHECK(type IN ('lost', 'found')),
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    location TEXT,
    date_lost_found TEXT,
    image_path TEXT,
    verification_question TEXT,
    verification_answer TEXT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK(status IN ('open', 'resolved')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(id)
);


CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lost_item_id INTEGER NOT NULL,
    found_item_id INTEGER NOT NULL,

    probability REAL,
    text_similarity REAL,
    image_similarity REAL,
    location_score REAL,
    date_score REAL,
    category_match REAL,
    ranking_score REAL,

    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(lost_item_id) REFERENCES items(id),
    FOREIGN KEY(found_item_id) REFERENCES items(id),

    UNIQUE(lost_item_id, found_item_id)
);


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
);
