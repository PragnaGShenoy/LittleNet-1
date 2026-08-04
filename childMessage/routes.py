import os
from flask import Blueprint, redirect, request, render_template, session, jsonify
from werkzeug.utils import secure_filename

from child.service import get_child_profile
from childMessage.service import (
    get_all_children,
    get_recent_conversations,
    get_conversation,
    create_conversation,
    get_messages,
    send_text_message,
    send_media_message
)

child_message_bp = Blueprint(
    "child_message", __name__,
    template_folder="templates"
)

MEDIA_UPLOAD_FOLDER = "uploads/messages"

ALLOWED_IMAGE = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_VIDEO = {"mp4", "mov", "avi", "mkv"}
ALLOWED_AUDIO = {"webm", "ogg", "mp3", "wav", "m4a"}
ALLOWED_FILE  = {"pdf", "doc", "docx", "txt"}


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


# ==========================================
# MESSAGE LIST
# ==========================================

@child_message_bp.route("/messages/")
def messages():

    if "user_id" not in session:
        return redirect("/login/")

    recent = get_recent_conversations(session["user_id"])
    children = get_all_children(session["user_id"])

    # Build a set of user_ids already in recent, to avoid duplicates in "new chat" list
    recent_ids = {r["user_id"] for r in recent}
    new_children = [c for c in children if c["user_id"] not in recent_ids]

    return render_template(
        "chat_list.html",
        recent=recent,
        children=new_children
    )


# ==========================================
# OPEN CHILD CHAT
# ==========================================

@child_message_bp.route("/chat/<int:child_id>/")
def chat(child_id):

    if "user_id" not in session:
        return redirect("/login/")

    current_child_id = session["user_id"]

    if current_child_id == child_id:
        return redirect("/messages/")

    conversation = get_conversation(current_child_id, child_id)

    if conversation is None:
        conversation_id = create_conversation(current_child_id, child_id)
    else:
        conversation_id = conversation["conversation_id"]

    messages_list = get_messages(conversation_id)

    # Get receiver name
    all_children = get_all_children(current_child_id)
    receiver_name = next(
        (c["full_name"] for c in all_children if c["user_id"] == child_id),
        "Chat"
    )

    return render_template(
        "chat.html",
        messages=messages_list,
        current_child_id=current_child_id,
        receiver_child_id=child_id,
        receiver_name=receiver_name,
        conversation_id=conversation_id
    )


# ==========================================
# SEND TEXT MESSAGE
# ==========================================

@child_message_bp.route("/send-message/<int:child_id>/", methods=["POST"])
def send_message(child_id):

    if "user_id" not in session:
        return redirect("/login/")

    current_child_id = session["user_id"]
    message_text = (request.form.get("message_text") or "").strip()

    if not message_text:
        return redirect(f"/chat/{child_id}/")

    conversation = get_conversation(current_child_id, child_id)
    if conversation is None:
        conversation_id = create_conversation(current_child_id, child_id)
    else:
        conversation_id = conversation["conversation_id"]

    send_text_message(conversation_id, current_child_id, child_id, message_text)

    return redirect(f"/chat/{child_id}/")


# ==========================================
# SEND MEDIA MESSAGE (image / video / voice / file)
# ==========================================

@child_message_bp.route("/send-media/<int:child_id>/", methods=["POST"])
def send_media(child_id):

    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    current_child_id = session["user_id"]

    media_file = request.files.get("media")
    if not media_file or media_file.filename == "":
        return jsonify({"error": "No file"}), 400

    filename = secure_filename(media_file.filename)
    ext = _ext(filename)

    if ext in ALLOWED_IMAGE:
        message_type = "IMAGE"
        subfolder = "images"
    elif ext in ALLOWED_VIDEO:
        message_type = "VIDEO"
        subfolder = "videos"
    elif ext in ALLOWED_AUDIO:
        message_type = "VOICE"
        subfolder = "audio"
    elif ext in ALLOWED_FILE:
        message_type = "FILE"
        subfolder = "files"
    else:
        return jsonify({"error": "File type not allowed"}), 400

    save_dir = os.path.join(MEDIA_UPLOAD_FOLDER, subfolder)
    os.makedirs(save_dir, exist_ok=True)

    filepath = os.path.join(save_dir, filename)
    media_file.save(filepath)

    conversation = get_conversation(current_child_id, child_id)
    if conversation is None:
        conversation_id = create_conversation(current_child_id, child_id)
    else:
        conversation_id = conversation["conversation_id"]

    send_media_message(
        conversation_id,
        current_child_id,
        child_id,
        message_type,
        filepath
    )

    return jsonify({
        "ok": True,
        "message_type": message_type,
        "media_path": filepath
    })
