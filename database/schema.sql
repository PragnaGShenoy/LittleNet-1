#Instagram for kids,
#db name 

CREATE DATABASE safeconnect_db;


#login tables

#table 1

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,

    username VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,

    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,

    role VARCHAR(20) NOT NULL
        CHECK (role IN ('CHILD', 'PARENT')),

    age INTEGER,

    dob DATE,

    account_status VARCHAR(20) DEFAULT 'PENDING_APPROVAL'
        CHECK (account_status IN ('PENDING_APPROVAL', 'ACTIVE', 'REJECTED')),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

#table 2

CREATE TABLE parent_child_map (
    map_id SERIAL PRIMARY KEY,

    child_id INTEGER NOT NULL,

    parent_id INTEGER,

    parent_name VARCHAR(100) NOT NULL,

    parent_email VARCHAR(100) NOT NULL,

    verification_token VARCHAR(128),

    approval_token VARCHAR(128),

    approval_token_expires_at TIMESTAMP WITH TIME ZONE,

    approval_status VARCHAR(30) DEFAULT 'PENDING_PARENT_VERIFICATION',

    approved BOOLEAN DEFAULT FALSE,

    is_token_used BOOLEAN DEFAULT FALSE,

    rejection_reason TEXT,

    verified_parent_id INTEGER,

    approved_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_child
        FOREIGN KEY (child_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_parent
        FOREIGN KEY (parent_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

CREATE TABLE parent_verifications (
    verification_id SERIAL PRIMARY KEY,
    parent_user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    child_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    verification_provider VARCHAR(50) NOT NULL DEFAULT 'SANDBOX_MOCK',
    verification_status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (verification_status IN ('PENDING', 'VERIFIED', 'FAILED', 'MANUAL_REVIEW')),
    liveness_status VARCHAR(30) DEFAULT 'PENDING'
        CHECK (liveness_status IN ('PENDING', 'PASSED', 'FAILED')),
    face_match_status VARCHAR(30) DEFAULT 'PENDING'
        CHECK (face_match_status IN ('PENDING', 'MATCHED', 'MISMATCHED', 'FAILED')),
    document_type VARCHAR(50) DEFAULT 'AADHAAR_MOCK',
    masked_id VARCHAR(20),
    consent_given BOOLEAN DEFAULT FALSE,
    consent_timestamp TIMESTAMP WITH TIME ZONE,
    verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

#table 3

CREATE TABLE login_activity (
    login_id SERIAL PRIMARY KEY,

    user_id INTEGER NOT NULL,

    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    ip_address VARCHAR(100),

    device_info TEXT,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

#table 4

CREATE TABLE activity_logs (
    log_id SERIAL PRIMARY KEY,

    child_id INTEGER NOT NULL,

    activity_type VARCHAR(50),

    activity_data TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (child_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

#table 5

CREATE TABLE parent_notifications (
    notification_id SERIAL PRIMARY KEY,

    parent_id INTEGER NOT NULL,

    child_id INTEGER NOT NULL,

    notification_type VARCHAR(50),

    notification_message TEXT,

    is_read BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (parent_id)
        REFERENCES users(user_id),

    FOREIGN KEY (child_id)
        REFERENCES users(user_id)
);


#child profile tables

CREATE TABLE child_profiles (
    profile_id SERIAL PRIMARY KEY,

    child_id INTEGER NOT NULL UNIQUE,
    parent_id INTEGER,

    full_name VARCHAR(150) NOT NULL,
    date_of_birth DATE,
    age INTEGER,

    school_name VARCHAR(200),
    location VARCHAR(200),

    current_class VARCHAR(50),

    bio TEXT,

    profile_picture VARCHAR(500),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (child_id)
        REFERENCES users(user_id),

    FOREIGN KEY (parent_id)
        REFERENCES users(user_id)
);

CREATE TABLE child_skills (
    skill_id SERIAL PRIMARY KEY,

    child_id INTEGER NOT NULL,

    skill_name VARCHAR(100),

    FOREIGN KEY (child_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

CREATE TABLE child_interests (
    interest_id SERIAL PRIMARY KEY,

    child_id INTEGER NOT NULL,

    interest_name VARCHAR(100),

    FOREIGN KEY (child_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

CREATE TABLE child_ambitions (
    ambition_id SERIAL PRIMARY KEY,

    child_id INTEGER NOT NULL,

    ambition_name VARCHAR(100),

    FOREIGN KEY (child_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);


#post tables

CREATE TABLE posts(
    post_id SERIAL PRIMARY KEY,

    child_id INT NOT NULL,

    media_type VARCHAR(20) NOT NULL,

    media_path VARCHAR(500) NOT NULL,

    caption TEXT,

    content_category VARCHAR(100),

    safety_score NUMERIC(5,2),

    is_safe BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(child_id)
    REFERENCES users(user_id)
);



#followers table
CREATE TABLE followers (

    follower_id SERIAL PRIMARY KEY,

    child_id INT NOT NULL,

    following_child_id INT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_follow
    UNIQUE(child_id, following_child_id)

);

CREATE TABLE deleted_posts (

    deleted_post_id SERIAL PRIMARY KEY,

    original_post_id INT,

    child_id INT,

    media_type VARCHAR(20),

    media_path VARCHAR(500),

    caption TEXT,

    content_category VARCHAR(100),

    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

# quizzes table

CREATE TABLE quizzes (

    quiz_id SERIAL PRIMARY KEY,

    category VARCHAR(100) NOT NULL,

    question TEXT NOT NULL,

    option_a VARCHAR(255) NOT NULL,

    option_b VARCHAR(255) NOT NULL,

    option_c VARCHAR(255) NOT NULL,

    option_d VARCHAR(255) NOT NULL,

    correct_answer VARCHAR(255) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE parent_quiz_settings (

    setting_id SERIAL PRIMARY KEY,

    child_id INT UNIQUE NOT NULL,

    quiz_frequency INT DEFAULT 5,

    mandatory_quiz BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE child_quiz_progress (

    progress_id SERIAL PRIMARY KEY,

    child_id INT UNIQUE,

    posts_seen INT DEFAULT 0,

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE parent_quiz_settings
ADD COLUMN parent_id INT;

ALTER TABLE parent_quiz_settings

ADD CONSTRAINT parent_quiz_settings_parent_id_fkey

FOREIGN KEY(parent_id)

REFERENCES users(user_id);



CREATE TABLE child_conversations (

    conversation_id SERIAL PRIMARY KEY,

    child1_id INT NOT NULL,

    child2_id INT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(child1_id, child2_id),

    FOREIGN KEY (child1_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    FOREIGN KEY (child2_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE

);


CREATE TABLE child_messages (

    child_message_id SERIAL PRIMARY KEY,

    conversation_id INT NOT NULL,

    sender_child_id INT NOT NULL,

    receiver_child_id INT NOT NULL,

    message_type VARCHAR(20) DEFAULT 'TEXT',

    message_text TEXT,

    media_path VARCHAR(500),

    is_seen BOOLEAN DEFAULT FALSE,

    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id)
        REFERENCES child_conversations(conversation_id)
        ON DELETE CASCADE,

    FOREIGN KEY (sender_child_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    FOREIGN KEY (receiver_child_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE

);




ALTER TABLE public.child_messages
    ADD COLUMN IF NOT EXISTS is_deleted boolean DEFAULT false;

ALTER TABLE public.child_messages
    ADD COLUMN IF NOT EXISTS delivered_at timestamp without time zone;

ALTER TABLE public.child_messages
    ADD COLUMN IF NOT EXISTS seen_at timestamp without time zone;


ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_story BOOLEAN DEFAULT FALSE;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_highlight BOOLEAN DEFAULT FALSE;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS highlight_title VARCHAR(100);
ALTER TABLE child_profiles ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE;