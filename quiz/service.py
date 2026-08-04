

from database.connection import get_db_connection


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

    """,
    (
        parent_id,
        child_id,
        quiz_frequency,
        mandatory_quiz
    ))

    conn.commit()

    cur.close()
    conn.close()


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

    """,
    (category,))

    quiz = cur.fetchone()

    cur.close()
    conn.close()

    return quiz


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

    """,
    (
        child_id,
        quiz_id,
        selected_answer,
        is_correct
    ))

    conn.commit()

    cur.close()
    conn.close()

def get_child_quiz_settings(
    child_id
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""

        SELECT *

        FROM parent_quiz_settings

        WHERE child_id = %s

    """,
    (child_id,))

    settings = cur.fetchone()

    cur.close()
    conn.close()

    return settings

def get_quiz_for_child(
    child_id
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""

        SELECT *

        FROM quizzes

        ORDER BY RANDOM()

        LIMIT 1

    """)

    quiz = cur.fetchone()

    cur.close()
    conn.close()

    return quiz

def get_quiz_by_id(
    quiz_id
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""

        SELECT *

        FROM quizzes

        WHERE quiz_id = %s

    """,
    (quiz_id,))

    quiz = cur.fetchone()

    cur.close()
    conn.close()

    return quiz

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

    """,
    (child_id,))

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

            COUNT(*) as total,

            COUNT(*) FILTER (
                WHERE is_correct = TRUE
            ) as correct,

            COUNT(*) FILTER (
                WHERE is_correct = FALSE
            ) as wrong

        FROM child_quiz_attempts

        WHERE child_id = %s

    """,
    (child_id,))

    summary = cur.fetchone()

    cur.close()
    conn.close()

    return summary