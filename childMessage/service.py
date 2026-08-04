import os
from database.connection import get_db_connection

# ==========================================

# GET RECENT CONVERSATIONS (ordered by latest message)

# ==========================================

def get_recent_conversations(current_child_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.user_id,
            u.full_name,
            latest.message_text,
            latest.message_type,
            latest.sent_at
        FROM child_conversations cc
        JOIN users u ON u.user_id = CASE
            WHEN cc.child1_id = %s THEN cc.child2_id
            ELSE cc.child1_id
        END
        LEFT JOIN LATERAL (
            SELECT message_text, message_type, sent_at
            FROM child_messages
            WHERE conversation_id = cc.conversation_id
              AND is_deleted = FALSE
            ORDER BY sent_at DESC
            LIMIT 1
        ) latest ON TRUE
        WHERE cc.child1_id = %s OR cc.child2_id = %s
        ORDER BY latest.sent_at DESC NULLS LAST
    """, (current_child_id, current_child_id, current_child_id))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# ==========================================

# GET ALL OTHER ACTIVE CHILDREN

# ==========================================

def get_all_children(
current_child_id
):


    conn = get_db_connection()

    cur = conn.cursor()


    cur.execute("""

        SELECT

            user_id,

            full_name

        FROM users

        WHERE role = 'CHILD'

        AND user_id != %s

        ORDER BY full_name ASC

    """,
    (
        current_child_id,
    ))


    children = cur.fetchall()


    cur.close()

    conn.close()


    return children




# ==========================================

# GET EXISTING CONVERSATION

# ==========================================

def get_conversation(
    child_one_id,
    child_two_id
):

    # Keep the smaller child ID first
    first_child_id = min(
        child_one_id,
        child_two_id
    )

    # Keep the larger child ID second
    second_child_id = max(
        child_one_id,
        child_two_id
    )


    conn = get_db_connection()

    cur = conn.cursor()


    cur.execute("""

        SELECT
            conversation_id

        FROM child_conversations

        WHERE child1_id = %s

        AND child2_id = %s

    """,
    (
        first_child_id,
        second_child_id
    ))


    conversation = cur.fetchone()


    cur.close()

    conn.close()


    return conversation

# ==========================================

# CREATE NEW CONVERSATION

# ==========================================

def create_conversation(

    child_one_id,

    child_two_id

):

    # Always save the smaller ID in child1_id
    # and the larger ID in child2_id.

    first_child_id = min(

        child_one_id,

        child_two_id

    )

    second_child_id = max(

        child_one_id,

        child_two_id

    )


    conn = get_db_connection()

    cur = conn.cursor()


    cur.execute("""

        INSERT INTO child_conversations

        (

            child1_id,

            child2_id

        )

        VALUES

        (

            %s,

            %s

        )

        RETURNING conversation_id

    """,
    (
        first_child_id,

        second_child_id
    ))


    conversation = cur.fetchone()


    conn.commit()


    cur.close()

    conn.close()


    return conversation[

        "conversation_id"

    ]


# ==========================================

# GET ALL CHAT MESSAGES

# ==========================================

def get_messages(


conversation_id


):


    conn = get_db_connection()

    cur = conn.cursor()


    cur.execute("""

        SELECT

            cm.child_message_id,

            cm.conversation_id,

            cm.sender_child_id,

            cm.receiver_child_id,

            cm.message_type,

            cm.message_text,

            cm.media_path,

            cm.is_seen,

            cm.sent_at,

            u.full_name

        FROM child_messages cm

        JOIN users u

        ON cm.sender_child_id = u.user_id

        WHERE

        cm.conversation_id = %s

        AND

        cm.is_deleted = FALSE

        ORDER BY

        cm.sent_at ASC

    """,
    (
        conversation_id,
    ))


    messages = cur.fetchall()


    cur.close()

    conn.close()


    return messages


# ==========================================

# SEND TEXT MESSAGE

# ==========================================

def send_text_message(


conversation_id,

sender_child_id,

receiver_child_id,

message_text


):


    conn = get_db_connection()

    cur = conn.cursor()


    cur.execute("""

        INSERT INTO child_messages(

            conversation_id,

            sender_child_id,

            receiver_child_id,

            message_type,

            message_text

        )

        VALUES(

            %s,

            %s,

            %s,

            'TEXT',

            %s

        )

    """,
    (
        conversation_id,

        sender_child_id,

        receiver_child_id,

        message_text
    ))


    conn.commit()


    cur.close()

    conn.close()


# ==========================================

# SEND MEDIA MESSAGE (IMAGE / VIDEO / VOICE / FILE)

# ==========================================

def send_media_message(
    conversation_id,
    sender_child_id,
    receiver_child_id,
    message_type,
    media_path
):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO child_messages(
            conversation_id,
            sender_child_id,
            receiver_child_id,
            message_type,
            media_path
        )
        VALUES(%s, %s, %s, %s, %s)
    """, (
        conversation_id,
        sender_child_id,
        receiver_child_id,
        message_type,
        media_path
    ))

    conn.commit()
    cur.close()
    conn.close()

