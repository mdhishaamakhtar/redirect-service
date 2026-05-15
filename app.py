"""Minimal HTTP redirect endpoint using the `redirect_uri` query parameter."""

from __future__ import annotations

import json
import os
from html import escape
from urllib.parse import urlparse, urlunparse, quote

from flask import Flask, Response, abort, redirect, request

app = Flask(__name__)

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_MAX_REDIRECT_URI_LENGTH = 2048
_CHROME_ANDROID_PACKAGE = "com.android.chrome"
_IOS_CHROME_SCHEME = {"https": "googlechromes", "http": "googlechrome"}

# Small delay lets Chrome intercept `googlechromes://`/`googlechrome://`; if unresolved, fall back.
_IOS_CHROME_BRIDGE_FALLBACK_MS = 850


def _validate_redirect_target(raw: str) -> str:
    value = raw.strip()
    if not value or len(value) > _MAX_REDIRECT_URI_LENGTH:
        abort(400)
    parsed = urlparse(value)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        abort(400)
    return value


def _is_whatsapp_agent(user_agent: str | None) -> bool:
    if not user_agent:
        return False
    return "whatsapp" in user_agent.lower()


def _is_likely_android(user_agent: str) -> bool:
    return "android" in user_agent.lower()


def _is_likely_ios(user_agent: str) -> bool:
    ua = user_agent.lower()
    if "iphone" in ua or "ipad" in ua or "ipod" in ua:
        return True
    return "mobile" in ua and "safari/" in ua and "android" not in ua


def _strip_fragment_for_intent_launch(target_url: str) -> str:
    """Android intent URIs reuse `#`; keep fragment only in fallback `S.browser_fallback_url`."""

    parsed = urlparse(target_url)
    stripped = parsed._replace(fragment="")
    return urlunparse(stripped)


def _android_chrome_intent_url(target_url: str) -> str:
    """
    Prefer opening the destination in Chrome (Android Intent URL), with HTTPS/HTTP fallback
    via `S.browser_fallback_url` (Chrome docs).

    Raises ValueError when the intent cannot be built safely.
    """

    parsed = urlparse(target_url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        raise ValueError("invalid target")

    fallback = quote(target_url, safe="")

    parsed_launch = urlparse(_strip_fragment_for_intent_launch(target_url))
    path = parsed_launch.path or "/"
    host_path_query = parsed_launch.netloc + path
    if parsed_launch.query:
        host_path_query += f"?{parsed_launch.query}"

    return (
        f"intent://{host_path_query}#Intent;"
        f"scheme={scheme};"
        f"package={_CHROME_ANDROID_PACKAGE};"
        f"S.browser_fallback_url={fallback};"
        "end"
    )


def _ios_chrome_custom_scheme_url(target_url: str) -> str:
    """Map http(s) to Chrome for iOS custom schemes (Chromium iOS documentation)."""

    parsed = urlparse(target_url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _IOS_CHROME_SCHEME or not parsed.netloc:
        raise ValueError("invalid target")

    chrome_scheme = _IOS_CHROME_SCHEME[scheme]
    tail = parsed.netloc + (parsed.path or "/")
    if parsed.query:
        tail += f"?{parsed.query}"
    if parsed.fragment:
        tail += f"#{parsed.fragment}"
    return f"{chrome_scheme}://{tail}"


def _ios_chrome_bridge_page(chrome_scheme_url: str, fallback_https_url: str) -> str:
    """HTML bridge: attempt Chrome URL, then fall back to the default browser URL."""

    js_chrome = json.dumps(chrome_scheme_url)
    js_fallback = json.dumps(fallback_https_url)
    esc_fb = escape(fallback_https_url, quote=True)

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<noscript><meta http-equiv="refresh" content="0;url={esc_fb}"></noscript>
<title>Opening link</title>
<script>
(function () {{
  var chromeUrl = {js_chrome};
  var fallbackUrl = {js_fallback};
  window.location.replace(chromeUrl);
  window.setTimeout(function () {{
    window.location.replace(fallbackUrl);
  }}, {_IOS_CHROME_BRIDGE_FALLBACK_MS});
}})();
</script>
</head><body>
<p><a href="{esc_fb}">Continue in your browser</a></p>
</body></html>
"""


def _redirect_for_whatsapp(user_agent: str, target_url: str) -> Response:
    """Route WhatsApp in-app browsers toward Chrome where possible."""

    try:
        if _is_likely_android(user_agent):
            intent_url = _android_chrome_intent_url(target_url)
            return redirect(intent_url, code=302)

        if _is_likely_ios(user_agent):
            chrome_url = _ios_chrome_custom_scheme_url(target_url)
            html = _ios_chrome_bridge_page(chrome_url, target_url)
            return Response(
                html,
                status=200,
                headers={"Cache-Control": "no-store"},
                mimetype="text/html; charset=utf-8",
            )
    except ValueError:
        pass

    return redirect(target_url, code=302)


@app.get("/")
def redirect_handler():
    raw = request.args.get("redirect_uri")
    if raw is None:
        abort(400)
    target = _validate_redirect_target(raw)
    user_agent = request.headers.get("User-Agent")
    if _is_whatsapp_agent(user_agent):
        return _redirect_for_whatsapp(user_agent, target)
    return redirect(target, code=302)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
