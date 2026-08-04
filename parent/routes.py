from flask import Blueprint, redirect, request
from flask import render_template
from flask import session

from parent.service import (
    get_child_content_for_approval,
    get_child_followers,
    get_child_following,
    get_child_posts,
    get_deleted_posts,
    get_parent_child,
    get_parent_children,
    get_time_limit,
    get_weekly_usage,
    save_child_content_approval,
    save_time_limit
)

parent_bp = Blueprint(
    "parent",
    __name__,
    template_folder="templates"
)


@parent_bp.route("/parent/dashboard/")
def parent_dashboard():

    children = get_parent_children(
        session["user_id"]
    )

    return render_template(
        "parent_dashboard.html",
        children=children
    )

from parent.service import get_child_profile_for_parent

@parent_bp.route("/parent/child/<int:child_id>/")
def view_child_profile(child_id):

    profile = get_child_profile_for_parent(
        child_id
    )

    return render_template(
        "child_profile_view.html",
        profile=profile
    )

@parent_bp.route(
    "/parent/approve-content/"
)
def approve_content():

    content = get_child_content_for_approval(
        session["user_id"]
    )

    return render_template(
        "approve_content.html",
        content=content
    )

@parent_bp.route(
    "/parent/save-approval/",
    methods=["POST"]
)
def save_approval():

    skill_ids = request.form.getlist("skills")
    interest_ids = request.form.getlist("interests")
    ambition_ids = request.form.getlist("ambitions")

    content = get_child_content_for_approval(
        session["user_id"]
    )

    save_child_content_approval(
        content["child_id"],
        skill_ids,
        interest_ids,
        ambition_ids
    )

    return """
    <h2>
    Approval Saved Successfully
    </h2>
    """

@parent_bp.route(
    "/parent/deleted-posts/"
)
def deleted_posts():

    posts = get_deleted_posts()

    return render_template(
        "deleted_posts.html",
        posts=posts
    )

@parent_bp.route(
    "/parent/time-limit/",
    methods=["GET", "POST"]
)
def time_limit():

    child = get_parent_child(
        session["user_id"]
    )

    if request.method == "POST":

        save_time_limit(
            child["user_id"],
            request.form["daily_limit"],
            "strict_mode" in request.form
        )

        return redirect("/parent/time-limit/")

    limit_data = get_time_limit(
        child["user_id"]
    )

    return render_template(
        "time_limit.html",
        child=child,
        limit_data=limit_data
    )

@parent_bp.route(
    "/parent/usage-report/"
)
def usage_report():

    child = get_parent_child(
        session["user_id"]
    )

    report = get_weekly_usage(
        child["user_id"]
    )

    return render_template(
        "usage_report.html",
        report=report
    )

@parent_bp.route("/parent/child-posts/")
def child_posts():

    child = get_parent_child(
        session["user_id"]
    )

    posts = get_child_posts(
        child["user_id"]
    )

    return render_template(
        "child_posts.html",
        posts=posts,
        child=child
    )

@parent_bp.route(
    "/parent/child-connections/"
)
def child_connections():

    parent_id = session["user_id"]

    child = get_parent_child(
        session["user_id"]
    )

    child_id = child["user_id"]

    followers = get_child_followers(
        child_id
    )

    following = get_child_following(
        child_id
    )

    return render_template(

        "child_connections.html",

        followers=followers,

        following=following

    )