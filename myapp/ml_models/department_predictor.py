import pickle
import os
from django.conf import settings

MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    "myapp",
    "ml_models",
    "department_classifier.pkl"
)

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)


def predict_department(title, description):

    text = f"{title} {description}".lower()

    if any(word in text for word in ["invoice", "billing", "payment", "refund"]):
        return "Finance"

    if any(word in text for word in ["leave", "vacation", "salary", "payroll", "hr"]):
        return "HR"

    if any(word in text for word in ["vpn", "server", "login", "network", "password", "database"]):
        return "IT Support"

    if any(word in text for word in ["complaint", "customer", "support", "refund request"]):
        return "Customer Support"

    prediction = model.predict([text])[0]

    return prediction