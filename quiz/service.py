from database.connection import get_db_connection
from datetime import date


# ============================================================
# PARENT QUIZ SETTINGS
# ============================================================

def get_quiz_settings(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM parent_quiz_settings
        WHERE child_id = %s
    """, (child_id,))

    settings = cur.fetchone()

    cur.close()
    conn.close()

    return settings


def save_quiz_settings(
    parent_id,
    child_id,
    quiz_frequency,
    mandatory_quiz
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO parent_quiz_settings(
            parent_id,
            child_id,
            quiz_frequency,
            mandatory_quiz
        )
        VALUES(%s,%s,%s,%s)

        ON CONFLICT(child_id)

        DO UPDATE SET
            quiz_frequency = EXCLUDED.quiz_frequency,
            mandatory_quiz = EXCLUDED.mandatory_quiz

    """, (
        parent_id,
        child_id,
        quiz_frequency,
        mandatory_quiz
    ))

    conn.commit()

    cur.close()
    conn.close()


def get_child_quiz_settings(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM parent_quiz_settings
        WHERE child_id = %s
    """, (child_id,))

    settings = cur.fetchone()

    cur.close()
    conn.close()

    return settings


# ============================================================
# AGE CALCULATION
# ============================================================

def get_child_age(child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT date_of_birth
        FROM child_profiles
        WHERE child_id = %s
    """, (child_id,))

    profile = cur.fetchone()

    cur.close()
    conn.close()

    if not profile:
        return None

    dob = profile["date_of_birth"]

    if not dob:
        return None

    today = date.today()

    age = (
        today.year
        - dob.year
        - (
            (today.month, today.day)
            < (dob.month, dob.day)
        )
    )

    return age


# ============================================================
# AGE GROUP
# ============================================================

def get_child_age_group(child_id):

    age = get_child_age(child_id)

    if age is None:
        return None

    if 6 <= age <= 8:
        return "6-8"

    if 9 <= age <= 11:
        return "9-11"

    if 12 <= age <= 13:
        return "12-13"

    return None


# ============================================================
# GET QUESTIONS FOR CHILD
# ============================================================

def get_quizzes_for_child(
    child_id,
    limit=5
):

    age_group = get_child_age_group(
        child_id
    )

    if age_group is None:
        return []

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            quiz_id,
            category,
            question,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_answer,
            age_group
        FROM quizzes
        WHERE age_group = %s
        ORDER BY RANDOM()
        LIMIT %s
    """, (
        age_group,
        limit
    ))

    quizzes = cur.fetchall()

    cur.close()
    conn.close()

    return quizzes


# ============================================================
# GET RANDOM QUIZ BY CATEGORY
# ============================================================

def get_random_quiz_by_category(
    category
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM quizzes
        WHERE category = %s
        ORDER BY RANDOM()
        LIMIT 1
    """, (category,))

    quiz = cur.fetchone()

    cur.close()
    conn.close()

    return quiz


# ============================================================
# GET ONE QUIZ FOR CHILD
# ============================================================

def get_quiz_for_child(
    child_id
):

    quizzes = get_quizzes_for_child(
        child_id,
        limit=1
    )

    if not quizzes:
        return None

    return quizzes[0]


# ============================================================
# GET QUIZ BY ID
# ============================================================

def get_quiz_by_id(
    quiz_id
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM quizzes
        WHERE quiz_id = %s
    """, (quiz_id,))

    quiz = cur.fetchone()

    cur.close()
    conn.close()

    return quiz


# ============================================================
# SAVE QUIZ ATTEMPT
# ============================================================

def save_quiz_attempt(
    child_id,
    quiz_id,
    selected_answer,
    is_correct
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO child_quiz_attempts(
            child_id,
            quiz_id,
            selected_answer,
            is_correct
        )
        VALUES(%s,%s,%s,%s)
    """, (
        child_id,
        quiz_id,
        selected_answer,
        is_correct
    ))

    conn.commit()

    cur.close()
    conn.close()


# ============================================================
# PARENT QUIZ REPORT
# ============================================================

def get_quiz_attempts(
    child_id
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            q.question,
            q.correct_answer,
            a.selected_answer,
            a.is_correct,
            a.attempted_at

        FROM child_quiz_attempts a

        JOIN quizzes q
        ON a.quiz_id = q.quiz_id

        WHERE a.child_id = %s

        ORDER BY a.attempted_at DESC
    """, (child_id,))

    attempts = cur.fetchall()

    cur.close()
    conn.close()

    return attempts


def get_quiz_summary(
    child_id
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) AS total,

            COUNT(*) FILTER (
                WHERE is_correct = TRUE
            ) AS correct,

            COUNT(*) FILTER (
                WHERE is_correct = FALSE
            ) AS wrong

        FROM child_quiz_attempts

        WHERE child_id = %s
    """, (child_id,))

    summary = cur.fetchone()

    cur.close()
    conn.close()

    return summary