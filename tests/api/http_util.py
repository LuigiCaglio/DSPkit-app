"""Minimal multipart POST over urllib, so the API tests need no new packages.

FastAPI's TestClient would be the obvious tool, but it needs httpx, which isn't
in the venv. Driving a real server over HTTP also exercises the actual request
parsing the browser hits, which TestClient partly bypasses.
"""
import io
import json
import urllib.error
import urllib.request

BOUNDARY = "----dspkittests"


def post(base, path, fields, files=None, timeout=180, headers=None):
    """POST multipart/form-data. Returns (status, parsed_json)."""
    body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{BOUNDARY}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.write(f"{v}\r\n".encode())
    for k, (name, data) in (files or {}).items():
        body.write(f"--{BOUNDARY}\r\n".encode())
        body.write(
            f'Content-Disposition: form-data; name="{k}"; filename="{name}"\r\n'.encode()
        )
        body.write(b"Content-Type: text/csv\r\n\r\n")
        body.write(data)
        body.write(b"\r\n")
    body.write(f"--{BOUNDARY}--\r\n".encode())

    req = urllib.request.Request(
        base + path,
        data=body.getvalue(),
        headers={
            "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get(base, path, timeout=60):
    """GET JSON. Returns (status, parsed_json)."""
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def request_json(base, path, method, payload=None, headers=None, timeout=60):
    """Send a JSON body with an arbitrary method. Returns (status, parsed_json)."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"detail": body.decode(errors="replace")}


class Results:
    """Tiny pass/fail recorder — enough structure without pulling in pytest."""

    def __init__(self):
        self.passed = 0
        self.failed = []

    def check(self, condition, label, detail=""):
        if condition:
            self.passed += 1
            print(f"  ok   {label}" + (f"  [{detail}]" if detail else ""))
        else:
            self.failed.append(label)
            print(f"  FAIL {label}" + (f"  [{detail}]" if detail else ""))
        return bool(condition)

    def section(self, name):
        print(f"\n{name}")

    def report(self):
        total = self.passed + len(self.failed)
        print(f"\n{self.passed}/{total} passed")
        for f in self.failed:
            print(f"  failed: {f}")
        return 1 if self.failed else 0
