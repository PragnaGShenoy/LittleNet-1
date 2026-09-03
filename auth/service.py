import secrets
import bcrypt
import base64
from datetime import datetime, timedelta, timezone
from jinja2 import Template

from database.connection import get_db_connection
from mailg.send_email import send_email
from auth.verification_provider import default_verification_provider


def register_child(form_data):
    """
    Registers a new child account with strict anti-self-approval validation.
    Prevents child email == parent email.
    Creates child with status 'PENDING_APPROVAL' and sends parent verification invitation.
    """
    child_email = form_data.get("email", "").strip().lower()
    parent_email = form_data.get("parent_email", "").strip().lower()
    username = form_data.get("username", "").strip()
    full_name = form_data.get("full_name", "").strip()
    parent_name = form_data.get("parent_name", "").strip()
    password = form_data.get("password", "")
    age = form_data.get("age", "")

    # 1. Strict anti-self-parenting validation
    if not child_email or not parent_email:
        return {"success": False, "error": "Both child email and parent email are required."}

    if child_email == parent_email:
        return {
            "success": False,
            "error": "Self-approval is strictly prevented. Child email and parent email must be different accounts."
        }

    if not username or not full_name or not password or not parent_name:
        return {"success": False, "error": "Please fill in all required fields."}

    try:
        age_int = int(age)
        if age_int < 5 or age_int > 17:
            return {"success": False, "error": "Child age must be between 5 and 17 years."}
    except (ValueError, TypeError):
        return {"success": False, "error": "Please enter a valid age."}

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection error. Please try again later."}

    cur = conn.cursor()

    # 2. Check for duplicate username or email
    cur.execute("SELECT user_id, email, username FROM users WHERE email = %s OR username = %s", (child_email, username))
    existing_user = cur.fetchone()
    if existing_user:
        cur.close()
        conn.close()
        if existing_user["email"].lower() == child_email:
            return {"success": False, "error": "An account with this child email already exists. Please log in."}
        return {"success": False, "error": "Username already taken. Please choose another username."}

    hashed_password = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # 3. Create child account with PENDING_APPROVAL status
    cur.execute("""
        INSERT INTO users(
            username,
            full_name,
            email,
            password_hash,
            role,
            age,
            account_status
        )
        VALUES(%s, %s, %s, %s, %s, %s, %s)
        RETURNING user_id
    """,
    (
        username,
        full_name,
        child_email,
        hashed_password,
        "CHILD",
        age_int,
        "PENDING_APPROVAL"
    ))

    child_id = cur.fetchone()["user_id"]

    # 4. Generate secure verification invitation token
    verification_token = secrets.token_urlsafe(32)

    # Check if a parent account already exists for parent_email
    cur.execute("SELECT user_id FROM users WHERE email = %s AND role = 'PARENT'", (parent_email,))
    existing_parent = cur.fetchone()
    parent_id = existing_parent["user_id"] if existing_parent else None

    cur.execute("""
        INSERT INTO parent_child_map(
            child_id,
            parent_id,
            parent_name,
            parent_email,
            verification_token,
            approval_status,
            approved,
            is_token_used
        )
        VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
    """,
    (
        child_id,
        parent_id,
        parent_name,
        parent_email,
        verification_token,
        "PENDING_PARENT_VERIFICATION",
        False,
        False
    ))

    conn.commit()
    cur.close()
    conn.close()

    # 5. Send parent identity verification invitation email
    verification_url = f"http://127.0.0.1:5000/verify-parent/{verification_token}/"

    try:
        with open("mailg/templates/parent_invitation.html", "r", encoding="utf-8") as f:
            template_content = f.read()
        email_body = Template(template_content).render(
            parent_name=parent_name,
            child_name=full_name,
            child_username=username,
            child_age=age_int,
            child_email=child_email,
            verification_url=verification_url
        )
    except Exception as e:
        print(f"[MAIL RENDER WARN] {e}")
        email_body = f"""
        <h2>LittleNet Parent Verification</h2>
        <p>Child <strong>{full_name}</strong> (@{username}) has registered and listed you as supervising parent.</p>
        <p><a href="{verification_url}">Click here to verify your identity and approve the account</a></p>
        """

    send_email(
        parent_email,
        "LittleNet: Action Required - Verify Parent Identity for " + full_name,
        email_body
    )

    return {
        "success": True,
        "child_id": child_id,
        "child_name": full_name,
        "parent_email": parent_email,
        "verification_token": verification_token
    }


def get_parent_verification_data(token):
    """
    Fetches registration and child details associated with a parent verification token.
    """
    conn = get_db_connection()
    if not conn:
        return None

    cur = conn.cursor()
    cur.execute("""
        SELECT 
            pcm.map_id,
            pcm.child_id,
            pcm.parent_id,
            pcm.parent_name,
            pcm.parent_email,
            pcm.verification_token,
            pcm.approval_status,
            pcm.approved,
            u.username AS child_username,
            u.full_name AS child_name,
            u.age AS child_age,
            u.email AS child_email,
            u.created_at AS child_created_at
        FROM parent_child_map pcm
        JOIN users u ON pcm.child_id = u.user_id
        WHERE pcm.verification_token = %s
    """, (token,))

    data = cur.fetchone()
    cur.close()
    conn.close()
    return data


def process_parent_verification(token, form_data, selfie_bytes, doc_bytes=None):
    """
    Executes live selfie and ID document verification via IdentityVerificationProvider.
    Creates or activates the parent user account upon successful verification.
    Generates a secure, expiring approval token and dispatches the approval email.
    """
    map_data = get_parent_verification_data(token)
    if not map_data:
        return {"success": False, "error": "Invalid or expired verification invitation link."}

    child_id = map_data["child_id"]
    parent_name = form_data.get("parent_name", map_data["parent_name"]).strip()
    parent_email = map_data["parent_email"].strip().lower()
    doc_type = form_data.get("document_type", "AADHAAR_MOCK")
    doc_number = form_data.get("document_number", "").strip()
    dob = form_data.get("dob", "").strip()
    consent = bool(form_data.get("consent"))

    if not consent:
        return {"success": False, "error": "You must provide explicit consent for biometric and identity verification."}

    if not selfie_bytes:
        return {"success": False, "error": "Live camera selfie is required for identity verification."}

    # 1. Execute Identity Document Verification
    id_res = default_verification_provider.verify_parent_identity(
        document_type=doc_type,
        document_number=doc_number,
        full_name=parent_name,
        dob_or_year=dob,
        document_image_bytes=doc_bytes
    )

    if not id_res.get("success"):
        # Record failed verification audit
        _record_verification_audit(
            parent_user_id=map_data["parent_id"],
            child_id=child_id,
            status="FAILED",
            liveness="FAILED",
            face_match="FAILED",
            masked_id=id_res.get("masked_id", "XXXX-XXXX-0000"),
            consent=consent
        )
        return {
            "success": False,
            "error": id_res.get("error_message", "Identity verification failed."),
            "status": id_res.get("status", "FAILED")
        }

    # 2. Execute Liveness and Face Matching
    liveness_res = default_verification_provider.verify_liveness(selfie_bytes)
    if not liveness_res.get("success"):
        _record_verification_audit(
            parent_user_id=map_data["parent_id"],
            child_id=child_id,
            status="FAILED",
            liveness="FAILED",
            face_match="FAILED",
            masked_id=id_res.get("masked_id"),
            consent=consent
        )
        return {
            "success": False,
            "error": liveness_res.get("error_message", "Liveness check failed. Please retake a clear live selfie."),
            "status": "FAILED"
        }

    face_res = default_verification_provider.verify_face_match(selfie_bytes, doc_bytes)
    if not face_res.get("success"):
        _record_verification_audit(
            parent_user_id=map_data["parent_id"],
            child_id=child_id,
            status="FAILED",
            liveness=liveness_res.get("liveness_status", "PASSED"),
            face_match="FAILED",
            masked_id=id_res.get("masked_id"),
            consent=consent
        )
        return {
            "success": False,
            "error": face_res.get("error_message", "Face match failed."),
            "status": "FAILED"
        }

    # 3. Create or link Parent Account
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database error while processing verification."}

    cur = conn.cursor()

    cur.execute("SELECT user_id, password_hash, account_status FROM users WHERE email = %s", (parent_email,))
    parent_user = cur.fetchone()

    if parent_user:
        parent_id = parent_user["user_id"]
        # Update name if needed
        cur.execute("UPDATE users SET full_name = %s, account_status = 'ACTIVE' WHERE user_id = %s", (parent_name, parent_id))
    else:
        # Create parent account
        raw_pw = form_data.get("password", "")
        if not raw_pw:
            cur.close()
            conn.close()
            return {"success": False, "error": "Please set a password for your new LittleNet parent account."}

        pw_hash = bcrypt.hashpw(raw_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cur.execute("""
            INSERT INTO users(username, full_name, email, password_hash, role, account_status)
            VALUES(%s, %s, %s, %s, 'PARENT', 'ACTIVE')
            RETURNING user_id
        """, (parent_email, parent_name, parent_email, pw_hash))
        parent_id = cur.fetchone()["user_id"]

    # 4. Record Successful Verification Audit Log
    cur.execute("""
        INSERT INTO parent_verifications(
            parent_user_id,
            child_id,
            verification_provider,
            verification_status,
            liveness_status,
            face_match_status,
            document_type,
            masked_id,
            consent_given,
            consent_timestamp,
            verified_at
        )
        VALUES(%s, %s, %s, 'VERIFIED', 'PASSED', 'MATCHED', %s, %s, TRUE, NOW(), NOW())
    """, (
        parent_id,
        child_id,
        id_res.get("provider", "SANDBOX_MOCK"),
        doc_type,
        id_res.get("masked_id")
    ))

    # 5. Generate secure, expiring, single-use approval token
    approval_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)

    cur.execute("""
        UPDATE parent_child_map
        SET parent_id = %s,
            verified_parent_id = %s,
            approval_token = %s,
            approval_token_expires_at = %s,
            approval_status = 'AWAITING_PARENT_APPROVAL',
            is_token_used = FALSE
        WHERE verification_token = %s
    """, (parent_id, parent_id, approval_token, expires_at, token))

    conn.commit()
    cur.close()
    conn.close()

    # 6. Send Approval Email to Verified Parent Email
    approval_url = f"http://127.0.0.1:5000/parent/approve-child/{approval_token}/"
    try:
        with open("mailg/templates/approval_email.html", "r", encoding="utf-8") as f:
            template_content = f.read()
        approval_body = Template(template_content).render(
            parent_name=parent_name,
            child_name=map_data["child_name"],
            child_username=map_data["child_username"],
            child_age=map_data["child_age"],
            approval_url=approval_url
        )
    except Exception as e:
        print(f"[APPROVAL MAIL RENDER WARN] {e}")
        approval_body = f"""
        <h2>LittleNet Parent Approval</h2>
        <p>Parent identity verified for {parent_name}.</p>
        <p><a href="{approval_url}">Click here to log in and approve {map_data['child_name']}'s account</a></p>
        """

    send_email(
        parent_email,
        f"LittleNet: Review & Approve Child Account for {map_data['child_name']}",
        approval_body
    )

    return {
        "success": True,
        "status": "VERIFIED",
        "parent_id": parent_id,
        "parent_email": parent_email,
        "approval_token": approval_token,
        "masked_id": id_res.get("masked_id")
    }


def _record_verification_audit(parent_user_id, child_id, status, liveness, face_match, masked_id, consent):
    """Helper to record audit entry even on verification failure."""
    try:
        conn = get_db_connection()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO parent_verifications(
                parent_user_id,
                child_id,
                verification_status,
                liveness_status,
                face_match_status,
                masked_id,
                consent_given,
                consent_timestamp
            )
            VALUES(%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (parent_user_id, child_id, status, liveness, face_match, masked_id, consent))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("[AUDIT RECORD ERROR]", e)


def get_child_approval_details(approval_token, logged_in_parent_id):
    """
    Validates approval token, single-use status, expiration, and parent authorization.
    Returns structured data for the approval page or a specific invalid reason.
    """
    conn = get_db_connection()
    if not conn:
        return {"valid": False, "reason": "DATABASE_ERROR"}

    cur = conn.cursor()
    cur.execute("""
        SELECT 
            pcm.map_id,
            pcm.child_id,
            pcm.parent_id,
            pcm.verified_parent_id,
            pcm.parent_name,
            pcm.parent_email,
            pcm.approval_token,
            pcm.approval_token_expires_at,
            pcm.approval_status,
            pcm.approved,
            pcm.is_token_used,
            u.username AS child_username,
            u.full_name AS child_name,
            u.age AS child_age,
            u.email AS child_email,
            u.account_status AS child_account_status,
            u.created_at AS child_created_at
        FROM parent_child_map pcm
        JOIN users u ON pcm.child_id = u.user_id
        WHERE pcm.approval_token = %s
    """, (approval_token,))

    data = cur.fetchone()

    if not data:
        cur.close()
        conn.close()
        return {"valid": False, "reason": "INVALID_TOKEN"}

    # Check if token is already used
    if data["is_token_used"] or data["approved"]:
        cur.close()
        conn.close()
        return {"valid": False, "reason": "TOKEN_ALREADY_USED", "data": data}

    # Check expiration
    if data["approval_token_expires_at"]:
        now_utc = datetime.now(timezone.utc)
        expires_at = data["approval_token_expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now_utc > expires_at:
            cur.close()
            conn.close()
            return {"valid": False, "reason": "TOKEN_EXPIRED", "data": data}

    # Check parent ownership
    if logged_in_parent_id != data["parent_id"] and logged_in_parent_id != data["verified_parent_id"]:
        cur.close()
        conn.close()
        return {"valid": False, "reason": "UNAUTHORIZED_PARENT", "data": data}

    # Check parent verification status
    cur.execute("""
        SELECT verification_id, verification_status, masked_id, verified_at
        FROM parent_verifications
        WHERE parent_user_id = %s AND verification_status = 'VERIFIED'
        ORDER BY verified_at DESC
        LIMIT 1
    """, (logged_in_parent_id,))
    verification = cur.fetchone()

    cur.close()
    conn.close()

    if not verification:
        return {"valid": False, "reason": "PARENT_NOT_VERIFIED", "data": data}

    return {
        "valid": True,
        "child": {
            "child_id": data["child_id"],
            "full_name": data["child_name"],
            "username": data["child_username"],
            "age": data["child_age"],
            "email": data["child_email"],
            "created_at": data["child_created_at"],
            "status": data["child_account_status"]
        },
        "parent": {
            "parent_id": data["parent_id"],
            "name": data["parent_name"],
            "email": data["parent_email"]
        },
        "verification": {
            "status": verification["verification_status"],
            "masked_id": verification["masked_id"],
            "verified_at": verification["verified_at"]
        }
    }


def process_child_decision(approval_token, logged_in_parent_id, decision, rejection_reason=None):
    """
    Approves or rejects a child account with single-use token invalidation.
    Strictly verifies that logged_in_parent_id matches the linked verified parent.
    """
    check = get_child_approval_details(approval_token, logged_in_parent_id)
    if not check["valid"]:
        return {"success": False, "error": f"Cannot complete action: {check['reason']}"}

    child_id = check["child"]["child_id"]
    child_name = check["child"]["full_name"]
    child_email = check["child"]["email"]
    parent_email = check["parent"]["email"]

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database error while processing decision."}

    cur = conn.cursor()

    if decision.upper() == "APPROVE":
        cur.execute("UPDATE users SET account_status = 'ACTIVE' WHERE user_id = %s", (child_id,))
        cur.execute("""
            UPDATE parent_child_map
            SET approved = TRUE,
                approved_at = NOW(),
                is_token_used = TRUE,
                approval_status = 'APPROVED'
            WHERE approval_token = %s
        """, (approval_token,))
        conn.commit()
        cur.close()
        conn.close()

        # Send activation confirmation emails
        send_email(
            child_email,
            "LittleNet Account Approved!",
            f"<h2>Welcome to LittleNet, {child_name}!</h2><p>Your parent has verified their identity and approved your account. You can now log in at <a href='http://127.0.0.1:5000/login/'>LittleNet Login</a>.</p>"
        )
        return {"success": True, "action": "APPROVED", "child_name": child_name}

    else:
        cur.execute("UPDATE users SET account_status = 'REJECTED' WHERE user_id = %s", (child_id,))
        cur.execute("""
            UPDATE parent_child_map
            SET approved = FALSE,
                is_token_used = TRUE,
                approval_status = 'REJECTED',
                rejection_reason = %s
            WHERE approval_token = %s
        """, (rejection_reason or "Declined by supervising parent", approval_token))
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "action": "REJECTED", "child_name": child_name}


def approve_child_account(token):
    """
    Legacy wrapper for backward compatibility.
    """
    conn = get_db_connection()
    if not conn:
        return False
    cur = conn.cursor()
    cur.execute("SELECT child_id, parent_email, parent_id FROM parent_child_map WHERE approval_token = %s AND approved = FALSE", (token,))
    child = cur.fetchone()
    if not child:
        cur.close()
        conn.close()
        return False

    child_id = child["child_id"]
    cur.execute("UPDATE users SET account_status = 'ACTIVE' WHERE user_id = %s", (child_id,))
    cur.execute("UPDATE parent_child_map SET approved = TRUE, approved_at = NOW(), is_token_used = TRUE WHERE child_id = %s", (child_id,))
    conn.commit()
    cur.close()
    conn.close()
    return True


def login_user(email, password):
    """
    Authenticates a user (Child or Parent) with bcrypt verification.
    """
    conn = get_db_connection()
    if not conn:
        return None

    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (email.strip().lower(),))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return None

    try:
        if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            return None
    except Exception as e:
        print("[AUTH ERROR]", e)
        return None

    return user


def register_parent_account(token, form_data):
    """
    Registers a parent account from token.
    """
    conn = get_db_connection()
    if not conn:
        return False

    cur = conn.cursor()
    cur.execute("SELECT * FROM parent_child_map WHERE approval_token = %s OR verification_token = %s", (token, token))
    parent_data = cur.fetchone()

    if not parent_data:
        cur.close()
        conn.close()
        return False

    password_hash = bcrypt.hashpw(
        form_data["password"].encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    parent_name = parent_data["parent_name"]
    parent_email = parent_data["parent_email"]

    cur.execute("""
        INSERT INTO users(username, full_name, email, password_hash, role, account_status)
        VALUES(%s, %s, %s, %s, 'PARENT', 'ACTIVE')
        RETURNING user_id
    """, (parent_email, parent_name, parent_email, password_hash))

    parent_id = cur.fetchone()["user_id"]

    cur.execute("UPDATE parent_child_map SET parent_id = %s WHERE child_id = %s", (parent_id, parent_data["child_id"]))
    conn.commit()
    cur.close()
    conn.close()
    return True


def save_usage_log(child_id, login_time, logout_time, duration_minutes):
    """
    Logs child active session duration.
    """
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO child_usage_logs(child_id, login_time, logout_time, duration_minutes)
        VALUES(%s, %s, %s, %s)
    """, (child_id, login_time, logout_time, duration_minutes))
    conn.commit()
    cur.close()
    conn.close()