from flask import Blueprint, jsonify
import flask
from parent.service import get_child_profile_for_parent, get_parent_children

parent_api_bp = Blueprint(
    "parent_api",
    __name__
)

@parent_api_bp.route("/api/parent/child/<int:child_id>/", methods=["GET"])
def api_child_profile(child_id):

    profile = get_child_profile_for_parent(child_id)

    if not profile:

        return flask.jsonify({

            "success": False,
            "message": "Child not found"

        }), 404

    return flask.jsonify({

        "success": True,

        "profile": {

            "user_id": profile["child_id"],
            "full_name": profile["full_name"],
            "age": profile["age"],
            "school_name": profile["school_name"],
            "location": profile["location"],
            "current_class": profile["current_class"],
            "bio": profile["bio"]

        }

    })

@parent_api_bp.route("/api/parent/children/<int:parent_id>/")
def api_parent_children(parent_id):

    children = get_parent_children(parent_id)

    return jsonify({

        "success": True,
        "children": children

    })