import os
import threading
import cv2
import requests

from ultralytics import YOLO
from nudenet import NudeDetector
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.environ.get("HF_TOKEN")

# ── YOLO models ───────────────────────────────────────────────────────────────

yolo_coco = YOLO("yolov8n.pt")

try:
    yolo_oiv7 = YOLO("yolov8n-oiv7.pt")
    OIV7_AVAILABLE = True
except Exception as e:
    print(f"[ML] OIV7 model unavailable: {e}")
    yolo_oiv7 = None
    OIV7_AVAILABLE = False

nsfw_detector = NudeDetector()

# ── Falconsai NSFW model — loads in background thread ────────────────────────

_falconsai_pipe  = None
_falconsai_ready = threading.Event()
_falconsai_failed = False

def _load_falconsai_background():
    global _falconsai_pipe, _falconsai_failed
    try:
        from transformers import pipeline
        print("[ML] Loading Falconsai NSFW model in background…")
        _falconsai_pipe = pipeline(
            "image-classification",
            model="Falconsai/nsfw_image_detection",
        )
        _falconsai_ready.set()
        print("[ML] Falconsai NSFW model ready.")
    except Exception as e:
        _falconsai_failed = True
        print(f"[ML] Falconsai failed to load: {e}")

threading.Thread(target=_load_falconsai_background, daemon=True).start()


# ── CLIP violence model — loads in background thread ─────────────────────────

_clip_pipe   = None
_clip_ready  = threading.Event()
_clip_failed = False

VIOLENT_PROMPTS = [
    "people physically fighting or attacking each other",
    "domestic violence or physical abuse",
    "violent bullying or physical assault",
    "blood and gore in an image",
    "person being hurt or injured",
]

DRUG_PROMPTS = [
    "person smoking cigarettes or drugs",
    "illegal drugs or drug paraphernalia",
    "alcohol bottles and people drinking",
    "marijuana or cannabis",
]

BULLY_PROMPTS = [
    "person being humiliated or mocked",
    "group of people bullying or harassing someone",
    "cyberbullying or online harassment",
]

SAFE_PROMPTS = [
    "a normal portrait of a person",
    "friends in a casual photo",
    "children playing happily",
    "school classroom learning",
    "family having a meal together",
    "kids doing homework or studying",
]

_ALL_PROMPTS = VIOLENT_PROMPTS + DRUG_PROMPTS + BULLY_PROMPTS + SAFE_PROMPTS

def _load_clip_background():
    global _clip_pipe, _clip_failed
    try:
        from transformers import pipeline
        print("[ML] Loading CLIP zero-shot violence model in background…")
        _clip_pipe = pipeline(
            "zero-shot-image-classification",
            model="openai/clip-vit-base-patch32",
        )
        _clip_ready.set()
        print("[ML] CLIP violence model ready.")
    except Exception as e:
        _clip_failed = True
        print(f"[ML] CLIP failed to load: {e}")

threading.Thread(target=_load_clip_background, daemon=True).start()


# ── Label sets (NudeNet fallback) ─────────────────────────────────────────────

UNSAFE_NUDE_LABELS = {
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
}

SUGGESTIVE_NUDE_LABELS = {
    "FEMALE_BREAST_COVERED",
    "FEMALE_GENITALIA_COVERED",
    "BELLY_EXPOSED",
}

COCO_WEAPON_CLASSES = {"knife"}

OIV7_WEAPON_CLASSES = {
    "handgun", "gun", "rifle", "shotgun", "sword",
    "knife", "dagger", "pistol", "firearm", "weapon",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resize_for_check(image_path, max_side=640):
    img = cv2.imread(image_path)
    if img is None:
        return image_path, False

    h, w = img.shape[:2]
    if max(h, w) <= max_side:
        return image_path, False

    scale = max_side / max(h, w)
    small = cv2.resize(img, (int(w * scale), int(h * scale)))
    tmp_path = image_path + "_resized.jpg"
    cv2.imwrite(tmp_path, small)
    return tmp_path, True


def _check_hf_nsfw(image_path):
    """Primary NSFW check via HuggingFace Inference API (AdamCodd ViT — strongest free model)."""
    if not HF_TOKEN:
        return None
    try:
        with open(image_path, "rb") as f:
            data = f.read()
        response = requests.post(
            "https://api-inference.huggingface.co/models/AdamCodd/vit-base-nsfw-detector",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            data=data,
            timeout=20,
        )
        if response.status_code != 200:
            print(f"[ML] HF API status {response.status_code}: {response.text[:120]}")
            return None
        results = response.json()
        if not isinstance(results, list):
            return None
        nsfw_score = next(
            (r["score"] for r in results if r["label"].lower() in ("nsfw", "explicit")), 0.0
        )
        if nsfw_score >= 0.65:
            return {"safe": False, "score": round(nsfw_score * 100, 2)}
        return {"safe": True, "score": round(nsfw_score * 100, 2)}
    except Exception as e:
        print(f"[ML] HF API error: {e}")
    return None


def _check_nsfw_falconsai(image_path):
    """Primary NSFW check using Falconsai fine-tuned classifier."""
    if _falconsai_failed or not _falconsai_ready.is_set():
        return None  # signal caller to fall through to NudeNet

    try:
        from PIL import Image as PILImage
        image = PILImage.open(image_path).convert("RGB")
        results = _falconsai_pipe(image)
        # results is [{label, score}, ...] — find the nsfw score
        nsfw_score = next(
            (r["score"] for r in results if r["label"].lower() == "nsfw"), 0.0
        )
        if nsfw_score >= 0.60:
            return {"safe": False, "score": round(nsfw_score * 100, 2)}
        return {"safe": True, "score": round(nsfw_score * 100, 2)}
    except Exception as e:
        print(f"[ML] Falconsai error on {image_path}: {e}")
        return None


def _check_nsfw_nudenet(image_path):
    """Fallback NSFW check using NudeNet (body-part detection)."""
    try:
        for item in nsfw_detector.detect(image_path):
            label = item.get("class", "")
            score = item.get("score", 0.0)

            if label in UNSAFE_NUDE_LABELS and score >= 0.45:
                return {"safe": False, "score": round(score * 100, 2)}
            if label in SUGGESTIVE_NUDE_LABELS and score >= 0.55:
                return {"safe": False, "score": round(score * 100, 2)}
    except Exception as e:
        print(f"[ML] NudeNet error: {e}")

    return {"safe": True, "score": 0.0}


def _check_content_clip(image_path):
    """
    Zero-shot CLIP check for violence, drugs, bullying.
    Returns {"safe": False, "category": ..., "score": ...} or {"safe": True}.
    Flags only when the bad label beats the best safe label by >= 0.08.
    """
    if _clip_failed or not _clip_ready.is_set():
        return {"safe": True, "score": 0.0}

    try:
        from PIL import Image as PILImage
        image = PILImage.open(image_path).convert("RGB")
        scores = _clip_pipe(image, candidate_labels=_ALL_PROMPTS)

        label_map = {r["label"]: r["score"] for r in scores}
        max_s = max((label_map.get(p, 0.0) for p in SAFE_PROMPTS), default=0.0)

        checks = [
            (VIOLENT_PROMPTS, 0.50, "VIOLENCE"),
            (DRUG_PROMPTS,    0.50, "DRUG"),
        ]
        for prompts, threshold, category in checks:
            max_bad = max((label_map.get(p, 0.0) for p in prompts), default=0.0)
            if max_bad >= threshold and max_bad > max_s + 0.15:
                return {"safe": False, "category": category, "score": round(max_bad * 100, 2)}

    except Exception as e:
        print(f"[ML] CLIP error on {image_path}: {e}")

    return {"safe": True, "score": 0.0}


# ── Core safety check ─────────────────────────────────────────────────────────

def check_image_safety(image_path):
    result = {
        "safe": True,
        "category": "SAFE",
        "score": 100,
        "objects": []
    }

    small_path, was_resized = _resize_for_check(image_path, max_side=640)

    try:
        # ── 1. NSFW ensemble: Falconsai + NudeNet always run together ─────────
        falconsai = _check_nsfw_falconsai(small_path)
        nudenet   = _check_nsfw_nudenet(small_path)

        if (falconsai is not None and not falconsai["safe"]) or (not nudenet["safe"]):
            score = (falconsai["score"] if falconsai and not falconsai["safe"]
                     else nudenet["score"])
            result.update(safe=False, category="ADULT", score=score)
            return result

        # ── 2. YOLO COCO — knife ──────────────────────────────────────────────
        try:
            for r in yolo_coco(small_path, verbose=False):
                for box in r.boxes:
                    label = yolo_coco.names[int(box.cls)].lower()
                    if float(box.conf) >= 0.40:
                        result["objects"].append(label)
                        if label in COCO_WEAPON_CLASSES:
                            result.update(safe=False, category="WEAPON", score=90)
                            return result
        except Exception as e:
            print(f"[ML] COCO YOLO error: {e}")

        # ── 3. YOLO OIV7 — guns, rifles, etc. ────────────────────────────────
        if OIV7_AVAILABLE:
            try:
                for r in yolo_oiv7(small_path, verbose=False):
                    for box in r.boxes:
                        label = yolo_oiv7.names[int(box.cls)].lower()
                        conf  = float(box.conf)
                        if conf >= 0.40 and label in OIV7_WEAPON_CLASSES:
                            result["objects"].append(label)
                            result.update(safe=False, category="WEAPON",
                                          score=round(conf * 100, 2))
                            return result
            except Exception as e:
                print(f"[ML] OIV7 YOLO error: {e}")

        # ── 4. CLIP — violence, drugs, bullying ───────────────────────────────
        clip = _check_content_clip(small_path)
        if not clip["safe"]:
            result.update(safe=False, category=clip["category"], score=clip["score"])
            return result

    finally:
        if was_resized and os.path.exists(small_path):
            os.remove(small_path)

    return result


# ── Video safety check ────────────────────────────────────────────────────────

def extract_video_frames(video_path, interval=24):
    os.makedirs("uploads/temp_frames", exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    frame_paths = []
    frame_count = 0

    while True:
        success, frame = cap.read()
        if not success:
            break
        if frame_count % interval == 0:
            path = os.path.join("uploads/temp_frames", f"frame_{frame_count}.jpg")
            cv2.imwrite(path, frame)
            frame_paths.append(path)
        frame_count += 1

    cap.release()
    return frame_paths


def check_video_safety(video_path):
    frame_paths = extract_video_frames(video_path)
    try:
        for frame_path in frame_paths:
            result = check_image_safety(frame_path)
            if not result["safe"]:
                return {
                    "safe": False,
                    "category": result["category"],
                    "score": result["score"]
                }
    finally:
        for f in frame_paths:
            if os.path.exists(f):
                os.remove(f)

    return {"safe": True, "category": "SAFE", "score": 100}
