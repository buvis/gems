"""Meta-budget share of spend — trailing-window meta vs total from the ledger.

The operator holds a meta-budget policy (Claude-on-Claude work targets
``<= 30%`` of monthly spend; released-plugin repo work counts as *product*, not
meta). This module computes that share as a pure, UI-free number the brief
surfaces render.

Ledger
------
``track_cost.py`` (the Claude ``Stop`` hook) appends one JSON object per line to
``~/.local/share/agents/metrics/costs.jsonl``. Each row is::

    {"host", "ts" (ISO-8601 Z), "sid", "model", "tier", "cumulative": true,
     ["nested": true], "in", "cache_write", "cache_read", "out",
     "cost_usd" (number)}

Rows carry **no** project/cwd field, and are **cumulative per sid** — the running
total as of that ``Stop`` event. So a session's spend is the MAX (last, by ``ts``)
``cost_usd`` for that ``sid`` in the window, never the sum of its rows (summing
double-counts). Both roots (ledger dir, transcripts dir) are constructor
arguments, never hardcoded, so tests point them at fixtures.

Attribution join (rows lack cwd)
--------------------------------
Because a ledger row has no cwd, a session is classified by finding its
transcript. Claude stores transcripts at
``~/.claude/projects/<encoded-cwd>/<sid>.jsonl`` where the directory name is the
session's cwd with every ``/`` rewritten to ``-`` (e.g. ``-Users-bob--claude``
decodes to ``/Users/bob/.claude``). The collector globs
``<projects_dir>/*/<sid>.jsonl``, decodes the parent directory back to a cwd, and
classifies:

* cwd under ``~/.claude`` (the meta root) OR under any configured meta-repo
  root (``meta_repos``, default none)       -> **META**
* any other cwd                             -> **PRODUCT**
* no transcript found for the sid           -> **PRODUCT**

Unknown sessions count as product so the meta share is never silently inflated.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict

__all__ = ["META_CEILING_PCT", "MetaShare", "collect"]

# Ceiling for the meta-share policy, in percent. INCLUSIVE — a share at or above
# this is "over" (red): 30.0% => over. Config-overridable via ``collect``.
META_CEILING_PCT = 30.0


class MetaShare(BaseModel):
    """The trailing-window meta-budget share of spend.

    A frozen, ``extra="forbid"`` typed model matching the ``contracts.py`` style.
    The ``n/a`` state (absent or empty ledger for the window) is carried by
    ``available=False`` with zeroed figures, never by an exception.

    Attributes:
        available: ``True`` when the window held at least one priced session;
            ``False`` is the "n/a" state the surfaces render as ``meta n/a``.
        meta_pct: Meta spend as a percentage of total (``0.0`` when unavailable).
        total_usd: Total spend across all sessions in the window.
        meta_usd: Spend attributed to meta (``~/.claude``) sessions.
        window_days: The trailing window in days.
        ceiling_pct: The policy ceiling in percent (inclusive).
        over_ceiling: ``True`` when ``meta_pct >= ceiling_pct`` (red state).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    available: bool
    meta_pct: float = 0.0
    total_usd: float = 0.0
    meta_usd: float = 0.0
    window_days: int = 30
    ceiling_pct: float = META_CEILING_PCT
    over_ceiling: bool = False


def _default_ledger_dir() -> Path:
    """Return the live ledger directory (``track_cost.py``'s ``METRICS_DIR``)."""
    return Path.home() / ".local" / "share" / "agents" / "metrics"


def _default_projects_dir() -> Path:
    """Return the live Claude transcripts root (``~/.claude/projects``)."""
    return Path.home() / ".claude" / "projects"


def _meta_root() -> Path:
    """Return the resolved meta root — sessions under it count as meta."""
    return (Path.home() / ".claude").resolve()


def _parse_ts(raw: object) -> datetime | None:
    """Parse an ISO-8601 ``ts`` (``...Z`` or offset) into an aware datetime.

    Returns ``None`` for anything unparseable, so a torn row is skipped rather
    than aborting the read.
    """
    if not isinstance(raw, str) or not raw:
        return None
    text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _read_rows(ledger: Path, cutoff: datetime) -> list[dict[str, object]]:
    """Read ledger rows at or after ``cutoff``, tolerating torn/blank lines.

    A missing or unreadable ledger yields ``[]`` (the n/a path), never an
    exception. A row missing a ``sid``, a numeric ``cost_usd``, or a parseable
    ``ts`` in-window is skipped.
    """
    if not ledger.is_file():
        return []
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: list[dict[str, object]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        sid = row.get("sid")
        cost = row.get("cost_usd")
        ts = _parse_ts(row.get("ts"))
        if not isinstance(sid, str) or not sid:
            continue
        if not isinstance(cost, (int, float)) or isinstance(cost, bool):
            continue
        if ts is None or ts < cutoff:
            continue
        rows.append(row)
    return rows


def _spend_by_sid(rows: list[dict[str, object]]) -> dict[str, float]:
    """Fold rows to per-sid spend = the MAX (last, by ``ts``) cumulative cost.

    Rows are cumulative per sid, so the session's spend is the latest running
    total, keyed by ``ts`` then falling back to last-seen order. Summing would
    double-count.
    """
    latest_ts: dict[str, datetime] = {}
    spend: dict[str, float] = {}
    for row in rows:
        sid = str(row["sid"])
        cost = float(row["cost_usd"])  # type: ignore[arg-type]
        ts = _parse_ts(row.get("ts"))
        if ts is None:
            continue
        if sid not in latest_ts or ts >= latest_ts[sid]:
            latest_ts[sid] = ts
            spend[sid] = cost
    return spend


def _encode_cwd(cwd: Path) -> str:
    """Encode a cwd the way Claude names its projects dir.

    Claude rewrites BOTH ``/`` and ``.`` in the absolute path to ``-`` — verified
    against the live ``~/.claude/projects`` tree: ``/Users/bob/.claude`` is stored
    as ``-Users-bob--claude`` (the ``/.`` collapses to ``--``) and
    ``/Users/bob/git/src/github.com/...`` as ``-Users-bob-git-src-github-com-...``
    (the ``.`` in ``github.com`` also becomes ``-``). A ``/``-only transform
    silently never matches ``.claude`` and attributes 0% meta on real data.

    The transform is not invertible (a literal ``-`` or ``.`` in a path is
    indistinguishable from a separator), which is exactly why attribution compares
    in this ENCODED space rather than decoding back to a cwd — the ambiguity is
    then symmetric on both sides and a real path containing ``-`` (e.g.
    ``gems-metabudget``) classifies correctly.
    """
    return str(cwd.resolve()).replace("/", "-").replace(".", "-")


def _is_meta_sid(sid: str, projects_dir: Path, meta_prefixes: set[str]) -> bool:
    """Classify one sid as meta by matching its transcript dir in encoded space.

    Globs ``<projects_dir>/*/<sid>.jsonl``; for each match, tests whether the
    parent directory name (Claude's ``/``->``-`` encoding of the session cwd)
    equals ANY prefix in ``meta_prefixes`` or begins with ``prefix + "-"`` — i.e.
    the cwd is at or under the meta root or any configured meta-repo root. A sid
    with no findable transcript is **not** meta (counts as product), so meta is
    never inflated.
    """
    try:
        matches = list(projects_dir.glob(f"*/{sid}.jsonl"))
    except OSError:
        return False
    for match in matches:
        name = match.parent.name
        if any(name == prefix or name.startswith(prefix + "-") for prefix in meta_prefixes):
            return True
    return False


def collect(  # noqa: PLR0913  # all keyword-only config-override seams for a pure collector
    window_days: int = 30,
    *,
    ledger_dir: Path | None = None,
    projects_dir: Path | None = None,
    meta_root: Path | None = None,
    meta_repos: list[Path] | None = None,
    ceiling_pct: float = META_CEILING_PCT,
) -> MetaShare:
    """Compute the trailing-window meta-budget share from the cost ledger.

    Pure and UI-free. Reads ``costs.jsonl`` under ``ledger_dir`` (default: the
    live ``~/.local/share/agents/metrics``), keeps rows whose ``ts`` is within
    the trailing ``window_days``, folds each sid to its MAX cumulative
    ``cost_usd``, then classifies each sid meta/product via the sid->transcript
    join under ``projects_dir`` (default: ``~/.claude/projects``). An absent or
    empty ledger (for the window) yields the ``n/a`` state — never an exception.

    Args:
        window_days: Trailing window in days.
        ledger_dir: Directory holding ``costs.jsonl``; defaults to the live root.
        projects_dir: Claude transcripts root for the attribution join; defaults
            to ``~/.claude/projects``.
        meta_root: The directory whose sessions count as meta; a decoded session
            cwd at or under it is meta. Defaults to ``~/.claude``. Overridable so
            tests classify against a fixture root, never the real home.
        meta_repos: Additional repo roots whose sessions also count as meta
            (Claude-tooling repos). A session whose cwd is at or under any of
            these — in addition to ``meta_root`` — is meta. Defaults to none, so
            the behaviour is exactly ``meta_root`` alone.
        ceiling_pct: Policy ceiling in percent (inclusive); at or above is over.

    Returns:
        The computed :class:`MetaShare`; ``available=False`` when no priced
        session falls in the window.
    """
    ledger = (ledger_dir or _default_ledger_dir()) / "costs.jsonl"
    projects = projects_dir or _default_projects_dir()
    meta_prefixes = {_encode_cwd(meta_root or _meta_root())}
    meta_prefixes |= {_encode_cwd(repo) for repo in (meta_repos or [])}

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = _read_rows(ledger, cutoff)
    spend = _spend_by_sid(rows)

    total = sum(spend.values())
    if not spend or total <= 0:
        return MetaShare(available=False, window_days=window_days, ceiling_pct=ceiling_pct)

    meta = sum(cost for sid, cost in spend.items() if _is_meta_sid(sid, projects, meta_prefixes))
    meta_pct = meta / total * 100.0
    return MetaShare(
        available=True,
        meta_pct=meta_pct,
        total_usd=total,
        meta_usd=meta,
        window_days=window_days,
        ceiling_pct=ceiling_pct,
        over_ceiling=meta_pct >= ceiling_pct,
    )
