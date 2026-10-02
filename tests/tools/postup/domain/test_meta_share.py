"""Unit tests for :mod:`postup.domain.meta_share`.

Every test points ``collect`` at fixture ``ledger_dir`` / ``projects_dir`` roots
under ``tmp_path`` via the config-override arguments — never the real
``~/.local`` ledger or ``~/.claude`` transcripts. Attribution is exercised for
meta (cwd under ``~/.claude``), product (any other cwd), and the
no-transcript-found case (which must count as product, never inflate meta).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from postup.domain.meta_share import META_CEILING_PCT, MetaShare, collect


def _iso(dt: datetime) -> str:
    """Format an aware datetime as the ledger's ``...Z`` ISO-8601 string."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(sid: str, cost: float, ts: datetime, *, model: str = "claude-sonnet") -> dict[str, object]:
    """Build one cumulative ledger row in the ``track_cost.py`` schema."""
    return {
        "host": "claude",
        "ts": _iso(ts),
        "sid": sid,
        "model": model,
        "tier": "sonnet",
        "cumulative": True,
        "in": 100,
        "cache_write": 0,
        "cache_read": 0,
        "out": 50,
        "cost_usd": cost,
    }


def _write_ledger(ledger_dir: Path, rows: list[dict[str, object]]) -> None:
    """Write ``costs.jsonl`` under ``ledger_dir`` from row dicts."""
    ledger_dir.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(r) for r in rows) + "\n"
    (ledger_dir / "costs.jsonl").write_text(body, encoding="utf-8")


def _encode_cwd_like_claude(cwd: Path) -> str:
    """Encode a cwd the way Claude REALLY names its projects dir.

    Deliberately reimplemented here (not imported from the module under test) so
    these fixtures are an independent oracle: Claude rewrites BOTH ``/`` and ``.``
    to ``-`` (verified against the live tree — ``/Users/bob/.claude`` ->
    ``-Users-bob--claude``, ``github.com`` -> ``github-com``). If the collector's
    own encoder regresses to ``/``-only, these tests must fail rather than agree
    with the bug.
    """
    return str(cwd.resolve()).replace("/", "-").replace(".", "-")


def _seed_transcript(projects_dir: Path, sid: str, cwd: Path) -> None:
    """Create ``<projects_dir>/<encoded-cwd>/<sid>.jsonl`` for the sid->cwd join."""
    d = projects_dir / _encode_cwd_like_claude(cwd)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sid}.jsonl").write_text('{"type":"assistant"}\n', encoding="utf-8")


class TestEmptyAndAbsentLedger:
    def test_absent_ledger_is_na(self, tmp_path):
        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
        )
        assert share.available is False
        assert share.meta_pct == 0.0
        assert share.total_usd == 0.0
        assert share.over_ceiling is False

    def test_empty_ledger_is_na(self, tmp_path):
        _write_ledger(tmp_path / "metrics", [])
        share = collect(ledger_dir=tmp_path / "metrics", projects_dir=tmp_path / "projects")
        assert share.available is False

    def test_all_rows_outside_window_is_na(self, tmp_path):
        old = datetime.now(timezone.utc) - timedelta(days=90)
        _write_ledger(tmp_path / "metrics", [_row("s1", 1.0, old)])
        share = collect(
            window_days=30,
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
        )
        assert share.available is False


class TestAttribution:
    def test_meta_session_counts_as_meta(self, tmp_path):
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        _write_ledger(tmp_path / "metrics", [_row("meta1", 4.0, now)])
        _seed_transcript(tmp_path / "projects", "meta1", meta_cwd)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
        )
        assert share.available is True
        assert share.meta_usd == 4.0
        assert share.total_usd == 4.0
        assert share.meta_pct == pytest.approx(100.0)

    def test_product_session_counts_as_product(self, tmp_path):
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        product_cwd = tmp_path / "git" / "buvis" / "gems"
        _write_ledger(tmp_path / "metrics", [_row("prod1", 6.0, now)])
        _seed_transcript(tmp_path / "projects", "prod1", product_cwd)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
        )
        assert share.available is True
        assert share.meta_usd == 0.0
        assert share.total_usd == 6.0
        assert share.meta_pct == 0.0

    def test_no_transcript_counts_as_product(self, tmp_path):
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        # A ledger row whose sid has NO transcript anywhere under projects_dir.
        _write_ledger(tmp_path / "metrics", [_row("orphan", 5.0, now)])

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
        )
        assert share.available is True
        assert share.meta_usd == 0.0  # never inflate meta
        assert share.total_usd == 5.0
        assert share.meta_pct == 0.0

    def test_dotted_paths_encode_like_claude(self, tmp_path):
        """Regression: cwds with a dot must encode '.'->'-' like Claude really does.

        The live-ledger probe found the collector encoded only '/'->'-', so
        ``/Users/bob/.claude`` became ``-Users-bob-.claude`` and never matched the
        real ``-Users-bob--claude`` — attributing 0% meta on real data while the
        fixtures (self-encoded the same wrong way) still passed. This guards both
        sides: a meta root whose leaf is ``.claude`` AND a product path containing
        a dot (``github.com``) must classify correctly.
        """
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        # A realistic product cwd with a dot in it, like a real repo checkout.
        product_cwd = tmp_path / "github.com" / "buvis" / "gems"
        _write_ledger(
            tmp_path / "metrics",
            [_row("meta1", 3.0, now), _row("prod1", 9.0, now)],
        )
        _seed_transcript(tmp_path / "projects", "meta1", meta_cwd)
        _seed_transcript(tmp_path / "projects", "prod1", product_cwd)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
        )
        # meta1 ($3) attributed to meta; prod1 ($9, dotted path) to product.
        assert share.meta_usd == 3.0
        assert share.total_usd == 12.0
        assert share.meta_pct == pytest.approx(25.0)

    def test_mixed_reproduces_known_pct(self, tmp_path):
        """25% meta: one meta session at $2, one product at $6 (2 / 8 = 25%)."""
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        product_cwd = tmp_path / "git" / "buvis" / "gems"
        _write_ledger(
            tmp_path / "metrics",
            [_row("meta1", 2.0, now), _row("prod1", 6.0, now)],
        )
        _seed_transcript(tmp_path / "projects", "meta1", meta_cwd)
        _seed_transcript(tmp_path / "projects", "prod1", product_cwd)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
        )
        assert share.total_usd == 8.0
        assert share.meta_usd == 2.0
        assert share.meta_pct == pytest.approx(25.0)
        assert share.over_ceiling is False


class TestCumulativePerSid:
    def test_per_sid_spend_is_max_not_sum(self, tmp_path):
        """Cumulative rows: a sid's spend is its LAST (max-ts) cost, not the sum."""
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        product_cwd = tmp_path / "git" / "buvis" / "gems"
        # prod1 accumulates 1 -> 3 -> 7 across three Stop events.
        _write_ledger(
            tmp_path / "metrics",
            [
                _row("prod1", 1.0, now - timedelta(minutes=20)),
                _row("prod1", 3.0, now - timedelta(minutes=10)),
                _row("prod1", 7.0, now),
            ],
        )
        _seed_transcript(tmp_path / "projects", "prod1", product_cwd)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
        )
        # 7.0 (last), NOT 1+3+7=11 (summing would double-count).
        assert share.total_usd == 7.0


class TestCeiling:
    def test_ceiling_is_inclusive_thirty_is_over(self, tmp_path):
        """30.0% exactly => over_ceiling True (the ceiling is inclusive)."""
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        product_cwd = tmp_path / "git" / "buvis" / "gems"
        # 3 meta / 10 total = 30.0% exactly.
        _write_ledger(
            tmp_path / "metrics",
            [_row("meta1", 3.0, now), _row("prod1", 7.0, now)],
        )
        _seed_transcript(tmp_path / "projects", "meta1", meta_cwd)
        _seed_transcript(tmp_path / "projects", "prod1", product_cwd)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
        )
        assert share.meta_pct == pytest.approx(30.0)
        assert share.ceiling_pct == META_CEILING_PCT
        assert share.over_ceiling is True

    def test_just_under_ceiling_is_not_over(self, tmp_path):
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        product_cwd = tmp_path / "git" / "buvis" / "gems"
        # 29 meta / 100 total = 29% < 30%.
        _write_ledger(
            tmp_path / "metrics",
            [_row("meta1", 29.0, now), _row("prod1", 71.0, now)],
        )
        _seed_transcript(tmp_path / "projects", "meta1", meta_cwd)
        _seed_transcript(tmp_path / "projects", "prod1", product_cwd)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
        )
        assert share.meta_pct == pytest.approx(29.0)
        assert share.over_ceiling is False


class TestConfiguredMetaRepos:
    """Config-driven ``meta_repos`` allowlist (PRD 00087).

    A session whose transcript cwd is at or under any configured meta-repo root
    counts as meta, in addition to ``~/.claude``. Default (``[]`` / omitted)
    preserves the exact pre-config behaviour.
    """

    def test_configured_repo_counts_as_meta(self, tmp_path):
        """(a) a session under a configured meta-repo is attributed meta."""
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        tooling_repo = tmp_path / "git" / "buvis" / "claude-tooling"
        _write_ledger(tmp_path / "metrics", [_row("tool1", 4.0, now)])
        _seed_transcript(tmp_path / "projects", "tool1", tooling_repo)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
            meta_repos=[tooling_repo],
        )
        assert share.available is True
        assert share.meta_usd == 4.0
        assert share.total_usd == 4.0
        assert share.meta_pct == pytest.approx(100.0)

    def test_claude_home_still_meta_with_config(self, tmp_path):
        """(b) ~/.claude remains meta even when meta_repos is configured."""
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        tooling_repo = tmp_path / "git" / "buvis" / "claude-tooling"
        _write_ledger(tmp_path / "metrics", [_row("home1", 5.0, now)])
        _seed_transcript(tmp_path / "projects", "home1", meta_cwd)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
            meta_repos=[tooling_repo],
        )
        assert share.meta_usd == 5.0
        assert share.total_usd == 5.0
        assert share.meta_pct == pytest.approx(100.0)

    def test_unlisted_repo_counts_as_product(self, tmp_path):
        """(c) a session under an UNLISTED repo stays product."""
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        tooling_repo = tmp_path / "git" / "buvis" / "claude-tooling"
        unlisted_repo = tmp_path / "git" / "buvis" / "gems"
        _write_ledger(
            tmp_path / "metrics",
            [_row("tool1", 4.0, now), _row("prod1", 6.0, now)],
        )
        _seed_transcript(tmp_path / "projects", "tool1", tooling_repo)
        _seed_transcript(tmp_path / "projects", "prod1", unlisted_repo)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
            meta_repos=[tooling_repo],
        )
        # tool1 ($4) meta via config; prod1 ($6) unlisted -> product.
        assert share.meta_usd == 4.0
        assert share.total_usd == 10.0
        assert share.meta_pct == pytest.approx(40.0)

    def test_empty_meta_repos_matches_non_config_result(self, tmp_path):
        """(d) meta_repos=[] / omitted is identical to the non-config path.

        Reproduces :meth:`TestAttribution.test_mixed_reproduces_known_pct` (one
        meta $2, one product $6 -> 25%) and asserts passing ``meta_repos=[]`` and
        omitting it entirely both yield the same back-compatible result.
        """
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        product_cwd = tmp_path / "git" / "buvis" / "gems"
        _write_ledger(
            tmp_path / "metrics",
            [_row("meta1", 2.0, now), _row("prod1", 6.0, now)],
        )
        _seed_transcript(tmp_path / "projects", "meta1", meta_cwd)
        _seed_transcript(tmp_path / "projects", "prod1", product_cwd)

        kwargs = {
            "ledger_dir": tmp_path / "metrics",
            "projects_dir": tmp_path / "projects",
            "meta_root": meta_cwd,
        }
        omitted = collect(**kwargs)
        explicit_empty = collect(**kwargs, meta_repos=[])

        for share in (omitted, explicit_empty):
            assert share.total_usd == 8.0
            assert share.meta_usd == 2.0
            assert share.meta_pct == pytest.approx(25.0)
        assert explicit_empty == omitted

    def test_dotted_configured_repo_encodes_and_matches(self, tmp_path):
        """(e) a configured repo path containing a dot encodes/matches correctly.

        A real Claude-tooling checkout path like
        ``.../github.com/buvis/agent-skills`` has a dot in ``github.com`` that
        the encoder must rewrite to ``-`` on BOTH sides, exactly like ``.claude``
        — otherwise the prefix never matches the transcript dir name.
        """
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        dotted_repo = tmp_path / "git" / "src" / "github.com" / "buvis" / "agent-skills"
        _write_ledger(tmp_path / "metrics", [_row("skill1", 3.0, now)])
        _seed_transcript(tmp_path / "projects", "skill1", dotted_repo)

        share = collect(
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
            meta_repos=[dotted_repo],
        )
        assert share.meta_usd == 3.0
        assert share.total_usd == 3.0
        assert share.meta_pct == pytest.approx(100.0)


class TestWindowFilter:
    def test_window_filter_excludes_old_rows(self, tmp_path):
        now = datetime.now(timezone.utc)
        meta_cwd = tmp_path / "home" / ".claude"
        product_cwd = tmp_path / "git" / "buvis" / "gems"
        # in-window product $10; a meta row 40 days ago must be dropped.
        _write_ledger(
            tmp_path / "metrics",
            [
                _row("prod1", 10.0, now - timedelta(days=5)),
                _row("metaOld", 90.0, now - timedelta(days=40)),
            ],
        )
        _seed_transcript(tmp_path / "projects", "prod1", product_cwd)
        _seed_transcript(tmp_path / "projects", "metaOld", meta_cwd)

        share = collect(
            window_days=30,
            ledger_dir=tmp_path / "metrics",
            projects_dir=tmp_path / "projects",
            meta_root=meta_cwd,
        )
        assert share.total_usd == 10.0  # old meta row excluded
        assert share.meta_usd == 0.0
        assert share.meta_pct == 0.0

    def test_returns_metashare_instance(self, tmp_path):
        share = collect(ledger_dir=tmp_path / "m", projects_dir=tmp_path / "p")
        assert isinstance(share, MetaShare)
