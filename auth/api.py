from flask import Blueprint
from flask import jsonify
from flask import request

from auth.service import login_user
from child.service import profile_exists

api_bp = Blueprint(
    "api",
    __name__
)

@api_bp.route(
    "/api/login/",
    methods=["POST"]
)
def api_login():

    print("Mobile Login API Called")

    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    user = login_user(
        email,
        password
    )

    if not user:

        return jsonify({

            "success": False,
            "message": "Invalid Email or Password"

        }), 401

    if user["role"] == "CHILD":

        if user["account_status"] != "ACTIVE":

            return jsonify({

                "success": False,
                "message": "Waiting for Parent Approval"

            }), 403

        return jsonify({

            "success": True,
            "role": "CHILD",
            "user_id": user["user_id"],
            "full_name": user["full_name"],
            "has_profile": profile_exists(
                user["user_id"]
            )

        })

    return jsonify({

        "success": True,
        "role": "PARENT",
        "user_id": user["user_id"],
        "full_name": user["full_name"]

    })