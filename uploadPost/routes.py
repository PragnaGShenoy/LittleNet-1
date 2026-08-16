from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect
from flask import session
from child.service import follow_child, get_child_profile, is_following
from uploadPost.ml_service import check_image_safety, check_video_safety
from uploadPost.service import add_comment, delete_post, get_my_posts, get_post_comments,  like_post, save_post
from uploadPost.service import get_all_posts

import os

from werkzeug.utils import secure_filename

upload_bp = Blueprint(
    "upload",
    __name__,
    template_folder="templates"
)

@upload_bp.route(
    "/child/upload-post/",
    methods=["GET", "POST"]
)
def upload_post():

    if "user_id" not in session:
        return redirect("/login/")

    if request.method == "POST":

        media = request.files["media"]

        filename = secure_filename(
            media.filename
        )

        extension = filename.split(".")[-1].lower()

        image_extensions = [
            "jpg",
            "jpeg",
            "png",
            "gif",
            "webp"
        ]

        video_extensions = [
            "mp4",
            "mov",
            "avi",
            "mkv"
        ]

        

        if extension in image_extensions:

            filepath = os.path.join(
                "uploads/images",
                filename
            )

            media.save(filepath)

            moderation = check_image_safety(filepath)

            if not moderation["safe"]:

                os.remove(filepath)

                return f"""
                    Upload Rejected

                Reason:
                    {moderation['category']}
                """

            save_post(
                session["user_id"],
                "IMAGE",
                filepath,
                request.form["caption"],
                request.form["content_category"]
             )

            return """
               Image Uploaded Successfully
            """

        if extension in video_extensions:

            filepath = os.path.join(
                    "uploads/videos",
                    filename
                )

            media.save(filepath)

            safety_result = check_video_safety(
                    filepath
                )

            if not safety_result["safe"]:

                os.remove(filepath)

                return f"""
                    Unsafe Content Detected

                    Category:
                        {safety_result['category']}
                    Score:
                        {safety_result['score']}"""

            save_post(
                session["user_id"],
                "VIDEO",
                filepath,
                request.form["caption"],
                request.form["content_category"]
            )

            return """
            <h2>
                Video Uploaded Successfully
            </h2>
            """

        return "Unsupported File Type"

    return render_template(
        "upload_post.html"
    )

@upload_bp.route("/feed/")
def feed():

    if "user_id" not in session:
        return redirect("/login/")

    posts = get_all_posts()

    for post in posts:

        post["is_following"] = is_following(
            session["user_id"],
            post["child_id"]
        )

    return render_template(
        "feed.html",
        posts=posts
    )


@upload_bp.route("/my-posts/")
def my_posts():

    posts = get_my_posts(session["user_id"])

    for post in posts:
        post["comments"] = get_post_comments(post["post_id"])

    profile = get_child_profile(session["user_id"])

    return render_template(
        "my_posts.html",
        posts=posts,
        profile=profile,
    )
@upload_bp.route("/like/<int:post_id>/")
def like(post_id):

    print("LIKE CLICKED")
    print("POST ID:", post_id)
    print("USER ID:", session["user_id"])

    like_post(
        post_id,
        session["user_id"]
    )

    return "Like Saved"


@upload_bp.route(
    "/delete-post/<int:post_id>/"
)
def delete_post_route(post_id):

    delete_post(post_id)

    return redirect("/my-posts/")

@upload_bp.route(
    "/comment/<int:post_id>/",
    methods=["POST"]
)
def comment(post_id):

    if "user_id" not in session:
        return redirect("/login/")

    add_comment(
        post_id,
        session["user_id"],
        request.form["comment"]
    )

    return redirect("/recommended/")


