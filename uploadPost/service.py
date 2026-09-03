from database.connection import get_db_connection

def get_random_posts(child_id, limit=6):
    """Random approved posts from other children — refreshes on each load."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            p.*,
            u.full_name,
            cp.profile_picture,
            (SELECT COUNT(*) FROM likes  l WHERE l.post_id = p.post_id) AS likes,
            (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.post_id) AS comments_count
        FROM posts p
        JOIN users u ON p.child_id = u.user_id
        LEFT JOIN child_profiles cp ON p.child_id = cp.child_id
        WHERE p.is_safe = TRUE
          AND (p.is_story IS NULL OR p.is_story = FALSE)
          AND (p.is_archived IS NULL OR p.is_archived = FALSE)
          AND p.child_id != %s
        ORDER BY RANDOM()
        LIMIT %s
    """, (child_id, limit))
    posts = cur.fetchall()
    cur.close(); conn.close()
    return posts

def save_post(
    child_id,
    media_type,
    media_path,
    caption,
    content_category,
    is_story=False
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO posts(
            child_id,
            media_type,
            media_path,
            caption,
            content_category,
            is_story
        )
        VALUES(%s,%s,%s,%s,%s,%s)
    """,
    (
        child_id,
        media_type,
        media_path,
        caption,
        content_category,
        is_story
    ))

    conn.commit()

    cur.close()
    conn.close()


def get_all_posts():

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.full_name,

        (
            SELECT COUNT(*)
            FROM likes l
            WHERE l.post_id = p.post_id
        ) AS likes

        FROM posts p
        JOIN users u
        ON p.child_id = u.user_id

        ORDER BY p.created_at DESC;
        """)

    posts = cur.fetchall()

    cur.close()
    conn.close()

    return posts

def get_my_posts(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,

            (
                SELECT COUNT(*)
                FROM likes l
                WHERE l.post_id = p.post_id
            ) AS likes,

            (
                SELECT COUNT(*)
                FROM comments c
                WHERE c.post_id = p.post_id
            ) AS comments_count

        FROM posts p

        WHERE p.child_id = %s

        ORDER BY p.created_at DESC
    """, (child_id,))

    posts = cur.fetchall()

    cur.close()
    conn.close()

    return posts

def like_post(post_id, child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO likes(
                post_id,
                child_id
            )
            VALUES(%s,%s)
        """,
        (
            post_id,
            child_id
        ))

        conn.commit()

        print("LIKE SAVED SUCCESSFULLY")

    except Exception as e:

        print("DATABASE ERROR:")
        print(e)

        conn.rollback()

    cur.close()
    conn.close()

def is_liked(post_id, child_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM likes WHERE post_id=%s AND child_id=%s", (post_id, child_id))
    result = cur.fetchone()
    cur.close(); conn.close()
    return result is not None

def unlike_post(post_id, child_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM likes WHERE post_id=%s AND child_id=%s", (post_id, child_id))
    conn.commit(); cur.close(); conn.close()

def get_like_count(post_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM likes
        WHERE post_id = %s
    """, (post_id,))

    count = cur.fetchone()["total"]

    cur.close()
    conn.close()

    return count



def delete_post(post_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM posts
        WHERE post_id = %s
    """, (post_id,))

    post = cur.fetchone()

    if not post:
        return

    cur.execute("""
        INSERT INTO deleted_posts(
            original_post_id,
            child_id,
            media_type,
            media_path,
            caption,
            content_category
        )
        VALUES(%s,%s,%s,%s,%s,%s)
    """,
    (
        post["post_id"],
        post["child_id"],
        post["media_type"],
        post["media_path"],
        post["caption"],
        post["content_category"]
    ))

    cur.execute("""
        DELETE FROM posts
        WHERE post_id = %s
    """, (post_id,))

    conn.commit()

    cur.close()
    conn.close()

def add_comment(
    post_id,
    child_id,
    comment_text
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO comments(
            post_id,
            child_id,
            comment_text
        )
        VALUES(%s,%s,%s)
    """,
    (
        post_id,
        child_id,
        comment_text
    ))

    conn.commit()

    cur.close()
    conn.close()

def get_post_comments(post_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            c.*,
            u.full_name
        FROM comments c

        JOIN users u
        ON c.child_id = u.user_id

        WHERE c.post_id = %s

        ORDER BY c.created_at DESC
    """, (post_id,))

    comments = cur.fetchall()

    cur.close()
    conn.close()

    return comments


def edit_post(post_id, child_id, caption, category=None):
    """Edit caption and category of own post."""
    conn = get_db_connection()
    cur = conn.cursor()
    if category:
        cur.execute("""
            UPDATE posts
            SET caption = %s, content_category = %s
            WHERE post_id = %s AND child_id = %s
        """, (caption, category, post_id, child_id))
    else:
        cur.execute("""
            UPDATE posts
            SET caption = %s
            WHERE post_id = %s AND child_id = %s
        """, (caption, post_id, child_id))
    conn.commit()
    cur.close()
    conn.close()
    return True


def toggle_archive_post(post_id, child_id):
    """Toggle is_archived on own post."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE posts
        SET is_archived = NOT COALESCE(is_archived, FALSE)
        WHERE post_id = %s AND child_id = %s
        RETURNING is_archived
    """, (post_id, child_id))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return row["is_archived"] if row else False

