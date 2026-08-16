import os
from datetime import datetime
from flask import Blueprint, redirect, request, jsonify
from flask import render_template
from flask import session
from werkzeug.utils import secure_filename

from child.service import create_child_profile, follow_child, get_followers, get_followers_count, get_following, get_following_count, get_post_comments, get_post_count, get_random_children, get_recommended_posts, get_remaining_time, is_child_locked, is_following, unfollow_child, update_child_profile, update_profile_picture
from child.service import get_child_profile
from parent.service import get_time_limit
from quiz.service import get_child_quiz_settings, get_quiz_for_child

child_bp = Blueprint(
    "child",
    __name__,
    template_folder="templates"
)


def _accurate_remaining_seconds(child_id):
    """Remaining seconds including the current live session elapsed time."""
    remaining_minutes = get_remaining_time(child_id)
    if remaining_minutes is None:
        return None
    login_time_str = session.get("login_time")
    if login_time_str:
        elapsed_seconds = int(
            (datetime.now() - datetime.fromisoformat(login_time_str)).total_seconds()
        )
    else:
        elapsed_seconds = 0
    return max(0, remaining_minutes * 60 - elapsed_seconds)


@child_bp.route("/api/time-remaining/")
def api_time_remaining():
    """JSON endpoint — polled by client-side countdown on every child page."""
    if "user_id" not in session or session.get("role") != "CHILD":
        return jsonify({"error": "not logged in"}), 401

    remaining_seconds = _accurate_remaining_seconds(session["user_id"])
    limit_data = get_time_limit(session["user_id"])
    strict = bool(limit_data and limit_data.get("strict_mode"))

    return jsonify({
        "remaining_seconds": remaining_seconds,
        "strict_mode": strict
    })


@child_bp.route("/child/dashboard/")
def dashboard():

    if "user_id" not in session:
        return redirect("/login/")

    limit_data = get_time_limit(session["user_id"])

    # Use accurate remaining (includes current session)
    remaining_seconds = _accurate_remaining_seconds(session["user_id"])
    strict = bool(limit_data and limit_data.get("strict_mode"))

    # Kick out immediately if time already expired in strict mode
    if strict and remaining_seconds is not None and remaining_seconds <= 0:
        return render_template("time_limit_reached.html")

    return render_template(
        "child_dashboard.html",
        full_name=session["full_name"],
        remaining_seconds=remaining_seconds,
        strict_mode=strict
    )

@child_bp.route(
    "/time-limit-reached/"
)
def time_limit_reached():

    return render_template(
        "time_limit_reached.html"
    )

@child_bp.route("/child/create-profile/", methods=["GET", "POST"])
def create_profile():

    if "user_id" not in session:
        return redirect("/login/")

    if request.method == "POST":

        create_child_profile(
            session["user_id"],
            request.form
        )

        return redirect("/child/dashboard/")

    return render_template("create_profile.html")

@child_bp.route("/child/profile/")
def profile():

    if "user_id" not in session:
        return redirect("/login/")

    child_id = session["user_id"]
    profile_data = get_child_profile(child_id)

    return render_template(
        "profile.html",
        profile=profile_data,
        post_count=get_post_count(child_id),
        followers_count=get_followers_count(child_id),
        following_count=get_following_count(child_id),
    )


@child_bp.route(
    "/child/edit-profile/",
    methods=["GET", "POST"]
)
def edit_profile():

    if "user_id" not in session:
        return redirect("/login/")

    if request.method == "POST":

        update_child_profile(
            session["user_id"],
            request.form
        )

        return redirect("/child/profile/")

    profile_data = get_child_profile(
        session["user_id"]
    )

    return render_template(
        "edit_profile.html",
        profile=profile_data
    )

@child_bp.route(
    "/follow/<int:child_id>/"
)
def follow(child_id):

    current_user = session["user_id"]

    # Don't follow yourself
    if current_user == child_id:
        return redirect("/feed/")

    if is_following(
        current_user,
        child_id
    ):

        unfollow_child(
            current_user,
            child_id
        )

    else:

        follow_child(
            current_user,
            child_id
        )

    return redirect("/discover/")

@child_bp.route("/followers/")
def followers():

    followers_list = get_followers(
        session["user_id"]
    )

    return render_template(
        "followers.html",
        followers=followers_list
    )

@child_bp.route("/following/")
def following():

    following_list = get_following(
        session["user_id"]
    )

    return render_template(
        "following.html",
        following=following_list
    )

@child_bp.route("/unfollow/<int:child_id>/")
def unfollow(child_id):

    unfollow_child(
        session["user_id"],
        child_id
    )

    return redirect("/discover/")


@child_bp.route("/recommended/")
def recommended():

    if "user_id" not in session:
        return redirect("/login/")

    page = int(
        request.args.get(
            "page",
            1
        )
    )

    limit = 5

    offset = (
        page - 1
    ) * limit

    posts = get_recommended_posts(
        session["user_id"],
        limit,
        offset
    )

    for post in posts:

        post["comments"] = get_post_comments(
            post["post_id"]
        )

    settings = get_child_quiz_settings(
        session["user_id"]
    )

    feed_items = []

    if settings:

       frequency = settings[
          "quiz_frequency"
       ]

    else:

        frequency = 999999


    global_position = offset

    for post in posts:

        global_position += 1

        feed_items.append({

        "type": "POST",

        "data": post

       })

    if global_position % frequency == 0:

        quiz = get_quiz_for_child(
            session["user_id"]
        )

        if quiz:

            feed_items.append({

                "type": "QUIZ",

                "data": quiz

            })

    quiz_result = session.pop(
    "quiz_result",
        None
    )

    return render_template(

    "recommended.html",

    feed_items=feed_items,

    settings=settings,

    quiz_result=quiz_result,

    page=page
)

@child_bp.route("/child/upload-profile-picture/", methods=["POST"])
def upload_profile_picture():

    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    photo = request.files.get("photo")
    if not photo or photo.filename == "":
        return jsonify({"error": "No file"}), 400

    allowed = {"jpg", "jpeg", "png", "gif", "webp"}
    ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
    if ext not in allowed:
        return jsonify({"error": "Invalid file type"}), 400

    save_dir = os.path.join("uploads", "profile_pictures")
    os.makedirs(save_dir, exist_ok=True)

    filename = f"profile_{session['user_id']}.{ext}"
    filepath = os.path.join(save_dir, filename)
    photo.save(filepath)

    update_profile_picture(session["user_id"], filepath)

    return jsonify({"ok": True, "path": "/" + filepath})


@child_bp.route("/discover/")
def discover():

    children = get_random_children(
        session["user_id"]
    )

    for child in children:

        child["is_following"] = is_following(
            session["user_id"],
            child["user_id"]
        )

    return render_template(
        "discover.html",
        children=children
    )


