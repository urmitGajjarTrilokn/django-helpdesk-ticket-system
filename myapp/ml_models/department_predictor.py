import logging
import os
import pickle
import warnings

from django.conf import settings
from sklearn.exceptions import InconsistentVersionWarning

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    "myapp",
    "ml_models",
    "department_classifier.pkl",
)

_model = None
_model_load_attempted = False
_model_load_error = None


def _get_model():
    global _model, _model_load_attempted, _model_load_error
    if _model_load_attempted:
        return _model

    _model_load_attempted = True
    try:
        with open(MODEL_PATH, "rb") as f:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always", InconsistentVersionWarning)
                _model = pickle.load(f)
            if any(issubclass(w.category, InconsistentVersionWarning) for w in captured):
                logger.warning(
                    "Department model was trained with a different scikit-learn version. "
                    "Model loaded, but retraining is recommended."
                )
    except Exception as exc:
        _model_load_error = exc
        logger.warning("Department model load failed: %s", exc)
        _model = None
    return _model


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

    model = _get_model()
    if model is None:
        raise RuntimeError(f"Department model unavailable: {_model_load_error}")

    prediction = model.predict([text])[0]

    return prediction
