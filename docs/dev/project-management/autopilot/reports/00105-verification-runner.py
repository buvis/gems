"""Run the unchanged suite in writable isolated host state/config, report runner counts."""
import os
import re
import subprocess
import sys

environment = dict(os.environ)
environment.update(
    UV_CACHE_DIR='/tmp/gems-autocodex-uv-cache',
    XDG_STATE_HOME='/tmp/gems-autocodex-test-state',
    BUVIS_CONFIG_DIR='/tmp/gems-autocodex-test-config',
)
result = subprocess.run(
    ['uv', 'run', '--no-sync', 'pytest', '-q', '--tb=line'],
    env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600,
)
sys.stdout.write(result.stdout)
summary = next((line for line in reversed(result.stdout.splitlines()) if re.search(r'\d+ (?:passed|failed)', line)), '')
counts = {kind: int(value) for value, kind in re.findall(r'(\d+) (passed|failed|skipped)', summary)}
if not counts:
    raise SystemExit(result.returncode or 2)
print(f'PASS {counts.get("passed", 0)} FAIL {counts.get("failed", 0)} SKIP {counts.get("skipped", 0)} EXIT {result.returncode}')
raise SystemExit(result.returncode)
