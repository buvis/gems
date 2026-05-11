# pidash

Read-only TUI dashboard for autopilot PRD cycle progress, plus the bundled
Claude Code hooks that feed it.

## Quick start

```bash
uv tool install buvis-gems[pidash]
pidash hooks install        # one-time: register hooks in ~/.claude/settings.json
pidash                      # watch all active autopilot sessions
```

`pidash hooks install` is idempotent: re-run it after a settings.json edit and
nothing duplicates. It also detects and replaces legacy
`python3 ~/.claude/hooks/<name>.py` entries from earlier dotfiles installs.

Use `pidash hooks status` to verify the six entries are registered, or
`pidash hooks uninstall` to remove pidash-owned entries while leaving unrelated
hooks intact.

Full documentation lives at <https://buvis.github.io/gems/tools/pidash.html>.
