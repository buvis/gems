from __future__ import annotations

import datetime
from pathlib import Path

from buvis.pybase.adapters import console


class ZseqFilename:
    @staticmethod
    def is_zettelseq(filename: Path, *, is_reporting_fails: bool = False) -> bool:
        try:
            datetime.datetime.strptime(
                filename.stem[:14],
                "%Y%m%d%H%M%S",
            ).astimezone().date()
        except ValueError:
            if is_reporting_fails:
                console.failure(f"{filename.absolute()} is not in zettelseq scheme")

            return False

        return True

    @staticmethod
    def get_seq_from_zettelseq(zettelseq: str) -> int:
        """
        Extract the sequence number from a filename.

        The function identifies the sequence number by starting after the first 14 characters
        (representing the timestamp) and gradually increasing the length of the substring until
        it can no longer be converted to an integer. The sequence number is returned as an integer.

        :param filename: The filename containing the sequence number.
        :type filename: str
        :return: The extracted sequence number as an integer.
        :rtype: int
        :raises ValueError: If no valid sequence number is found in the filename.

        Example:
            >>> extract_sequence_number('20240114122450-0081-Enhanced-NR')
            81
        """
        start_index = 14
        length = 1
        last_valid_sequence = None

        for length in range(1, len(zettelseq) - start_index + 1):
            sequence_string = zettelseq[start_index : start_index + length]

            if sequence_string == "-":
                start_index = start_index + 1
                continue

            try:
                sequence_number = int(sequence_string)
                last_valid_sequence = sequence_number
            except ValueError:
                break

        if last_valid_sequence is not None:
            return last_valid_sequence

        msg = f"No valid sequence number found in the filename ({zettelseq})."
        raise ValueError(msg)
