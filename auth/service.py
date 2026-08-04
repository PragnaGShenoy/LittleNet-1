import token

import bcrypt
import uuid
from mailg.send_email import send_email

from database.connection import get_db_connection


def register_child(form_data):

    conn = get_db_connection()
    cur = conn.cursor()

    password = form_data["password"]

    hashed_password = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    cur.execute("""
        INSERT INTO users(
            username,
            full_name,
            email,
            password_hash,
            role,
            age
        )
        VALUES(%s,%s,%s,%s,%s,%s)
        RETURNING user_id
    """,
    (
        form_data["username"],
        form_data["full_name"],
        form_data["email"],
        hashed_password,
        "CHILD",
        form_data["age"]
    ))

    child_id = cur.fetchone()["user_id"]

    approval_token = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO parent_child_map(
            child_id,
            parent_name,
            parent_email,
            approval_token
        )
        VALUES(%s,%s,%s,%s)
    """,
    (
        child_id,
        form_data["parent_name"],
        form_data["parent_email"],
        approval_token
    ))

    approval_link = (
    f"http://127.0.0.1:5000/approve/{approval_token}/"
)

    send_email(
        form_data["parent_email"],
        "LittleNet Parent Approval",
        f"""
        <h2>LittleNet Parent Approval</h2>

        <p>
            Child Name: {form_data["full_name"]}
        </p>

        <p>
            Click the link below to approve the account:
        </p>

        <a href="{approval_link}">
            Approve Child Account
        </a>
        """
    )

    conn.commit()

    cur.close()
    conn.close()

    return approval_token


def approve_child_account(token):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT child_id, parent_email
        FROM parent_child_map
        WHERE approval_token = %s
        AND approved = FALSE
    """, (token,))

    child = cur.fetchone()

    if not child:
        cur.close()
        conn.close()
        return False

    child_id = child["child_id"]
    parent_email = child["parent_email"]

    cur.execute("""
        UPDATE users
        SET account_status = 'ACTIVE'
        WHERE user_id = %s
    """, (child_id,))

    cur.execute("""
        UPDATE parent_child_map
        SET approved = TRUE,
            approved_at = NOW()
        WHERE child_id = %s
    """, (child_id,))

    conn.commit()

    registration_link = (
    f"http://127.0.0.1:5000/register-parent/{token}/"
    )

    send_email(
        parent_email,
        "LittleNet Parent Registration",
        f"""
        <h2>Parent Account Setup</h2>

        <a href="{registration_link}">
            Create Parent Account
        </a>
        """
    )

    cur.close()
    conn.close()

    return True


import bcrypt

def login_user(email, password):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE email = %s
    """, (email,))

    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        return None

    if not bcrypt.checkpw(
        password.encode(),
        user["password_hash"].encode()
    ):
        return None

    return user



def register_parent_account(token, form_data):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM parent_child_map
        WHERE approval_token = %s
        AND approved = TRUE
    """, (token,))

    parent_data = cur.fetchone()

    if not parent_data:
        cur.close()
        conn.close()
        return False

    password_hash = bcrypt.hashpw(
        form_data["password"].encode(),
        bcrypt.gensalt()
    ).decode()

    parent_name = parent_data["parent_name"]
    parent_email = parent_data["parent_email"]
    
    cur.execute("""
    INSERT INTO users(
        username,
        full_name,
        email,
        password_hash,
        role,
        account_status
    )
    VALUES(%s,%s,%s,%s,%s,%s)
    RETURNING user_id
    """,
    (
        parent_email,
        parent_name,
        parent_email,
        password_hash,
        "PARENT",
        "ACTIVE"
    ))

    parent_id = cur.fetchone()["user_id"]


    cur.execute("""
    UPDATE parent_child_map
    SET parent_id = %s
    WHERE child_id = %s
    """,
    (
        parent_id,
        parent_data["child_id"]
    ))


    conn.commit()

    cur.close()
    conn.close()

    return True


def save_usage_log(
    child_id,
    login_time,
    logout_time,
    duration_minutes
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO child_usage_logs(
            child_id,
            login_time,
            logout_time,
            duration_minutes
        )
        VALUES(%s,%s,%s,%s)
    """,
    (
        child_id,
        login_time,
        logout_time,
        duration_minutes
    ))

    conn.commit()

    cur.close()
    conn.close()
    