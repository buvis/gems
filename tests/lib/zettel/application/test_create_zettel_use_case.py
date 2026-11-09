from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.application.use_cases.create_zettel_use_case import (
    CreateZettelUseCase,
)
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter
from buvis.pybase.zettel.domain.templates import ZettelTemplate
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


@pytest.fixture
def mock_zettel_writer():
    return MagicMock(spec=ZettelWriter)


@pytest.fixture
def create_zettel_use_case(tmp_path, mock_zettel_writer):
    return CreateZettelUseCase(tmp_path, mock_zettel_writer)


def _setup_factory_mock(mocker):
    mock_factory = mocker.patch("buvis.pybase.zettel.application.use_cases.create_zettel_use_case.ZettelFactory")
    return mock_factory


def _make_template_and_zettel(mock_factory, zettel_id="20231026120000", with_hooks=False):
    mock_template = MagicMock(spec=ZettelTemplate)
    mock_data = MagicMock(spec=ZettelData)
    mock_data.metadata = {"id": zettel_id}
    mock_data.file_path = None
    mock_data.sections = []
    mock_data.reference = {}
    mock_template.build_data.return_value = mock_data

    mock_zettel = MagicMock(spec=Zettel)
    mock_zettel.id = zettel_id
    mock_zettel.get_data.return_value = mock_data
    mock_factory.create.return_value = mock_zettel

    if with_hooks:
        mock_hook = MagicMock()
        mock_template.hooks.return_value = [mock_hook]
    else:
        mock_template.hooks.return_value = []

    return mock_template, mock_data, mock_zettel


class TestCreateZettelUseCase:
    def test_calls_writer_save(self, mocker, create_zettel_use_case, mock_zettel_writer):
        mock_factory = _setup_factory_mock(mocker)
        mock_template, mock_data, mock_zettel = _make_template_and_zettel(mock_factory)
        mock_data.metadata["title"] = "Test Zettel"

        create_zettel_use_case.execute(mock_template, {"title": "Test Zettel"})

        mock_zettel_writer.save.assert_called_once_with(mock_zettel)
        assert mock_data.file_path == str(create_zettel_use_case.zettelkasten_path / "20231026120000.md")

    def test_raises_file_exists(self, mocker, create_zettel_use_case, tmp_path):
        mocker.patch("time.sleep", autospec=True)
        mock_factory = _setup_factory_mock(mocker)
        mock_template, mock_data, mock_zettel = _make_template_and_zettel(mock_factory)

        (tmp_path / "20231026120000.md").touch()

        with pytest.raises(FileExistsError):
            create_zettel_use_case.execute(mock_template, {"title": "Test Zettel"})

    def test_runs_hooks(self, mocker, create_zettel_use_case, mock_zettel_writer):
        hook_runner = MagicMock()
        create_zettel_use_case = CreateZettelUseCase(
            create_zettel_use_case.zettelkasten_path,
            mock_zettel_writer,
            hook_runner=hook_runner,
        )
        mock_factory = _setup_factory_mock(mocker)
        mock_template, mock_data, mock_zettel = _make_template_and_zettel(mock_factory, with_hooks=True)

        create_zettel_use_case.execute(mock_template, {"title": "Test Zettel"})

        hook_runner.assert_called_once_with(
            mock_template.hooks.return_value,
            mock_data,
            create_zettel_use_case.zettelkasten_path,
        )

    def test_returns_path(self, mocker, create_zettel_use_case, mock_zettel_writer):
        mock_factory = _setup_factory_mock(mocker)
        mock_template, mock_data, mock_zettel = _make_template_and_zettel(mock_factory)

        path = create_zettel_use_case.execute(mock_template, {"title": "Test Zettel"})

        expected_path = create_zettel_use_case.zettelkasten_path / "20231026120000.md"
        assert path == expected_path


class FreshTemplate:
    name = "Example"

    def __init__(
        self,
        ids: tuple[int, ...] = (20231026120000,),
        sections: list[tuple[str, str]] | None = None,
        body_section: str | None = None,
    ) -> None:
        self.ids = ids
        self.sections = sections if sections is not None else [("# Example Title", "existing")]
        self.body_section = body_section
        self.built: list[ZettelData] = []
        self.received: list[dict[str, Any]] = []

    def questions(self) -> list:
        return []

    def hooks(self) -> list:
        return []

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        zettel_id = self.ids[min(len(self.built), len(self.ids) - 1)]
        data = ZettelData(
            metadata={
                "id": zettel_id,
                "date": datetime(2023, 10, 26, 12, tzinfo=timezone.utc),
                "type": "note",
                "title": answers.get("title", "Example Title"),
            },
            sections=list(self.sections),
        )
        self.built.append(data)
        self.received.append(answers)
        return data


def _run_with_body(
    use_case: CreateZettelUseCase,
    writer: MagicMock,
    template: FreshTemplate,
    method: str,
    body: str | None,
    answers: dict[str, Any] | None = None,
) -> tuple[Path, ZettelData]:
    answers = answers if answers is not None else {"title": "Example Title"}
    result = getattr(use_case, method)(template, answers, body=body)
    if method == "prepare":
        return result[0], result[1].get_data()
    return result, writer.save.call_args.args[0].get_data()


class TestPrepareBody:
    @pytest.mark.parametrize("method", ["prepare", "execute"])
    def test_existing_trailing_blank_lines_leave_one_body_separator(
        self, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, method: str
    ) -> None:
        sections = [("# Example Title", "existing\n\n"), ("## Other", "  preserved\n")]

        _, data = _run_with_body(
            create_zettel_use_case, mock_zettel_writer, FreshTemplate(sections=sections), method, "added"
        )

        assert data.sections == [("# Example Title", "existing\n\nadded"), sections[1]]

    @pytest.mark.parametrize("method", ["prepare", "execute"])
    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ("\r\n \t\r\n    indented\r\n\tinside  \r\n\r\n", "    indented\n\tinside"),
            ("\n\n  second  \n\nnext  \t", "  second  \n\nnext"),
            ("The train arrived before dawn.", "The train arrived before dawn."),
        ],
    )
    def test_normalizes_body_preserving_content_indentation(
        self,
        create_zettel_use_case: CreateZettelUseCase,
        mock_zettel_writer: MagicMock,
        method: str,
        body: str | None,
        expected: str,
    ) -> None:
        template = FreshTemplate()

        _, data = _run_with_body(create_zettel_use_case, mock_zettel_writer, template, method, body)

        assert data.sections == [("# Example Title", f"existing\n\n{expected}")]

    @pytest.mark.parametrize("method", ["prepare", "execute"])
    @pytest.mark.parametrize("body", [None, "", " \t\r\n\n"])
    def test_absent_or_blank_body_preserves_all_template_content(
        self, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, method: str, body: str | None
    ) -> None:
        sections = [("# Example Title", "  original  \n"), ("## Other", "second\n\n")]

        _, data = _run_with_body(
            create_zettel_use_case, mock_zettel_writer, FreshTemplate(sections=sections), method, body
        )

        assert data.sections == sections

    @pytest.mark.parametrize("method", ["prepare", "execute"])
    @pytest.mark.parametrize("heading", ["## Body", "## Commentary"])
    def test_matches_exact_first_heading_and_preserves_other_sections(
        self, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, method: str, heading: str
    ) -> None:
        sections = [
            ("# Example Title", "intro"),
            (f"{heading} Extra", "prefix"),
            (f"#{heading}", "level"),
            (heading, "target"),
            (heading, "duplicate"),
        ]

        _, data = _run_with_body(
            create_zettel_use_case,
            mock_zettel_writer,
            FreshTemplate(sections=sections, body_section=heading),
            method,
            "supplied",
        )

        assert data.sections == [*sections[:3], (heading, "target\n\nsupplied"), sections[4]]

    @pytest.mark.parametrize("heading", [None, "## Missing", "## Body Extra"])
    def test_missing_exact_heading_falls_back_to_first_section(
        self, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, heading: str | None
    ) -> None:
        sections = [("# Example Title", "first"), ("## Body", "second")]

        _, data = _run_with_body(
            create_zettel_use_case,
            mock_zettel_writer,
            FreshTemplate(sections=sections, body_section=heading),
            "prepare",
            "added",
        )

        assert data.sections == [("# Example Title", "first\n\nadded"), sections[1]]

    @pytest.mark.parametrize("method", ["prepare", "execute"])
    def test_empty_target_does_not_add_leading_separator(
        self, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, method: str
    ) -> None:
        sections = [("# Example Title", "intro"), ("## Notes", "")]

        _, data = _run_with_body(
            create_zettel_use_case,
            mock_zettel_writer,
            FreshTemplate(sections=sections, body_section="## Notes"),
            method,
            "  supplied",
        )

        assert data.sections == [sections[0], ("## Notes", "  supplied")]

    @pytest.mark.parametrize("title", ["Example Title", "Another Title", "Field Journal"])
    @pytest.mark.parametrize("method", ["prepare", "execute"])
    def test_initializes_missing_sections_with_answer_title(
        self, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, title: str, method: str
    ) -> None:
        answers = {"title": title}

        _, data = _run_with_body(
            create_zettel_use_case, mock_zettel_writer, FreshTemplate(sections=[]), method, "  supplied", answers
        )

        assert data.sections == [(f"# {title}", "  supplied")]

    def test_prepare_returns_path_and_fixed_zettel_without_side_effects(
        self, tmp_path: Path, mock_zettel_writer: MagicMock
    ) -> None:
        root = tmp_path / "missing" / "vault"
        hooks = MagicMock()
        use_case = CreateZettelUseCase(root, mock_zettel_writer, hook_runner=hooks)
        template = FreshTemplate(ids=(20231026120001,))
        answers = {"title": "Another Title"}

        path, zettel = use_case.prepare(template, answers, body="added")

        assert path == root / "20231026120001.md"
        assert isinstance(zettel, Zettel)
        assert zettel.id == 20231026120001
        assert zettel.get_data().file_path == str(path)
        assert template.received == [answers]
        assert not root.exists()
        mock_zettel_writer.save.assert_not_called()
        hooks.assert_not_called()


class TestPreparationWithoutTitleMetadata:
    @pytest.mark.parametrize("method", ["prepare", "execute"])
    def test_body_survives_preparation_when_template_omits_title_metadata(
        self, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, method: str
    ) -> None:
        class UntitledTemplate(FreshTemplate):
            def build_data(self, answers: dict[str, Any]) -> ZettelData:
                data = super().build_data(answers)
                del data.metadata["title"]
                return data

        path, data = _run_with_body(
            create_zettel_use_case,
            mock_zettel_writer,
            UntitledTemplate(sections=[]),
            method,
            "  supplied",
            {"title": "Answer Title"},
        )

        assert path == create_zettel_use_case.zettelkasten_path / "20231026120000.md"
        assert data.file_path == str(path)
        assert len(data.sections) == 1
        assert data.sections[0][1] == "  supplied"


class TestReservationInspectionFailures:
    @pytest.mark.parametrize("error", [OSError("inspection failed"), KeyboardInterrupt()])
    @pytest.mark.parametrize("replace_placeholder", [False, True])
    def test_inspection_failure_closes_reservation_and_skips_save_and_hooks(
        self, tmp_path: Path, monkeypatch: Any, error: BaseException, replace_placeholder: bool
    ) -> None:
        original_open, original_fstat = os.open, os.fstat
        descriptors = []
        path = tmp_path / "20231026120000.md"
        replacement = tmp_path / "replacement.md"
        replacement.write_text("replacement note")
        writer, hooks = MagicMock(spec=ZettelWriter), MagicMock()
        use_case = CreateZettelUseCase(tmp_path, writer, hook_runner=hooks)

        def record_open(target: Any, flags: int, mode: int = 511, **kwargs: Any) -> int:
            descriptor = original_open(target, flags, mode, **kwargs)
            if Path(target) == path:
                descriptors.append(descriptor)
            return descriptor

        def fail_inspection(descriptor: int) -> os.stat_result:
            if descriptor in descriptors:
                if replace_placeholder and replacement.exists():
                    replacement.replace(path)
                raise error
            return original_fstat(descriptor)

        try:
            with monkeypatch.context() as boundary:
                boundary.setattr(os, "open", record_open)
                boundary.setattr(os, "fstat", fail_inspection)
                with pytest.raises(type(error)) as caught:
                    use_case.execute(FreshTemplate(), {})
            assert caught.value is error
            assert path.read_bytes() == (b"replacement note" if replace_placeholder else b"")
            writer.save.assert_not_called()
            hooks.assert_not_called()
            assert len(descriptors) == 1
            if replace_placeholder:
                assert path.read_text() == "replacement note"
            with pytest.raises(OSError):
                original_fstat(descriptors[0])
        finally:
            for descriptor in descriptors:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


class TestCollisionBudget:
    @pytest.mark.parametrize("method", ["prepare", "execute"])
    def test_waits_for_next_second_on_collision(
        self,
        mocker: Any,
        create_zettel_use_case: CreateZettelUseCase,
        mock_zettel_writer: MagicMock,
        tmp_path: Path,
        method: str,
    ) -> None:
        sleep = mocker.patch("time.sleep", autospec=True)
        occupied = tmp_path / "20231026120000.md"
        occupied.write_text("existing note")
        template = FreshTemplate(ids=(20231026120000, 20231026120001))

        path, data = _run_with_body(create_zettel_use_case, mock_zettel_writer, template, method, "added")

        assert path == tmp_path / "20231026120001.md"
        assert data.file_path == str(path)
        assert data.sections == [("# Example Title", "existing\n\nadded")]
        assert len(template.built) == 2
        assert template.built[0] is not template.built[1]
        assert occupied.read_text() == "existing note"
        sleep.assert_called_once_with(1)

    @pytest.mark.parametrize("method", ["prepare", "execute"])
    def test_gives_up_after_five_attempts(
        self,
        mocker: Any,
        create_zettel_use_case: CreateZettelUseCase,
        mock_zettel_writer: MagicMock,
        tmp_path: Path,
        method: str,
    ) -> None:
        sleep = mocker.patch("time.sleep", autospec=True)
        occupied = tmp_path / "20231026120000.md"
        occupied.write_text("existing note")
        template = FreshTemplate()

        with pytest.raises(FileExistsError, match=f"^Zettel already exists: {occupied}$"):
            getattr(create_zettel_use_case, method)(template, {"title": "Example Title"})

        assert len(template.built) == 5
        assert sleep.call_args_list == [((1,), {})] * 4
        assert occupied.read_text() == "existing note"
        mock_zettel_writer.save.assert_not_called()

    @pytest.mark.parametrize("method", ["prepare", "execute"])
    def test_attempt_budget_resets_for_each_invocation(
        self,
        mocker: Any,
        create_zettel_use_case: CreateZettelUseCase,
        mock_zettel_writer: MagicMock,
        tmp_path: Path,
        method: str,
    ) -> None:
        mocker.patch("time.sleep", autospec=True)
        (tmp_path / "20231026120000.md").touch()
        with pytest.raises(FileExistsError):
            getattr(create_zettel_use_case, method)(FreshTemplate(), {})
        template = FreshTemplate(ids=(20231026120001,))

        path, data = _run_with_body(create_zettel_use_case, mock_zettel_writer, template, method, "again")

        assert path == tmp_path / "20231026120001.md"
        assert data.sections[0][1] == "existing\n\nagain"
        assert len(template.built) == 1

    def test_second_writer_loses_reservation_and_retries(
        self, mocker: Any, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, tmp_path: Path
    ) -> None:
        sleep = mocker.patch("time.sleep", autospec=True)
        original_open = os.open
        occupied = tmp_path / "20231026120000.md"
        template = FreshTemplate(ids=(20231026120000, 20231026120001))

        def race(path: Any, flags: int, mode: int = 511, **kwargs: Any) -> int:
            if Path(path) == occupied:
                occupied.write_text("concurrent note")
            return original_open(path, flags, mode, **kwargs)

        mocker.patch("os.open", side_effect=race)

        path = create_zettel_use_case.execute(template, {"title": "Example Title"})

        assert path == tmp_path / "20231026120001.md"
        assert occupied.read_text() == "concurrent note"
        assert len(template.built) == 2
        mock_zettel_writer.save.assert_called_once()
        sleep.assert_called_once_with(1)

    def test_existence_and_reservation_collisions_share_five_attempts(
        self, mocker: Any, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, tmp_path: Path
    ) -> None:
        sleep = mocker.patch("time.sleep", autospec=True)
        original_open = os.open
        ids = tuple(20231026120000 + index for index in range(6))
        for zettel_id in (ids[0], ids[2]):
            (tmp_path / f"{zettel_id}.md").write_text("existing")

        def lose_reservation(path: Any, flags: int, mode: int = 511, **kwargs: Any) -> int:
            Path(path).write_text("concurrent")
            return original_open(path, flags, mode, **kwargs)

        mocker.patch("os.open", side_effect=lose_reservation)
        template = FreshTemplate(ids=ids)

        with pytest.raises(FileExistsError, match=f"Zettel already exists: {tmp_path / f'{ids[4]}.md'}"):
            create_zettel_use_case.execute(template, {})

        assert len(template.built) == 5
        assert sleep.call_args_list == [((1,), {})] * 4
        assert not (tmp_path / f"{ids[5]}.md").exists()
        assert (tmp_path / f"{ids[4]}.md").read_text() == "concurrent"
        mock_zettel_writer.save.assert_not_called()


class TestReservationAndHooks:
    @pytest.mark.parametrize("zettel_id", [20231026120000, 20231026120001])
    def test_exclusively_reserves_file_then_runs_hooks_then_saves(
        self, tmp_path: Path, mocker: Any, zettel_id: int
    ) -> None:
        original_open = os.open
        reservation = []
        events = []
        path = tmp_path / f"{zettel_id}.md"
        writer = MagicMock(spec=ZettelWriter)

        def record_open(target: Any, flags: int, mode: int = 511, **kwargs: Any) -> int:
            descriptor = original_open(target, flags, mode, **kwargs)
            reservation.append((Path(target), flags, mode, descriptor))
            return descriptor

        def save(zettel: Zettel) -> None:
            assert path.read_bytes() == b""
            with pytest.raises(OSError):
                os.fstat(reservation[0][3])
            assert zettel.get_data().file_path == str(path)
            events.append("save")
            path.write_text("saved note")

        def hooks(hook_list: list[Any], data: ZettelData, root: Path) -> None:
            assert hook_list == []
            assert data.file_path == str(path)
            assert root == tmp_path
            assert path.read_bytes() == b""
            events.append("hooks")

        mocker.patch("os.open", side_effect=record_open)
        writer.save.side_effect = save
        use_case = CreateZettelUseCase(tmp_path, writer, hook_runner=hooks)

        assert use_case.execute(FreshTemplate(ids=(zettel_id,)), {}) == path

        assert reservation[0][:3] == (path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
        assert len(reservation) == 1
        assert writer.save.call_count == 1
        assert events == ["hooks", "save"]

    @pytest.mark.parametrize("error", [PermissionError("denied"), OSError("disk failure")])
    def test_noncollision_reservation_error_is_surfaced_without_retry(
        self,
        mocker: Any,
        create_zettel_use_case: CreateZettelUseCase,
        mock_zettel_writer: MagicMock,
        tmp_path: Path,
        error: BaseException,
    ) -> None:
        sleep = mocker.patch("time.sleep", autospec=True)
        mocker.patch("os.open", side_effect=error)
        template = FreshTemplate()

        with pytest.raises(type(error), match=str(error)) as caught:
            create_zettel_use_case.execute(template, {})

        assert caught.value is error
        assert len(template.built) == 1
        assert list(tmp_path.iterdir()) == []
        mock_zettel_writer.save.assert_not_called()
        sleep.assert_not_called()

    def test_interrupted_descriptor_close_cleans_owned_reservation(
        self, mocker: Any, create_zettel_use_case: CreateZettelUseCase, mock_zettel_writer: MagicMock, tmp_path: Path
    ) -> None:
        original_open = os.open
        original_close = os.close
        descriptors = []
        interrupted = False

        def record_open(path: Any, flags: int, mode: int = 511, **kwargs: Any) -> int:
            descriptor = original_open(path, flags, mode, **kwargs)
            descriptors.append(descriptor)
            return descriptor

        def interrupt_once(descriptor: int) -> None:
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt
            original_close(descriptor)

        mocker.patch("os.open", side_effect=record_open)
        mocker.patch("os.close", side_effect=interrupt_once)

        with pytest.raises(KeyboardInterrupt):
            create_zettel_use_case.execute(FreshTemplate(), {})

        assert len(descriptors) == 1
        original_close(descriptors[0])
        assert list(tmp_path.iterdir()) == []
        mock_zettel_writer.save.assert_not_called()

    @pytest.mark.parametrize("error", [OSError("save failed"), KeyboardInterrupt()])
    def test_save_failure_removes_owned_placeholder_after_hooks_ran(
        self, tmp_path: Path, mock_zettel_writer: MagicMock, error: BaseException
    ) -> None:
        hook_runner = MagicMock(return_value=[])
        mock_zettel_writer.save.side_effect = error
        use_case = CreateZettelUseCase(tmp_path, mock_zettel_writer, hook_runner=hook_runner)

        with pytest.raises(type(error)) as caught:
            use_case.execute(FreshTemplate(), {})

        assert caught.value is error
        assert list(tmp_path.iterdir()) == []
        mock_zettel_writer.save.assert_called_once()
        hook_runner.assert_called_once()

    @pytest.mark.parametrize("error", [OSError("save failed"), KeyboardInterrupt()])
    def test_cleanup_preserves_file_that_replaced_owned_placeholder(
        self, tmp_path: Path, mock_zettel_writer: MagicMock, error: BaseException
    ) -> None:
        path = tmp_path / "20231026120000.md"
        replacement = tmp_path / "replacement.md"
        replacement.write_text("replacement note")
        replacement_identity = (replacement.stat().st_dev, replacement.stat().st_ino)

        def replace_and_fail(zettel: Zettel) -> None:
            replacement.replace(path)
            raise error

        mock_zettel_writer.save.side_effect = replace_and_fail
        use_case = CreateZettelUseCase(tmp_path, mock_zettel_writer)

        with pytest.raises(type(error)):
            use_case.execute(FreshTemplate(), {})

        assert path.read_text() == "replacement note"
        assert (path.stat().st_dev, path.stat().st_ino) == replacement_identity

    @pytest.mark.parametrize("error", [ValueError("bad hook"), OSError("hook disk failure")])
    def test_hook_error_fails_before_save_and_removes_placeholder(
        self, tmp_path: Path, mock_zettel_writer: MagicMock, error: BaseException
    ) -> None:
        hook_runner = MagicMock(side_effect=error)
        use_case = CreateZettelUseCase(tmp_path, mock_zettel_writer, hook_runner=hook_runner)

        with pytest.raises(RuntimeError) as caught:
            use_case.execute(FreshTemplate(), {})

        assert str(caught.value) == f"hook failed: {error}"
        assert caught.value.__cause__ is error
        assert list(tmp_path.iterdir()) == []
        mock_zettel_writer.save.assert_not_called()
        hook_runner.assert_called_once()

    def test_hook_keyboard_interrupt_is_preserved_and_nothing_is_saved(
        self, tmp_path: Path, mock_zettel_writer: MagicMock
    ) -> None:
        interrupt = KeyboardInterrupt()
        hook_runner = MagicMock(side_effect=interrupt)
        use_case = CreateZettelUseCase(tmp_path, mock_zettel_writer, hook_runner=hook_runner)

        with pytest.raises(KeyboardInterrupt) as caught:
            use_case.execute(FreshTemplate(), {})

        assert caught.value is interrupt
        assert list(tmp_path.iterdir()) == []
        mock_zettel_writer.save.assert_not_called()


class SlugTemplate(FreshTemplate):
    folder = "contact"
    file_stem = "slug"


class TestTemplatePlacement:
    def test_slug_template_writes_into_folder(self, tmp_path: Path, mock_zettel_writer: MagicMock) -> None:
        use_case = CreateZettelUseCase(tmp_path, mock_zettel_writer)

        path = use_case.execute(SlugTemplate(), {"title": "Ada  Lovelace"})

        assert path == tmp_path / "contact" / "ada-lovelace.md"
        assert (tmp_path / "contact").is_dir()
        saved = mock_zettel_writer.save.call_args.args[0]
        assert saved.get_data().file_path == str(path)
        assert use_case.prepare(SlugTemplate(), {"title": "Alan Turing"})[0] == tmp_path / "contact" / "alan-turing.md"

    def test_slug_collision_fails_without_retry(
        self, mocker: Any, tmp_path: Path, mock_zettel_writer: MagicMock
    ) -> None:
        sleep = mocker.patch("time.sleep", autospec=True)
        occupied = tmp_path / "contact" / "ada-lovelace.md"
        occupied.parent.mkdir()
        occupied.write_text("existing")
        template = SlugTemplate()

        with pytest.raises(FileExistsError, match=f"^Zettel already exists: {occupied}$"):
            CreateZettelUseCase(tmp_path, mock_zettel_writer).execute(template, {"title": "Ada Lovelace"})

        assert len(template.built) == 1
        sleep.assert_not_called()
        assert occupied.read_text() == "existing"
        mock_zettel_writer.save.assert_not_called()

    def test_empty_slug_fails_before_any_write(self, tmp_path: Path, mock_zettel_writer: MagicMock) -> None:
        with pytest.raises(
            ValueError, match="title '日本語' gives an empty slug; use a title with Latin letters or digits"
        ):
            CreateZettelUseCase(tmp_path, mock_zettel_writer).execute(SlugTemplate(), {"title": "日本語"})

        assert list(tmp_path.iterdir()) == []
        mock_zettel_writer.save.assert_not_called()

    def test_hook_metadata_is_in_the_saved_file(self, tmp_path: Path) -> None:
        writer = MagicMock(spec=ZettelWriter)
        seen: dict[str, Any] = {}
        writer.save.side_effect = lambda zettel: seen.update(zettel.get_data().metadata)

        def hooks(hook_list: list[Any], data: ZettelData, root: Path) -> list[str]:
            data.metadata["resources"] = "[project resources](file:///tmp/p)"
            return ["root missing"]

        use_case = CreateZettelUseCase(tmp_path, writer, hook_runner=hooks)

        use_case.execute(FreshTemplate(), {})

        assert seen["resources"] == "[project resources](file:///tmp/p)"
        assert use_case.warnings == ["root missing"]
