import pandas as pd
import re
import joblib

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score


# =========================
# Load Dataset
# =========================

df = pd.read_csv("helpdesk_tickets_cleaned.csv")


# =========================
# Text Cleaning Function
# =========================

def clean_text(text):

    text = text.lower()

    # remove ticket ids
    text = re.sub(r'\[tkt-\d+\]', ' ', text)

    # remove special characters
    text = re.sub(r'[^a-z\s]', ' ', text)

    text = re.sub(r'\s+', ' ', text)

    return text.strip()


df["title"] = df["title"].apply(clean_text)
df["description"] = df["description"].apply(clean_text)


# =========================
# Combine title + description
# =========================

df["text"] = df["title"] + " " + df["description"]

X = df["text"]
y = df["department"]


# =========================
# Train / Test Split
# =========================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    stratify=y,
    random_state=42
)


# =========================
# Optimized Pipeline
# =========================

model = Pipeline([

    (
        "tfidf",

        TfidfVectorizer(

            stop_words="english",

            # capture phrases like "invoice issue"
            ngram_range=(1,2),

            # ignore extremely common words
            max_df=0.9,

            # ignore rare words
            min_df=3,

            # improves weighting
            sublinear_tf=True
        )
    ),

    (
        "clf",

        LogisticRegression(

            solver="lbfgs",

            max_iter=2000,

            class_weight="balanced",

            # regularization strength
            C=3
        )
    )
])


# =========================
# Train Model
# =========================

model.fit(X_train, y_train)


# =========================
# Evaluation
# =========================

predictions = model.predict(X_test)

print("Accuracy:", accuracy_score(y_test, predictions))

print("\nClassification Report:\n")

print(classification_report(y_test, predictions))


# =========================
# Save Model
# =========================

joblib.dump(model, "department_classifier.pkl")

print("\nModel saved as department_classifier.pkl")