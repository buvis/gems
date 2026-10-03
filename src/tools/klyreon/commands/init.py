"""``klyreon init`` -- create the vault skeleton and the config that points at it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from buvis.pybase.filesystem import atomic_write_text
from buvis.pybase.result import CommandResult

from klyreon.vault.config import config_path
from klyreon.vault.git import is_git_vault

_VAULT_DIRS = (
    "sources",
    "wiki/notes",
    "wiki/mocs",
    "wiki/trails",
)

_VOICE_STARTER = """\
# Vault voice

Describe the voice every concept zettel is drafted in: tone, register,
preferred vocabulary, and whether the vault writes in second or third person.
Klyreon's ingest renders source material into this voice.
"""


@dataclass(frozen=True, slots=True)
class AssetOffer:
    """How ``init`` should handle the operator asset-install offer.

    ``operators`` names packs to install without prompting; otherwise, on a real
    TTY and not ``no_input``, ``confirm`` is asked per operator. ``no_input`` or
    a non-TTY skips the offer entirely.
    """

    operators: list[str] = field(default_factory=list)
    no_input: bool = False
    is_tty: bool = False
    confirm: Callable[[str], bool] | None = None


class CommandInit:
    """Create ``<root>/sources``, ``<root>/wiki/{notes,mocs,trails}``, a voice
    starter, and the klyreon config pointing at ``<root>``.

    Idempotent: existing directories and files are left untouched and reported.
    Rewriting a config that points elsewhere needs ``force``. Never runs
    ``git init``; warns when the root is not a git work tree.
    """

    def __init__(self, path: Path, *, force: bool = False, offer: AssetOffer | None = None) -> None:
        self.root = path.expanduser().resolve()
        self.force = force
        self.offer = offer or AssetOffer()

    def execute(self) -> CommandResult:
        info: list[str] = []
        warnings: list[str] = []

        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            info.append(f"created vault root {self.root}")
        elif not self.root.is_dir():
            return CommandResult(success=False, error=f"vault root is not a directory: {self.root}")

        for rel in _VAULT_DIRS:
            target = self.root / rel
            if target.is_dir():
                info.append(f"exists: {rel}/")
            else:
                target.mkdir(parents=True, exist_ok=True)
                info.append(f"created: {rel}/")

        voice = self.root / "voice.md"
        if voice.exists():
            info.append("exists: voice.md")
        else:
            atomic_write_text(voice, _VOICE_STARTER)
            info.append("created: voice.md")

        config_result = self._write_config(info, warnings)
        if config_result is not None:
            return config_result

        if not is_git_vault(self.root):
            warnings.append(
                f"{self.root} is not inside a git work tree. Autonomous commands (ingest, maintain) "
                "will be refused until you run 'git init' there yourself; klyreon never creates the repo.",
            )

        self._offer_assets(info, warnings)

        return CommandResult(
            success=True,
            output=f"vault ready at {self.root}",
            info=info,
            warnings=warnings,
        )

    def _offer_assets(self, info: list[str], warnings: list[str]) -> None:
        """Install the asset packs the user asked for, or offer them on a TTY.

        ``--operator`` installs those packs without prompting. Otherwise, on a
        real TTY and not ``--no-input``, prompt per operator. With ``--no-input``
        or no TTY, skip the offer and print how to run ``klyreon assets install``.
        No autonomous run ever reaches this: ``init`` is interactive setup.
        """
        from klyreon.assets import installer
        from klyreon.assets.registry import known_operator_names

        offer = self.offer
        chosen = list(offer.operators)
        if not chosen:
            if offer.no_input or not offer.is_tty or offer.confirm is None:
                info.append("skipped operator assets; run 'klyreon assets install --operator <name>' to add them")
                return
            for operator in known_operator_names():
                if offer.confirm(f"Install the {operator} asset pack?"):
                    chosen.append(operator)

        if not chosen:
            return

        report = installer.install(chosen)
        info += [f"asset written: {p}" for p in report.written]
        info += [f"asset current: {p}" for p in report.current]
        warnings += [f"backed up your edit of {orig} to {backup}" for orig, backup in report.displaced]

    def _write_config(self, info: list[str], warnings: list[str]) -> CommandResult | None:
        cfg = config_path()
        new_body = yaml.safe_dump({"root": str(self.root)}, default_flow_style=False, sort_keys=False)

        if cfg.is_file():
            existing = self._existing_root(cfg)
            if existing == str(self.root):
                info.append(f"exists: config {cfg} (already points here)")
                return None
            if not self.force:
                return CommandResult(
                    success=False,
                    error=(
                        f"config {cfg} already points at {existing!r}; refusing to overwrite. "
                        "Pass --force to repoint it."
                    ),
                )
            warnings.append(f"repointed config {cfg} from {existing!r} to {self.root} (--force)")

        cfg.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(cfg, new_body)
        info.append(f"wrote config {cfg}")
        return None

    @staticmethod
    def _existing_root(cfg: Path) -> str | None:
        try:
            loaded = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return None
        if isinstance(loaded, dict):
            value = loaded.get("root")
            return value if isinstance(value, str) else None
        return None
