from flask import render_template

from database.connection import get_db_connection
from datetime import date

def profile_exists(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT profile_id
        FROM child_profiles
        WHERE child_id = %s
    """, (child_id,))

    profile = cur.fetchone()

    cur.close()
    conn.close()

    return profile is not None



def create_child_profile(child_id, form_data):

    conn = get_db_connection()
    cur = conn.cursor()

    # get parent id
    cur.execute("""
        SELECT parent_id
        FROM parent_child_map
        WHERE child_id = %s
    """, (child_id,))

    parent = cur.fetchone()

    parent_id = parent["parent_id"]

    cur.execute("""
        INSERT INTO child_profiles(
            child_id,
            parent_id,
            full_name,
            date_of_birth,
            school_name,
            location,
            current_class,
            bio
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
    """,
    (
        child_id,
        parent_id,
        form_data["full_name"],
        form_data["date_of_birth"],
        form_data["school_name"],
        form_data["location"],
        form_data["current_class"],
        form_data["bio"]
    ))

    dob = form_data["date_of_birth"]

    dob_parts = dob.split("-")

    birth_date = date(
        int(dob_parts[0]),
        int(dob_parts[1]),
        int(dob_parts[2])
    )

    today = date.today()

    age = today.year - birth_date.year - (
            (today.month, today.day)
            <
            (birth_date.month, birth_date.day)
        )


    skills = form_data.getlist("skills")

    for skill in skills:

        cur.execute("""
            INSERT INTO child_skills(
                child_id,
                skill_name
            )
            VALUES(%s,%s)
        """,
        (
            child_id,
            skill
        ))

    interests = form_data.getlist("interests")

    for interest in interests:

        cur.execute("""
            INSERT INTO child_interests(
                child_id,
                interest_name
            )
            VALUES(%s,%s)
        """,
        (
            child_id,
            interest
        ))

    ambitions = form_data.getlist("ambitions")

    for ambition in ambitions:

        cur.execute("""
            INSERT INTO child_ambitions(
                child_id,
                ambition_name
            )
            VALUES(%s,%s)
        """,
        (
            child_id,
            ambition
        ))
    
    conn.commit()

    cur.close()
    conn.close()


def get_child_profile(child_id):

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


def update_child_profile(
    child_id,
    form_data
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE child_profiles
        SET
            full_name = %s,
            school_name = %s,
            location = %s,
            current_class = %s,
            bio = %s,
            updated_at = NOW()
        WHERE child_id = %s
    """,
    (
        form_data["full_name"],
        form_data["school_name"],
        form_data["location"],
        form_data["current_class"],
        form_data["bio"],
        child_id
    ))

    conn.commit()

    cur.close()
    conn.close()


def update_profile_picture(child_id, filepath):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE child_profiles
        SET profile_picture = %s,
            updated_at = NOW()
        WHERE child_id = %s
    """, (filepath, child_id))

    conn.commit()
    cur.close()
    conn.close()




def follow_child(
    child_id,
    following_child_id
):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO followers(
                child_id,
                following_child_id
            )
            VALUES(%s,%s)
        """,
        (
            child_id,
            following_child_id
        ))

        conn.commit()

    except:
        conn.rollback()

    cur.close()
    conn.close()

def get_followers_count(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        AS total
        FROM followers
        WHERE following_child_id = %s
    """, (child_id,))

    total = cur.fetchone()["total"]

    cur.close()
    conn.close()

    return total

def get_following_count(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        AS total
        FROM followers
        WHERE child_id = %s
    """, (child_id,))

    total = cur.fetchone()["total"]

    cur.close()
    conn.close()

    return total

def is_following(
    child_id,
    following_child_id
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM followers
        WHERE child_id = %s
        AND following_child_id = %s
    """,
    (
        child_id,
        following_child_id
    ))

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result is not None


def unfollow_child(
    child_id,
    following_child_id
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM followers
        WHERE child_id = %s
        AND following_child_id = %s
    """,
    (
        child_id,
        following_child_id
    ))

    conn.commit()

    cur.close()
    conn.close()

def get_followers(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.user_id,
            u.full_name
        FROM followers f
        JOIN users u
        ON f.child_id = u.user_id
        WHERE f.following_child_id = %s
    """, (child_id,))

    followers = cur.fetchall()

    cur.close()
    conn.close()

    return followers

def get_following(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.user_id,
            u.full_name
        FROM followers f
        JOIN users u
        ON f.following_child_id = u.user_id
        WHERE f.child_id = %s
    """, (child_id,))

    following = cur.fetchall()

    cur.close()
    conn.close()

    return following

def get_recommended_posts(child_id,limit=5,offset=0):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""

            SELECT DISTINCT
                p.*,
                u.full_name,

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

            JOIN users u
            ON p.child_id = u.user_id

            WHERE p.content_category IN (

                SELECT skill_name
                FROM child_skills
                WHERE child_id = %s
                AND approved = TRUE

                UNION

                SELECT interest_name
                FROM child_interests
                WHERE child_id = %s
                AND approved = TRUE

                UNION

                SELECT ambition_name
                FROM child_ambitions
                WHERE child_id = %s
                AND approved = TRUE

            )

            ORDER BY likes DESC
            LIMIT %s OFFSET %s
        """,
        (
            child_id,
            child_id,
            child_id,
            limit,
            offset
        ))
    posts = cur.fetchall()

    cur.close()
    conn.close()

    return posts

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

        LIMIT 5
    """, (post_id,))

    comments = cur.fetchall()

    cur.close()
    conn.close()

    return comments

def get_random_children(current_child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.user_id,
            u.full_name,

            (
                SELECT COUNT(*)
                FROM followers f
                WHERE f.following_child_id = u.user_id
            ) AS followers

        FROM users u

        WHERE u.role = 'CHILD'
        AND u.user_id != %s

        ORDER BY RANDOM()

        LIMIT 20
    """, (current_child_id,))

    children = cur.fetchall()

    cur.close()
    conn.close()

    return children


from parent.service import get_time_limit

def get_today_usage(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
        COALESCE(
            SUM(duration_minutes),
            0
        ) AS total

        FROM child_usage_logs

        WHERE child_id = %s
        AND usage_date = CURRENT_DATE
    """,
    (child_id,))

    total = cur.fetchone()["total"]

    cur.close()
    conn.close()

    return total



def get_remaining_time(child_id):

    limit_data = get_time_limit(
        child_id
    )

    if not limit_data:
        return None

    today_usage = get_today_usage(
        child_id
    )

    remaining = (
        limit_data["daily_limit_minutes"]
        -
        today_usage
    )

    return max(
        remaining,
        0
    )
def is_child_locked(child_id):

    limit_data = get_time_limit(
        child_id
    )

    if not limit_data:
        return False

    # Parent did NOT enable strict mode
    if limit_data["strict_mode"] == False:
        return False

    remaining_time = get_remaining_time(
        child_id
    )

    return remaining_time <= 0

    