from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from bim.commands.doc.shared.naming import build_canonical_filename
from bim.commands.doc.shared.settings_models import DocSettings
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.triage import write_proposal
from pytest_mock import MockerFixture

from . import promote_helpers
from .promote_helpers import _advance_seconds, _build_command, _build_proposal, _stage_triage_pair

if TYPE_CHECKING:
    from bim.commands.doc.promote.promote import CommandPromote

settings = promote_helpers.settings
registry_path = promote_helpers.registry_path
lock_path = promote_helpers.lock_path
state_db = promote_helpers.state_db

# Substring pinned by test_naming.py::test_sixty_consecutive_collisions_raises_value_error;
# maximally discriminating since it survives any future change to promote's wrapper prefix.
_COLLISION_EXHAUSTED = "could not resolve filename collision after 60 attempts"


def stage_and_build(
    *,
    triage_dir: Path,
    basename: str,
    settings: DocSettings,
    registry_path: Path,
    lock_path: Path,
    state_db: StateDB,
    mocker: MockerFixture,
    pdf_bytes: bytes | None = None,
) -> tuple[CommandPromote, Path]:
    """Stage a triage PDF, write its proposal, and build the promote command.

    Returns the built command and the proposal ``.yml`` path (several tests
    assert the ``.yml`` survives a failed promote).
    """
    pdf, yml = _stage_triage_pair(triage_dir, basename)
    if pdf_bytes is not None:
        pdf.write_bytes(pdf_bytes)
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    write_proposal(yml, _build_proposal(sha256=sha, triage_pdf=pdf))
    cmd, _ = _build_command(
        settings=settings,
        registry_path=registry_path,
        lock_path=lock_path,
        state_db=state_db,
        proposal_yml=yml,
        mocker=mocker,
        ocr_pdf=pdf,
    )
    return cmd, yml


class TestCommandPromoteCollisions:
    """Filename-collision regressions for promote's naming stage."""

    def test_pdf_collision_increments_timestamp_and_preserves_existing_file(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """A pre-existing filed PDF at the canonical name must not be overwritten;
        promote must advance to the next free (seconds+1) canonical slot."""
        existing_canonical = settings.paths.business_root / "cez-as" / "20210311000000-cez-as-7102105594.invoice.pdf"
        existing_canonical.parent.mkdir(parents=True, exist_ok=True)
        existing_bytes = b"%PDF-1.4\nfirst-arrival\n"
        existing_canonical.write_bytes(existing_bytes)

        triage_dir = settings.paths.business_root / "_triage"
        cmd, _yml = stage_and_build(
            triage_dir=triage_dir,
            basename="20210311083422-cez-as-7102105594.invoice",
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            mocker=mocker,
        )

        result = cmd.execute()

        assert result.success is True

        filed_pdf = Path(result.metadata["pdf_path"])
        # The new file MUST NOT have overwritten the pre-existing one.
        assert filed_pdf != existing_canonical
        assert existing_canonical.exists()
        assert existing_canonical.read_bytes() == existing_bytes
        # The new filename should differ in the seconds portion of the timestamp.
        assert filed_pdf.name.startswith("20210311000001-cez-as-7102105594.invoice")

        pdf_files = list((settings.paths.business_root / "cez-as").glob("*.pdf"))
        assert len(pdf_files) == 2

    def test_zettel_collision_increments_timestamp_and_preserves_existing_zettel(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """A pre-existing zettel under <vault>/<doc-subdir>/<issuer-slug>/ must
        block the same canonical filename from being reused during promote."""
        existing_zettel = (
            settings.paths.vault_root
            / "Zettelkasten"
            / "documents"
            / "cez-as"
            / "20210311000000-cez-as-7102105594.invoice.md"
        )
        existing_zettel.parent.mkdir(parents=True, exist_ok=True)
        existing_text = "# pre-existing zettel\n\nthis content must survive\n"
        existing_zettel.write_text(existing_text, encoding="utf-8")

        triage_dir = settings.paths.business_root / "_triage"
        cmd, _yml = stage_and_build(
            triage_dir=triage_dir,
            basename="20210311083422-cez-as-7102105594.invoice",
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            mocker=mocker,
        )

        result = cmd.execute()

        assert result.success is True

        # The pre-existing zettel must still hold its original content.
        assert existing_zettel.exists()
        assert existing_zettel.read_text(encoding="utf-8") == existing_text

        zettel_path = Path(result.metadata["zettel_path"])
        assert zettel_path != existing_zettel
        assert zettel_path.name.startswith("20210311000001-cez-as-7102105594.invoice")

    def test_two_promotes_colliding_on_same_canonical_name_both_survive(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """PRD Must-have #3: two colliding triage proposals must both survive,
        and the second zettel's id: frontmatter must carry the incremented
        zk_timestamp, not the pre-collision one."""
        triage_dir = settings.paths.business_root / "_triage"

        def _promote(suffix: str, pdf_bytes: bytes) -> tuple[Path, Path]:
            cmd, _ = stage_and_build(
                triage_dir=triage_dir,
                basename=f"20210311083422-cez-as-7102105594.invoice-{suffix}",
                settings=settings,
                registry_path=registry_path,
                lock_path=lock_path,
                state_db=state_db,
                mocker=mocker,
                pdf_bytes=pdf_bytes,
            )
            result = cmd.execute()
            assert result.success is True
            return Path(result.metadata["pdf_path"]), Path(result.metadata["zettel_path"])

        first_pdf, _ = _promote("a", b"%PDF-1.4\nfirst arrival\n")
        first_bytes = first_pdf.read_bytes()
        assert first_pdf.name.startswith("20210311000000-cez-as-7102105594.invoice")

        second_pdf, second_zettel = _promote("b", b"%PDF-1.4\nsecond arrival\n")
        assert second_pdf != first_pdf
        assert second_pdf.name.startswith("20210311000001-cez-as-7102105594.invoice")
        assert first_pdf.exists()
        assert first_pdf.read_bytes() == first_bytes

        issuer_dir = settings.paths.business_root / "cez-as"
        assert len(list(issuer_dir.glob("*.pdf"))) == 2
        vault_issuer_dir = settings.paths.vault_root / "Zettelkasten" / "documents" / "cez-as"
        assert len(list(vault_issuer_dir.glob("*.md"))) == 2

        text = second_zettel.read_text(encoding="utf-8")
        _, frontmatter_text, _ = text.split("---", 2)
        frontmatter = yaml.safe_load(frontmatter_text)
        assert frontmatter["id"] == 20210311000001

    def test_collision_exhaustion_returns_failure_without_writing(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """When resolve_collision exhausts its real 60-attempt cap, promote must
        fail loud instead of writing a PDF/zettel or deleting the proposal."""
        issuer_dir = settings.paths.business_root / "cez-as"
        issuer_dir.mkdir(parents=True, exist_ok=True)
        base_zk_timestamp = "20210311000000"
        for offset in range(60):
            candidate_ts = _advance_seconds(base_zk_timestamp, offset)
            candidate_filename = build_canonical_filename(
                zk_timestamp=candidate_ts,
                issuer_slug="cez-as",
                title_or_number="7102105594",
                doc_type="invoice",
            )
            (issuer_dir / candidate_filename).write_bytes(b"colliding pdf")

        triage_dir = settings.paths.business_root / "_triage"
        cmd, yml = stage_and_build(
            triage_dir=triage_dir,
            basename="20210311083422-cez-as-7102105594.invoice",
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            mocker=mocker,
        )

        result = cmd.execute()

        assert result.success is False
        error = result.error or ""
        assert error != ""
        assert _COLLISION_EXHAUSTED in error

        # _finalize must never have run: proposal is untouched.
        assert yml.exists()
        # No new PDF was written beyond the 60 pre-seeded incumbents.
        assert len(list(issuer_dir.glob("*.pdf"))) == 60
        # No zettel was written for this issuer at all.
        vault_issuer_dir = settings.paths.vault_root / "Zettelkasten" / "documents" / "cez-as"
        assert not vault_issuer_dir.exists() or list(vault_issuer_dir.glob("*.md")) == []

    def test_filesystem_error_during_collision_resolution_returns_failure_without_traceback(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """A mocked OSError from resolve_collision must be caught and returned
        as CommandResult(success=False, ...) instead of a raw traceback, with
        an error message distinguishable from the exhaustion failure."""
        triage_dir = settings.paths.business_root / "_triage"
        cmd, yml = stage_and_build(
            triage_dir=triage_dir,
            basename="20210311083422-cez-as-7102105594.invoice",
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            mocker=mocker,
        )

        os_error_text = "[Errno 30] Read-only file system"
        mocker.patch(
            "bim.commands.doc.promote.promote.resolve_collision",
            side_effect=OSError(os_error_text),
        )

        result = cmd.execute()

        assert result.success is False
        error = result.error or ""
        assert error != ""
        # The OSError's own text must be surfaced to the caller.
        assert os_error_text in error
        # Must be distinguishable from the exhaustion-path failure message.
        assert _COLLISION_EXHAUSTED not in error

        # _finalize must never have run: proposal is untouched, nothing written.
        assert yml.exists()
        assert not (settings.paths.business_root / "cez-as").exists()
        vault_issuer_dir = settings.paths.vault_root / "Zettelkasten" / "documents" / "cez-as"
        assert not vault_issuer_dir.exists()

    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory mode bits")
    def test_real_permission_error_during_collision_resolution_returns_failure(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """A real PermissionError from resolve_collision's own mkdir (not a
        mock) must be caught and returned as CommandResult(success=False, ...)
        with no traceback escaping."""
        triage_dir = settings.paths.business_root / "_triage"
        cmd, yml = stage_and_build(
            triage_dir=triage_dir,
            basename="20210311083422-cez-as-7102105594.invoice",
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            mocker=mocker,
        )

        business_root = settings.paths.business_root
        original_mode = business_root.stat().st_mode
        os.chmod(business_root, 0o500)
        try:
            result = cmd.execute()
        finally:
            os.chmod(business_root, original_mode)

        assert result.success is False
        error = result.error or ""
        assert error != ""
        assert _COLLISION_EXHAUSTED not in error
        # Pin WHICH failure this is: without it the test passes on any earlier
        # failure the chmod happens to cause, never reaching the resolver.
        assert "filesystem error while resolving the filename collision" in error

        # _finalize must never have run: proposal is untouched.
        assert yml.exists()
