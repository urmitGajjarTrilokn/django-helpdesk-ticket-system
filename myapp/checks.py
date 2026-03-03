from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def ai_config_checks(app_configs, **kwargs):
    issues = []

    timeout = getattr(settings, "GEMINI_TIMEOUT_SECONDS", 10)
    retries = getattr(settings, "GEMINI_MAX_RETRIES", 1)
    api_key = getattr(settings, "GEMINI_API_KEY", "")

    if not isinstance(timeout, int) or timeout <= 0:
        issues.append(
            Error(
                "GEMINI_TIMEOUT_SECONDS must be a positive integer.",
                id="myapp.E001",
            )
        )

    if not isinstance(retries, int) or retries < 0:
        issues.append(
            Error(
                "GEMINI_MAX_RETRIES must be a non-negative integer.",
                id="myapp.E002",
            )
        )

    if isinstance(retries, int) and retries > 5:
        issues.append(
            Warning(
                "GEMINI_MAX_RETRIES is high; this may slow ticket creation noticeably.",
                id="myapp.W001",
            )
        )

    if not api_key:
        issues.append(
            Warning(
                "GEMINI_API_KEY is not set; AI priority prediction will be skipped.",
                id="myapp.W002",
            )
        )

    return issues
