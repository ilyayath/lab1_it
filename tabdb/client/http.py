"""HTTP-клієнт REST API TabDB на стандартній бібліотеці."""

import json
import urllib.error
import urllib.request
from urllib.parse import quote

from .. import datatypes
from ..datatypes import TabDBError


class ServerError(TabDBError):
    """Сервер недоступний або відповів непередбачено."""


def urllib_transport(method, url, body, timeout=10):
    """Надсилає запит і повертає (код статусу, тіло відповіді в байтах)."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise ServerError(f"Сервер {url} недоступний: {reason}")


class ApiClient:
    """Виклики REST API з перетворенням помилок назад у винятки TabDB.

    transport можна підмінити (наприклад, у тестах — на TestClient FastAPI).
    """

    def __init__(self, base_url, transport=urllib_transport):
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    def request(self, method, *path, body=None):
        url = self.base_url + "/api/v1/" + "/".join(quote(str(p), safe="") for p in path)
        status, content = self.transport(method, url, body)
        payload = json.loads(content) if content else None
        if status >= 400:
            raise to_exception(status, payload)
        return payload

    def get(self, *path):
        return self.request("GET", *path)

    def post(self, *path, body=None):
        return self.request("POST", *path, body=body)

    def put(self, *path, body=None):
        return self.request("PUT", *path, body=body)

    def delete(self, *path):
        return self.request("DELETE", *path)


def to_exception(status, payload):
    """Відтворює виняток сервера, зокрема помилки валідації окремих полів."""
    if not isinstance(payload, dict) or "message" not in payload:
        return ServerError(f"Сервер повернув помилку HTTP {status}")

    cls = getattr(datatypes, payload.get("error", ""), None)
    if not (isinstance(cls, type) and issubclass(cls, TabDBError)):
        cls = TabDBError
    if cls is datatypes.ValidationError:
        errors = {int(i): msg for i, msg in payload.get("errors", {}).items()}
        return cls(payload["message"], errors)
    return cls(payload["message"])
