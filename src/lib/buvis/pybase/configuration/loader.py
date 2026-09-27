from __future__ import annotations

import logging
import os
import re
import stat
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigurationError, MissingEnvVarError

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")
_ESCAPE_PLACEHOLDER = "\x00ESCAPED_DOLLAR\x00"


def _substitute(content: str) -> tuple[str, list[str]]:
    """Substitute env vars in content string.

    Replaces ${VAR} patterns with environment values. Supports
    ${VAR:-default} syntax for fallback values.

    Args:
        content: String with potential ${VAR} patterns.

    Returns:
        Tuple of (substituted_content, missing_vars) where missing_vars
        contains names of required env vars that weren't set.

    Note:
        Single-pass only - values from env are NOT re-processed.
    """
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        var_name, default = match.group(1), match.group(2)
        value = os.environ.get(var_name)
        if value is not None:
            return value
        if default is not None:
            return default
        missing.append(var_name)
        return match.group(0)  # Keep original for error message

    result = _ENV_PATTERN.sub(replace, content)
    return result, missing


def _split_directive(key: str) -> tuple[str, str]:
    """Split a merge key into its base name and directive suffix.

    Args:
        key: A config key, optionally suffixed with ``+`` (append) or ``-``
            (remove).

    Returns:
        Tuple of (base_key, directive) where directive is ``"+"``, ``"-"``, or
        ``""`` for a plain key. A bare ``"+"`` / ``"-"`` key (empty base) is
        treated as plain — there is no list to target.
    """
    if len(key) > 1 and key[-1] in ("+", "-"):
        return key[:-1], key[-1]
    return key, ""


def _apply_list_directives(
    target: dict[str, Any],
    base: str,
    appends: list[Any],
    removes: list[Any],
) -> None:
    """Apply accumulated ``+``/``-`` directives for one base key in one layer.

    Appends run before removes so that a layer which both adds and removes the
    same token nets to removed (removal wins). Append is order-preserving with
    dedup against the existing list.

    Args:
        target: Merged dict being built (mutated in place).
        base: Base key the directives target.
        appends: Items collected from ``base+`` in this layer.
        removes: Items collected from ``base-`` in this layer.

    Raises:
        ConfigurationError: If ``base`` already exists and is not a list.
    """
    current = target.get(base)
    if current is None:
        current = []
    elif not isinstance(current, list):
        msg = f"Merge directive on key '{base}' requires a list value, but '{base}' is {type(current).__name__}."
        raise ConfigurationError(msg)

    merged = list(current)
    for item in appends:
        if item not in merged:
            merged.append(item)
    for item in removes:
        while item in merged:
            merged.remove(item)

    target[base] = merged


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Recursively merge source into target.

    Plain keys replace (dicts recurse, everything else overwrites), unchanged
    from the original behaviour. Keys suffixed ``+`` / ``-`` are data-level
    directives on list-valued keys: ``key+`` appends to ``key`` (order-preserving,
    dedup) and ``key-`` removes from it. Within one ``source`` layer a plain
    ``key`` resets the accumulated list first, then same-layer ``+``/``-`` apply
    (``+`` before ``-``). Directive keys are stripped from ``target``; consumers
    see only plain keys.

    Args:
        target: Dict to merge into (mutated in place).
        source: Dict to merge from.

    Raises:
        ConfigurationError: If a ``+``/``-`` directive targets a non-list key.
    """
    # First pass: plain keys (replace/recurse), unchanged semantics. A plain key
    # also resets any accumulated list, so it must land before same-layer
    # directives.
    pending: dict[str, tuple[list[Any], list[Any]]] = {}
    for k, v in source.items():
        base, directive = _split_directive(k)
        if directive == "":
            if k in target and isinstance(target[k], dict) and isinstance(v, dict):
                _deep_merge(target[k], v)
            else:
                target[k] = v
            continue
        items = list(v) if isinstance(v, list) else [v]
        appends, removes = pending.setdefault(base, ([], []))
        if directive == "+":
            appends.extend(items)
        else:
            removes.extend(items)

    # Second pass: apply collected directives against the (now plain-key-updated)
    # target.
    for base, (appends, removes) in pending.items():
        _apply_list_directives(target, base, appends, removes)


class ConfigurationLoader:
    """Load YAML configs with env var substitution.

    Provides static methods for loading configuration files with support for
    environment variable interpolation using ${VAR} or ${VAR:-default} syntax.
    """

    @staticmethod
    def _get_search_paths(config_dir: str | None = None) -> list[Path]:
        """Build ordered list of config directories to search.

        Args:
            config_dir: Explicit config directory override (bypasses env lookup).

        Returns:
            list[Path]: Search paths from highest to lowest priority:
                1. config_dir / BUVIS_CONFIG_DIR (if set and non-empty)
                2. ~/.config/buvis (default)
                3. Current working directory
        """
        if config_dir is not None:
            paths = [Path(config_dir).expanduser(), Path.home() / ".config" / "buvis"]
        else:
            paths = get_config_dirs()
        paths.append(Path.cwd())
        return paths

    @staticmethod
    def _is_world_writable(path: Path) -> bool:
        """Check if file has world-writable permissions.

        Args:
            path: Path to check permissions for.

        Returns:
            True if file is world-writable, False otherwise or on error.
            Always False on Windows where Unix permission bits are meaningless.
        """
        if os.name == "nt":
            return False
        try:
            mode = path.stat().st_mode
            return bool(mode & stat.S_IWOTH)
        except OSError:
            return False

    @staticmethod
    def _is_safe_path(candidate: Path, allowed_bases: list[Path]) -> bool:
        """Reject symlinks pointing outside expected directories.

        Args:
            candidate: Path to validate (may be symlink).
            allowed_bases: Directories the resolved path must be under.

        Returns:
            True if resolved path is under one of allowed_bases, False otherwise.
        """
        try:
            resolved = candidate.resolve()
            for base in allowed_bases:
                try:
                    resolved.relative_to(base.resolve())
                    return True
                except ValueError:
                    continue
            return False
        except (OSError, RuntimeError):
            return False

    @staticmethod
    def _get_candidate_files(paths: list[Path], tool_name: str | None) -> list[Path]:
        """Generate candidate config file paths from search locations.

        Args:
            paths: Base directories to search for config files.
            tool_name: Optional tool name for tool-specific configs.

        Returns:
            Ordered list of candidate paths per location (lowest to highest
            priority within a location): config.yaml, config.local.yaml,
            buvis.yaml, buvis.local.yaml, buvis-{tool}.yaml,
            buvis-{tool}.local.yaml. Each ``*.local.yaml`` machine-local twin sits
            immediately after (higher priority than) its shared file. See
            :meth:`find_config_files_ranked` for a clean low-to-high ordering.
        """
        candidates: list[Path] = []
        stems = ["config", "buvis", *([f"buvis-{tool_name}"] if tool_name else [])]
        for base in paths:
            for stem in stems:
                candidates.append(base / f"{stem}.yaml")
                candidates.append(base / f"{stem}.local.yaml")
        return candidates

    @staticmethod
    def _escape_literals(text: str) -> str:
        """Replace escaped $${VAR} sequences with placeholder.

        Args:
            text: Raw config text that may contain $${VAR} escape sequences.

        Returns:
            Text with $${...} replaced by placeholder for later restoration.
        """
        return text.replace("$${", f"{_ESCAPE_PLACEHOLDER}{{")

    @staticmethod
    def _restore_literals(text: str) -> str:
        """Restore placeholder back to literal ${...} syntax.

        Args:
            text: Text containing placeholders from _escape_literals.

        Returns:
            Text with placeholders converted to literal ${...}.
        """
        return text.replace(f"{_ESCAPE_PLACEHOLDER}{{", "${")

    @staticmethod
    def load_yaml(file_path: Path) -> dict[str, Any]:
        """Load YAML file with environment variable substitution.

        Supports ${VAR} for required vars (raises on missing) and
        ${VAR:-default} for optional vars with defaults. Use $${VAR}
        to escape and get literal ${VAR} in output.

        Args:
            file_path: Path to YAML file to load.

        Returns:
            Parsed YAML content as dict. Empty files return {}.

        Raises:
            MissingEnvVarError: If required environment variables are missing.
            FileNotFoundError: If file doesn't exist.
            yaml.YAMLError: If YAML syntax is invalid. Check problem_mark for line/col.
        """
        if ConfigurationLoader._is_world_writable(file_path):
            logger.warning("Config file %s is world-writable", file_path)

        content = file_path.read_text(encoding="utf-8")

        # Escape $${VAR} -> placeholder (preserves literal syntax)
        content = ConfigurationLoader._escape_literals(content)

        # Substitute ${VAR} and ${VAR:-default} with env values
        content, missing = _substitute(content)

        # Restore placeholders -> ${VAR} (literal output)
        content = ConfigurationLoader._restore_literals(content)

        if missing:
            raise MissingEnvVarError(sorted(missing))

        return yaml.safe_load(content) or {}

    @staticmethod
    def find_config_files(tool_name: str | None = None, *, config_dir: str | None = None) -> list[Path]:
        """Find configuration files that apply to a tool.

        Args:
            tool_name: Optional tool identifier used to narrow the search scope.
            config_dir: Explicit config directory override (bypasses env lookup).

        Returns:
            list[Path]: Existing config files as candidates. NOTE: this list is
            NOT a single monotonic priority ranking. Directories are ordered
            highest-priority-first ($BUVIS_CONFIG_DIR, then ~/.config/buvis, then
            cwd), but WITHIN each directory the stems are ordered lowest-first
            (config.yaml < buvis.yaml < buvis-{tool}.yaml, per
            _get_candidate_files). The result is therefore mixed-order. Callers
            that need a clean precedence order (e.g. to feed merge_configs, where
            later wins) MUST sort explicitly by (directory rank, stem rank) — a
            blind reversed() of this list inverts precedence both across
            directories and across stems within a directory.
        """
        paths = ConfigurationLoader._get_search_paths(config_dir)
        candidates = ConfigurationLoader._get_candidate_files(paths, tool_name)
        result: list[Path] = []

        for candidate in candidates:
            try:
                if not candidate.is_file():
                    continue
                if not ConfigurationLoader._is_safe_path(candidate, paths):
                    logger.warning("Skipping unsafe config path: %s", candidate)
                    continue
                result.append(candidate.resolve())
            except PermissionError:
                logger.debug("Permission denied: %s", candidate)
                continue

        return result

    @staticmethod
    def find_config_files_ranked(
        tool_name: str | None = None,
        *,
        config_dir: str | None = None,
        config_path: str | Path | None = None,
    ) -> list[Path]:
        """Find existing config files in LOW-to-HIGH priority order.

        Unlike :meth:`find_config_files` (whose raw output is mixed-order — see
        its docstring), this returns the discovered files sorted so that later
        entries have higher precedence. Feed the result directly to
        :meth:`merge_configs` (where later wins) without reversing.

        Precedence, lowest first: cwd < ~/.config/buvis < $BUVIS_CONFIG_DIR
        across directories, and config.yaml < config.local.yaml < buvis.yaml <
        buvis.local.yaml < buvis-{tool}.yaml < buvis-{tool}.local.yaml within each
        directory (each machine-local ``*.local.yaml`` twin outranks its shared
        file). An explicit ``config_path`` (from ``--config FILE``) is EXCLUSIVE:
        when given and readable it is the sole layer, and discovery is skipped
        entirely — matching :meth:`ConfigResolver._load_yaml`, so a tool's plan
        and its settings resolve from the same single file (no discovered layer
        leaks under the explicit selection).

        Args:
            tool_name: Optional tool identifier for the ``buvis-{tool}.yaml`` slot.
            config_dir: Explicit config directory override (bypasses env lookup).
            config_path: Explicit config FILE (from ``--config``). When given and
                readable it is EXCLUSIVE — the returned list is exactly that one
                file and discovery is skipped, matching the settings resolver so
                plan and settings share one source. A path that is not an
                existing file is skipped (Click's ``--config`` already validates
                existence; a direct caller passing a missing file falls back to
                the discovered layers rather than an error here).

        Returns:
            list[Path]: Existing, safe config files, lowest priority first.
        """
        # An explicit --config FILE is EXCLUSIVE: when readable it is the sole
        # layer and discovery is skipped, matching ConfigResolver._load_yaml so a
        # tool's plan and settings resolve from the same single file. A non-file
        # falls through to discovery (Click already validates --config existence).
        if config_path is not None:
            explicit = Path(config_path).expanduser()
            try:
                if explicit.is_file():
                    return [explicit.resolve()]
            except OSError:
                logger.debug("Cannot stat explicit config path: %s", explicit)

        paths = ConfigurationLoader._get_search_paths(config_dir)
        base_stems = ["config", "buvis", *([f"buvis-{tool_name}"] if tool_name else [])]
        # Interleave each stem with its .local twin so the twin gets a higher
        # stem_rank (wins) than its shared file.
        stems = [s for stem in base_stems for s in (stem, f"{stem}.local")]

        # dir_rank: 0 = highest-priority dir (paths[0]); stem_rank: 0 = lowest stem.
        # LOW-to-HIGH sort key: higher dir_rank (lower priority) first, then lower
        # stem_rank first -> ascending on (-dir_rank, stem_rank).
        ranked: list[tuple[int, int, Path]] = []
        for dir_rank, base in enumerate(paths):
            for stem_rank, stem in enumerate(stems):
                candidate = base / f"{stem}.yaml"
                try:
                    if not candidate.is_file():
                        continue
                    if not ConfigurationLoader._is_safe_path(candidate, paths):
                        logger.warning("Skipping unsafe config path: %s", candidate)
                        continue
                    ranked.append((-dir_rank, stem_rank, candidate.resolve()))
                except PermissionError:
                    logger.debug("Permission denied: %s", candidate)
                    continue

        ranked.sort(key=lambda item: (item[0], item[1]))
        return [path for _, _, path in ranked]

    @staticmethod
    def merge_configs(
        *configs: dict[str, Any],
        known_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        """Deep merge dicts. Later values override earlier.

        Nested dicts merge recursively; plain non-dict values replace. Keys
        suffixed ``+`` / ``-`` are list directives resolved by :func:`_deep_merge`
        (append / remove), stripped from the result.

        Args:
            configs: Dicts to merge, in order of increasing priority.
            known_keys: Optional set of expected base key names. When given, a
                directive (``key+`` / ``key-``) targeting a base key absent from
                this set logs a warning — a cheap typo guard (e.g. ``exclude+``
                missing the ``s``). Omitting it disables the check.

        Returns:
            New dict with all configs merged.

        Raises:
            ConfigurationError: If a directive targets a non-list key.
        """
        if known_keys is not None:
            for cfg in configs:
                for key in cfg:
                    base, directive = _split_directive(key)
                    if directive and base not in known_keys:
                        logger.warning(
                            "Config merge directive '%s' targets unknown key '%s' (known: %s) — possible typo",
                            key,
                            base,
                            sorted(known_keys),
                        )
        result: dict[str, Any] = {}
        for cfg in configs:
            _deep_merge(result, cfg)
        return result


def get_config_dirs() -> list[Path]:
    """Config dirs in priority order (highest first).

    1. $BUVIS_CONFIG_DIR (if set and non-empty)
    2. ~/.config/buvis (default)
    """
    dirs: list[Path] = []
    if env_dir := os.getenv("BUVIS_CONFIG_DIR"):
        dirs.append(Path(env_dir).expanduser())
    dirs.append(Path.home() / ".config" / "buvis")
    return dirs
