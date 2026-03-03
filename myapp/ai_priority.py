import json
import logging
import re
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
    model = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
    timeout = int(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 10))

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
            "maxOutputTokens": 50,
            "responseMimeType": "application/json",
        },
    }

    req = request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            error_body = ""
        last_error = f"HTTP {exc.code}: {exc.reason}"
        if error_body:
            last_error = f"{last_error} | {error_body[:500]}"
        logger.warning("Gemini priority prediction failed: %s", last_error)
        fallback = heuristic_priority_from_text(title, description)
        fallback["error"] = last_error
        return fallback
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        last_error = str(exc)
        logger.warning("Gemini priority prediction failed: %s", last_error)
        fallback = heuristic_priority_from_text(title, description)
        fallback["error"] = last_error or "prediction_failed"
        return fallback

    try:
        candidate = result.get("candidates", [])[0]
        content = candidate.get("content", {})

        if "parts" in content:
            text = content["parts"][0].get("text", "")

        elif "text" in content:
            text = content.get("text", "")

        else:
            text = ""

        if not text:
            raise ValueError("Empty response text")

    except Exception as exc:
        logger.warning(
            "Gemini response format unexpected for priority prediction: %s | Full response: %s",
            exc,
            result,
        )
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
