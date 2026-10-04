# Releasing buvis-gems

How to cut a release of `buvis-gems`. One public command — `release` — bumps the
version, updates the changelog, tags, and pushes; CI then builds and publishes.

This repo releases **everything together as one unit** (`buvis-gems` on PyPI).
There are no independently-versioned components, so `release` takes no
`--component`; the ordinary command releases the whole package.

## Quick reference

```bash
release --dry-run patch                # preview a bump, change nothing
release patch | minor | major          # bump, changelog, tag, push → CI publishes to PyPI
release --pre rc1                       # pre-release the CURRENT version to TestPyPI
release --pre rc1 minor                 # bump minor AND pre-release to TestPyPI
release                                  # after an rc: strip the suffix, release stable to PyPI
release local                            # build a .devN wheel and install it locally (no tag, no push)
```

`release` is the PATH shim (`tools/release`) that forwards to the mise `release`
task; the implementation is `tools/lib/release`. `mise` puts `tools/` on PATH, so
`release` works from anywhere in the repo once `mise` is active.

## Version authority

The single source of truth is the `version` field in `pyproject.toml`.

> **Why a file, not the git tag?** maturin reads the version from `pyproject.toml`
> at build time to compile the Rust extension. Tag-based versioning (hatch-vcs)
> would need glue to inject the version before maturin sees it, so the version
> lives in the file and `release` keeps the tag in sync with it.

`release` reads the current version from `pyproject.toml`, computes the next one,
writes it back, regenerates `uv.lock`, commits (`build(gems): bump to vX.Y.Z`),
tags, and pushes.

## Bump policy

Semantic versioning:

- `patch` — bug fixes, no API change (`0.13.0 → 0.13.1`)
- `minor` — new backward-compatible features (`0.13.0 → 0.14.0`)
- `major` — breaking changes (`0.13.0 → 1.0.0`)

Pre-releases append a suffix with `--pre <suffix>` (e.g. `rc1` → `0.14.0rc1`).
`--pre` with no bump part pre-releases the current base version; `--pre` with a
bump part bumps first, then suffixes.

## Tag convention

Tags are `gems-v<version>` — e.g. `gems-v0.13.1`, `gems-v0.14.0rc1`. The
`gems-v` prefix is what `release local` and the publish workflow key off.

## Required checks

Before releasing, the working tree must be clean and the branch current:

- `release` runs `git pull --ff-only` and **aborts if the pull is not fast-forward**
  or the **working tree is dirty** (`git status --porcelain` non-empty).
- It aborts if the computed tag **already exists**.

Run the repo gates yourself first (they are not re-run by `release`):

```bash
uv run pytest                    # full suite
uv run mypy src/lib/ src/tools/  # type check
pre-commit run --all-files       # ruff, format, tool-wiring, framework-import guard
```

The CHANGELOG `[Unreleased]` section must hold the entries for this release —
`release` promotes `[Unreleased]` to `[X.Y.Z] - <date>` for a **stable** release
(it does **not** touch the changelog for a `--pre` release, so rc notes stay under
`[Unreleased]` until the stable cut).

## Publication destinations

Publishing is done by CI (`.github/workflows/publish.yml`), triggered by the pushed
tag. Routing is automatic:

| Trigger                                   | Destination | PyPI environment |
|-------------------------------------------|-------------|------------------|
| Tag containing `rc` (e.g. `gems-v…rc1`)   | TestPyPI    | `testpypi`       |
| Stable tag (e.g. `gems-v0.14.0`)          | PyPI        | `pypi`           |
| Manual `workflow_dispatch`                | TestPyPI (default; `testpypi` input toggles) | `testpypi` |

Publishing uses PyPI **Trusted Publishing** (OIDC) — no API tokens stored in the
repo. A stable (non-rc) push also creates a **GitHub Release**: it attaches the
wheels + sdist and a CycloneDX SBOM, and extracts that version's section from
`CHANGELOG.md` as the release notes.

### First-time setup (already done for buvis-gems)

- test.pypi.org: add a trusted publisher — owner `buvis`, repo `gems`, workflow
  `publish.yml`, environment `testpypi`.
- GitHub repo settings: create the `testpypi` and `pypi` environments.

## Typical flows

**Stable patch/minor/major release:**

```bash
release --dry-run minor          # confirm the target version
# ensure CHANGELOG [Unreleased] has this release's notes
release minor                    # bump, changelog→dated section, tag, push
# CI builds the wheel matrix and publishes to PyPI, then cuts the GitHub Release
```

**Release-candidate → stable:**

```bash
release --pre rc1 minor          # 0.13.0 → 0.14.0rc1, pushed, published to TestPyPI
# verify the rc from TestPyPI; iterate rc2, rc3 as needed
release                          # strips the rc suffix → 0.14.0 stable, published to PyPI
```

**Local test build (no tag, no push):**

```bash
release local                    # builds buvis-gems X.Y.Z.devN and installs it
                                 # (version derived from commit distance since the last tag)
```

## Partial-failure recovery

Published versions and release tags are **immutable** — never bump again to paper
over a half-finished release. Identify what completed and resume at the same
version/commit.

- **`release` aborted before tagging** (dirty tree, non-ff pull, lock failure):
  nothing was pushed. Fix the cause and re-run `release` — the version in
  `pyproject.toml` is unchanged until the commit step, so no state leaked.
- **Commit/tag landed but the push failed:** the tag exists locally. Push it
  explicitly: `git push origin HEAD gems-v<version>`. Do not re-run `release`
  (it would see the tag already exists and abort).
- **Tag pushed but CI publish failed:** the tag and commit are immutable and
  correct. Re-run the **publish workflow** for that tag from the GitHub Actions
  UI (re-run failed jobs), or dispatch `publish.yml` manually. Trusted Publishing
  is idempotent per version — a version already live on the index will not be
  re-uploaded; verify the published artifacts match and stop on any mismatch.
- **TestPyPI succeeded but you need PyPI:** that is the normal rc→stable path —
  run `release` (no args) to cut the stable tag; do not try to promote the rc
  artifact.

## See also

- `AGENTS.md` → **Release** section (the condensed reference).
- `tools/lib/release` — the implementation.
- `.github/workflows/publish.yml` — the publish + GitHub-release workflow.
