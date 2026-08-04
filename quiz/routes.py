from flask import *
from flask import render_template
from parent.service import get_parent_child
from quiz.service import *

quiz_bp = Blueprint(
    "quiz",
    __name__,
    template_folder="templates"
)

@quiz_bp.route(
    "/quiz/settings/"
)
def quiz_settings():

    parent_id = session["user_id"]
    child = get_parent_child(parent_id)
    child_id = child["user_id"]

    settings = get_quiz_settings(
        child_id
    )

    return render_template(
        "parent_quiz_settings.html",
        settings=settings
    )

@quiz_bp.route(
    "/quiz/save-settings/",
    methods=["POST"]
)
def save_settings():

    parent_id = session["user_id"]
    child = get_parent_child(parent_id)

    child_id = child["user_id"]

    save_quiz_settings(

        parent_id,

        child_id,

        int(
            request.form[
                "quiz_frequency"
            ]
        ),

        "mandatory_quiz"
        in request.form

    )

    return redirect(
        "/quiz/settings/"
    )

@quiz_bp.route(
    "/quiz/submit/",
    methods=["POST"]
)
def submit_quiz():

    quiz_id = request.form[
        "quiz_id"
    ]

    selected_answer = request.form[
        "answer"
    ]

    quiz = get_quiz_by_id(
        quiz_id
    )

    is_correct = (

        selected_answer

        ==

        quiz[
            "correct_answer"
        ]

    )

    save_quiz_attempt(

        session["user_id"],

        quiz_id,

        selected_answer,

        is_correct

    )

    session["quiz_result"] = {

        "is_correct": is_correct,

        "correct_answer":
        quiz["correct_answer"]

    }

    return redirect(
        request.referrer
    )

@quiz_bp.route(
    "/parent/quiz-report/"
)
def parent_quiz_report():

    parent_id = session["user_id"]
    child = get_parent_child(parent_id)
    child_id = child["user_id"]

    attempts = get_quiz_attempts(
        child_id
    )

    summary = get_quiz_summary(
        child_id
    )

    return render_template(

        "parent_quiz_report.html",

        attempts=attempts,

        summary=summary

    )