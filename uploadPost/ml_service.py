from ultralytics import YOLO
from nudenet import NudeDetector
import cv2
import tempfile
import os

yolo_model = YOLO("yolov8n.pt")
nsfw_detector = NudeDetector()

WEAPON_CLASSES = {
    "knife",
    "gun",
    "pistol",
    "rifle"
}

def check_image_safety(image_path):

    result = {
        "safe": True,
        "category": "SAFE",
        "score": 100,
        "objects": []
    }

    # Adult-content detection
    nsfw_results = nsfw_detector.detect(image_path)

    for item in nsfw_results:
        if item.get("score", 0) >= 0.8:
            result["safe"] = False
            result["category"] = "ADULT"
            result["score"] = round(item["score"] * 100, 2)
            return result

    # Object detection
    detections = yolo_model(image_path)

    detected_objects = set()

    for r in detections:
        for cls in r.boxes.cls:
            label = yolo_model.names[int(cls)]
            detected_objects.add(label)

    result["objects"] = list(detected_objects)

    # Weapon check (only effective if your model actually supports these classes)
    for obj in detected_objects:
        if obj.lower() in WEAPON_CLASSES:
            result["safe"] = False
            result["category"] = "WEAPON"
            result["score"] = 90
            return result

    return result


def extract_video_frames(video_path):

    os.makedirs(
        "uploads/temp_frames",
        exist_ok=True
    )

    cap = cv2.VideoCapture(video_path)

    frame_paths = []

    frame_count = 0
    frame_interval = 30

    while True:

        success, frame = cap.read()

        if not success:
            break

        if frame_count % frame_interval == 0:

            frame_path = os.path.join(
                "uploads/temp_frames",
                f"frame_{frame_count}.jpg"
            )

            cv2.imwrite(
                frame_path,
                frame
            )

            frame_paths.append(
                frame_path
            )

        frame_count += 1

    cap.release()

    return frame_paths


def check_video_safety(video_path):

    frame_paths = extract_video_frames(
        video_path
    )

    for frame_path in frame_paths:

        result = check_image_safety(
            frame_path
        )

        if not result["safe"]:

            # cleanup frames
            for f in frame_paths:
                if os.path.exists(f):
                    os.remove(f)

            return {
                "safe": False,
                "category": result["category"],
                "score": result["score"]
            }

    # cleanup frames
    for f in frame_paths:
        if os.path.exists(f):
            os.remove(f)

    return {
        "safe": True,
        "category": "SAFE",
        "score": 100
    }