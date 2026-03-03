import json
import logging
import re
import time
from urllib import error, request

from django.conf import settings


logger = logging.getLogger(__name__)

ALLOWED_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "URGENT"}

URGENT_KEYWORDS = {
    "outage", "down", "breach", "security incident", "data loss", "critical",
    "production down", "all users", "cannot login", "payment failed", "payroll blocked",
}
HIGH_KEYWORDS = {
    "blocked", "cannot access", "failed", "error", "urgent", "invoice", "payroll",
    "database", "latency", "timeout", "customer impact", "major",
}
LOW_KEYWORDS = {
    "typo", "ui issue", "alignment", "cosmetic", "enhancement", "suggestion",
    "minor", "small", "formatting",
}


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


def heuristic_priority_from_text(title: str, description: str) -> dict:
    text = f"{title or ''} {description or ''}".lower()

    urgent_hits = sum(1 for kw in URGENT_KEYWORDS if kw in text)
    high_hits = sum(1 for kw in HIGH_KEYWORDS if kw in text)
    low_hits = sum(1 for kw in LOW_KEYWORDS if kw in text)

    if urgent_hits >= 1:
        priority = "URGENT"
        reason = "Rule-based fallback detected outage/security/business-critical terms."
    elif high_hits >= 2:
        priority = "HIGH"
        reason = "Rule-based fallback detected significant impact/blocking signals."
    elif low_hits >= 1 and high_hits == 0:
        priority = "LOW"
        reason = "Rule-based fallback detected cosmetic/minor request terms."
    else:
        priority = "MEDIUM"
        reason = "Rule-based fallback defaulted to medium impact."

    return {
        "priority": priority,
        "reason": reason,
        "raw_text": "",
        "model": "heuristic-fallback",
        "error": "",
    }


def predict_ticket_priority_with_meta(title: str, description: str) -> dict:
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    timeout = int(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 10))
    retries = int(getattr(settings, "GEMINI_MAX_RETRIES", 1))

    if not api_key:
        fallback = heuristic_priority_from_text(title, description)
        fallback["error"] = "missing_api_key"
        return fallback

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
        fallback = heuristic_priority_from_text(title, description)
        fallback["error"] = last_error or "prediction_failed"
        return fallback

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Gemini response format unexpected for priority prediction: %s", exc)
        fallback = heuristic_priority_from_text(title, description)
        fallback["error"] = "invalid_response_format"
        return fallback

    return {
        "priority": _extract_priority(text),
        "reason": _extract_reason(text),
        "raw_text": _safe_trim(text, 2000),
        "model": model,
        "error": "",
    }


def predict_ticket_priority(title: str, description: str) -> str | None:
    return predict_ticket_priority_with_meta(title=title, description=description).get("priority")
