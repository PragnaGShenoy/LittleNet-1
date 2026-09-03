from datetime import datetime
from database.connection import get_db_connection

def create_child_notification(
    recipient_id,
    actor_id,
    notif_type,
    message,
    related_post_id=None,
    related_story_id=None
):
    """
    Creates a child notification.
    Ensures a user doesn't receive a notification for their own actions,
    and prevents duplicate unread notifications of the same type for the same target.
    """
    if recipient_id is None or recipient_id == actor_id:
        return None

    conn = get_db_connection()
    if not conn:
        return None
    cur = conn.cursor()

    try:
        # Check for existing unread identical notification to avoid duplicates
        cur.execute("""
            SELECT notification_id FROM child_notifications
            WHERE recipient_user_id = %s
              AND actor_user_id = %s
              AND notification_type = %s
              AND is_read = FALSE
              AND COALESCE(related_post_id, -1) = COALESCE(%s, -1)
              AND COALESCE(related_story_id, -1) = COALESCE(%s, -1)
        """, (recipient_id, actor_id, notif_type, related_post_id, related_story_id))
        existing = cur.fetchone()

        if existing:
            # Update created_at and message if necessary
            cur.execute("""
                UPDATE child_notifications
                SET created_at = CURRENT_TIMESTAMP, message = %s
                WHERE notification_id = %s
                RETURNING notification_id
            """, (message, existing["notification_id"]))
            row = cur.fetchone()
            conn.commit()
            return row["notification_id"] if row else None

        cur.execute("""
            INSERT INTO child_notifications (
                recipient_user_id,
                actor_user_id,
                notification_type,
                message,
                related_post_id,
                related_story_id,
                is_read
            )
            VALUES (%s, %s, %s, %s, %s, %s, FALSE)
            RETURNING notification_id
        """, (
            recipient_id,
            actor_id,
            notif_type,
            message,
            related_post_id,
            related_story_id
        ))
        row = cur.fetchone()
        conn.commit()
        return row["notification_id"] if row else None
    except Exception as e:
        print("[NOTIFICATION ERROR] create_child_notification failed:", e)
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def get_child_notifications(child_id, limit=40):
    """
    Fetches the notification history for a child with actor details and relative time.
    """
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                n.notification_id,
                n.recipient_user_id,
                n.actor_user_id,
                n.notification_type,
                n.message,
                n.related_post_id,
                n.related_story_id,
                n.is_read,
                n.created_at,
                u.full_name AS actor_name,
                u.username AS actor_username,
                cp.profile_picture AS actor_profile_picture,
                p.media_path AS post_media_path,
                p.media_type AS post_media_type,
                p.is_story AS post_is_story,
                EXTRACT(EPOCH FROM (NOW() - n.created_at)) AS age_seconds
            FROM child_notifications n
            LEFT JOIN users u ON n.actor_user_id = u.user_id
            LEFT JOIN child_profiles cp ON n.actor_user_id = cp.child_id
            LEFT JOIN posts p ON COALESCE(n.related_post_id, n.related_story_id) = p.post_id
            WHERE n.recipient_user_id = %s
            ORDER BY n.created_at DESC
            LIMIT %s
        """, (child_id, limit))
        rows = cur.fetchall()

        notifications = []
        for r in rows:
            age_sec = int(r.get("age_seconds") or 0)
            if age_sec < 60:
                time_ago = "Just now"
            elif age_sec < 3600:
                time_ago = f"{age_sec // 60}m ago"
            elif age_sec < 86400:
                time_ago = f"{age_sec // 3600}h ago"
            else:
                time_ago = f"{age_sec // 86400}d ago"

            notifications.append({
                "notification_id": r["notification_id"],
                "recipient_user_id": r["recipient_user_id"],
                "actor_user_id": r["actor_user_id"],
                "actor_name": r["actor_name"] or "LittleNet Friend",
                "actor_username": r["actor_username"] or "",
                "actor_profile_picture": (r["actor_profile_picture"] or "").replace("\\", "/"),
                "notification_type": r["notification_type"],
                "message": r["message"],
                "related_post_id": r["related_post_id"],
                "related_story_id": r["related_story_id"],
                "post_media_path": (r["post_media_path"] or "").replace("\\", "/"),
                "post_media_type": r["post_media_type"],
                "post_is_story": bool(r["post_is_story"]),
                "is_read": bool(r["is_read"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else "",
                "time_ago": time_ago
            })
        return notifications
    except Exception as e:
        print("[NOTIFICATION ERROR] get_child_notifications failed:", e)
        return []
    finally:
        cur.close()
        conn.close()


def get_unread_notification_count(child_id):
    """Returns unread notification count for a child."""
    conn = get_db_connection()
    if not conn:
        return 0
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) AS unread_count
            FROM child_notifications
            WHERE recipient_user_id = %s AND is_read = FALSE
        """, (child_id,))
        row = cur.fetchone()
        return row["unread_count"] if row else 0
    except Exception as e:
        print("[NOTIFICATION ERROR] get_unread_notification_count failed:", e)
        return 0
    finally:
        cur.close()
        conn.close()


def mark_notification_read(notification_id, child_id):
    """Marks a single notification as read for child_id."""
    conn = get_db_connection()
    if not conn:
        return False
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE child_notifications
            SET is_read = TRUE
            WHERE notification_id = %s AND recipient_user_id = %s
        """, (notification_id, child_id))
        conn.commit()
        return True
    except Exception as e:
        print("[NOTIFICATION ERROR] mark_notification_read failed:", e)
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def mark_all_notifications_read(child_id):
    """Marks all notifications as read for child_id."""
    conn = get_db_connection()
    if not conn:
        return False
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE child_notifications
            SET is_read = TRUE
            WHERE recipient_user_id = %s AND is_read = FALSE
        """, (child_id,))
        conn.commit()
        return True
    except Exception as e:
        print("[NOTIFICATION ERROR] mark_all_notifications_read failed:", e)
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def check_and_generate_quiz_reminders(child_id):
    """
    Checks if a child has a quiz reminder due and generates a notification if none exists recently.
    """
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    try:
        # Check if reminder already created today
        cur.execute("""
            SELECT 1 FROM child_notifications
            WHERE recipient_user_id = %s
              AND notification_type = 'QUIZ_REMINDER'
              AND created_at > NOW() - INTERVAL '12 hours'
        """, (child_id,))
        if cur.fetchone():
            return

        # Check quiz settings
        cur.execute("""
            SELECT mandatory_quiz, quiz_frequency
            FROM parent_quiz_settings
            WHERE child_id = %s
        """, (child_id,))
        settings = cur.fetchone()

        if settings:
            cur.execute("""
                INSERT INTO child_notifications (
                    recipient_user_id,
                    actor_user_id,
                    notification_type,
                    message,
                    is_read
                )
                VALUES (%s, NULL, 'QUIZ_REMINDER', 'It is time to play your fun daily quiz! 🧠 Learn & earn badges.', FALSE)
            """, (child_id,))
            conn.commit()
    except Exception as e:
        print("[NOTIFICATION ERROR] check_and_generate_quiz_reminders error:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()
