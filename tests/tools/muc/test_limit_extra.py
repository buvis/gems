from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestCommandLimitExtra:
    @patch("muc.commands.limit.limit.ffmpeg")
    def test_execute_mixed_successes_and_errors(self, mock_ffmpeg: MagicMock, tmp_path) -> None:
        from muc.commands.limit.limit import CommandLimit

        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        good_flac = source / "good.flac"
        good_flac.write_bytes(b"fake")
        bad_flac = source / "bad.flac"
        bad_flac.write_bytes(b"fake")

        mock_ffmpeg.Error = type("Error", (Exception,), {"stderr": b"ffmpeg error"})

        def probe_side_effect(path, **kwargs):
            if "bad" in path:
                raise mock_ffmpeg.Error("fail")
            return {
                "streams": [
                    {
                        "codec_type": "audio",
                        "bit_rate": "2000000",
                        "sample_rate": "96000",
                        "bits_per_sample": "24",
                    }
                ]
            }

        mock_ffmpeg.probe.side_effect = probe_side_effect

        cmd = CommandLimit(source_dir=source, output_dir=output, bitrate=1411000, bit_depth=16, sampling_rate=44100)
        result = cmd.execute()

        assert not result.success
        assert result.error is not None

    @patch("muc.commands.limit.limit.ffmpeg")
    def test_execute_nested_directory_structure(self, mock_ffmpeg: MagicMock, tmp_path) -> None:
        from muc.commands.limit.limit import CommandLimit

        source = tmp_path / "source"
        nested = source / "artist" / "album"
        nested.mkdir(parents=True)
        output = tmp_path / "output"
        output.mkdir()

        flac = nested / "track.flac"
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
    def test_execute_skips_files_in_output_dir(self, mock_ffmpeg: MagicMock, tmp_path) -> None:
        from muc.commands.limit.limit import CommandLimit

        source = tmp_path / "source"
        source.mkdir()
        output = source / "output"
        output.mkdir()

        flac_in_output = output / "already.flac"
        flac_in_output.write_bytes(b"fake")

        cmd = CommandLimit(source_dir=source, output_dir=output, bitrate=1411000, bit_depth=16, sampling_rate=44100)
        result = cmd.execute()

        assert result.success
        assert result.output == "No files to transcode"
        mock_ffmpeg.probe.assert_not_called()

    @patch("muc.commands.limit.limit.ffmpeg")
    def test_execute_errors_only(self, mock_ffmpeg: MagicMock, tmp_path) -> None:
        from muc.commands.limit.limit import CommandLimit

        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        flac = source / "test.flac"
        flac.write_bytes(b"fake")

        mock_ffmpeg.Error = type("Error", (Exception,), {"stderr": b"codec error"})
        mock_ffmpeg.probe.side_effect = mock_ffmpeg.Error("fail")

        cmd = CommandLimit(source_dir=source, output_dir=output, bitrate=1411000, bit_depth=16, sampling_rate=44100)
        result = cmd.execute()

        assert not result.success
        assert result.output is None
        assert result.error is not None
