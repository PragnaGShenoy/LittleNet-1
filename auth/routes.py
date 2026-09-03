import base64
from datetime import datetime
from flask import Blueprint, render_template, request, session, redirect, jsonify, url_for

from auth.service import (
    register_child,
    get_parent_verification_data,
    process_parent_verification,
    get_child_approval_details,
    process_child_decision,
    login_user,
    save_usage_log
)
from child.service import profile_exists
from database.connection import get_db_connection

auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="templates"
)


@auth_bp.route("/register-child", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        result = register_child(request.form)
        if result.get("success"):
            return render_template(
                "child_register.html",
                success_msg=True,
                parent_email=result.get("parent_email"),
                verification_link=f"/verify-parent/{result.get('verification_token')}/"
            )
        return render_template(
            "child_register.html",
            error=result.get("error"),
            form_data=request.form
        ), 400

    return render_template("child_register.html")


@auth_bp.route("/verify-parent/<token>/", methods=["GET", "POST"])
def verify_parent(token):
    child_data = get_parent_verification_data(token)
    if not child_data:
        return render_template(
            "approval_success.html",
            is_error=True,
            title="Invalid Verification Link",
            message="This parent identity verification link is invalid or has already been used.",
            button_url="/login/",
            button_text="Go to Login"
        ), 404

    # Check if parent account exists already
    conn = get_db_connection()
    parent_exists = False
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE email = %s AND role = 'PARENT'", (child_data["parent_email"].lower(),))
        parent_exists = bool(cur.fetchone())
        cur.close()
        conn.close()

    if request.method == "POST":
        selfie_b64 = request.form.get("selfie_data", "")
        selfie_bytes = b""
        if selfie_b64 and "base64," in selfie_b64:
            try:
                selfie_bytes = base64.b64decode(selfie_b64.split("base64,")[1])
            except Exception as e:
                print("[SELFIE DECODE ERROR]", e)

        result = process_parent_verification(token, request.form, selfie_bytes)
        if not result.get("success"):
            return render_template(
                "parent_verify.html",
                child=child_data,
                parent_exists=parent_exists,
                error=result.get("error")
            ), 400

        # Auto-login newly verified parent into session
        session["user_id"] = result["parent_id"]
        session["role"] = "PARENT"
        session["full_name"] = request.form.get("parent_name", child_data["parent_name"])

        # Redirect straight to child approval page
        approval_token = result.get("approval_token")
        return redirect(f"/parent/approve-child/{approval_token}/")

    return render_template("parent_verify.html", child=child_data, parent_exists=parent_exists)


@auth_bp.route("/parent/approve-child/<token>/", methods=["GET", "POST"])
def parent_approve_child(token):
    # Require authentication as PARENT
    if "user_id" not in session or session.get("role") != "PARENT":
        return redirect(f"/login/?next=/parent/approve-child/{token}/")

    logged_in_parent_id = session["user_id"]
    check = get_child_approval_details(token, logged_in_parent_id)

    if request.method == "POST":
        if not check.get("valid"):
            return render_template(
                "approval_success.html",
                is_error=True,
                title="Action Failed",
                message=f"Cannot process request: {check.get('reason')}",
                button_url="/parent/dashboard/",
                button_text="Go to Parent Dashboard"
            ), 403

        decision = request.form.get("decision", "APPROVE")
        rejection_reason = request.form.get("rejection_reason")
        result = process_child_decision(token, logged_in_parent_id, decision, rejection_reason)

        if result.get("success"):
            if result.get("action") == "APPROVED":
                return render_template(
                    "approval_success.html",
                    is_verified=True,
                    title="Child Account Approved!",
                    message=f"You have successfully verified and activated {result.get('child_name')}'s account. Your parental supervision controls are now active.",
                    button_url="/parent/dashboard/",
                    button_text="Go to Parent Dashboard"
                )
            else:
                return render_template(
                    "approval_success.html",
                    is_error=True,
                    title="Account Declined",
                    message=f"You have declined the registration request for {result.get('child_name')}.",
                    button_url="/parent/dashboard/",
                    button_text="Go to Parent Dashboard"
                )

        return render_template(
            "approval_success.html",
            is_error=True,
            title="Error",
            message=result.get("error", "An error occurred."),
            button_url="/parent/dashboard/",
            button_text="Go to Parent Dashboard"
        ), 400

    return render_template(
        "approve_child.html",
        valid=check.get("valid"),
        reason=check.get("reason"),
        child=check.get("child"),
        parent=check.get("parent"),
        verification=check.get("verification")
    )


@auth_bp.route("/approve/<token>/")
def approve_child_redirect(token):
    """Legacy redirect to secure parent approval endpoint."""
    return redirect(f"/parent/approve-child/{token}/")


@auth_bp.route("/login/", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next") or request.form.get("next") or ""

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        user = login_user(email, password)

        if not user:
            return render_template("login.html", error="Invalid Email or Password"), 401

        if user["role"] == "CHILD":
            if user["account_status"] != "ACTIVE":
                return render_template(
                    "login.html",
                    error="Your account is waiting for Parent Identity Verification and Approval."
                ), 403

            session["user_id"] = user["user_id"]
            session["role"] = user["role"]
            session["full_name"] = user["full_name"]
            session["login_time"] = datetime.now().isoformat()

            if not profile_exists(user["user_id"]):
                return redirect("/child/create-profile/")

            return redirect("/child/dashboard/")

        if user["role"] == "PARENT":
            session["user_id"] = user["user_id"]
            session["role"] = user["role"]
            session["full_name"] = user["full_name"]

            # If user came with a valid next URL (e.g. pending child approval), redirect there
            if next_url and next_url.startswith("/"):
                return redirect(next_url)

            return redirect("/parent/dashboard/")

    return render_template("login.html", next_url=next_url)


@auth_bp.route("/register-parent/<token>/", methods=["GET", "POST"])
def register_parent(token):
    """Redirect to verified parent portal."""
    return redirect(f"/verify-parent/{token}/")


@auth_bp.route("/logout/")
def logout():
    if "user_id" in session and session.get("role") == "CHILD":
        login_time_str = session.get("login_time")
        if login_time_str:
            try:
                login_time = datetime.fromisoformat(login_time_str)
                logout_time = datetime.now()
                duration_minutes = max(1, int((logout_time - login_time).total_seconds() / 60))
                save_usage_log(session["user_id"], login_time, logout_time, duration_minutes)
            except Exception as e:
                print("[LOGOUT USAGE LOG ERROR]", e)

    session.clear()
    return redirect("/login/")