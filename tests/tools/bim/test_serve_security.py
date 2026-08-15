"""Unit tests for ``bim.commands.serve._security``.

Covers path confinement (``confine_path``), token generation
(``generate_token``), the ``require_token`` FastAPI dependency, and
``install_security``'s ``TrustedHostMiddleware`` wiring.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from bim.commands.serve._security import (
    LOOPBACK_HOSTS,
    TOKEN_HEADER,
    AppState,
    confine_path,
    generate_token,
    install_security,
    require_token,
)
from buvis.pybase.adapters import console
from fastapi import FastAPI, HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request


def _make_request(headers: dict[str, str], app: FastAPI) -> Request:
    """Build a real ``starlette.requests.Request`` off a minimal ASGI scope."""
    scope = {
        "type": "http",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        "app": app,
    }
    return Request(scope)


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake ``$HOME`` directory, with ``HOME`` patched to point at it."""
    home = tmp_path / "fake_home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


class TestConfinePath:
    def test_rejects_path_outside_allowed_roots(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        app_state = AppState(default_directory=str(vault), archive_directory=None)

        with pytest.raises(HTTPException) as exc_info:
            confine_path("/etc/passwd", app_state)
        assert exc_info.value.status_code == 403

    def test_rejects_path_traversal_escape(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        app_state = AppState(default_directory=str(vault), archive_directory=None)

        escape_path = str(vault / ".." / ".." / "etc" / "passwd")

        with pytest.raises(HTTPException) as exc_info:
            confine_path(escape_path, app_state)
        assert exc_info.value.status_code == 403

    def test_rejects_symlink_escape(self, tmp_path: Path) -> None:
        """Symlink physically inside the vault whose target lies outside it
        must not be treated as confined (this pins down that resolution,
        not mere path-prefix matching, gates access)."""
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("leaked")

        vault = tmp_path / "vault"
        vault.mkdir()
        link = vault / "escape.txt"
        os.symlink(secret, link)

        app_state = AppState(default_directory=str(vault), archive_directory=None)

        with pytest.raises(HTTPException) as exc_info:
            confine_path(str(link), app_state)
        assert exc_info.value.status_code == 403

    def test_allows_real_in_vault_path(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        note = vault / "note.md"
        note.write_text("hello")

        app_state = AppState(default_directory=str(vault), archive_directory=None)

        result = confine_path(str(note), app_state)
        assert result == note.resolve()

    def test_allows_path_under_archive_directory(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        archive = tmp_path / "archive"
        archive.mkdir()
        archived_note = archive / "old.md"
        archived_note.write_text("archived")

        app_state = AppState(default_directory=str(vault), archive_directory=str(archive))

        result = confine_path(str(archived_note), app_state)
        assert result == archived_note.resolve()

    def test_rejects_empty_file_path(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        app_state = AppState(default_directory=str(vault), archive_directory=None)

        with pytest.raises(HTTPException) as exc_info:
            confine_path("", app_state)
        assert exc_info.value.status_code == 403

    def test_rejects_empty_file_path_even_when_cwd_is_in_vault(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty ``file_path`` must never resolve to the current working
        directory, even when the process happens to be running from inside
        an allowed root."""
        vault = tmp_path / "vault"
        vault.mkdir()
        app_state = AppState(default_directory=str(vault), archive_directory=None)
        monkeypatch.chdir(vault)

        with pytest.raises(HTTPException) as exc_info:
            confine_path("", app_state)
        assert exc_info.value.status_code == 403

    def test_resolve_oserror_raises_403(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``file_path`` whose ``.resolve()`` raises ``OSError`` (e.g. a
        circular symlink) must be denied, not propagate the OSError."""
        vault = tmp_path / "vault"
        vault.mkdir()
        app_state = AppState(default_directory=str(vault), archive_directory=None)

        target = str(vault / "loop")
        original_resolve = Path.resolve

        def fake_resolve(self: Path, *args: object, **kwargs: object) -> Path:
            if str(self) == target:
                raise OSError("Too many levels of symbolic links")
            return original_resolve(self, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", fake_resolve)

        with pytest.raises(HTTPException) as exc_info:
            confine_path(target, app_state)
        assert exc_info.value.status_code == 403

    def test_allows_absolute_path_under_tilde_form_default_directory(self, fake_home: Path) -> None:
        """``default_directory`` given in tilde form must be expanded before
        confinement, so a real file inside it is reachable by its absolute
        path, not just by luck of a matching cwd."""
        vault = fake_home / "vault-under-a-fake-home"
        vault.mkdir()
        note = vault / "note.md"
        note.write_text("hello")

        app_state = AppState(default_directory="~/vault-under-a-fake-home", archive_directory=None)

        result = confine_path(str(note), app_state)
        assert result == note.resolve()

    def test_allows_tilde_form_request_path_under_tilde_form_default_directory(self, fake_home: Path) -> None:
        """The incoming ``file_path`` is also expanded, so a tilde-form
        request path resolves to the same real file as its absolute form."""
        vault = fake_home / "vault-under-a-fake-home"
        vault.mkdir()
        note = vault / "note.md"
        note.write_text("hello")

        app_state = AppState(default_directory="~/vault-under-a-fake-home", archive_directory=None)

        result = confine_path("~/vault-under-a-fake-home/note.md", app_state)
        assert result == note.resolve()

    def test_rejects_path_outside_tilde_form_default_directory(self, fake_home: Path) -> None:
        vault = fake_home / "vault-under-a-fake-home"
        vault.mkdir()
        outside = fake_home / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("leaked")

        app_state = AppState(default_directory="~/vault-under-a-fake-home", archive_directory=None)

        with pytest.raises(HTTPException) as exc_info:
            confine_path(str(secret), app_state)
        assert exc_info.value.status_code == 403

    def test_allows_path_under_tilde_form_archive_directory(self, fake_home: Path) -> None:
        """``archive_directory`` given in tilde form must be expanded the
        same way as ``default_directory``."""
        vault = fake_home / "vault"
        vault.mkdir()
        archive = fake_home / "archive-under-a-fake-home"
        archive.mkdir()
        archived_note = archive / "old.md"
        archived_note.write_text("archived")

        app_state = AppState(default_directory=str(vault), archive_directory="~/archive-under-a-fake-home")

        result = confine_path(str(archived_note), app_state)
        assert result == archived_note.resolve()

    def test_allows_tilde_form_request_path_against_absolute_form_allowed_root(self, fake_home: Path) -> None:
        """A tilde-form request path must expand and resolve into an
        ordinary, already-absolute ``default_directory``."""
        vault = fake_home / "vault"
        vault.mkdir()
        note = vault / "note.md"
        note.write_text("hello")

        app_state = AppState(default_directory=str(vault), archive_directory=None)

        result = confine_path("~/vault/note.md", app_state)
        assert result == note.resolve()

    def test_rejects_tilde_form_request_path_outside_absolute_form_allowed_root(self, fake_home: Path) -> None:
        vault = fake_home / "vault"
        vault.mkdir()
        outside = fake_home / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("leaked")

        app_state = AppState(default_directory=str(vault), archive_directory=None)

        with pytest.raises(HTTPException) as exc_info:
            confine_path("~/outside/secret.txt", app_state)
        assert exc_info.value.status_code == 403


class TestGenerateToken:
    def test_returns_non_empty_string(self) -> None:
        token = generate_token()
        assert isinstance(token, str)
        assert token != ""

    def test_returns_reasonably_long_token(self) -> None:
        token = generate_token()
        assert len(token) >= 32

    def test_two_calls_return_different_values(self) -> None:
        assert generate_token() != generate_token()


class TestRequireToken:
    def test_missing_header_raises_401(self) -> None:
        app = FastAPI()
        app.state.buvis_token = "expected-token"
        request = _make_request({}, app)

        with pytest.raises(HTTPException) as exc_info:
            require_token(request)
        assert exc_info.value.status_code == 401

    def test_mismatched_header_raises_401(self) -> None:
        app = FastAPI()
        app.state.buvis_token = "expected-token"
        request = _make_request({TOKEN_HEADER: "wrong-token"}, app)

        with pytest.raises(HTTPException) as exc_info:
            require_token(request)
        assert exc_info.value.status_code == 401

    def test_matching_header_returns_none(self) -> None:
        app = FastAPI()
        app.state.buvis_token = "expected-token"
        request = _make_request({TOKEN_HEADER: "expected-token"}, app)

        assert require_token(request) is None

    def test_non_ascii_header_raises_401_not_type_error(self) -> None:
        """``secrets.compare_digest`` raises ``TypeError`` on a non-ASCII
        ``str`` argument; that must be turned into the documented 401, not
        left to escape as an uncaught exception."""
        app = FastAPI()
        app.state.buvis_token = "expected-token"
        request = _make_request({TOKEN_HEADER: "tökén"}, app)

        with pytest.raises(HTTPException) as exc_info:
            require_token(request)
        assert exc_info.value.status_code == 401


class TestInstallSecurity:
    def _trusted_host_kwargs(self, app: FastAPI) -> dict[str, object]:
        for middleware in app.user_middleware:
            if middleware.cls is TrustedHostMiddleware:
                return dict(middleware.kwargs)
        raise AssertionError("TrustedHostMiddleware was not installed")

    def test_mints_token_onto_app_state(self) -> None:
        app = FastAPI()
        install_security(app, "127.0.0.1")
        assert isinstance(app.state.buvis_token, str)
        assert app.state.buvis_token != ""

    def test_loopback_host_restricts_allowed_hosts_to_loopback_set(self) -> None:
        app = FastAPI()
        install_security(app, "127.0.0.1")
        kwargs = self._trusted_host_kwargs(app)
        assert set(kwargs["allowed_hosts"]) == LOOPBACK_HOSTS

    def test_non_loopback_host_widens_allowed_hosts_to_wildcard(self) -> None:
        app = FastAPI()
        install_security(app, "0.0.0.0")
        kwargs = self._trusted_host_kwargs(app)
        assert list(kwargs["allowed_hosts"]) == ["*"]

    @pytest.mark.parametrize("host", sorted(LOOPBACK_HOSTS))
    def test_loopback_host_marks_token_in_page_true(self, host: str) -> None:
        app = FastAPI()
        install_security(app, host)
        assert app.state.token_in_page is True

    def test_non_loopback_host_marks_token_in_page_false(self) -> None:
        app = FastAPI()
        install_security(app, "0.0.0.0")
        assert app.state.token_in_page is False

    def test_non_loopback_host_surfaces_minted_token_to_operator_via_console(self) -> None:
        app = FastAPI()
        with console.capture() as capture:
            install_security(app, "0.0.0.0")

        assert app.state.buvis_token in capture.get()

    def test_non_loopback_warning_describes_unauthenticated_reads_not_protected_writes(self) -> None:
        app = FastAPI()
        with console.capture() as capture:
            install_security(app, "0.0.0.0")

        output = capture.get().lower()
        assert "read notes without" in output
        assert "writes still require it" not in output
