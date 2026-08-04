from flask import Blueprint, jsonify
from flask import render_template
from flask import request
from datetime import datetime

from auth.service import register_child,register_parent_account, save_usage_log
from child.service import profile_exists

from auth.service import login_user
from flask import request

from flask import session
from flask import redirect

auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="templates"
)


@auth_bp.route("/register-child", methods=["GET", "POST"])
def register_page():

    if request.method == "POST":

        register_child(request.form)

        return """
        <h2>
        Registration Successful.
        Waiting for Parent Approval.
        </h2>
        """

    return render_template("child_register.html")



from auth.service import approve_child_account

@auth_bp.route("/approve/<token>/")
def approve_child(token):

    result = approve_child_account(token)

    if result:
        return """
        <h2>
        Child Account Approved Successfully
        </h2>
        """

    return """
    <h2>
    Invalid Approval Link
    </h2>
    """



@auth_bp.route("/login/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = login_user(email, password)

        if not user:
            return "Invalid Email or Password"

        if user["role"] == "CHILD":

            if user["account_status"] != "ACTIVE":
                return "Waiting for Parent Approval"

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

            return redirect("/parent/dashboard/")

    return render_template("login.html")





@auth_bp.route("/register-parent/<token>/", methods=["GET", "POST"])
def register_parent(token):

    if request.method == "POST":

        register_parent_account(token, request.form)

        return """
        <h2>
        Parent Account Created Successfully
        </h2>
        """

    return render_template("parent_register.html")


@auth_bp.route("/logout/")
def logout():

    if "user_id" in session and session.get("role") == "CHILD":

        login_time_str = session.get("login_time")

        if login_time_str:

            login_time = datetime.fromisoformat(login_time_str)
            logout_time = datetime.now()

            duration_minutes = max(1, int(
                (logout_time - login_time).total_seconds() / 60
            ))

            save_usage_log(
                session["user_id"],
                login_time,
                logout_time,
                duration_minutes
            )

    session.clear()

    return redirect("/login/")