import os
import threading
import cv2
import torch

from ultralytics import YOLO
from nudenet import NudeDetector
from dotenv import load_dotenv

from transformers import (
    AutoProcessor,
    AutoModelForZeroShotImageClassification
)

from PIL import Image


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# YOLO COCO
# ============================================================

print("[ML] Loading YOLO COCO...")

yolo_coco = YOLO("yolov8n.pt")


# ============================================================
# YOLO OIV7
# ============================================================

try:

    print("[ML] Loading YOLO OIV7...")

    yolo_oiv7 = YOLO("yolov8n-oiv7.pt")

    OIV7_AVAILABLE = True

except Exception as e:

    print(
        f"[ML] OIV7 model unavailable: {e}"
    )

    yolo_oiv7 = None

    OIV7_AVAILABLE = False


# ============================================================
# NUDENET
# ============================================================

print("[ML] Loading NudeNet...")

nsfw_detector = NudeDetector()

print("[ML] NudeNet ready.")


# ============================================================
# FALCONSAI NSFW MODEL
# ============================================================

_falconsai_pipe = None

_falconsai_ready = threading.Event()

_falconsai_failed = False


def _load_falconsai_background():

    global _falconsai_pipe
    global _falconsai_failed

    try:

        from transformers import pipeline

        print(
            "[ML] Loading Falconsai NSFW model..."
        )

        _falconsai_pipe = pipeline(
            "image-classification",
            model="Falconsai/nsfw_image_detection"
        )

        _falconsai_ready.set()

        print(
            "[ML] Falconsai NSFW model ready."
        )

    except Exception as e:

        _falconsai_failed = True

        print(
            f"[ML] Falconsai failed to load: {e}"
        )


threading.Thread(
    target=_load_falconsai_background,
    daemon=True
).start()


# ============================================================
# CLIP / BROAD VISUAL SAFETY MODEL
# ============================================================

print(
    "[ML] Loading broad visual safety model..."
)

VISUAL_MODEL_NAME = (
    "openai/clip-vit-base-patch32"
)


try:

    visual_processor = AutoProcessor.from_pretrained(
        VISUAL_MODEL_NAME
    )

    visual_model = (
        AutoModelForZeroShotImageClassification
        .from_pretrained(
            VISUAL_MODEL_NAME
        )
    )

    visual_model.eval()

    VISUAL_MODEL_AVAILABLE = True

    print(
        "[ML] Broad visual safety model ready."
    )

except Exception as e:

    visual_processor = None

    visual_model = None

    VISUAL_MODEL_AVAILABLE = False

    print(
        f"[ML] Broad visual model failed: {e}"
    )


# ============================================================
# VISUAL SAFETY CATEGORIES
# ============================================================

VISUAL_UNSAFE_CATEGORIES = [

    # --------------------------------------------------------
    # ADULT / SEXUAL
    # --------------------------------------------------------

    "sexually explicit content",

    "sexual activity",

    "nudity or exposed private parts",

    "erotic or sexually suggestive content",

    "people having sex",

    "adult sexual behavior",

    "a sexually suggestive pose",

    # --------------------------------------------------------
    # ROMANCE / INTIMACY
    # --------------------------------------------------------

    "people kissing romantically",

    "people making out",

    "romantic intimate physical contact",

    "an intimate romantic scene",

    # --------------------------------------------------------
    # VIOLENCE
    # --------------------------------------------------------

    "people fighting",

    "physical violence",

    "physical assault",

    "domestic violence",

    "someone being attacked",

    "blood or gore",

    "a violent injury",

    # --------------------------------------------------------
    # DRUGS / SMOKING / ALCOHOL
    # --------------------------------------------------------

    "illegal drug use",

    "illegal drugs or drug paraphernalia",

    "people using drugs",

    "people smoking cigarettes",

    "smoking or vaping",

    "people drinking alcohol",

    "alcohol consumption",

    # --------------------------------------------------------
    # BULLYING / HARASSMENT
    # --------------------------------------------------------

    "bullying",

    "cyberbullying",

    "harassment",

    "humiliating or abusive behavior",

    "someone being bullied",

    # --------------------------------------------------------
    # WEAPONS / DANGEROUS OBJECTS
    # --------------------------------------------------------

    "a photo of a knife or sharp blade",

    "a sharp knife or kitchen knife",

    "a dangerous weapon or firearm",

    "guns or rifles",

    # --------------------------------------------------------
    # OTHER UNSAFE CONTENT
    # --------------------------------------------------------

    "disturbing or inappropriate content",

    "dangerous inappropriate behavior",

]


VISUAL_SAFE_CATEGORY = (
    "normal child-friendly content"
)


# ============================================================
# VISUAL CLASSIFIER THRESHOLDS
# ============================================================

VISUAL_SAFE_MARGIN = 0.03

# Different thresholds for different types of unsafe content.
# CLIP is more reliable for adult/sexual content than for
# bullying/abuse, so bullying requires a much higher confidence.

VISUAL_CATEGORY_THRESHOLDS = {

    # Weapons / dangerous objects
    "a photo of a knife or sharp blade": 0.22,
    "a sharp knife or kitchen knife": 0.22,
    "a dangerous weapon or firearm": 0.22,
    "guns or rifles": 0.22,

    # Adult / sexual content
    "sexually explicit content": 0.20,
    "sexual activity": 0.20,
    "nudity or exposed private parts": 0.20,
    "erotic or sexually suggestive content": 0.20,
    "people having sex": 0.20,
    "adult sexual behavior": 0.20,
    "a sexually suggestive pose": 0.20,

    # Romance / intimacy
    "people kissing romantically": 0.20,
    "people making out": 0.20,
    "romantic intimate physical contact": 0.20,
    "an intimate romantic scene": 0.20,

    # Violence
    "people fighting": 0.30,
    "physical violence": 0.30,
    "physical assault": 0.30,
    "domestic violence": 0.30,
    "someone being attacked": 0.30,
    "blood or gore": 0.30,
    "a violent injury": 0.30,

    # Drugs / smoking / alcohol
    "illegal drug use": 0.30,
    "illegal drugs or drug paraphernalia": 0.30,
    "people using drugs": 0.30,
    "people smoking cigarettes": 0.30,
    "smoking or vaping": 0.30,
    "people drinking alcohol": 0.30,
    "alcohol consumption": 0.30,

    # Bullying / harassment
    # Higher threshold because CLIP gives many innocent
    # child photos false positives for these categories.
    "bullying": 0.75,
    "cyberbullying": 0.75,
    "harassment": 0.75,
    "humiliating or abusive behavior": 0.75,
    "someone being bullied": 0.75,

    # Other disturbing content
    "disturbing or inappropriate content": 0.50,
    "dangerous inappropriate behavior": 0.50,
}


# ============================================================
# NUDENET LABELS
# ============================================================

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


# ============================================================
# WEAPON LABELS
# ============================================================

COCO_WEAPON_CLASSES = {
    "knife",
    "scissors"
}


OIV7_WEAPON_CLASSES = {
    "handgun",
    "gun",
    "rifle",
    "shotgun",
    "sword",
    "knife",
    "kitchen knife",
    "dagger",
    "pistol",
    "firearm",
    "weapon",
    "axe",
    "bomb",
    "missile",
    "syringe",
    "scissors"
}


# ============================================================
# IMAGE RESIZE
# ============================================================

def _resize_for_check(
    image_path,
    max_side=640
):

    img = cv2.imread(
        image_path
    )

    if img is None:

        return image_path, False


    height, width = img.shape[:2]


    if max(height, width) <= max_side:

        return image_path, False


    scale = (
        max_side /
        max(height, width)
    )


    resized = cv2.resize(
        img,
        (
            int(width * scale),
            int(height * scale)
        )
    )


    temp_path = (
        image_path +
        "_resized.jpg"
    )


    cv2.imwrite(
        temp_path,
        resized,
        [
            cv2.IMWRITE_JPEG_QUALITY,
            85
        ]
    )


    return temp_path, True


# ============================================================
# FALCONSAI NSFW CHECK
# ============================================================

def _check_nsfw_falconsai(
    image_path
):

    if _falconsai_failed:

        return None


    if not _falconsai_ready.is_set():

        print(
            "[ML] Falconsai model "
            "is not ready yet."
        )

        return None


    try:

        image = Image.open(
            image_path
        ).convert("RGB")


        results = _falconsai_pipe(
            image
        )


        nsfw_score = next(

            (
                item["score"]

                for item in results

                if item.get(
                    "label",
                    ""
                ).lower() == "nsfw"

            ),

            0.0

        )


        # ----------------------------------------------------
        # PRINT RAW SCORE
        # ----------------------------------------------------

        print(
            f"[ML] Falconsai RAW NSFW score: "
            f"{nsfw_score:.4f}"
        )


        # ----------------------------------------------------
        # 40% THRESHOLD
        # ----------------------------------------------------

        if nsfw_score >= 0.40:

            return {

                "safe": False,

                "score": round(
                    nsfw_score * 100,
                    2
                )

            }


        return {

            "safe": True,

            "score": round(
                nsfw_score * 100,
                2
            )

        }


    except Exception as e:

        print(
            f"[ML] Falconsai error: {e}"
        )

        return None


# ============================================================
# NUDENET CHECK
# ============================================================

def _check_nsfw_nudenet(
    image_path
):

    try:

        detections = nsfw_detector.detect(
            image_path
        )


        for detection in detections:

            label = detection.get(
                "class",
                ""
            )


            score = float(
                detection.get(
                    "score",
                    0.0
                )
            )


            # ------------------------------------------------
            # EXPOSED BODY PARTS
            # ------------------------------------------------

            if (

                label
                in UNSAFE_NUDE_LABELS

                and

                score >= 0.40

            ):

                return {

                    "safe": False,

                    "score": round(
                        score * 100,
                        2
                    )

                }


            # ------------------------------------------------
            # SUGGESTIVE CONTENT
            # ------------------------------------------------

            if (

                label
                in SUGGESTIVE_NUDE_LABELS

                and

                score >= 0.50

            ):

                return {

                    "safe": False,

                    "score": round(
                        score * 100,
                        2
                    )

                }


    except Exception as e:

        print(
            f"[ML] NudeNet error: {e}"
        )


    return {

        "safe": True,

        "score": 0.0

    }


# ============================================================
# BROAD VISUAL CONTENT CHECK
# ============================================================

def _check_visual_content(image_path):

    if not VISUAL_MODEL_AVAILABLE:

        print(
            "[ML] Visual model unavailable."
        )

        return {
            "safe": True,
            "category": "SAFE",
            "score": 0.0
        }

    try:

        # --------------------------------------------------------
        # OPEN IMAGE
        # --------------------------------------------------------

        image = Image.open(
            image_path
        ).convert("RGB")


        # --------------------------------------------------------
        # ALL VISUAL LABELS
        # --------------------------------------------------------

        labels = (
            VISUAL_UNSAFE_CATEGORIES
            + [
                VISUAL_SAFE_CATEGORY
            ]
        )


        # --------------------------------------------------------
        # PROCESS IMAGE + TEXT LABELS
        # --------------------------------------------------------

        inputs = visual_processor(

            text=labels,

            images=image,

            return_tensors="pt",

            padding=True

        )


        # --------------------------------------------------------
        # RUN CLIP
        # --------------------------------------------------------

        with torch.no_grad():

            outputs = visual_model(
                **inputs
            )


        logits = (
            outputs.logits_per_image
        )


        probabilities = (
            logits.softmax(dim=1)[0]
        )


        # --------------------------------------------------------
        # SORT RESULTS
        # --------------------------------------------------------

        results = sorted(

            zip(
                labels,
                probabilities.tolist()
            ),

            key=lambda item: item[1],

            reverse=True

        )


        # --------------------------------------------------------
        # GET SAFE SCORE
        # --------------------------------------------------------

        safe_score = 0.0

        for label, score in results:

            if label == VISUAL_SAFE_CATEGORY:

                safe_score = score

                break


        # --------------------------------------------------------
        # TOP RESULT
        # --------------------------------------------------------

        top_label = results[0][0]

        top_score = results[0][1]


        print(
            "[ML] Visual classifier:"
        )

        print(
            f"       TOP: {top_label} "
            f"({top_score * 100:.2f}%)"
        )

        print(
            f"       SAFE: "
            f"{safe_score * 100:.2f}%"
        )


        # --------------------------------------------------------
        # PRINT TOP 5
        # --------------------------------------------------------

        print(
            "[ML] Top visual categories:"
        )

        for label, score in results[:5]:

            print(
                f"       {label}: "
                f"{score * 100:.2f}%"
            )


        # --------------------------------------------------------
        # CHECK WHETHER TOP LABEL IS UNSAFE
        # --------------------------------------------------------

        if (
            top_label in VISUAL_UNSAFE_CATEGORIES
        ):

            # Get category-specific threshold.
            threshold = (
                VISUAL_CATEGORY_THRESHOLDS.get(
                    top_label,
                    0.30
                )
            )


            print(
                f"[ML] Threshold for "
                f"'{top_label}': "
                f"{threshold * 100:.0f}%"
            )


            # ----------------------------------------------------
            # UNSAFE CATEGORY MUST:
            #
            # 1. Reach its own threshold
            # 2. Beat the safe category by the margin
            # ----------------------------------------------------

            if (

                top_score >= threshold

                and

                top_score >= (
                    safe_score
                    + VISUAL_SAFE_MARGIN
                )

            ):

                print(
                    "[ML] BLOCKED BY "
                    "VISUAL CLASSIFIER:"
                )

                print(
                    f"       {top_label}"
                )

                print(
                    f"       Score: "
                    f"{top_score * 100:.2f}%"
                )

                return {

                    "safe": False,

                    "category": top_label,

                    "score": round(
                        top_score * 100,
                        2
                    )

                }


        # --------------------------------------------------------
        # SAFE
        # --------------------------------------------------------

        print(
            "[ML] VISUAL CONTENT SAFE"
        )

        return {

            "safe": True,

            "category": "SAFE",

            "score": round(
                safe_score * 100,
                2
            )

        }


    except Exception as e:

        print(
            "[ML] Visual classifier "
            f"error: {e}"
        )

        return {

            "safe": True,

            "category": "SAFE",

            "score": 0.0

        }


        # ----------------------------------------------------
        # PROCESS IMAGE + TEXT LABELS
        # ----------------------------------------------------

        inputs = visual_processor(

            text=labels,

            images=image,

            return_tensors="pt",

            padding=True

        )


        # ----------------------------------------------------
        # RUN CLIP
        # ----------------------------------------------------

        with torch.no_grad():

            outputs = visual_model(
                **inputs
            )


        logits = (
            outputs.logits_per_image
        )


        probabilities = (
            logits.softmax(
                dim=1
            )[0]
        )


        results = sorted(

            zip(
                labels,
                probabilities.tolist()
            ),

            key=lambda item: item[1],

            reverse=True

        )


        # ----------------------------------------------------
        # TOP RESULT
        # ----------------------------------------------------

        top_label = results[0][0]

        top_score = results[0][1]


        safe_score = 0.0


        for label, score in results:

            if (
                label
                == VISUAL_SAFE_CATEGORY
            ):

                safe_score = score

                break


        print(
            "[ML] Visual classifier:"
        )


        print(
            f"       TOP: {top_label} "
            f"({top_score * 100:.2f}%)"
        )


        print(
            f"       SAFE: "
            f"{safe_score * 100:.2f}%"
        )


        # ----------------------------------------------------
        # PRINT TOP 5
        # ----------------------------------------------------

        print(
            "[ML] Top visual categories:"
        )


        for label, score in results[:5]:

            print(

                f"       {label}: "

                f"{score * 100:.2f}%"

            )


        # ----------------------------------------------------
        # CHECK IF TOP CATEGORY IS UNSAFE
        # ----------------------------------------------------

        if (

            top_label
            != VISUAL_SAFE_CATEGORY

            and

            top_label
            in VISUAL_UNSAFE_CATEGORIES

            and

            top_score
            >= VISUAL_UNSAFE_THRESHOLD

            and

            top_score
            >= (
                safe_score
                + VISUAL_SAFE_MARGIN
            )

        ):

            print(
                "[ML] BLOCKED BY "
                "VISUAL CLASSIFIER:"
            )

            print(
                f"       {top_label}"
            )


            return {

                "safe": False,

                "category": top_label,

                "score": round(
                    top_score * 100,
                    2
                )

            }


        return {

            "safe": True,

            "category": "SAFE",

            "score": round(
                top_score * 100,
                2
            )

        }


    except Exception as e:

        print(
            "[ML] Visual classifier "
            f"error: {e}"
        )


        return {

            "safe": True,

            "category": "SAFE",

            "score": 0.0

        }


# ============================================================
# IMAGE SAFETY CHECK
# ============================================================

def check_image_safety(
    image_path
):

    result = {

        "safe": True,

        "category": "SAFE",

        "score": 100,

        "objects": []

    }


    # --------------------------------------------------------
    # RESIZE
    # --------------------------------------------------------

    small_path, was_resized = (
        _resize_for_check(
            image_path,
            max_side=640
        )
    )


    try:

        # ====================================================
        # 1. FALCONSAI
        # ====================================================

        falconsai = (
            _check_nsfw_falconsai(
                small_path
            )
        )


        if falconsai is not None:

            print(

                f"[ML] Falconsai NSFW score: "

                f"{falconsai['score']}%"

            )


            if not falconsai["safe"]:

                print(
                    "[ML] BLOCKED: ADULT "
                    "(Falconsai)"
                )


                result.update(

                    safe=False,

                    category="ADULT",

                    score=falconsai["score"]

                )


                return result


        # ====================================================
        # 2. NUDENET
        # ====================================================

        nudenet = (
            _check_nsfw_nudenet(
                small_path
            )
        )


        print(

            f"[ML] NudeNet score: "

            f"{nudenet['score']}%"

        )


        if not nudenet["safe"]:

            print(
                "[ML] BLOCKED: ADULT "
                "(NudeNet)"
            )


            result.update(

                safe=False,

                category="ADULT",

                score=nudenet["score"]

            )


            return result


        # ====================================================
        # 3. BROAD VISUAL CLASSIFIER
        # ====================================================

        visual = (
            _check_visual_content(
                small_path
            )
        )


        if not visual["safe"]:
            visual_label = visual.get("category", "")
            blocked_cat = "WEAPON" if any(w in visual_label.lower() for w in ["knife", "blade", "weapon", "gun", "rifle", "firearm"]) else "INAPPROPRIATE"
            print(f"[ML] BLOCKED BY VISUAL CLASSIFIER: {blocked_cat} ('{visual_label}', score: {visual['score']}%)")
            result.update(
                safe=False,
                category=blocked_cat,
                score=visual["score"]
            )
            return result


        # ====================================================
        # 4. YOLO COCO
        # ====================================================

        try:
            detections = yolo_coco(
                small_path,
                conf=0.25,
                verbose=False
            )

            for r in detections:
                for box in r.boxes:
                    label = (
                        yolo_coco.names[
                            int(box.cls)
                        ].lower()
                    )
                    confidence = float(box.conf)
                    xyxy = [round(float(coord), 1) for coord in box.xyxy[0].tolist()]

                    print(f"[ML DEBUG] YOLO COCO detected: '{label}' | Confidence: {confidence:.3f} | Box: {xyxy}")

                    if confidence >= 0.25:
                        result["objects"].append(label)

                        if label in COCO_WEAPON_CLASSES:
                            print(f"[ML] BLOCKED BY YOLO COCO: WEAPON ('{label}', conf: {confidence:.3f})")
                            result.update(
                                safe=False,
                                category="WEAPON",
                                score=round(confidence * 100, 2)
                            )
                            return result

        except Exception as e:
            print(f"[ML] COCO YOLO error: {e}")

        # ====================================================
        # 5. YOLO OIV7
        # ====================================================

        if OIV7_AVAILABLE:
            try:
                detections = yolo_oiv7(
                    small_path,
                    conf=0.25,
                    verbose=False
                )

                for r in detections:
                    for box in r.boxes:
                        label = (
                            yolo_oiv7.names[
                                int(box.cls)
                            ].lower()
                        )
                        confidence = float(box.conf)
                        xyxy = [round(float(coord), 1) for coord in box.xyxy[0].tolist()]

                        print(f"[ML DEBUG] YOLO OIV7 detected: '{label}' | Confidence: {confidence:.3f} | Box: {xyxy}")

                        if confidence >= 0.25 and label in OIV7_WEAPON_CLASSES:
                            print(f"[ML] BLOCKED BY YOLO OIV7: WEAPON ('{label}', conf: {confidence:.3f})")
                            result["objects"].append(label)
                            result.update(
                                safe=False,
                                category="WEAPON",
                                score=round(confidence * 100, 2)
                            )
                            return result

            except Exception as e:
                print(f"[ML] OIV7 error: {e}")


    finally:

        # ----------------------------------------------------
        # DELETE TEMP IMAGE
        # ----------------------------------------------------

        if (

            was_resized

            and

            os.path.exists(
                small_path
            )

        ):

            try:

                os.remove(
                    small_path
                )

            except Exception:

                pass


    print(
        "[ML] CONTENT SAFE"
    )


    return result


# ============================================================
# VIDEO FRAME EXTRACTION
# ============================================================

def extract_video_frames(

    video_path,

    max_frames=12

):

    os.makedirs(

        "uploads/temp_frames",

        exist_ok=True

    )


    cap = cv2.VideoCapture(
        video_path
    )


    if not cap.isOpened():

        print(
            "[ML] Could not open video."
        )

        return []


    total_frames = int(

        cap.get(
            cv2.CAP_PROP_FRAME_COUNT
        )

    )


    if total_frames <= 0:

        cap.release()

        return []


    # --------------------------------------------------------
    # SELECT REPRESENTATIVE FRAMES
    # --------------------------------------------------------

    if total_frames <= max_frames:

        frame_numbers = list(
            range(total_frames)
        )

    else:

        frame_numbers = [

            int(

                i
                *
                (total_frames - 1)
                /
                (max_frames - 1)

            )

            for i in range(
                max_frames
            )

        ]


    frame_paths = []


    # --------------------------------------------------------
    # EXTRACT
    # --------------------------------------------------------

    for index, frame_number in enumerate(

        frame_numbers

    ):

        cap.set(

            cv2.CAP_PROP_POS_FRAMES,

            frame_number

        )


        success, frame = (
            cap.read()
        )


        if not success:

            continue


        path = os.path.join(

            "uploads",

            "temp_frames",

            f"frame_{index}.jpg"

        )


        cv2.imwrite(

            path,

            frame,

            [

                cv2.IMWRITE_JPEG_QUALITY,

                80

            ]

        )


        frame_paths.append(
            path
        )


    cap.release()


    print(

        f"[ML] Video frames selected: "

        f"{len(frame_paths)}"

    )


    return frame_paths


# ============================================================
# VIDEO SAFETY CHECK
# ============================================================

def check_video_safety(
    video_path
):

    # --------------------------------------------------------
    # SELECT 12 REPRESENTATIVE FRAMES
    # --------------------------------------------------------

    frame_paths = (
        extract_video_frames(

            video_path,

            max_frames=12

        )
    )


    if not frame_paths:

        return {

            "safe": False,

            "category": "VIDEO_ERROR",

            "score": 0

        }


    try:

        # ----------------------------------------------------
        # CHECK EVERY FRAME
        # ----------------------------------------------------

        for index, frame_path in enumerate(

            frame_paths,

            start=1

        ):

            print("")

            print(
                "================================"
            )

            print(

                f"[ML] Checking video frame "

                f"{index}/{len(frame_paths)}"

            )

            print(
                "================================"
            )


            result = (
                check_image_safety(
                    frame_path
                )
            )


            # ------------------------------------------------
            # STOP IMMEDIATELY
            # ------------------------------------------------

            if not result["safe"]:

                print("")

                print(
                    "================================"
                )

                print(
                    "[ML] VIDEO BLOCKED"
                )

                print(

                    f"[ML] CATEGORY: "

                    f"{result['category']}"

                )

                print(

                    f"[ML] SCORE: "

                    f"{result['score']}%"

                )

                print(
                    "================================"
                )


                return {

                    "safe": False,

                    "category": result[
                        "category"
                    ],

                    "score": result[
                        "score"
                    ]

                }


    finally:

        # ----------------------------------------------------
        # DELETE TEMPORARY FRAMES
        # ----------------------------------------------------

        for frame_path in frame_paths:

            if os.path.exists(
                frame_path
            ):

                try:

                    os.remove(
                        frame_path
                    )

                except Exception:

                    pass


    print("")

    print(
        "================================"
    )

    print(
        "[ML] VIDEO SAFE"
    )

    print(
        "================================"
    )


    return {

        "safe": True,

        "category": "SAFE",

        "score": 100

    }