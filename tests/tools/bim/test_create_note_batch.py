from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bim.commands.create_note.batch import create_single, parse_batch_file


class TestParseBatchYaml:
    def test_defaults_and_items(self, tmp_path):
        spec = tmp_path / "batch.yaml"
        spec.write_text(
            "type: contact\ntags: people,work\nitems:\n"
            "  - title: Alice\n    answers:\n      email: a@b.com\n"
            "  - title: Bob\n    type: project\n    tags: dev\n"
        )
        default_type, default_tags, items = parse_batch_file(spec)
        assert default_type == "contact"
        assert default_tags == "people,work"
        assert len(items) == 2
        assert items[0]["title"] == "Alice"
        assert items[0]["answers"] == {"email": "a@b.com"}
        assert items[1]["type"] == "project"
        assert items[1]["tags"] == "dev"

    def test_per_item_override(self, tmp_path):
        spec = tmp_path / "batch.yml"
        spec.write_text("type: note\nitems:\n  - title: X\n    type: project\n")
        _, _, items = parse_batch_file(spec)
        assert items[0]["type"] == "project"

    def test_missing_items_key(self, tmp_path):
        spec = tmp_path / "batch.yaml"
        spec.write_text("type: note\n")
        with pytest.raises(ValueError, match="items"):
            parse_batch_file(spec)

    def test_item_missing_title(self, tmp_path):
        spec = tmp_path / "batch.yaml"
        spec.write_text("items:\n  - type: note\n")
        with pytest.raises(ValueError, match="title"):
            parse_batch_file(spec)


class TestParseBatchCsv:
    def test_basic_csv(self, tmp_path):
        spec = tmp_path / "batch.csv"
        spec.write_text("title,type,tags,email\nAlice,contact,\"people,work\",a@b.com\n")
        default_type, default_tags, items = parse_batch_file(spec)
        assert default_type is None
        assert default_tags is None
        assert len(items) == 1
        assert items[0]["title"] == "Alice"
        assert items[0]["type"] == "contact"
        assert items[0]["answers"] == {"email": "a@b.com"}

    def test_extra_columns_become_answers(self, tmp_path):
        spec = tmp_path / "batch.csv"
        spec.write_text("title,type,foo,bar\nX,note,1,2\n")
        _, _, items = parse_batch_file(spec)
        assert items[0]["answers"] == {"foo": "1", "bar": "2"}

    def test_missing_title_column(self, tmp_path):
        spec = tmp_path / "batch.csv"
        spec.write_text("type,tags\nnote,x\n")
        with pytest.raises(ValueError, match="title"):
            parse_batch_file(spec)

    def test_unsupported_extension(self, tmp_path):
        spec = tmp_path / "batch.json"
        spec.write_text("{}")
        with pytest.raises(ValueError, match="Unsupported"):
            parse_batch_file(spec)


class TestCreateSingle:
    def _make_template(self, questions=None):
        tpl = MagicMock()
        tpl.questions.return_value = questions or []
        return tpl

    @patch("bim.commands.create_note.batch.get_hook_runner")
    @patch("bim.commands.create_note.batch.get_repo")
    @patch("bim.commands.create_note.batch.CreateZettelUseCase")
    def test_success(self, mock_uc_cls, mock_repo, mock_hook, tmp_path):
        expected_path = tmp_path / "123.md"
        mock_uc_cls.return_value.execute.return_value = expected_path
        tpl = self._make_template()

        result = create_single(tmp_path, tpl, "My Title", tags="a,b")

        assert result == expected_path
        mock_uc_cls.return_value.execute.assert_called_once()
        call_args = mock_uc_cls.return_value.execute.call_args
        assert call_args[0][1]["title"] == "My Title"
        assert call_args[0][1]["tags"] == "a,b"

    def test_missing_required_answer(self, tmp_path):
        from buvis.pybase.zettel.domain.templates import Question

        q = Question(key="email", prompt="Email?", required=True)
        tpl = self._make_template(questions=[q])

        result = create_single(tmp_path, tpl, "Title")

        assert result is None

    @patch("bim.commands.create_note.batch.get_hook_runner")
    @patch("bim.commands.create_note.batch.get_repo")
    @patch("bim.commands.create_note.batch.CreateZettelUseCase")
    def test_file_exists_error(self, mock_uc_cls, mock_repo, mock_hook, tmp_path):
        mock_uc_cls.return_value.execute.side_effect = FileExistsError("exists")
        tpl = self._make_template()

        result = create_single(tmp_path, tpl, "Title")

        assert result is None


class TestCommandBatch:
    @patch("bim.commands.create_note.batch.get_hook_runner")
    @patch("bim.commands.create_note.batch.get_repo")
    @patch("bim.commands.create_note.batch.CreateZettelUseCase")
    @patch("bim.commands.create_note.create_note.get_templates")
    def test_full_batch_flow(self, mock_templates, mock_uc_cls, mock_repo, mock_hook, tmp_path):
        tpl = MagicMock()
        tpl.questions.return_value = []
        mock_templates.return_value = {"contact": tpl}
        mock_uc_cls.return_value.execute.return_value = tmp_path / "out.md"

        spec = tmp_path / "batch.yaml"
        spec.write_text("type: contact\nitems:\n  - title: Alice\n  - title: Bob\n")

        from bim.commands.create_note.create_note import CommandCreateNote

        cmd = CommandCreateNote(path_zettelkasten=tmp_path, batch_file=spec)
        cmd.execute()

        assert mock_uc_cls.return_value.execute.call_count == 2

    @patch("bim.commands.create_note.batch.get_hook_runner")
    @patch("bim.commands.create_note.batch.get_repo")
    @patch("bim.commands.create_note.batch.CreateZettelUseCase")
    @patch("bim.commands.create_note.create_note.get_templates")
    def test_cli_type_override(self, mock_templates, mock_uc_cls, mock_repo, mock_hook, tmp_path):
        tpl = MagicMock()
        tpl.questions.return_value = []
        mock_templates.return_value = {"project": tpl}
        mock_uc_cls.return_value.execute.return_value = tmp_path / "out.md"

        spec = tmp_path / "batch.csv"
        spec.write_text("title\nAlice\n")

        from bim.commands.create_note.create_note import CommandCreateNote

        cmd = CommandCreateNote(path_zettelkasten=tmp_path, zettel_type="project", batch_file=spec)
        cmd.execute()

        mock_uc_cls.return_value.execute.assert_called_once()

    @patch("bim.commands.create_note.create_note.get_templates")
    def test_no_type_skips_item(self, mock_templates, tmp_path):
        mock_templates.return_value = {}

        spec = tmp_path / "batch.yaml"
        spec.write_text("items:\n  - title: Alice\n")

        from bim.commands.create_note.create_note import CommandCreateNote

        cmd = CommandCreateNote(path_zettelkasten=tmp_path, batch_file=spec)
        cmd.execute()
