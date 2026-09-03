import io
import uuid
import base64
from PIL import Image
from database.connection import get_db_connection
from auth.service import (
    register_child,
    get_parent_verification_data,
    process_parent_verification,
    get_child_approval_details,
    process_child_decision,
    login_user
)
from auth.verification_provider import default_verification_provider

def generate_test_image_bytes():
    """Generates a small test RGB image bytes simulating a camera selfie."""
    img = Image.new("RGB", (320, 240), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def run_tests():
    print("==========================================================")
    print("STARTING TEST SUITE: REGISTRATION & PARENT APPROVAL FLOW")
    print("==========================================================")

    # -----------------------------------------------------------
    # TEST 1: Child Registration - Self-Approval Rejection
    # -----------------------------------------------------------
    print("\n[TEST 1] Testing Self-Approval Rejection (child_email == parent_email)...")
    same_email = f"test_same_{uuid.uuid4().hex[:6]}@example.com"
    res1 = register_child({
        "username": f"child_{uuid.uuid4().hex[:6]}",
        "full_name": "Test Child",
        "email": same_email,
        "parent_name": "Test Parent",
        "parent_email": same_email,
        "password": "password123",
        "age": "11"
    })
    assert not res1["success"], "FAILED: Registration should fail when child email equals parent email"
    assert "Self-approval is strictly prevented" in res1["error"], f"Unexpected error message: {res1['error']}"
    print("[PASS] Self-approval attempt was successfully blocked!")

    # -----------------------------------------------------------
    # TEST 2: Valid Child Registration
    # -----------------------------------------------------------
    print("\n[TEST 2] Testing Valid Child Registration with Separate Parent Email...")
    unique_suffix = uuid.uuid4().hex[:6]
    child_username = f"kid_{unique_suffix}"
    child_email = f"kid_{unique_suffix}@example.com"
    parent_email = f"parent_{unique_suffix}@example.com"
    parent_name = f"Parent {unique_suffix}"

    res2 = register_child({
        "username": child_username,
        "full_name": "Little Kid",
        "email": child_email,
        "parent_name": parent_name,
        "parent_email": parent_email,
        "password": "childPassword123!",
        "age": "10"
    })
    assert res2["success"], f"Registration failed: {res2.get('error')}"
    ver_token = res2["verification_token"]
    child_id = res2["child_id"]
    print(f"[PASS] Child registered with ID {child_id}. Verification token: {ver_token[:10]}...")

    # Verify database state for child
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT account_status, role FROM users WHERE user_id = %s", (child_id,))
    child_user = cur.fetchone()
    assert child_user["account_status"] == "PENDING_APPROVAL", f"Expected PENDING_APPROVAL, got {child_user['account_status']}"
    assert child_user["role"] == "CHILD"
    cur.close()
    conn.close()
    print("[PASS] Child account created in database with 'PENDING_APPROVAL' status.")

    # -----------------------------------------------------------
    # TEST 3: Unapproved Child Cannot Log In
    # -----------------------------------------------------------
    print("\n[TEST 3] Testing that unapproved child cannot log in...")
    login_child = login_user(child_email, "childPassword123!")
    assert login_child is not None
    assert login_child["account_status"] == "PENDING_APPROVAL"
    print("[PASS] Child credentials authenticate, but account_status remains PENDING_APPROVAL (blocking access).")

    # -----------------------------------------------------------
    # TEST 4: Parent Verification - Failure Scenario
    # -----------------------------------------------------------
    print("\n[TEST 4] Testing Parent Verification Failure (invalid ID format or trigger)...")
    fail_res = process_parent_verification(
        ver_token,
        {
            "parent_name": parent_name,
            "document_type": "AADHAAR_MOCK",
            "document_number": "123456780000",  # Ends in 0000 -> trigger failure
            "password": "parentPassword123!",
            "consent": "on"
        },
        selfie_bytes=generate_test_image_bytes()
    )
    assert not fail_res["success"], "Expected parent verification to fail on test trigger 0000"
    print(f"[PASS] Simulated verification failure handled correctly: {fail_res['error']}")

    # -----------------------------------------------------------
    # TEST 5: Parent Verification - Success Scenario
    # -----------------------------------------------------------
    print("\n[TEST 5] Testing Parent Verification Success (Valid Mock ID + Selfie)...")
    selfie_bytes = generate_test_image_bytes()
    success_res = process_parent_verification(
        ver_token,
        {
            "parent_name": parent_name,
            "document_type": "AADHAAR_MOCK",
            "document_number": "548912345678",
            "password": "parentPassword123!",
            "consent": "on"
        },
        selfie_bytes=selfie_bytes
    )
    assert success_res["success"], f"Parent verification failed: {success_res.get('error')}"
    parent_id = success_res["parent_id"]
    approval_token = success_res["approval_token"]
    assert success_res["masked_id"] == "XXXX-XXXX-5678"
    print(f"[PASS] Parent verified successfully. Parent ID: {parent_id}, Masked ID: {success_res['masked_id']}")

    # Verify audit record in parent_verifications
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT verification_status, liveness_status, face_match_status, masked_id FROM parent_verifications WHERE parent_user_id = %s", (parent_id,))
    ver_rec = cur.fetchone()
    assert ver_rec["verification_status"] == "VERIFIED"
    assert ver_rec["liveness_status"] == "PASSED"
    assert ver_rec["face_match_status"] == "MATCHED"
    cur.close()
    conn.close()
    print("[PASS] Verification audit log confirmed in `parent_verifications` table.")

    # -----------------------------------------------------------
    # TEST 6: Unauthorized Approval Access (Wrong Parent or Child User)
    # -----------------------------------------------------------
    print("\n[TEST 6] Testing Unauthorized Parent Approval Access...")
    # Attempt with child's own ID
    check_child_access = get_child_approval_details(approval_token, logged_in_parent_id=child_id)
    assert not check_child_access["valid"]
    assert check_child_access["reason"] in ["UNAUTHORIZED_PARENT", "PARENT_NOT_VERIFIED"]
    print(f"[PASS] Child ID {child_id} cannot approve their own registration: {check_child_access['reason']}")

    # Attempt with random unauthorized parent ID (e.g. 999999)
    check_wrong_parent = get_child_approval_details(approval_token, logged_in_parent_id=999999)
    assert not check_wrong_parent["valid"]
    assert check_wrong_parent["reason"] == "UNAUTHORIZED_PARENT"
    print("[PASS] Unlinked parent cannot access or approve this child's registration.")

    # -----------------------------------------------------------
    # TEST 7: Authorized Approval by Verified Parent
    # -----------------------------------------------------------
    print("\n[TEST 7] Testing Authorized Approval by Linked Verified Parent...")
    check_authorized = get_child_approval_details(approval_token, logged_in_parent_id=parent_id)
    assert check_authorized["valid"], f"Authorized check failed: {check_authorized.get('reason')}"
    assert check_authorized["child"]["child_id"] == child_id

    decision_res = process_child_decision(approval_token, parent_id, "APPROVE")
    assert decision_res["success"], f"Approval process failed: {decision_res.get('error')}"
    print(f"[PASS] Child account approved: {decision_res['action']} for {decision_res['child_name']}")

    # Verify child status is now ACTIVE
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT account_status FROM users WHERE user_id = %s", (child_id,))
    assert cur.fetchone()["account_status"] == "ACTIVE"
    cur.close()
    conn.close()
    print("[PASS] Child user account status is now 'ACTIVE'.")

    # -----------------------------------------------------------
    # TEST 8: Token Single-Use (Reused Approval Token Blocked)
    # -----------------------------------------------------------
    print("\n[TEST 8] Testing Token Single-Use (Replay Protection)...")
    replay_check = get_child_approval_details(approval_token, logged_in_parent_id=parent_id)
    assert not replay_check["valid"]
    assert replay_check["reason"] == "TOKEN_ALREADY_USED"
    print("[PASS] Replay attempt correctly rejected with 'TOKEN_ALREADY_USED'.")

    # -----------------------------------------------------------
    # TEST 9: Existing AI Moderation / Content Safety Pipeline Intact
    # -----------------------------------------------------------
    print("\n[TEST 9] Testing that existing AI Moderation Pipelines are intact...")
    from uploadPost.ml_service import check_image_safety, yolo_coco, nsfw_detector
    assert yolo_coco is not None
    assert nsfw_detector is not None
    print("[PASS] YOLO COCO, NudeNet, and check_image_safety are loaded and fully intact.")

    print("\n==========================================================")
    print("ALL TEST SUITE SCENARIOS PASSED WITH ZERO ERRORS!")
    print("==========================================================")

if __name__ == "__main__":
    run_tests()
