from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect
from flask import session
from flask import jsonify
from database.connection import get_db_connection
from child.service import follow_child, get_child_profile, is_following, delete_story, update_story_caption
from uploadPost.ml_service import check_image_safety, check_video_safety
from uploadPost.service import add_comment, delete_post, get_my_posts, get_post_comments, like_post, save_post, get_all_posts, is_liked, unlike_post, get_like_count, get_random_posts

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

    # ---------------------------------------------
    # CHECK LOGIN
    # ---------------------------------------------

    if "user_id" not in session:
        return redirect("/login/")


    # ---------------------------------------------
    # CHECK CHILD ROLE
    # ---------------------------------------------

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT role
        FROM users
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user or user["role"] != "CHILD":
        return jsonify(
            success=False,
            error="Only child users can create posts."
        ), 403


    # ---------------------------------------------
    # GET REQUEST
    # ---------------------------------------------

    if request.method == "GET":
        return render_template(
            "upload_post.html"
        )


    # ---------------------------------------------
    # GET MEDIA
    # ---------------------------------------------

    media = request.files.get("media")

    if not media or not media.filename:
        return jsonify(
            success=False,
            error="Please select an image or video."
        ), 400


    # ---------------------------------------------
    # FILE NAME + EXTENSION
    # ---------------------------------------------

    filename = secure_filename(
        media.filename
    )

    if not filename:
        return jsonify(
            success=False,
            error="Invalid file name."
        ), 400

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()


    # ---------------------------------------------
    # ALLOWED EXTENSIONS
    # ---------------------------------------------

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


    # ---------------------------------------------
    # FORM DATA
    # ---------------------------------------------

    caption = request.form.get(
        "caption",
        ""
    )

    content_category = request.form.get(
        "content_category",
        "Other"
    )


    # =================================================
    # IMAGE
    # =================================================

    if extension in image_extensions:

        filepath = os.path.join(
            "uploads/images",
            filename
        )

        media.save(filepath)

        try:

            moderation = check_image_safety(
                filepath
            )

        except Exception as e:

            print(
                "[UPLOAD ERROR] Image moderation error:",
                e
            )

            if os.path.exists(filepath):
                os.remove(filepath)

            return jsonify(
                success=False,
                error="An unexpected error occurred while checking your content."
            ), 400


        if not moderation["safe"]:

            if os.path.exists(filepath):
                os.remove(filepath)

            return jsonify(
                success=False,
                blocked=True,
                category=moderation.get(
                    "category",
                    "INAPPROPRIATE"
                ),
                score=moderation.get(
                    "score",
                    0
                ),
                message="This image contains inappropriate content and cannot be posted."
            ), 400


        # IMAGE IS SAFE → SAVE

        save_post(
            session["user_id"],
            "IMAGE",
            filepath,
            caption,
            content_category
        )

        return jsonify(
            success=True
        )


    # =================================================
    # VIDEO
    # =================================================

    if extension in video_extensions:

        filepath = os.path.join(
            "uploads/videos",
            filename
        )

        media.save(filepath)

        try:

            safety_result = check_video_safety(
                filepath
            )

        except Exception as e:

            print(
                "[UPLOAD ERROR] Video moderation error:",
                e
            )

            if os.path.exists(filepath):
                os.remove(filepath)

            return jsonify(
                success=False,
                error="An unexpected error occurred while checking your content."
            ), 400


        if not safety_result["safe"]:

            if os.path.exists(filepath):
                os.remove(filepath)

            return jsonify(
                success=False,
                blocked=True,
                category=safety_result.get(
                    "category",
                    "INAPPROPRIATE"
                ),
                score=safety_result.get(
                    "score",
                    0
                ),
                message="This video contains inappropriate content and cannot be posted."
            ), 400


        # VIDEO IS SAFE → SAVE

        save_post(
            session["user_id"],
            "VIDEO",
            filepath,
            caption,
            content_category
        )

        return jsonify(
            success=True
        )


    # ---------------------------------------------
    # UNSUPPORTED FILE
    # ---------------------------------------------

    return jsonify(
        success=False,
        error="Unsupported file type."
    ), 400

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


# ── AJAX: toggle like ─────────────────────────────────────────────────────────
@upload_bp.route("/api/like/<int:post_id>/", methods=["POST"])
def api_like(post_id):
    if "user_id" not in session:
        return jsonify(error="not logged in"), 401
    uid = session["user_id"]
    if is_liked(post_id, uid):
        unlike_post(post_id, uid)
        liked = False
    else:
        like_post(post_id, uid)
        liked = True
    return jsonify(liked=liked, count=get_like_count(post_id))


# ── AJAX: submit comment ──────────────────────────────────────────────────────
@upload_bp.route("/api/comment/<int:post_id>/", methods=["POST"])
def api_comment(post_id):
    if "user_id" not in session:
        return jsonify(error="not logged in"), 401
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="empty comment"), 400
    add_comment(post_id, session["user_id"], text)
    return jsonify(ok=True, full_name=session.get("full_name","You"), text=text)


# ── AJAX: get comments ────────────────────────────────────────────────────────
@upload_bp.route("/api/comments/<int:post_id>/")
def api_comments(post_id):
    if "user_id" not in session:
        return jsonify([]), 401
    comments = get_post_comments(post_id)
    return jsonify([{"full_name": c["full_name"], "text": c["comment_text"]} for c in comments])


# ── AJAX: single post detail (for profile lightbox) ──────────────────────────
@upload_bp.route("/api/post-detail/<int:post_id>/")
def api_post_detail(post_id):
    if "user_id" not in session:
        return jsonify(error="not logged in"), 401
    uid = session["user_id"]
    from database.connection import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, u.full_name,
               (SELECT COUNT(*) FROM likes l WHERE l.post_id=p.post_id) AS likes
        FROM posts p JOIN users u ON p.child_id=u.user_id
        WHERE p.post_id=%s
    """, (post_id,))
    p = cur.fetchone()
    comments = get_post_comments(post_id)
    cur.close(); conn.close()
    if not p:
        return jsonify(error="not found"), 404
    return jsonify(
        post_id=p["post_id"],
        full_name=p["full_name"],
        media_type=p["media_type"],
        media_path=(p["media_path"] or "").replace("\\","/"),
        caption=p["caption"] or "",
        likes=p["likes"],
        liked=is_liked(post_id, uid),
        comments=[{"full_name": c["full_name"], "comment_text": c["comment_text"]} for c in comments],
    )


# ── AJAX: random feed posts ───────────────────────────────────────────────────
@upload_bp.route("/api/random-posts/")
def api_random_posts():
    if "user_id" not in session:
        return jsonify([]), 401
    uid = session["user_id"]
    posts = get_random_posts(uid, limit=6)
    result = []
    for p in posts:
        result.append({
            "post_id":         p["post_id"],
            "full_name":       p["full_name"],
            "media_type":      p["media_type"],
            "media_path":      (p["media_path"] or "").replace("\\","/"),
            "caption":         p["caption"] or "",
            "content_category":p["content_category"] or "",
            "likes":           p["likes"],
            "comments_count":  p["comments_count"],
            "profile_picture": (p["profile_picture"] or "").replace("\\","/"),
            "liked":           is_liked(p["post_id"], uid),
        })
    return jsonify(result)


# ── Story upload (POST only, AJAX) — supports multiple files ─────────────────
@upload_bp.route("/upload-story/", methods=["POST"])
def upload_story():
    if "user_id" not in session:
        return jsonify(success=False, error="not logged in"), 401

    files = request.files.getlist("media")
    if not files or all(f.filename == "" for f in files):
        return jsonify(success=False, error="no file")

    caption    = request.form.get("caption", "")
    music_key  = request.form.get("music_key", "")
    music_file = request.files.get("music_file")

    # Build the music caption suffix
    music_suffix = ""
    if music_file and music_file.filename:
        mfname = secure_filename(music_file.filename)
        music_dir = os.path.join("uploads", "music")
        os.makedirs(music_dir, exist_ok=True)
        mfpath = os.path.join(music_dir, mfname).replace("\\", "/")
        music_file.save(mfpath)
        music_suffix = "||music_file:" + mfpath
    elif music_key:
        music_suffix = "||music:" + music_key

    image_extensions = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
    video_extensions = {"mp4", "mov", "avi", "mkv", "webm"}

    saved = 0
    for media in files:
        if not media or media.filename == "":
            continue
        filename = secure_filename(media.filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext in image_extensions:
            filepath = os.path.join("uploads/images", filename).replace("\\", "/")
            media.save(filepath)
            moderation = check_image_safety(filepath)
            if not moderation["safe"]:
                os.remove(filepath)
                continue
            save_post(session["user_id"], "IMAGE", filepath,
                      caption + music_suffix, "Story", is_story=True)
            saved += 1

        elif ext in video_extensions:
            filepath = os.path.join("uploads/videos", filename).replace("\\", "/")
            media.save(filepath)
            safety = check_video_safety(filepath)
            if not safety["safe"]:
                os.remove(filepath)
                continue
            save_post(session["user_id"], "VIDEO", filepath,
                      caption + music_suffix, "Story", is_story=True)
            saved += 1

    if saved > 0:
        return jsonify(success=True, count=saved)
    return jsonify(success=False, error="no safe media uploaded")


# ── Story delete ──────────────────────────────────────────────────────────────
@upload_bp.route("/api/delete-story/<int:post_id>/", methods=["POST"])
def api_delete_story(post_id):
    if "user_id" not in session:
        return jsonify(ok=False), 401
    delete_story(post_id, session["user_id"])
    return jsonify(ok=True)


# ── Story edit caption ────────────────────────────────────────────────────────
@upload_bp.route("/api/edit-story-caption/<int:post_id>/", methods=["POST"])
def api_edit_story_caption(post_id):
    if "user_id" not in session:
        return jsonify(ok=False), 401
    data = request.get_json(silent=True) or {}
    caption = (data.get("caption") or "").strip()
    update_story_caption(post_id, session["user_id"], caption)
    return jsonify(ok=True)

