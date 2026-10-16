from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from sysup.capabilities.x509 import X509Expiry

if TYPE_CHECKING:
    from pathlib import Path


def _self_signed_pem(not_after: datetime) -> bytes:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "example.test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_after - timedelta(days=365))
        .not_valid_after(not_after)
        .sign(key, hashes.SHA256())
    )
    from cryptography.hazmat.primitives.serialization import Encoding

    return certificate.public_bytes(Encoding.PEM)


class TestX509ExpiryWithCryptography:
    def test_pem_file_not_after(self, tmp_path: Path) -> None:
        pytest.importorskip("cryptography")
        not_after = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        pem = _self_signed_pem(not_after)
        pem_path = tmp_path / "cert.pem"
        pem_path.write_bytes(pem)
        result = X509Expiry().expires_at(path=str(pem_path))
        assert result == not_after

    def test_host_port_uses_get_server_certificate(self, mocker) -> None:
        pytest.importorskip("cryptography")
        not_after = datetime(2031, 6, 7, 8, 9, 10, tzinfo=timezone.utc)
        pem = _self_signed_pem(not_after).decode()
        get_cert = mocker.patch(
            "sysup.capabilities.x509.ssl.get_server_certificate",
            return_value=pem,
        )
        result = X509Expiry().expires_at(host="example.test:8443")
        assert result == not_after
        get_cert.assert_called_once_with(("example.test", 8443), timeout=10)


class TestX509ExpiryValidation:
    def test_exactly_one_of_path_or_host(self) -> None:
        assert X509Expiry().expires_at() == "x509-expiry needs exactly one of path or host"
        assert X509Expiry().expires_at(path="/a", host="b") == "x509-expiry needs exactly one of path or host"

    def test_missing_extra_reports_unknown_with_install_hint(self, monkeypatch) -> None:
        monkeypatch.setitem(__import__("sys").modules, "cryptography", None)
        result = X509Expiry().expires_at(path="/some/cert.pem")
        assert result == "x509-expiry needs the sysup-cert extra: uv tool install 'buvis-gems[sysup-cert]'"
