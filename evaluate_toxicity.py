import pandas as pd
from transformers import pipeline
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

# ==========================================
# 1. LOAD JIGSAW DATASET
# ==========================================

DATASET_PATH = "datasets/train.csv"

print("Loading Jigsaw dataset...")

df = pd.read_csv(DATASET_PATH)

print(f"Dataset loaded: {len(df):,} comments")


# ==========================================
# 2. LOAD TOXICITY MODEL
# ==========================================

print("\nLoading toxicity model...")

classifier = pipeline(
    "text-classification",
    model="unitary/toxic-bert",
    truncation=True,
    max_length=512
)

print("Toxicity model loaded.")


# ==========================================
# 3. PREPARE DATA
# ==========================================

df = df.head(100)

texts = df["comment_text"].fillna("").astype(str).tolist()

true_labels = df["toxic"].astype(int).tolist()

# ==========================================
# 4. RUN MODEL
# ==========================================

print("\nRunning toxicity detection...")
print("This may take some time for 159,571 comments.\n")

predicted_labels = []

BATCH_SIZE = 16

for start in range(0, len(texts), BATCH_SIZE):

    batch = texts[start:start + BATCH_SIZE]

    results = classifier(batch)

    for result in results:

        label = result["label"].upper()

        if label == "TOXIC":
            predicted_labels.append(1)
        else:
            predicted_labels.append(0)

    processed = min(
        start + BATCH_SIZE,
        len(texts)
    )

    if processed % 1000 < BATCH_SIZE or processed == len(texts):

        print(
            f"Processed {processed:,} / "
            f"{len(texts):,}"
        )


# ==========================================
# 5. CALCULATE METRICS
# ==========================================

accuracy = accuracy_score(
    true_labels,
    predicted_labels
)

precision = precision_score(
    true_labels,
    predicted_labels,
    zero_division=0
)

recall = recall_score(
    true_labels,
    predicted_labels,
    zero_division=0
)

f1 = f1_score(
    true_labels,
    predicted_labels,
    zero_division=0
)

cm = confusion_matrix(
    true_labels,
    predicted_labels
)


# ==========================================
# 6. DISPLAY RESULTS
# ==========================================

print("\n")
print("=" * 60)
print("        LITTLE NET TOXICITY EVALUATION")
print("=" * 60)

print(f"\nDataset size : {len(df):,}")

print(f"\nAccuracy     : {accuracy:.4f} ({accuracy * 100:.2f}%)")
print(f"Precision    : {precision:.4f} ({precision * 100:.2f}%)")
print(f"Recall       : {recall:.4f} ({recall * 100:.2f}%)")
print(f"F1 Score     : {f1:.4f} ({f1 * 100:.2f}%)")


# ==========================================
# 7. CONFUSION MATRIX
# ==========================================

tn, fp, fn, tp = cm.ravel()

print("\nConfusion Matrix:")
print()
print("                 Predicted")
print("              Not Toxic  Toxic")
print(f"Actual Not Toxic   {tn:6d}   {fp:6d}")
print(f"Actual Toxic       {fn:6d}   {tp:6d}")

print("\nFalse Positives :", fp)
print("False Negatives :", fn)


# ==========================================
# 8. CLASSIFICATION REPORT
# ==========================================

print("\nClassification Report:")
print()

print(
    classification_report(
        true_labels,
        predicted_labels,
        target_names=[
            "Not Toxic",
            "Toxic"
        ],
        zero_division=0
    )
)

print("=" * 60)
print("Evaluation completed.")
print("=" * 60)