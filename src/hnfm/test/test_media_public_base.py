"""Presigned media URLs are signed for the host the browser actually used.

The cluster ingress path-routes frontend, API and MinIO behind one origin,
but that origin answers to several names (hnfm.lan, the tailnet name). The
redirect to MinIO must be signed for whichever one the request came in on.
"""

from starlette.requests import Request

from hnfm.web.api import _request_public_base


def _req(headers: dict, scheme: str = "http") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/x",
        "query_string": b"",
        "scheme": scheme,
        "server": ("hnfm-web", 8000),
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


def test_uses_forwarded_origin_when_minio_shares_the_app_origin(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_BASE", "https://hnfm.lan")
    monkeypatch.setenv("S3_PUBLIC_URL", "https://hnfm.lan")
    req = _req({
        "host": "hnfm-web:8000",
        "x-forwarded-host": "hnfm.example.ts.net",
        "x-forwarded-proto": "https",
    })
    assert _request_public_base(req) == "https://hnfm.example.ts.net"


def test_falls_back_to_host_header(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_BASE", "https://hnfm.lan")
    monkeypatch.setenv("S3_PUBLIC_URL", "https://hnfm.lan")
    req = _req({"host": "hnfm.lan"}, scheme="https")
    assert _request_public_base(req) == "https://hnfm.lan"


def test_none_when_minio_has_its_own_public_url(monkeypatch):
    # Mac dev / external MinIO: S3_PUBLIC_URL is the only host that can sign.
    monkeypatch.setenv("PUBLIC_API_BASE", "http://localhost:8000")
    monkeypatch.setenv("S3_PUBLIC_URL", "http://localhost:9400")
    req = _req({"host": "localhost:8000"})
    assert _request_public_base(req) is None


def test_presigned_url_signs_for_requested_origin(monkeypatch):
    from hnfm.storage import object_store

    monkeypatch.setenv("S3_PUBLIC_URL", "https://hnfm.lan")
    object_store.reset()
    default = object_store.presigned_url("k/v.mp4")
    remote = object_store.presigned_url("k/v.mp4", public_base="https://hnfm.example.ts.net")
    assert default.startswith("https://hnfm.lan/hnfm-media/k/v.mp4?")
    assert remote.startswith("https://hnfm.example.ts.net/hnfm-media/k/v.mp4?")
    object_store.reset()
