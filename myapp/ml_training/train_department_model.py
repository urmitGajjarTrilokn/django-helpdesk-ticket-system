import pandas as pd
import pickle

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report

# load dataset
df = pd.read_csv("helpdesk_tickets_cleaned.csv")

# combine text
df["text"] = df["title"] + " " + df["description"]

X = df["text"]
y = df["department"]

# split
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# pipeline
model = Pipeline([
    ("tfidf", TfidfVectorizer(
        stop_words="english",
        ngram_range=(1,2),
        max_features=10000
    )),
    ("clf", LogisticRegression(
        max_iter=1000,
        class_weight="balanced"
    ))
])

# train
model.fit(X_train, y_train)

# test
preds = model.predict(X_test)

print("Accuracy:", accuracy_score(y_test, preds))
print("\nClassification Report:\n")
print(classification_report(y_test, preds))

# save model
with open("department_classifier.pkl", "wb") as f:
    pickle.dump(model, f)

print("\nModel saved successfully")