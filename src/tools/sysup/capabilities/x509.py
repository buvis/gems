from __future__ import annotations

import ssl
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

__all__ = ["X509Expiry"]

_DEFAULT_PORT = 443
_CONNECT_TIMEOUT = 10


class X509Expiry:
    """Report the not-after date of a PEM file or a TLS endpoint's certificate.

    Reads exactly one of a local PEM ``path`` or a remote ``host`` (``name`` or
    ``name:port``, port 443 by default). The ``cryptography`` parser is imported
    lazily inside :meth:`expires_at` so a core-only install (without the
    ``sysup-cert`` extra) can still import sysup and track gh tokens; the missing
    extra is reported as an unknown reason with an install hint.
    """

    @property
    def inputs(self: X509Expiry) -> Mapping[str, object]:
        return {"path": "", "host": ""}

    def expires_at(self: X509Expiry, **kwargs: object) -> datetime | str:
        """Return the certificate not-after datetime, or an unknown reason.

        Args:
            **kwargs: exactly one of ``path`` (a PEM file) or ``host`` (``name``
                or ``name:port``).

        Returns:
            The certificate's ``not_valid_after_utc``, or one of the documented
            unknown reasons as a string.
        """
        path = str(kwargs.get("path", ""))
        host = str(kwargs.get("host", ""))
        if bool(path) == bool(host):
            return "x509-expiry needs exactly one of path or host"

        try:
            from cryptography import x509
        except ImportError:
            return "x509-expiry needs the sysup-cert extra: uv tool install 'buvis-gems[sysup-cert]'"

        try:
            pem = self._pem_from_path(path) if path else self._pem_from_host(host)
            certificate = x509.load_pem_x509_certificate(pem)
        except (OSError, ValueError) as exc:
            return f"{type(exc).__name__}: {exc}"

        return certificate.not_valid_after_utc

    def _pem_from_path(self: X509Expiry, path: str) -> bytes:
        return Path(path).expanduser().read_bytes()

    def _pem_from_host(self: X509Expiry, host: str) -> bytes:
        # Split on the first colon: `name` keeps the default port, `name:port`
        # supplies one. IPv6 literals are out of scope (single-colon inputs).
        name, _, port_text = host.partition(":")
        port = int(port_text) if port_text else _DEFAULT_PORT
        pem = ssl.get_server_certificate((name, port), timeout=_CONNECT_TIMEOUT)
        return pem.encode()
