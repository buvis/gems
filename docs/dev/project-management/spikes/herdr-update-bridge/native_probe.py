"""Disposable macOS experiment; never updates an app/core or touches live homes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent


def main() -> None:
    report: dict[str, object] = {"completed": False, "observations": []}
    observations: list[str] = []
    process: subprocess.Popen[bytes] | None = None
    # Darwin Unix-domain socket paths are short; the default /var/folders
    # temporary prefix can leave insufficient room for app/core socket names.
    with tempfile.TemporaryDirectory(prefix="hbridge-", dir="/private/tmp") as directory:
        root = Path(directory).resolve()
        app_home = root / "app-home"
        mod = app_home / "mods" / "update-probe"
        mod.mkdir(parents=True)
        for name in ("main.js", "mod.json"):
            shutil.copy2(HERE / name, mod / name)
        for name in ("layouts",):
            (app_home / name).mkdir()
        app_bundle = root / "Probe.app"
        app = app_bundle / "Contents/MacOS/Herdr"
        # Preserve signed bundle metadata. A name other than Herdr.app prevents
        # startup from repointing the user's CLI link (core_bin/cli_link.rs).
        shutil.copytree("/Applications/Herdr.app", app_bundle, symlinks=True)
        core_source = Path(shutil.which("hc") or str(Path.home() / ".local/bin/hc"))
        core_source = core_source.resolve(strict=True)
        core_bundle = root / "Core.app"
        assert core_source.parent.name == "MacOS" and core_source.parent.parent.name == "Contents"
        shutil.copytree(core_source.parents[2], core_bundle, symlinks=True)
        core = core_bundle / "Contents/MacOS" / core_source.name
        # Fail before GUI startup if the disposable copies cannot execute.
        for executable in (app, core):
            subprocess.run(["/usr/bin/codesign", "--verify", str(executable)], check=True, capture_output=True, text=True)
            subprocess.run([str(executable), "--version"], check=True, capture_output=True, text=True, timeout=5)
        env = {key: value for key, value in os.environ.items() if not key.startswith("HC_")}
        session = "hb-" + uuid.uuid4().hex[:12]
        env.update({
            "HC_SESSION": session,
            "HERDR_APP_HOME": str(app_home),
            "HERDR_CORE_DIRS": str(root),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "XDG_RUNTIME_DIR": str(root / "run"),
            "TMPDIR": str(root / "tmp"),
            "DO_NOT_TRACK": "1",
            "HERDR_APP_NO_SOUND": "1",
        })
        env.pop("HERDR_RELEASES_URL", None)
        for key in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR", "TMPDIR"):
            Path(env[key]).mkdir()
        (app_home / "settings.json").write_text(json.dumps({"core": str(core), "telemetry": False}))
        (app_home / "shared.json").write_text(json.dumps({"layout": "probe", "frame.welcomed": "skipped"}))
        (app_home / "layouts/probe.json").write_text(json.dumps({
            "type": "block", "id": "probe", "content": {"mod": "update-probe"},
        }))
        (app_home / "layouts/empty.json").write_text(json.dumps({"type": "column", "children": []}))
        profile = root / "isolation.sb"
        profile.write_text("\n".join([
            "(version 1)", "(allow default)", "(deny file-write*)",
            f'(allow file-write* (subpath {json.dumps(str(root))}) (subpath "/private/tmp") (subpath "/private/var/folders") (subpath "/dev"))',
            '(deny network-outbound (remote ip "*:*"))',
            f'(deny file-read* (subpath {json.dumps(str(Path.home() / ".config/herdr-app"))}) (subpath {json.dumps(str(Path.home() / ".local/state/herdr-core"))}))',
        ]))
        prefix = ["/usr/bin/sandbox-exec", "-f", str(profile)]

        def cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
            result = subprocess.run([*prefix, str(app), *args], env=env, capture_output=True, text=True, timeout=8)
            if check and result.returncode:
                raise RuntimeError(f"{args}: {result.stdout} {result.stderr}")
            return result

        def start(log: object) -> subprocess.Popen[bytes]:
            proc = subprocess.Popen([*prefix, str(app)], env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError(f"isolated app exited {proc.returncode}")
                    if cli("status", check=False).returncode == 0:
                        return proc
                    time.sleep(0.15)
                raise RuntimeError("isolated app did not become ready")
            except BaseException:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
                raise

        def probe() -> dict[str, object]:
            nonce = uuid.uuid4().hex
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                status = json.loads(cli("status").stdout)
                if status.get("errors"):
                    raise RuntimeError(f"isolated window errors: {status['errors']}")
                accepted = cli("do", f"update-probe.probe-{nonce}", check=False)
                if accepted.returncode == 0:
                    break
                if "unknown command" not in accepted.stdout + accepted.stderr:
                    raise RuntimeError(accepted.stdout + accepted.stderr)
                time.sleep(0.05)
            while time.monotonic() < deadline:
                try:
                    response = json.loads((app_home / "shared.json").read_text()).get("sysup.update-probe", {})
                    if response.get("schema") == 1 and response.get("nonce") == nonce:
                        return response
                except (OSError, ValueError):
                    pass
                time.sleep(0.05)
            raise RuntimeError("no matching persisted probe response within 5s")

        log_path = root / "app.log"
        try:
            # A syntax failure here cannot launch the GUI or any core.
            subprocess.run([*prefix, "/usr/bin/true"], check=True, capture_output=True, text=True)
            with log_path.open("wb") as log:
                process = start(log)
                first = probe()
                observations.append("loaded mod delivered fresh update state through shared.json")
                report["first_state"] = first["state"]
                cli("shot", str(root / "native.png"))
                shutil.copy2(root / "native.png", HERE / "native.png")
                cli("do", "app.quit")
                process.wait(timeout=10)
                process = None
                stale = json.loads((app_home / "shared.json").read_text())["sysup.update-probe"]
                assert stale["nonce"] == first["nonce"]
                process = start(log)
                second = probe()
                assert second["nonce"] != stale["nonce"]
                observations.append("fresh reply after real isolated app quit/relaunch; old persisted reply ignored")
                cli("do", "layout.switch", '{"name":"empty"}')
                time.sleep(0.5)
                missing = cli("do", "update-probe.probe-" + uuid.uuid4().hex, check=False)
                assert missing.returncode != 0, missing.stdout
                assert "unknown command" in missing.stderr + missing.stdout
                observations.append("layout without bridge returns unknown command instead of cached success")
                cli("do", "layout.switch", '{"name":"probe"}')
                time.sleep(0.5)
                probe()
                observations.append("probe recovers after switching back to its layout")
                report["completed"] = True
        except Exception as exc:
            report["error"] = str(exc) + (f": {exc.stderr}" if isinstance(exc, subprocess.CalledProcessError) else "")
        finally:
            if process is not None and process.poll() is None:
                cli("do", "app.quit", check=False)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)
            try:
                stopped = subprocess.run([*prefix, str(core), "server", "stop"], env=env, capture_output=True, text=True, timeout=10)
                report["core_stop_code"] = stopped.returncode
                report["core_stop_output"] = stopped.stdout + stopped.stderr
            except subprocess.TimeoutExpired:
                report["core_stop_code"] = "timeout"
            report["observations"] = observations
            report["app_log_tail"] = log_path.read_text(errors="replace")[-10000:] if log_path.exists() else ""
            (HERE / "native-result.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({key: value for key, value in report.items() if key != "app_log_tail"}, indent=2))
    if not report["completed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
