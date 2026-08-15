from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from bim.commands.doc.shared.naming import build_canonical_filename
from bim.commands.doc.shared.settings_models import DocSettings
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.triage import write_proposal
from pytest_mock import MockerFixture

from .test_promote import _build_command, _build_proposal, _stage_triage_pair


def _advance_seconds(zk_timestamp: str, seconds: int) -> str:
    moment = datetime.strptime(zk_timestamp, "%Y%m%d%H%M%S")
    return (moment + timedelta(seconds=seconds)).strftime("%Y%m%d%H%M%S")


class TestCommandPromoteCollisions:
    """Filename-collision regressions for promote's naming stage.

    Relocated from ``test_promote.py`` (which had grown past the repo's
    800-line test-file limit); shares that module's fixtures and helpers
    via import rather than duplicating them.
    """

    def test_pdf_collision_increments_timestamp_and_preserves_existing_file(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """A pre-existing filed PDF at the canonical name must not be overwritten;
        promote must advance to the next free (seconds+1) canonical slot.
        """
        existing_canonical = settings.paths.business_root / "cez-as" / "20210311000000-cez-as-7102105594.invoice.pdf"
        existing_canonical.parent.mkdir(parents=True, exist_ok=True)
        existing_bytes = b"%PDF-1.4\nfirst-arrival\n"
        existing_canonical.write_bytes(existing_bytes)

        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
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
        block the same canonical filename from being reused during promote.
        """
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
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
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
        """PRD Must-have #3: two triage proposals that resolve to the same
        canonical filename must both survive after promoting both.

        Unlike the pre-seeded-incumbent cases above, this drives the
        realistic promote -> promote sequence end to end (including the
        state_db/registry interaction of back-to-back promotes), and pins
        that the *second* zettel's ``id:`` frontmatter carries the
        INCREMENTED zk_timestamp rather than the pre-collision one
        (promote.py:223's ``zk_timestamp=resolved_zk_timestamp``). Reverting
        that line to ``zk_timestamp=zk_timestamp`` would file the second
        zettel under an incremented filename while still stamping it with
        the first zettel's id - a duplicate Zettelkasten ID.
        """
        triage_dir = settings.paths.business_root / "_triage"

        pdf1, yml1 = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice-a")
        pdf1.write_bytes(b"%PDF-1.4\nfirst arrival\n")
        sha1 = hashlib.sha256(pdf1.read_bytes()).hexdigest()
        write_proposal(yml1, _build_proposal(sha256=sha1, triage_pdf=pdf1))

        cmd1, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml1,
            mocker=mocker,
            ocr_pdf=pdf1,
        )
        result1 = cmd1.execute()
        assert result1.success is True

        first_pdf = Path(result1.metadata["pdf_path"])
        first_bytes = first_pdf.read_bytes()
        assert first_pdf.name.startswith("20210311000000-cez-as-7102105594.invoice")

        pdf2, yml2 = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice-b")
        pdf2.write_bytes(b"%PDF-1.4\nsecond arrival\n")
        sha2 = hashlib.sha256(pdf2.read_bytes()).hexdigest()
        write_proposal(yml2, _build_proposal(sha256=sha2, triage_pdf=pdf2))

        cmd2, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml2,
            mocker=mocker,
            ocr_pdf=pdf2,
        )
        result2 = cmd2.execute()
        assert result2.success is True

        second_pdf = Path(result2.metadata["pdf_path"])
        assert second_pdf != first_pdf
        assert second_pdf.name.startswith("20210311000001-cez-as-7102105594.invoice")

        # The first file's bytes are unchanged by the second promote.
        assert first_pdf.exists()
        assert first_pdf.read_bytes() == first_bytes

        issuer_dir = settings.paths.business_root / "cez-as"
        assert len(list(issuer_dir.glob("*.pdf"))) == 2

        vault_issuer_dir = settings.paths.vault_root / "Zettelkasten" / "documents" / "cez-as"
        assert len(list(vault_issuer_dir.glob("*.md"))) == 2

        # Guard: the second zettel's id: frontmatter must carry the
        # incremented zk_timestamp, not the pre-collision one.
        second_zettel_path = Path(result2.metadata["zettel_path"])
        text = second_zettel_path.read_text(encoding="utf-8")
        _, frontmatter_text, _ = text.split("---", 2)
        frontmatter = yaml.safe_load(frontmatter_text)
        assert frontmatter["id"] == 20210311000001
        assert frontmatter["id"] != 20210311000000

    def test_collision_exhaustion_returns_failure_without_writing(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """When resolve_collision exhausts its real 60-attempt cap, promote must
        fail loud instead of writing a PDF/zettel or deleting the proposal.

        Drives the actual cap by pre-creating a colliding PDF at every one of
        the 60 candidate canonical filenames instead of mocking
        ``resolve_collision`` (mocking it hid an ``AttributeError`` against
        pre-fix code rather than exercising the real exhaustion path).
        """
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
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
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

        result = cmd.execute()

        assert result.success is False
        error = result.error or ""
        assert error != ""
        assert "collision" in error.lower()

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
        """An OSError raised from inside resolve_collision (e.g. a read-only
        vault, a permissions failure, or ENOSPC) must be caught and returned
        as a CommandResult(success=False, error=...) instead of propagating
        out of CommandPromote.execute() as a raw traceback.

        The resulting error message must be non-empty, must surface the
        OSError's own text, and must be distinguishable from the unrelated
        60-attempt exhaustion failure message (which contains the substring
        "collision resolution failed").
        """
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
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
        assert "collision resolution failed" not in error

        # _finalize must never have run: proposal is untouched, nothing written.
        assert yml.exists()
        assert not (settings.paths.business_root / "cez-as").exists()
        vault_issuer_dir = settings.paths.vault_root / "Zettelkasten" / "documents" / "cez-as"
        assert not vault_issuer_dir.exists()
