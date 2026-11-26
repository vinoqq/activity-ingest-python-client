"""Reusable, single-request client for the activity ingest API.

Import :func:`submit_activity` and pass a JSON-ready activity mapping. Missing
or invalid required fields are returned by name without making a request.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import http.client
import json
import os
from typing import Any

HOST = "activity.aert.ipv64.net"
PATH = "/api/v1/ingest/activities"
ORIGIN = "https://activity.aert.ipv64.net"

# Required API fields and their maximum character counts.
REQUIRED_FIELDS = (
    ("platform_name", 160),
    ("account_identifier", 255),
    ("window_external_id", 255),
    ("window_title", 200),
    ("title", 300),
)

# Accepted JSON keys mirror the current ActivityIngest API schema. Rejecting
# unknown keys prevents accidental inclusion of credentials in the JSON body.
ALLOWED_FIELDS = frozenset(
    {
        "platform_name",
        "platform_type",
        "platform_website_url",
        "account_identifier",
        "account_display_name",
        "window_external_id",
        "window_title",
        "window_type",
        "window_url",
        "event_type",
        "title",
        "summary",
        "content",
        "occurred_at",
        "occurred_timezone",
        "source_url",
        "source_record_id",
    }
)


@dataclass(frozen=True)
class SubmissionResult:
    """HTTP status only; the response body is never read or returned."""

    status_code: int

    @property
    def accepted(self) -> bool:
        """Whether the API returned its documented created status."""
        return self.status_code == 201


class ActivitySubmissionError(RuntimeError):
    """Safe error message that never includes credentials or response content."""


def missing_required_fields(record: Mapping[str, Any]) -> list[str]:
    """Return missing/invalid required field names; this function never sends."""
    missing: list[str] = []
    for field, max_length in REQUIRED_FIELDS:
        value = record.get(field)
        if not isinstance(value, str):
            missing.append(field)
            continue
        value = value.strip()
        if not value or len(value) > max_length:
            missing.append(field)
    return missing


def submit_activity(
    record: Mapping[str, Any],
) -> list[str] | SubmissionResult:
    """Submit one activity or return missing required field names.

    If required fields are missing, blank, or over their API length limits, the
    field-name list is returned and no request is made. Otherwise this function
    reads the token only from ``ACTIVITY_WRITE_TOKEN`` and makes exactly one
    JSON POST to the fixed endpoint. It does not follow redirects or retry.
    The result contains only the HTTP status; response content is discarded.
    """
    if not isinstance(record, Mapping):
        raise TypeError("record must be a mapping; no request was sent")

    missing = missing_required_fields(record)
    if missing:
        return missing

    if any(not isinstance(key, str) or key not in ALLOWED_FIELDS for key in record):
        raise ValueError("record contains unsupported fields; no request was sent")

    token = os.environ.get("ACTIVITY_WRITE_TOKEN")
    if not token or token != token.strip():
        raise ActivitySubmissionError(
            "A valid ACTIVITY_WRITE_TOKEN is not available; no request was sent."
        )

    payload = dict(record)
    for field, _ in REQUIRED_FIELDS:
        payload[field] = payload[field].strip()
    payload.setdefault("event_type", "other")
    payload.setdefault("summary", "")

    try:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("record is not JSON-serializable; no request was sent") from None

    connection = http.client.HTTPSConnection(HOST, timeout=20)
    # Connect explicitly, then disallow implicit reconnects. http.client does
    # not follow HTTP redirects; this code makes one request() call and no retry.
    connection.auto_open = False
    try:
        connection.connect()
        connection.request(
            "POST",
            PATH,
            body=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": ORIGIN,
                "Content-Type": "application/json",
            },
        )
        response = connection.getresponse()
        status_code = response.status
        response.close()  # Discard without reading or logging the response body.
        return SubmissionResult(status_code=status_code)
    except (OSError, http.client.HTTPException, TimeoutError):
        raise ActivitySubmissionError(
            "The request result is unknown; do not retry this activity."
        ) from None
    finally:
        connection.close()
