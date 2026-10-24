"""TLS workaround, applied only when it is actually needed.

This macOS python.org build ships a broken OpenSSL trust store: TLS
verification fails even with a valid CA bundle, which also breaks the
Gnani SDK (it uses requests internally and has no fallback).

We probe a known HTTPS endpoint; only if verification genuinely fails do
we patch every seam a TLS handshake can go through:
- ssl.create_default_context (stdlib / httpx path)
- urllib3.util.ssl_.create_urllib3_context (requests path; it builds
  SSLContext(PROTOCOL_TLS_CLIENT) directly, bypassing create_default_context)
- ssl.SSLContext.wrap_socket (the reliable catch-all: resolved on the
  class at handshake time for every context, however it was created)

On healthy systems (e.g. the Debian Docker image) nothing is patched.

ponytail: dev-sandbox only - never ship this to production. A proper
fix is a Python build that trusts the system keychain.
"""

from __future__ import annotations

import ssl


def _tls_verify_broken() -> bool:
    try:
        import requests

        requests.get("https://api.vachana.ai", timeout=8)
        return False
    except requests.exceptions.SSLError:
        return True
    except requests.RequestException:
        return False  # network hiccup, not a TLS problem - do not patch


def _apply_patches() -> None:
    _ORIGINAL_WRAP = ssl.SSLContext.wrap_socket

    def _insecure_wrap(self, *args, **kwargs):
        self.check_hostname = False
        self.verify_mode = ssl.CERT_NONE
        return _ORIGINAL_WRAP(self, *args, **kwargs)

    ssl.SSLContext.wrap_socket = _insecure_wrap

    _ORIGINAL_CREATE = ssl.create_default_context

    def _insecure_default_context(*args, **kwargs) -> ssl.SSLContext:
        ctx = _ORIGINAL_CREATE(*args, **kwargs)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    ssl.create_default_context = _insecure_default_context

    try:
        import urllib3.util.ssl_ as _ssl_util

        _ORIGINAL_URLLIB3 = _ssl_util.create_urllib3_context

        def _insecure_urllib3_context(*args, **kwargs) -> ssl.SSLContext:
            ctx = _ORIGINAL_URLLIB3(*args, **kwargs)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

        _ssl_util.create_urllib3_context = _insecure_urllib3_context
    except ImportError:
        pass


if _tls_verify_broken():
    _apply_patches()