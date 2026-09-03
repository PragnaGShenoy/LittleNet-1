import psycopg2
from database.connection import get_db_connection

def run_migrations():
    """
    Ensures all tables, columns, and constraints required for the enhanced
    LittleNet registration and verified parent approval flow are present.
    """
    conn = get_db_connection()
    if not conn:
        print("[DB MIGRATION] Could not connect to database.")
        return False

    try:
        cur = conn.cursor()

        # 1. Ensure parent_verifications table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS parent_verifications (
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
        """)

        # 2. Ensure parent_child_map has enhanced columns for verification and single-use expiring approval tokens
        cur.execute("""
            ALTER TABLE parent_child_map
            ALTER COLUMN approval_token TYPE VARCHAR(128) USING approval_token::text;

            ALTER TABLE parent_child_map
            ADD COLUMN IF NOT EXISTS verification_token VARCHAR(128);

            ALTER TABLE parent_child_map
            ADD COLUMN IF NOT EXISTS approval_token_expires_at TIMESTAMP WITH TIME ZONE;

            ALTER TABLE parent_child_map
            ADD COLUMN IF NOT EXISTS approval_status VARCHAR(30) DEFAULT 'PENDING_PARENT_VERIFICATION';

            ALTER TABLE parent_child_map
            ADD COLUMN IF NOT EXISTS is_token_used BOOLEAN DEFAULT FALSE;

            ALTER TABLE parent_child_map
            ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

            ALTER TABLE parent_child_map
            ADD COLUMN IF NOT EXISTS verified_parent_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL;
        """)

        # 3. Update account_status check constraint on users if necessary
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'users_account_status_check'
                ) THEN
                    ALTER TABLE users DROP CONSTRAINT users_account_status_check;
                    ALTER TABLE users ADD CONSTRAINT users_account_status_check
                    CHECK (account_status IN ('PENDING_APPROVAL', 'PENDING_PARENT_VERIFICATION', 'ACTIVE', 'REJECTED'));
                END IF;
            END $$;
        """)

        # 4. Ensure child_notifications table exists for child notification system
        cur.execute("""
            CREATE TABLE IF NOT EXISTS child_notifications (
                notification_id SERIAL PRIMARY KEY,
                recipient_user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                actor_user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                notification_type VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                related_post_id INTEGER REFERENCES posts(post_id) ON DELETE SET NULL,
                related_story_id INTEGER REFERENCES posts(post_id) ON DELETE SET NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_child_notifs_recipient
                ON child_notifications(recipient_user_id, is_read, created_at DESC);
        """)

        # 5. Ensure likes table has proper unique constraint
        cur.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                like_id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
                child_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT likes_post_id_child_id_unique UNIQUE(post_id, child_id)
            );
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("[DB MIGRATION] Database schema successfully verified and migrated.")
        return True
    except Exception as e:
        print("[DB MIGRATION ERROR]", e)
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    run_migrations()
