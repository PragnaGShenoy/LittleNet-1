from database.connection import get_db_connection


def get_parent_children(parent_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.user_id,
            u.full_name
        FROM users u
        JOIN parent_child_map pcm
        ON u.user_id = pcm.child_id
        WHERE pcm.parent_id = %s
    """, (parent_id,))

    children = cur.fetchall()

    cur.close()
    conn.close()

    return children

from database.connection import get_db_connection

def get_child_profile_for_parent(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM child_profiles
        WHERE child_id = %s
    """, (child_id,))

    profile = cur.fetchone()

    cur.close()
    conn.close()

    return profile

def get_child_content_for_approval(parent_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT child_id
        FROM parent_child_map
        WHERE parent_id = %s
    """, (parent_id,))

    child = cur.fetchone()

    if not child:
        return None

    child_id = child["child_id"]

    cur.execute("""
        SELECT *
        FROM child_skills
        WHERE child_id = %s
    """, (child_id,))
    skills = cur.fetchall()

    cur.execute("""
        SELECT *
        FROM child_interests
        WHERE child_id = %s
    """, (child_id,))
    interests = cur.fetchall()

    cur.execute("""
        SELECT *
        FROM child_ambitions
        WHERE child_id = %s
    """, (child_id,))
    ambitions = cur.fetchall()

    cur.close()
    conn.close()

    return {
        "child_id": child_id,
        "skills": skills,
        "interests": interests,
        "ambitions": ambitions
    }

def save_child_content_approval(
    child_id,
    skill_ids,
    interest_ids,
    ambition_ids
):

    conn = get_db_connection()
    cur = conn.cursor()

    # Reset all approvals

    cur.execute("""
        UPDATE child_skills
        SET approved = FALSE
        WHERE child_id = %s
    """, (child_id,))

    cur.execute("""
        UPDATE child_interests
        SET approved = FALSE
        WHERE child_id = %s
    """, (child_id,))

    cur.execute("""
        UPDATE child_ambitions
        SET approved = FALSE
        WHERE child_id = %s
    """, (child_id,))

    # Approve selected skills

    for skill_id in skill_ids:

        cur.execute("""
            UPDATE child_skills
            SET approved = TRUE
            WHERE skill_id = %s
        """, (skill_id,))

    # Approve selected interests

    for interest_id in interest_ids:

        cur.execute("""
            UPDATE child_interests
            SET approved = TRUE
            WHERE interest_id = %s
        """, (interest_id,))

    # Approve selected ambitions

    for ambition_id in ambition_ids:

        cur.execute("""
            UPDATE child_ambitions
            SET approved = TRUE
            WHERE ambition_id = %s
        """, (ambition_id,))

    conn.commit()

    cur.close()
    conn.close()


def get_deleted_posts():

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            dp.*,
            u.full_name
        FROM deleted_posts dp
        JOIN users u
        ON dp.child_id = u.user_id
        ORDER BY dp.deleted_at DESC
    """)

    posts = cur.fetchall()

    cur.close()
    conn.close()

    return posts

def save_time_limit(
    child_id,
    daily_limit,
    strict_mode
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO child_time_limits(
            child_id,
            daily_limit_minutes,
            strict_mode
        )
        VALUES(%s,%s,%s)

        ON CONFLICT(child_id)

        DO UPDATE SET

        daily_limit_minutes =
        EXCLUDED.daily_limit_minutes,

        strict_mode =
        EXCLUDED.strict_mode
    """,
    (
        child_id,
        daily_limit,
        strict_mode
    ))

    conn.commit()

    cur.close()
    conn.close()

def get_time_limit(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM child_time_limits
        WHERE child_id = %s
    """, (child_id,))

    data = cur.fetchone()

    cur.close()
    conn.close()

    return data

def get_parent_child(parent_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.user_id,
            u.full_name

        FROM parent_child_map pcm

        JOIN users u
        ON pcm.child_id = u.user_id

        WHERE pcm.parent_id = %s
    """,
    (parent_id,))

    child = cur.fetchone()

    cur.close()
    conn.close()

    return child

def get_weekly_usage(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            usage_date,
            SUM(duration_minutes)
            AS total_minutes

        FROM child_usage_logs

        WHERE child_id = %s

        GROUP BY usage_date

        ORDER BY usage_date DESC

        LIMIT 7
    """,
    (child_id,))

    data = cur.fetchall()

    cur.close()
    conn.close()

    return data


def get_child_posts(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""

        SELECT
            p.*,

            (
                SELECT COUNT(*)
                FROM likes l
                WHERE l.post_id = p.post_id
            ) AS likes_count,

            (
                SELECT COUNT(*)
                FROM comments c
                WHERE c.post_id = p.post_id
            ) AS comments_count

        FROM posts p

        WHERE p.child_id = %s

        ORDER BY p.created_at DESC

    """,
    (child_id,))

    posts = cur.fetchall()

    cur.close()
    conn.close()

    return posts


def get_pending_follow_requests(parent_id):
    """Return all unapproved follow requests made BY any child of this parent."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            f.child_id      AS requester_id,
            u1.full_name    AS requester_name,
            f.following_child_id AS target_id,
            u2.full_name    AS target_name
        FROM followers f
        JOIN users u1 ON f.child_id = u1.user_id
        JOIN users u2 ON f.following_child_id = u2.user_id
        WHERE f.approved = FALSE
          AND f.child_id IN (
              SELECT child_id FROM parent_child_map WHERE parent_id = %s
          )
        ORDER BY f.child_id
    """, (parent_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def approve_follow(child_id, following_child_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE followers SET approved = TRUE
        WHERE child_id = %s AND following_child_id = %s
    """, (child_id, following_child_id))
    conn.commit()
    cur.close(); conn.close()


def reject_follow(child_id, following_child_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM followers
        WHERE child_id = %s AND following_child_id = %s AND approved = FALSE
    """, (child_id, following_child_id))
    conn.commit()
    cur.close(); conn.close()


def get_child_followers(child_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.full_name
        FROM followers f
        JOIN users u ON f.child_id = u.user_id
        WHERE f.following_child_id = %s AND f.approved = TRUE
    """, (child_id,))
    followers = cur.fetchall()
    cur.close(); conn.close()
    return followers

def get_child_following(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""

        SELECT
            u.user_id,
            u.full_name

        FROM followers f

        JOIN users u
        ON f.following_child_id = u.user_id

        WHERE f.child_id = %s AND f.approved = TRUE

    """,
    (child_id,))

    following = cur.fetchall()

    cur.close()
    conn.close()

    return following