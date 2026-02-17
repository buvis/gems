from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult

from zseq.shared import ZseqFilename


class CommandGetLast:
    def __init__(self: CommandGetLast, path_dir: str, *, is_reporting_misnamed: bool) -> None:
        self.path_dir = Path(path_dir)

        if not self.path_dir.is_dir():
            msg = f"{self.path_dir} is not a directory"
            raise ValueError(msg)

        self.is_reporting_misnamed = is_reporting_misnamed

    def execute(self: CommandGetLast) -> CommandResult:
        seqs = [
            ZseqFilename.get_seq_from_zettelseq(f.stem)
            for f in self.path_dir.iterdir()
            if f.is_file()
            and ZseqFilename.is_zettelseq(
                f,
                is_reporting_fails=self.is_reporting_misnamed,
            )
        ]

        if seqs:
            return CommandResult(
                success=True,
                output=f"Last sequence number in {self.path_dir.absolute()} is {max(seqs)}",
            )
        return CommandResult(
            success=False,
            error=f"No files following zettelseq naming scheme found in {self.path_dir.absolute()}",
        )
