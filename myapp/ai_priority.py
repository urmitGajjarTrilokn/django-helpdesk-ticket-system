import json
import logging
import re
import time
from urllib import error, request

from django.conf import settings


logger = logging.getLogger(__name__)

ALLOWED_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "URGENT"}


def _extract_priority(raw_text: str) -> str | None:
    if not raw_text:
        return None

    # First try JSON response.
    try:
        payload = json.loads(raw_text)
        value = str(payload.get("priority", "")).upper().strip()
        if value in ALLOWED_PRIORITIES:
            return value
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    # Fallback: find known labels in free text.
    match = re.search(r"\b(LOW|MEDIUM|HIGH|URGENT)\b", raw_text.upper())
    if match:
        value = match.group(1)
        if value in ALLOWED_PRIORITIES:
            return value
    return None


def _extract_reason(raw_text: str) -> str:
    if not raw_text:
        return ""
    try:
        payload = json.loads(raw_text)
        reason = str(payload.get("reason", "")).strip()
        return reason[:400]
    except (json.JSONDecodeError, TypeError, AttributeError):
        return ""


def _safe_trim(value: str, limit: int) -> str:
    value = (value or "").strip()
    return value[:limit]


def predict_ticket_priority_with_meta(title: str, description: str) -> dict:
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    timeout = int(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 10))
    retries = int(getattr(settings, "GEMINI_MAX_RETRIES", 1))

    if not api_key:
        return {
            "priority": None,
            "reason": "",
            "raw_text": "",
            "model": model,
            "error": "missing_api_key",
        }

    title = _safe_trim(title, 200)
    description = _safe_trim(description, 2500)

    prompt = (
        "Classify this helpdesk ticket priority into exactly one of: "
        "LOW, MEDIUM, HIGH, URGENT.\n"
        "Return strict JSON only in this format: "
        '{"priority":"LOW|MEDIUM|HIGH|URGENT","reason":"short reason"}.\n'
        "Use urgency, business impact, and service disruption severity.\n\n"
        f"Title: {title}\n"
        f"Description: {description}"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    }

    req = request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    max_attempts = max(1, retries + 1)
    result = None
    last_error = None
    for attempt in range(max_attempts):
        try:
            with request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt < max_attempts - 1:
                time.sleep(0.2 * (attempt + 1))

    if result is None:
        logger.warning("Gemini priority prediction failed after retries: %s", last_error)
        return {
            "priority": None,
            "reason": "",
            "raw_text": "",
            "model": model,
            "error": last_error or "prediction_failed",
        }

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Gemini response format unexpected for priority prediction: %s", exc)
        return {
            "priority": None,
            "reason": "",
            "raw_text": "",
            "model": model,
            "error": "invalid_response_format",
        }

    return {
        "priority": _extract_priority(text),
        "reason": _extract_reason(text),
        "raw_text": _safe_trim(text, 2000),
        "model": model,
        "error": "",
    }


def predict_ticket_priority(title: str, description: str) -> str | None:
    return predict_ticket_priority_with_meta(title=title, description=description).get("priority")
