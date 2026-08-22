from flask import *
from flask import render_template

from parent.service import get_parent_child
from quiz.service import *


quiz_bp = Blueprint(
    "quiz",
    __name__,
    template_folder="templates"
)


# ============================================================
# PARENT QUIZ SETTINGS
# ============================================================

@quiz_bp.route("/quiz/settings/")
def quiz_settings():

    parent_id = session["user_id"]

    child = get_parent_child(parent_id)

    child_id = child["user_id"]

    settings = get_quiz_settings(child_id)

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
            request.form["quiz_frequency"]
        ),

        "mandatory_quiz"
        in request.form

    )

    return redirect(
        "/quiz/settings/"
    )


# ============================================================
# START QUIZ
# ============================================================

@quiz_bp.route("/quiz/start/")
def start_quiz():

    # --------------------------------------------------------
    # Make sure child is logged in
    # --------------------------------------------------------

    if "user_id" not in session:

        return redirect("/login/")


    # --------------------------------------------------------
    # Get child ID
    # --------------------------------------------------------

    child_id = session["user_id"]


    # --------------------------------------------------------
    # Get child's age
    # --------------------------------------------------------

    age = get_child_age(child_id)

    age_group = get_child_age_group(child_id)
    print("========== QUIZ DEBUG ==========")
    print("CHILD ID:", child_id)
    print("AGE:", age)
    print("AGE GROUP:", age_group)
    print("================================")


    # --------------------------------------------------------
    # Check valid age
    # --------------------------------------------------------

    if age is None or age_group is None:

        return render_template(
            "quiz_result.html",
            error=(
                "This quiz is available for children "
                "between 6 and 13 years old."
            )
        )


    # --------------------------------------------------------
    # Get 5 questions for child's age
    # --------------------------------------------------------

    quizzes = get_quizzes_for_child(
        child_id,
        limit=5
    )
    print("NUMBER OF QUIZZES:", len(quizzes))
    print("QUIZ DATA:", quizzes)


    # --------------------------------------------------------
    # Make sure enough questions exist
    # --------------------------------------------------------

    if len(quizzes) < 5:

        return render_template(
            "quiz_result.html",
            error=(
                "There are not enough questions "
                "available for your age group yet."
            )
        )


    # --------------------------------------------------------
    # Store quiz information in session
    # --------------------------------------------------------

    session["quiz_questions"] = [
        quiz["quiz_id"]
        for quiz in quizzes
    ]

    session["quiz_current"] = 0

    session["quiz_score"] = 0

    session["quiz_age"] = age

    session["quiz_age_group"] = age_group


    # --------------------------------------------------------
    # Show first question
    # --------------------------------------------------------

    quiz = quizzes[0]


    return render_template(
        "quiz_card.html",
        quiz=quiz,
        question_number=1,
        total_questions=5,
        age=age,
        age_group=age_group
    )


# ============================================================
# SUBMIT ANSWER
# ============================================================

@quiz_bp.route(
    "/quiz/submit/",
    methods=["POST"]
)
def submit_quiz():

    # --------------------------------------------------------
    # Make sure child is logged in
    # --------------------------------------------------------

    if "user_id" not in session:

        return redirect("/login/")


    # --------------------------------------------------------
    # Make sure quiz has started
    # --------------------------------------------------------

    if "quiz_questions" not in session:

        return redirect("/quiz/start/")


    # --------------------------------------------------------
    # Get submitted answer
    # --------------------------------------------------------

    quiz_id = request.form.get("quiz_id")

    selected_answer = request.form.get("answer")


    if not quiz_id or not selected_answer:

        return redirect("/quiz/start/")


    quiz = get_quiz_by_id(
        int(quiz_id)
    )


    if not quiz:

        return redirect("/quiz/start/")


    # --------------------------------------------------------
    # Check answer
    # --------------------------------------------------------

    is_correct = (

        selected_answer
        ==
        quiz["correct_answer"]

    )


    # --------------------------------------------------------
    # Save attempt
    # --------------------------------------------------------

    save_quiz_attempt(

        session["user_id"],

        int(quiz_id),

        selected_answer,

        is_correct

    )


    # --------------------------------------------------------
    # Update score
    # --------------------------------------------------------

    if is_correct:

        session["quiz_score"] = (
            session.get("quiz_score", 0) + 1
        )


    # --------------------------------------------------------
    # Current question number
    # --------------------------------------------------------

    current_index = session.get(
        "quiz_current",
        0
    )


    # --------------------------------------------------------
    # Move to next question
    # --------------------------------------------------------

    next_index = current_index + 1


    # --------------------------------------------------------
    # Quiz finished
    # --------------------------------------------------------

    if next_index >= 5:

        final_score = session.get(
            "quiz_score",
            0
        )


        age = session.get(
            "quiz_age"
        )

        age_group = session.get(
            "quiz_age_group"
        )


        # Clear active quiz session

        session.pop(
            "quiz_questions",
            None
        )

        session.pop(
            "quiz_current",
            None
        )

        session.pop(
            "quiz_score",
            None
        )

        session.pop(
            "quiz_age",
            None
        )

        session.pop(
            "quiz_age_group",
            None
        )


        return render_template(

            "quiz_result.html",

            score=final_score,

            total=5,

            age=age,

            age_group=age_group

        )


    # --------------------------------------------------------
    # Save next question index
    # --------------------------------------------------------

    session["quiz_current"] = next_index


    # --------------------------------------------------------
    # Get next question
    # --------------------------------------------------------

    next_quiz_id = session[
        "quiz_questions"
    ][next_index]


    next_quiz = get_quiz_by_id(
        next_quiz_id
    )


    # --------------------------------------------------------
    # Show next question
    # --------------------------------------------------------

    return render_template(

        "quiz_card.html",

        quiz=next_quiz,

        question_number=next_index + 1,

        total_questions=5,

        age=session.get("quiz_age"),

        age_group=session.get("quiz_age_group"),

        previous_correct=is_correct

    )


# ============================================================
# PARENT QUIZ REPORT
# ============================================================

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