"""Unit tests for ``postup.adapters.web._security``."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from buvis.pybase.adapters import console
from fastapi import FastAPI, HTTPException
from postup.adapters.web._security import (
    LOOPBACK_HOSTS,
    TOKEN_HEADER,
    AppState,
    confine_path,
    generate_token,
    install_security,
    require_token,
)
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request


def _make_request(headers: dict[str, str], app: FastAPI) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "app": app,
    }
    return Request(scope)


class TestConfinePath:
    def test_rejects_path_outside_out_dir(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(HTTPException) as exc:
            confine_path("/etc/passwd", AppState(out_dir=str(out)))
        assert exc.value.status_code == 403

    def test_rejects_traversal_escape(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        out.mkdir()
        escape = str(out / ".." / ".." / "etc" / "passwd")
        with pytest.raises(HTTPException) as exc:
            confine_path(escape, AppState(out_dir=str(out)))
        assert exc.value.status_code == 403

    def test_rejects_symlink_escape(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.json"
        secret.write_text("leaked")
        out = tmp_path / "out"
        out.mkdir()
        link = out / "escape.json"
        os.symlink(secret, link)
        with pytest.raises(HTTPException) as exc:
            confine_path(str(link), AppState(out_dir=str(out)))
        assert exc.value.status_code == 403

    def test_rejects_empty_path(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(HTTPException) as exc:
            confine_path("", AppState(out_dir=str(out)))
        assert exc.value.status_code == 403

    def test_allows_real_path_in_out_dir(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        out.mkdir()
        contract = out / "data.json"
        contract.write_text("{}")
        assert confine_path(str(contract), AppState(out_dir=str(out))) == contract.resolve()


class TestGenerateToken:
    def test_non_empty_and_unique(self) -> None:
        a = generate_token()
        b = generate_token()
        assert a and b and a != b


class TestRequireToken:
    def test_missing_header_401(self) -> None:
        app = FastAPI()
        app.state.buvis_token = "expected"
        with pytest.raises(HTTPException) as exc:
            require_token(_make_request({}, app))
        assert exc.value.status_code == 401

    def test_mismatch_401(self) -> None:
        app = FastAPI()
        app.state.buvis_token = "expected"
        with pytest.raises(HTTPException) as exc:
            require_token(_make_request({TOKEN_HEADER: "wrong"}, app))
        assert exc.value.status_code == 401

    def test_match_returns_none(self) -> None:
        app = FastAPI()
        app.state.buvis_token = "expected"
        assert require_token(_make_request({TOKEN_HEADER: "expected"}, app)) is None

    def test_non_ascii_header_401_not_typeerror(self) -> None:
        app = FastAPI()
        app.state.buvis_token = "expected"
        with pytest.raises(HTTPException) as exc:
            require_token(_make_request({TOKEN_HEADER: "tökén"}, app))
        assert exc.value.status_code == 401


class TestInstallSecurity:
    def _trusted_kwargs(self, app: FastAPI) -> dict[str, object]:
        for m in app.user_middleware:
            if m.cls is TrustedHostMiddleware:
                return dict(m.kwargs)
        raise AssertionError("TrustedHostMiddleware not installed")

    def test_mints_token(self) -> None:
        app = FastAPI()
        install_security(app, "127.0.0.1")
        assert isinstance(app.state.buvis_token, str) and app.state.buvis_token

    def test_loopback_restricts_hosts_and_marks_token_in_page(self) -> None:
        app = FastAPI()
        install_security(app, "127.0.0.1")
        assert set(self._trusted_kwargs(app)["allowed_hosts"]) == LOOPBACK_HOSTS
        assert app.state.token_in_page is True

    def test_non_loopback_wildcards_hosts_and_warns_with_token(self) -> None:
        app = FastAPI()
        with console.capture() as capture:
            install_security(app, "0.0.0.0")
        assert list(self._trusted_kwargs(app)["allowed_hosts"]) == ["*"]
        assert app.state.token_in_page is False
        assert app.state.buvis_token in capture.get()
