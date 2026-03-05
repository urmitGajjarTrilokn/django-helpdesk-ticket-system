import pickle
import os
from django.conf import settings

MODEL_PATH = os.path.join(settings.BASE_DIR, "myapp/ml_models/department_classifier.pkl")

with open(MODEL_PATH, "rb") as f:
    vectorizer, model = pickle.load(f)


def predict_department(title, description):

    text = f"{title} {description}"

    X = vectorizer.transform([text])

    prediction = model.predict(X)[0]

    return prediction