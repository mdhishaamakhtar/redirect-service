"""Minimal HTTP redirect endpoint using the `redirect_uri` query parameter."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from flask import Flask, abort, redirect, request

app = Flask(__name__)

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_MAX_REDIRECT_URI_LENGTH = 2048


def _validate_redirect_target(raw: str) -> str:
    value = raw.strip()
    if not value or len(value) > _MAX_REDIRECT_URI_LENGTH:
        abort(400)
    parsed = urlparse(value)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        abort(400)
    return value


@app.get("/")
def redirect_handler():
    raw = request.args.get("redirect_uri")
    if raw is None:
        abort(400)
    target = _validate_redirect_target(raw)
    return redirect(target, code=301)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
