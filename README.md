# Activity Ingest Python Client

A dependency-free Python client for appending one activity to the Activity Registry.

```python
from post_activity import submit_activity

result = submit_activity(record)
if isinstance(result, list):
    print("Missing fields:", result)  # no request was sent
else:
    print("HTTP status:", result.status_code)
```

Set `ACTIVITY_WRITE_TOKEN` using your runtime's secret manager. With valid required fields, the client sends one JSON POST to the fixed ingest endpoint. It does not retry, follow redirects, or read the response body, and it has no read, edit, or delete function.
