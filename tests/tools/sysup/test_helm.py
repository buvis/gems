from __future__ import annotations

import subprocess

from sysup.capabilities.helm import HelmRepoUpdate


class TestHelmRepoUpdate:
    @staticmethod
    def _result(
        args: list[str],
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)

    def _helm_list(
        self,
        repos_json: str = '[{"name":"stable"}]',
        returncode: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        return self._result(
            ["/usr/local/bin/helm", "repo", "list", "-o", "json"],
            returncode=returncode,
            stdout=repos_json,
        )

    def test_update_runs_when_repos_present(self, mocker) -> None:
        mocker.patch("sysup.capabilities.helm.shutil.which", return_value="/usr/local/bin/helm")
        mock_run = mocker.patch("sysup.capabilities.helm.subprocess.run")
        mock_run.side_effect = [
            self._helm_list(),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = list(HelmRepoUpdate().run())

        assert len(steps) == 1
        assert steps[0].label == "helm repos"
        assert steps[0].success is True

    def test_helm_missing_skips(self, mocker) -> None:
        mocker.patch("sysup.capabilities.helm.shutil.which", return_value=None)
        steps = list(HelmRepoUpdate().run())
        assert steps[0].success is False
        assert "not found" in steps[0].message

    def test_no_repos_skips_update(self, mocker) -> None:
        """Regression: an empty helm repo list is a benign no-op, not a red failure."""
        mocker.patch("sysup.capabilities.helm.shutil.which", return_value="/usr/local/bin/helm")
        mock_run = mocker.patch("sysup.capabilities.helm.subprocess.run")
        mock_run.side_effect = [self._helm_list(repos_json="[]")]

        steps = list(HelmRepoUpdate().run())

        assert steps[0].success is True
        assert "no helm repos" in steps[0].message
        update_calls = [c for c in mock_run.call_args_list if c.args[0] == ["/usr/local/bin/helm", "repo", "update"]]
        assert update_calls == []

    def test_list_error_still_updates(self, mocker) -> None:
        """A failing repo list must not mask a real problem: run the update anyway."""
        mocker.patch("sysup.capabilities.helm.shutil.which", return_value="/usr/local/bin/helm")
        mock_run = mocker.patch("sysup.capabilities.helm.subprocess.run")
        mock_run.side_effect = [
            self._helm_list(repos_json="", returncode=1),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = list(HelmRepoUpdate().run())

        assert steps[0].success is True

    def test_unparseable_list_still_updates(self, mocker) -> None:
        mocker.patch("sysup.capabilities.helm.shutil.which", return_value="/usr/local/bin/helm")
        mock_run = mocker.patch("sysup.capabilities.helm.subprocess.run")
        mock_run.side_effect = [
            self._helm_list(repos_json="not-json"),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = list(HelmRepoUpdate().run())

        assert steps[0].success is True

    def test_update_fails(self, mocker) -> None:
        mocker.patch("sysup.capabilities.helm.shutil.which", return_value="/usr/local/bin/helm")
        mock_run = mocker.patch("sysup.capabilities.helm.subprocess.run")
        mock_run.side_effect = [
            self._helm_list(),
            self._result(["/usr/local/bin/helm", "repo", "update"], returncode=1, stderr="helm error"),
        ]

        steps = list(HelmRepoUpdate().run())

        assert steps[0].success is False
        assert "helm error" in steps[0].message

    def test_update_fails_empty_stderr_uses_unknown(self, mocker) -> None:
        mocker.patch("sysup.capabilities.helm.shutil.which", return_value="/usr/local/bin/helm")
        mock_run = mocker.patch("sysup.capabilities.helm.subprocess.run")
        mock_run.side_effect = [
            self._helm_list(),
            self._result(["/usr/local/bin/helm", "repo", "update"], returncode=1, stderr=""),
        ]

        steps = list(HelmRepoUpdate().run())

        assert steps[0].success is False
        assert "unknown error" in steps[0].message
