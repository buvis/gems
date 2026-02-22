from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestCommandLimit:
    @patch("muc.commands.limit.limit.ffmpeg")
    def test_execute_no_files(self, mock_ffmpeg: MagicMock, tmp_path) -> None:
        from muc.commands.limit.limit import CommandLimit

        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        cmd = CommandLimit(source_dir=source, output_dir=output, bitrate=1411000, bit_depth=16, sampling_rate=44100)
        result = cmd.execute()

        assert result.success
        assert result.output == "No files to transcode"

    @patch("muc.commands.limit.limit.ffmpeg")
    def test_execute_transcode(self, mock_ffmpeg: MagicMock, tmp_path) -> None:
        from muc.commands.limit.limit import CommandLimit

        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        flac = source / "test.flac"
        flac.write_bytes(b"fake")

        mock_ffmpeg.probe.return_value = {
            "streams": [
                {
                    "codec_type": "audio",
                    "bit_rate": "2000000",
                    "sample_rate": "96000",
                    "bits_per_sample": "24",
                }
            ]
        }

        cmd = CommandLimit(source_dir=source, output_dir=output, bitrate=1411000, bit_depth=16, sampling_rate=44100)
        result = cmd.execute()

        assert result.success
        assert "Transcoded" in result.output
        mock_ffmpeg.run.assert_called_once()

    @patch("muc.commands.limit.limit.ffmpeg")
    @patch("muc.commands.limit.limit.shutil")
    def test_execute_copy_within_limits(self, mock_shutil: MagicMock, mock_ffmpeg: MagicMock, tmp_path) -> None:
        from muc.commands.limit.limit import CommandLimit

        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        flac = source / "test.flac"
        flac.write_bytes(b"fake")

        mock_ffmpeg.probe.return_value = {
            "streams": [
                {
                    "codec_type": "audio",
                    "bit_rate": "700000",
                    "sample_rate": "44100",
                    "bits_per_sample": "16",
                }
            ]
        }

        cmd = CommandLimit(source_dir=source, output_dir=output, bitrate=1411000, bit_depth=16, sampling_rate=44100)
        result = cmd.execute()

        assert result.success
        assert "Copied" in result.output
        mock_shutil.copy2.assert_called_once()

    @patch("muc.commands.limit.limit.ffmpeg")
    def test_execute_no_audio_stream(self, mock_ffmpeg: MagicMock, tmp_path) -> None:
        from muc.commands.limit.limit import CommandLimit

        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        flac = source / "test.flac"
        flac.write_bytes(b"fake")

        mock_ffmpeg.probe.return_value = {"streams": [{"codec_type": "video"}]}

        cmd = CommandLimit(source_dir=source, output_dir=output, bitrate=1411000, bit_depth=16, sampling_rate=44100)
        result = cmd.execute()

        assert result.success
        assert len(result.warnings) == 1
        assert "no audio stream" in result.warnings[0]

    @patch("muc.commands.limit.limit.ffmpeg")
    def test_execute_ffmpeg_error(self, mock_ffmpeg: MagicMock, tmp_path) -> None:
        from muc.commands.limit.limit import CommandLimit

        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        flac = source / "test.flac"
        flac.write_bytes(b"fake")

        mock_ffmpeg.probe.side_effect = mock_ffmpeg.Error("fail")
        mock_ffmpeg.Error = type("Error", (Exception,), {"stderr": b"ffmpeg error"})
        mock_ffmpeg.probe.side_effect = mock_ffmpeg.Error("fail")

        cmd = CommandLimit(source_dir=source, output_dir=output, bitrate=1411000, bit_depth=16, sampling_rate=44100)
        result = cmd.execute()

        assert not result.success
